from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import unittest
from PIL import Image
from blockblast.motion import target_box_origin,drag_verified
from blockblast.runtime import RunControl
from blockblast.history import records,describe,duration,date
from blockblast.session import Session,Stats
from blockblast.config import DEFAULTS

class MotionTests(unittest.TestCase):
    def test_axes_independent_at_bottom_edge(self):
        state=SimpleNamespace(bounds=(61,580,1019,1539),cell=119.75)
        move=SimpleNamespace(row=5,col=0)
        x,y=target_box_origin(state,move,(93,1181,447,1534))
        # Bias is applied horizontally; vertically the piece is clamped to the
        # board instead of being pushed past the bottom border.
        self.assertAlmostEqual(x,90.94,delta=1)
        self.assertAlmostEqual(y,1186,delta=1)

    def test_right_edge_target_is_clamped_inside_board(self):
        state=SimpleNamespace(bounds=(61,580,1019,1539),cell=119.75)
        move=SimpleNamespace(row=2,col=6)
        x,y=target_box_origin(state,move,(800,800,1040,1040))
        self.assertEqual(x,1019-240)
        self.assertEqual(y,580+2.25*119.75)


    def test_unknown_sprite_releases_at_planned_point(self):
        # A visual detection miss must not return a piece that was already
        # dragged to a calibrated target: the board check is the final judge.
        calls=[]
        adb=SimpleNamespace(screenshot=lambda:Image.new('RGB',(1080,2400)),check_foreground=lambda p:None,run=lambda *args:calls.append(args))
        piece=SimpleNamespace(center=(200,1800),shape=((0,0),),box=(175,1775,225,1825))
        control=RunControl()
        with patch('blockblast.motion.floating_bounds',return_value=None),patch.object(control,'wait'):
            result=drag_verified(adb,None,SimpleNamespace(cell=100),piece,None,(300,1200),{},control)
        self.assertTrue(result.released)
        self.assertEqual(result.corrections,0)
        self.assertEqual(calls[-1][-3:],('UP',300,1200))

    def test_app_switch_during_hold_cancels_instead_of_crashing(self):
        from blockblast.adb import AppNotReady
        adb=SimpleNamespace(screenshot=lambda:Image.new('RGB',(1080,2400)),run=lambda *args:None)
        adb.check_foreground=__import__('unittest.mock',fromlist=['Mock']).Mock(side_effect=[None,AppNotReady('Home')])
        piece=SimpleNamespace(center=(200,1800),shape=((0,0),),box=(175,1775,225,1825))
        control=RunControl()
        with patch.object(control,'wait'):
            result=drag_verified(adb,None,SimpleNamespace(cell=100),piece,None,(300,1200),{},control)
        self.assertFalse(result.released)
        self.assertEqual(result.reason,'Home')

class HistoryTests(unittest.TestCase):
    def test_full_timeline_survives_event_log_rotation(self):
        with TemporaryDirectory() as folder:
            session=Session(folder,DEFAULTS|{'max_log_mb':1})
            for i in range(300):session.event('move',move=i,slot=0,row=0,col=0,payload='x'*10000)
            session.finish(Stats(),'test')
            events=list(records(session.directory))
            self.assertEqual(sum(e['event']=='move' for e in events),300)
            self.assertEqual(events[0]['move'],0)
            self.assertEqual(events[-1]['event'],'summary')
            report=events[-1]
            self.assertIn('started_at',report);self.assertIn('ended_at',report)
    def test_human_time_and_unknown_score(self):
        self.assertEqual(duration(3661),'01:01:01')
        self.assertEqual(date('2026-10-29T22:00:01+07:00'),'29.10.2026 22:00:01')
        self.assertIn('очки —',describe({'event':'move','time':'2026-10-29T22:00:01','move':1,'score':None}))
