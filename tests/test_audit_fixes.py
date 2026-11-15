"""Regressions for the audit: lifecycle boundaries, storage and screen geometry."""
import io
import json
import os
from pathlib import Path
import random
import string
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from PIL import Image
from blockblast.capture import VideoCapture
from blockblast.config import DEFAULTS
from blockblast.engine import Move
from blockblast.runtime import RunControl
from blockblast.score import ScoreReader
from blockblast.session import Session,Stats
from blockblast.stability import StableState
from blockblast.vision import Piece,State
from blockblast.__main__ import play
from test_runtime import FakeADB

class Clock:
    def __init__(self):self.now=0
    def __call__(self):self.now+=.06;return self.now

class AuditFixTests(unittest.TestCase):
    def play_fake(self,adb,control=None,**settings):
        control=control or RunControl()
        with tempfile.TemporaryDirectory() as root, \
             patch('blockblast.__main__.read',side_effect=lambda im,p:im.state), \
             patch('blockblast.__main__.time.monotonic',side_effect=Clock()), \
             patch.object(control,'wait',side_effect=lambda _:control.check()), \
             patch('blockblast.__main__.time.sleep'), \
             patch('blockblast.__main__.solve',side_effect=lambda board,pieces,*a:(Move(min(pieces),0,min(pieces),1<<min(pieces)),) if pieces else ()):
            play(adb,{},DEFAULTS|{'file_logs':False,'save_screenshots':False,'read_score':False,
                                'capture':'screenshot','show_board':False}|settings,
                 root=root,control=control,quiet=True)
        return control

    def test_cli_rejection_finishes_with_report(self):
        adb=FakeADB();adb.drag_precise=lambda *a:None
        c=self.play_fake(adb,max_rejections=0)
        self.assertEqual(c.status,'finished');self.assertEqual(c.stats['attempts'],2)
        self.assertIn('Жесты не подтверждены',c.reason);self.assertFalse(c.pause_event.is_set())

    def test_gui_rejection_still_allows_resume(self):
        adb=FakeADB();adb.drag_precise=lambda *a:None
        c=RunControl(can_resume=True)
        def notify(kind,data):
            if kind=='status' and data['status']=='paused' and c.pause_event.is_set():c.stop_event.set()
        c.callback=notify
        self.play_fake(adb,c,max_rejections=0)
        self.assertTrue(c.pause_event.is_set());self.assertIn('Остановлено пользователем',c.reason)

    def test_empty_start_ends_without_gesture(self):
        adb=FakeADB();adb.state.pieces={}
        c=self.play_fake(adb)
        self.assertEqual(adb.moves,0);self.assertEqual(c.status,'finished')
        self.assertIn('Лоток остаётся пустым',c.reason)

    def test_temporary_empty_tray_is_not_terminal(self):
        adb=FakeADB();original=adb.screenshot;reads=[0]
        def screenshot():
            image=original();reads[0]+=1
            if reads[0]<5:image.state.pieces={}
            return image
        adb.screenshot=screenshot
        c=self.play_fake(adb,max_moves=1)
        self.assertEqual(c.stats['moves'],1);self.assertEqual(c.reason,'Достигнут лимит ходов')

    def test_confirmed_score_reset_ends_before_next_gesture(self):
        adb=FakeADB();c=RunControl();reset=[False]
        def notify(kind,data):
            if kind=='state' and adb.moves==1:
                adb.state.board=1<<63;reset[0]=True
        c.callback=notify
        reader=Mock(available=True)
        reader.read.side_effect=lambda *a:(0 if reset[0] else 1000,5000)
        with patch('blockblast.__main__.ScoreReader',return_value=reader):
            self.play_fake(adb,c,read_score=True,score_every=100)
        self.assertEqual(adb.moves,1);self.assertIn('новая партия',c.reason)
        self.assertEqual(c.stats['score'],1000);self.assertEqual(c.stats['moves'],1)

    def test_single_low_ocr_after_resync_does_not_end_game(self):
        adb=FakeADB();c=RunControl();reset=[False];low=[False]
        def notify(kind,data):
            if kind=='state' and adb.moves==1 and not reset[0]:
                adb.state.board=1<<63;reset[0]=True
        c.callback=notify
        reader=Mock(available=True)
        def numbers(*args):
            if reset[0] and not low[0]:
                low[0]=True
                return 0,5000
            return 1000,5000
        reader.read.side_effect=numbers
        with patch('blockblast.__main__.ScoreReader',return_value=reader):
            self.play_fake(adb,c,read_score=True,score_every=100,max_moves=2)
        self.assertEqual(adb.moves,2);self.assertEqual(c.reason,'Достигнут лимит ходов')

    def test_initial_storage_failure_does_not_stop_play(self):
        with patch('blockblast.session.Path.mkdir',side_effect=OSError('disk full')):
            c=self.play_fake(FakeADB(),max_moves=1,file_logs=True)
        self.assertEqual(c.stats['moves'],1);self.assertEqual(c.status,'finished')
        self.assertTrue(any(k=='activity' and v['record']['event']=='storage_warning' for k,v in c.events))

    def test_active_history_respects_cap_and_keeps_summary(self):
        with tempfile.TemporaryDirectory() as root:
            s=Session(root,DEFAULTS|{'max_history_mb':1,'max_log_mb':1})
            rng=random.Random(123)
            for _ in range(300):s.event('probe',payload=''.join(rng.choices(string.ascii_letters,k=10000)))
            s.finish(Stats(moves=7),'test')
            size=sum(p.stat().st_size for p in s.directory.rglob('*') if p.is_file())
            self.assertLessEqual(size,1024*1024);self.assertTrue(s.storage_disabled)
            self.assertEqual(json.loads((s.directory/'summary.json').read_text())['moves'],7)
            from blockblast.history import records
            self.assertTrue(list(records(s.directory)))

    def test_oversized_screenshot_is_not_written(self):
        with tempfile.TemporaryDirectory() as root:
            s=Session(root,DEFAULTS|{'save_screenshots':True,'max_history_mb':1})
            image=Mock()
            image.save.side_effect=lambda buf,format:buf.write(b'x'*(2*1024*1024))
            s.screenshot(image)
            self.assertEqual(list(s.directory.glob('*.png')),[]);self.assertTrue(s.storage_disabled)
            s.finish(Stats(),'test')

    def test_corrupt_aggregate_does_not_break_summary(self):
        for data in ([],{'sessions':'bad','total_moves':None,'best':[] } ):
            with self.subTest(data=data),tempfile.TemporaryDirectory() as root:
                (Path(root)/'stats.json').write_text(json.dumps(data))
                s=Session(root,DEFAULTS);s.finish(Stats(moves=3),'test')
                self.assertEqual(json.loads((Path(root)/'stats.json').read_text())['total_moves'],3)

    def test_decoder_launch_failure_reaps_source(self):
        v=object.__new__(VideoCapture)
        for k,val in dict(closed=False,adb=SimpleNamespace(executable='adb',serial='test'),
                          width=540,height=1200,bitrate=4000000,segment_seconds=120,fps=12,
                          processes=[],remote_pid=None,messages=[],lock=threading.Lock(),
                          condition=threading.Condition()).items():setattr(v,k,val)
        source=Mock(stdout=io.BytesIO(),stderr=io.BytesIO(),poll=Mock(return_value=None))
        with patch('blockblast.capture.subprocess.Popen',side_effect=[source,OSError('decoder failed')]):v._run()
        source.terminate.assert_called_once();source.wait.assert_called_once()
        self.assertTrue(source.stdout.closed);self.assertEqual(v.processes,[])

    def test_gradual_drift_is_not_stable(self):
        o=StableState(3,.2)
        for i in range(8):
            p=Piece(((0,0),),(100+i*2,100),(100+i*2,100,150+i*2,150))
            self.assertFalse(o.observe(State(0,{0:p},(0,0,800,800),(1080,2400)),i*.1))
        state=State(0,{0:p},(0,0,800,800),(1080,2400))
        o.observe(state,1);self.assertTrue(o.observe(state,1.3))

    def test_stream_score_scale_without_screen_size(self):
        r=ScoreReader(False);r.available=True
        image=Image.new('RGB',(540,1200));image.info['capture_scale']=.5
        with patch.object(r,'number',return_value=None) as number:
            r.read(image,(61,580,1019,1539),{})
        self.assertEqual(number.call_args_list[0].args[1],[64.8,145,475.2,255.2])
        self.assertEqual(number.call_args_list[0].kwargs['upscale'],2)

class PreviewFixTests(unittest.TestCase):
    def test_new_session_clears_all_preview_caches(self):
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        from PySide6.QtWidgets import QApplication
        from blockblast.desktop import Window
        from test_desktop_states import Worker
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);(root/'profiles').mkdir();(root/'profiles/default.json').write_text('{}')
            with patch('blockblast.desktop.ROOT',root),patch('blockblast.desktop.load',return_value=dict(DEFAULTS)),patch('blockblast.desktop.BotWorker',side_effect=Worker):
                w=Window(discover=False)
                try:
                    w.discovered([('test','Phone')],'');w.phone.set_image(Image.new('RGB',(1080,2400),'red'))
                    w.start_bot()
                    self.assertIsNone(w.phone.image);self.assertIsNone(w.phone._pixmap);self.assertIsNone(w.phone._scaled_pixmap)
                finally:w.session_active=False;w.close();app.processEvents()
