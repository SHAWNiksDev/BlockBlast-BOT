from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from PIL import Image
from blockblast.config import DEFAULTS, load, save, validate
from blockblast.engine import Move
from blockblast.session import Session, Stats, clean
from blockblast.vision import State, Piece
from blockblast.__main__ import play, effective_settings, parse_args

class ConfigTests(unittest.TestCase):
    def test_default_unlimited_and_no_screenshots(self):
        self.assertEqual(DEFAULTS['max_moves'],0)
        self.assertFalse(DEFAULTS['save_screenshots'])

    def test_invalid_values_rejected(self):
        for values in ({'max_moves':-1},{'beam':0},{'speed':'warp'},{'file_logs':'false'},{'unknown':1}):
            with self.subTest(values=values),self.assertRaises(ValueError):
                validate(values)

    def test_config_roundtrip_and_cli_override(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'settings.json'
            save(DEFAULTS|{'max_moves':7},path)
            args=parse_args(['play','--config',str(path),'--moves','0','--no-logs'])
            result=effective_settings(args)
            self.assertEqual(result['max_moves'],0)
            self.assertNotIn('speed',result)
            self.assertFalse(result['file_logs'])
            self.assertEqual(load(path)['max_moves'],7)

class StorageTests(unittest.TestCase):
    def test_disabled_storage_creates_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            session=Session(d,DEFAULTS|{'file_logs':False,'save_screenshots':False})
            session.screenshot(Image.new('RGB',(10,10)))
            session.finish(Stats(),'test')
            self.assertEqual(list(Path(d).iterdir()),[])

    def test_retention_and_screenshot_limit(self):
        with tempfile.TemporaryDirectory() as d:
            settings=DEFAULTS|{'max_sessions':2,'max_screenshots':2,'save_screenshots':True}
            for _ in range(4):
                session=Session(d,settings)
                for _ in range(4):
                    session.screenshot(Image.new('RGB',(10,10)))
                self.assertEqual(len(list(session.directory.glob('*.png'))),2)
                session.finish(Stats(),'test')
            self.assertEqual(len(list((Path(d)/'logs').iterdir())),2)
            self.assertEqual(json.loads((Path(d)/'stats.json').read_text())['sessions'],4)

    def test_log_rotation_is_bounded(self):
        with tempfile.TemporaryDirectory() as d:
            session=Session(d,DEFAULTS)
            for i in range(300):
                session.event('test',payload='x'*10000)
            files=list(session.directory.glob('events.jsonl*'))
            self.assertEqual(len(files),2)
            self.assertTrue(all(p.stat().st_size<2.1*1024*1024 for p in files))
            session.finish(Stats(),'test')

    def test_clean_preserves_unknown_files_and_fixtures(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            generated=root/'artifacts'/'20261029-190307-027699'
            generated.mkdir(parents=True)
            (generated/'0001.png').write_bytes(b'png')
            (generated/'moves.jsonl').write_text('log')
            unknown=root/'artifacts'/'my-notes.txt'
            unknown.write_text('notes')
            self.assertEqual(clean(root,True,True)[0],1)
            self.assertTrue((generated/'0001.png').exists())
            clean(root,True)
            self.assertTrue((generated/'moves.jsonl').exists())
            self.assertTrue(unknown.exists())

    def test_score_monotonic_and_gain(self):
        stats=Stats()
        stats.update_score(100,1000)
        stats.update_score(140,1000)
        stats.update_score(12,None)
        report=stats.snapshot('test')
        self.assertEqual((report['score'],report['gained'],report['best']),(140,40,1000))

    def test_spurious_record_while_score_below_it_is_ignored(self):
        stats=Stats()
        stats.update_score(90000,110000)
        stats.update_score(90200,310000)  # one misread digit
        self.assertEqual((stats.score,stats.best),(90200,110000))
        stats.update_score(120000,120000)  # a real new record
        self.assertEqual((stats.score,stats.best),(120000,120000))

class FakeADB:
    def __init__(self, interrupt=False):
        pieces={slot:Piece(((0,0),),(200+slot*300,1800),(175+slot*300,1775,225+slot*300,1825)) for slot in range(3)}
        self.state=State(0,pieces,(61,580,1019,1539),(1080,2400))
        self.moves=0
        self.interrupt=interrupt
        self.timings=[]
    def check_foreground(self,package):
        pass
    def screenshot(self):
        return SimpleNamespace(state=deepcopy(self.state))
    def drag_precise(self,start,end,grab,release):
        if self.interrupt and self.moves:
            raise KeyboardInterrupt()
        slot=min(self.state.pieces)
        self.state.board|=1<<slot
        del self.state.pieces[slot]
        self.moves+=1
        self.timings.append((grab,release))
        if not self.state.pieces:
            self.state.pieces={i:Piece(((0,0),),(200+300*i,1800),(175+300*i,1775,225+300*i,1825)) for i in range(3)}

class PlaybackTests(unittest.TestCase):
    def run_bot(self, root, adb, limit):
        settings=DEFAULTS|{'max_moves':limit,'read_score':False,'save_screenshots':False,'capture':'screenshot','settle_time':.05,'stable_frames':2}
        plan=tuple(Move(i,0,i,1<<i) for i in range(3))
        with patch('blockblast.__main__.read',side_effect=lambda im,profile:im.state), \
             patch('blockblast.__main__.solve',return_value=plan) as solver, \
             patch('blockblast.__main__.time.sleep'),redirect_stdout(io.StringIO()) as output:
            play(adb,{},settings,root=root)
        return output.getvalue(),solver.call_count

    def test_prints_each_verified_board_and_reuses_plan(self):
        with tempfile.TemporaryDirectory() as d:
            output,calls=self.run_bot(d,FakeADB(),3)
            self.assertEqual(calls,1)
            self.assertIn('Поле после 1 ходов',output)
            self.assertIn('Поле после 3 ходов',output)
            report=json.loads(next((Path(d)/'logs').glob('*/summary.json')).read_text())
            self.assertEqual(report['moves'],3)
            self.assertEqual(report['reason'],'Достигнут лимит ходов')
            self.assertEqual(list(Path(d).rglob('*.png')),[])

    def test_unlimited_run_ctrl_c_writes_summary(self):
        with tempfile.TemporaryDirectory() as d:
            output,_=self.run_bot(d,FakeADB(interrupt=True),0)
            self.assertIn('Ctrl+C',output)
            report=json.loads(next((Path(d)/'logs').glob('*/summary.json')).read_text())
            self.assertEqual(report['moves'],1)


class NoRefillADB(FakeADB):
    def drag_precise(self,start,end,grab,release):
        slot=min(self.state.pieces)
        self.state.board|=1<<slot
        del self.state.pieces[slot]
        self.moves+=1


class GameOverTests(unittest.TestCase):
    def test_last_tray_piece_without_new_deal_stops_instead_of_hanging(self):
        adb=NoRefillADB()
        def plan(board,pieces,beam,forbidden=()):
            if not pieces:return ()
            return tuple(Move(i,0,i,1<<i) for i in sorted(pieces))
        with tempfile.TemporaryDirectory() as d, \
             patch('blockblast.__main__.read',side_effect=lambda image,profile:image.state), \
             patch('blockblast.__main__.solve',side_effect=plan), \
             patch('blockblast.__main__.time.sleep'),redirect_stdout(io.StringIO()):
            play(adb,{},DEFAULTS|{'max_moves':0,'capture':'screenshot','read_score':False,
                                  'settle_time':.05,'stable_frames':2},root=d)
            report=json.loads(next((Path(d)/'logs').glob('*/summary.json')).read_text())
        self.assertEqual(report['moves'],3)
        self.assertEqual(report['reason'],'Нет доступных ходов')


class TrayResyncADB(FakeADB):
    def __init__(self):
        super().__init__()
        self.after_first_reads=0
    def screenshot(self):
        if self.moves==1:
            self.after_first_reads+=1
            # One transient snapshot was accepted by the older recognizer.
            # The next snapshot has the same board and corrected tray shape.
            if self.after_first_reads>=2 and 1 in self.state.pieces:
                self.state.pieces[1].shape=((0,0),(1,0))
        return super().screenshot()

class TrayResyncTests(unittest.TestCase):
    def test_same_board_new_stable_tray_replans_instead_of_stopping(self):
        adb=TrayResyncADB()
        def plan(board,pieces,beam,forbidden=()):
            return tuple(Move(i,0,i,1<<i) for i in sorted(pieces))
        with tempfile.TemporaryDirectory() as d, \
             patch('blockblast.__main__.read',side_effect=lambda im,profile:im.state), \
             patch('blockblast.__main__.solve',side_effect=plan) as solver, \
             patch('blockblast.__main__.StableState.observe',return_value=True), \
             patch('blockblast.__main__.time.sleep'),redirect_stdout(io.StringIO()):
            play(adb,{},DEFAULTS|{'max_moves':2,'capture':'screenshot','read_score':False},root=d)
            report=json.loads(next((Path(d)/'logs').glob('*/summary.json')).read_text())
            events=[json.loads(line) for line in next((Path(d)/'logs').glob('*/events.jsonl')).read_text().splitlines()]
            self.assertEqual(report['moves'],2)
            self.assertEqual(solver.call_count,2)
            self.assertTrue(any(e['event']=='tray_resync' for e in events))
