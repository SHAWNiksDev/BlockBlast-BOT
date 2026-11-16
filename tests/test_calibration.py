import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from PIL import Image
from PySide6.QtCore import QObject, Signal, QPointF, QEvent
from PySide6.QtWidgets import QApplication
from blockblast.calibration import SetupDialog, RegionView, region_profile
from blockblast.profile import load_profile
from blockblast.vision import State, Piece


class FakeCapture(QObject):
    result=Signal(object,str)
    finished=Signal()
    def __init__(self,*args):super().__init__();self.running=False
    def start(self):pass
    def isRunning(self):return self.running


class CalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def tearDown(self):
        for widget in self.app.topLevelWidgets():
            widget.close();widget.deleteLater()
        self.app.sendPostedEvents(None,QEvent.Type.DeferredDelete)

    def test_invalid_regions_and_nonfinite_gain_rejected(self):
        for board,tray,gain in [([0,0,200,100],[0,220,300,300],1.5),
                                 ([0,0,200,200],[0,100,300,300],1.5),
                                 ([0,0,200,200],[0,220,500,300],1.5),
                                 ([0,0,200,200],[0,220,300,300],float('nan'))]:
            with self.subTest(board=board,tray=tray,gain=gain),self.assertRaises(ValueError):
                region_profile((400,600),board,tray,20,gain)

    def test_image_coordinates_account_for_letterboxing(self):
        view=RegionView();view.resize(400,400);view.set_image(Image.new('RGB',(200,400)))
        self.assertIsNone(view.point(QPointF(20,200)))
        self.assertEqual(view.point(QPointF(200,200)),(100,200))

    def test_check_required_and_edits_invalidate_saved_calibration(self):
        state=State(0,{0:Piece(((0,0),),(1,1),(0,0,2,2))},(10,10,210,210),(400,600))
        with TemporaryDirectory() as directory,patch('blockblast.calibration.Capture',FakeCapture):
            dialog=SetupDialog('synthetic-device',Path(directory))
            dialog.image=Image.new('RGB',(400,600));dialog.board=[10,10,210,210];dialog.tray=[10,250,390,350];dialog.pitch.setValue(20)
            dialog.store();self.assertIsNone(dialog.profile_path)
            with patch('blockblast.calibration.read',return_value=state):dialog.verify()
            self.assertTrue(dialog.save_button.isEnabled())
            dialog.gain.setValue(1.6);self.assertFalse(dialog.save_button.isEnabled())
            with patch('blockblast.calibration.read',side_effect=ValueError('bad region')):dialog.verify()
            self.assertIsNone(dialog.checked)
            with patch('blockblast.calibration.read',return_value=state):dialog.verify()
            dialog.store();self.assertEqual(load_profile(dialog.profile_path)['drag_gain'],1.6)
            self.assertNotIn('synthetic-device',dialog.profile_path.read_text())
            self.assertFalse(list(Path(directory).glob('**/*.png')))
            dialog.close()

    def test_dialog_keeps_capture_alive_until_thread_finishes(self):
        with TemporaryDirectory() as directory,patch('blockblast.calibration.Capture',FakeCapture):
            dialog=SetupDialog('synthetic-device',directory);dialog.show();dialog.capture.running=True
            dialog.close();self.assertTrue(dialog.isVisible())
            dialog.capture.running=False;dialog.close();self.assertFalse(dialog.isVisible())
