"""Actual pink palette and recovery from in-game board/tray resets."""
from contextlib import redirect_stdout
import io,json,time
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from PIL import Image,ImageDraw
from blockblast.vision import read,Piece,State
from blockblast.stability import matches_result
from blockblast.runtime import RunControl
from blockblast.config import DEFAULTS
from blockblast.engine import Move
from blockblast.__main__ import play
from blockblast.history import records
import test_runtime as doubles

ROOT=Path(__file__).resolve().parent.parent
PROFILE=json.loads((ROOT/'profiles/default.json').read_text())

class PaletteVisionTests(unittest.TestCase):
    def test_correct_board_with_wrong_tray_never_confirms_move(self):
        state=State(1,{0:Piece(((0,0),),(1,1),(0,0,2,2))},(0,0,8,8),(20,20))
        self.assertFalse(matches_result(state,1,{1:((0,0),)}));self.assertFalse(matches_result(state,1,{}));self.assertTrue(matches_result(state,1,{0:((0,0),)}))

class Clock:
    def __init__(self):self.value=time.monotonic()
    def __call__(self):self.value+=.06;return self.value

class ResetADB(doubles.FakeADB):
    def __init__(self,mode):
        super().__init__();self.mode=mode
        if mode=='board':self.state.board=1<<63
    def drag_precise(self,start,end,grab,release):
        self.moves+=1;slot=min(self.state.pieces);col=next(c for c in range(8) if not self.state.board&(1<<c));self.state.board|=1<<col;del self.state.pieces[slot]
        if self.moves==1 or not self.state.pieces:
            self.state.pieces=doubles.FakeADB().state.pieces
        if self.moves==1 and self.mode=='board':self.state.board=0

def plan(board,pieces,beam,forbidden=()):
    result=[]
    for slot in sorted(pieces):
        col=next(c for c in range(8) if not board&(1<<c));move=Move(slot,0,col,1<<col);result.append(move);board|=move.mask
    return tuple(result)

class PlaybackRecoveryTests(unittest.TestCase):
    def test_stable_unexpected_board_and_tray_recover_without_stale_wait(self):
        for mode in ('board','tray'):
            with self.subTest(mode=mode),TemporaryDirectory() as folder:
                adb=ResetADB(mode);control=RunControl();settings=DEFAULTS|{'max_moves':2,'read_score':False,'capture':'screenshot','settle_time':.05,'stable_frames':2}
                with patch('blockblast.__main__.read',side_effect=lambda image,profile:image.state),patch('blockblast.__main__.solve',side_effect=plan),patch('blockblast.__main__.time.sleep'),patch('blockblast.__main__.time.monotonic',side_effect=Clock()),redirect_stdout(io.StringIO()):
                    play(adb,{},settings,root=folder,control=control,quiet=True)
                self.assertEqual(control.stats['moves'],2);self.assertEqual(adb.moves,3);self.assertEqual(control.stats['rejected'],1);self.assertFalse(control.pause_event.is_set())
                events=list(records(next((Path(folder)/'logs').iterdir())))
                self.assertTrue(any(e['event']=='board_resync' for e in events));self.assertEqual(control.stats['reason'],'Достигнут лимит ходов')
    def test_obscured_screen_wait_status_is_deduplicated_and_stop_is_responsive(self):
        control=RunControl();adb=doubles.FakeADB();calls=0
        def obscured(image,profile):
            nonlocal calls
            calls+=1
            if calls>100:control.stop_event.set()
            raise ValueError('Поле закрыто окном или анимацией')
        with TemporaryDirectory() as folder,patch('blockblast.__main__.read',side_effect=obscured),patch('blockblast.__main__.time.sleep'),patch('blockblast.__main__.time.monotonic',side_effect=Clock()),patch.object(control,'wait',side_effect=lambda duration:control.check()):
            play(adb,{},DEFAULTS|{'read_score':False,'capture':'screenshot','animation_timeout':1.0,'verify_timeout':.2},root=folder,control=control,quiet=True)
        waiting=[data for kind,data in control.events if kind=='status' and data['status']=='paused']
        self.assertEqual(len(waiting),1);self.assertGreater(control.stats['paused_seconds'],0);self.assertIn('Остановлено пользователем',control.stats['reason'])

if __name__=='__main__':unittest.main()
