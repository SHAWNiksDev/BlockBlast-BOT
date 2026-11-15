from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from blockblast.adb import parse_screen_status, ADB
from blockblast.config import DEFAULTS
from blockblast.__main__ import play
from blockblast.runtime import RunControl
from test_runtime import FakeADB

class ScreenStatusTests(unittest.TestCase):
    def test_game_focused(self):
        self.assertTrue(parse_screen_status('mCurrentFocus=Window{x u0 com.block.juggle/Activity}')[0])
    def test_home_and_other_apps_pause(self):
        for focus in ('com.google.android.apps.nexuslauncher/.Main','com.android.settings/.Settings','null'):
            self.assertFalse(parse_screen_status('mCurrentFocus='+focus)[0])
    def test_shade_even_when_game_keeps_focus(self):
        data='mCurrentFocus=Window{x u0 com.block.juggle/Activity}\n  Window #2 Window{NotificationShade}:\n    isVisible=true\n'
        self.assertFalse(parse_screen_status(data)[0])
    def test_hidden_shade_does_not_pause(self):
        data='mCurrentFocus=Window{x u0 com.block.juggle/Activity}\n  Window #2 Window{NotificationShade}:\n    isVisible=false\n'
        self.assertTrue(parse_screen_status(data)[0])
    def test_home_with_visible_status_bar_has_home_reason(self):
        data='mCurrentFocus=Window{x u0 com.google.android.apps.nexuslauncher/.Main}\n  Window #2 Window{StatusBar}:\n    isVisible=true\n'
        self.assertIn('возвращения',parse_screen_status(data)[1])

    def test_screen_off_pauses(self):
        self.assertFalse(parse_screen_status('mCurrentFocus=Window{x u0 com.block.juggle/Activity}\nscreenState=SCREEN_STATE_OFF')[0])

class PausingADB(FakeADB):
    def __init__(self):
        super().__init__()
        self.visible=False
        self.status_calls=0
    def screen_status(self,package):
        self.status_calls+=1
        return self.visible,'Тестовая шторка'

class PauseFlowTests(unittest.TestCase):
    def test_waits_without_moves_then_resumes(self):
        adb=PausingADB()
        control=RunControl()
        errors=[]
        with tempfile.TemporaryDirectory() as d:
            settings=DEFAULTS|{'capture':'screenshot','read_score':False,'max_moves':1,'settle_time':.05,'stable_frames':2}
            def worker():
                try:
                    with redirect_stdout(io.StringIO()):
                        play(adb,{},settings,root=d,control=control,quiet=True)
                except Exception as exc:
                    errors.append(exc)
            with patch('blockblast.__main__.read',side_effect=lambda image,profile:image.state):
                # Reuse the real planner but arrange the fake single-cell position.
                from blockblast.engine import Move
                with patch('blockblast.__main__.solve',return_value=(Move(0,0,0,1),)):
                    thread=threading.Thread(target=worker)
                    thread.start()
                    deadline=time.monotonic()+3
                    while control.status!='paused' and time.monotonic()<deadline:
                        time.sleep(.01)
                    self.assertEqual(control.status,'paused')
                    self.assertEqual(adb.moves,0)
                    time.sleep(.2)
                    adb.visible=True
                    thread.join(5)
                    control.stop_event.set()
                    thread.join(3)
            self.assertFalse(thread.is_alive())
            self.assertEqual(errors,[])
            self.assertEqual(adb.moves,1)
            self.assertEqual(control.status,'finished')
            report=json.loads(next((Path(d)/'logs').glob('*/summary.json')).read_text())
            self.assertGreater(report['paused_seconds'],0)

    def test_stop_works_while_indefinitely_paused(self):
        adb=PausingADB()
        control=RunControl()
        control.stop_event.set()
        with tempfile.TemporaryDirectory() as d,redirect_stdout(io.StringIO()):
            play(adb,{},DEFAULTS|{'capture':'screenshot','read_score':False},root=d,control=control,quiet=True)
        self.assertEqual(adb.moves,0)
        self.assertEqual(control.status,'finished')

class DragTests(unittest.TestCase):
    def test_successful_drag_does_not_send_duplicate_up(self):
        adb=object.__new__(ADB)
        adb.run=lambda *args: b''
        with patch.object(adb,'run',return_value=b'') as call:
            adb.drag_precise((1,2),(3,4))
        self.assertEqual(call.call_count,1)
    def test_failed_drag_releases_touch(self):
        adb=object.__new__(ADB)
        with patch.object(adb,'run',side_effect=[RuntimeError('test'),b'']) as call:
            with self.assertRaises(RuntimeError):
                adb.drag_precise((1,2),(3,4))
        self.assertEqual(call.call_count,2)
