import os
import sys
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from PySide6.QtCore import QObject,Signal
from PySide6.QtWidgets import QApplication
from blockblast.config import DEFAULTS,load
from blockblast.runtime import RunControl
from blockblast.desktop import Window

class Worker(QObject):
    event=Signal(str,object)
    finished=Signal()
    def __init__(self,serial,settings):
        super().__init__();self.serial=serial;self.settings=dict(settings);self.running=False
        self.control=RunControl(lambda kind,data:self.event.emit(kind,data))
    def start(self):self.running=True
    def isRunning(self):return self.running
    def finish(self):self.running=False;self.finished.emit()

class DesktopStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.directory=TemporaryDirectory();self.root=Path(self.directory.name)
        (self.root/'profiles').mkdir();(self.root/'profiles/default.json').write_text('{}')
        self.patches=[patch('blockblast.desktop.ROOT',self.root),patch('blockblast.desktop.load',return_value=dict(DEFAULTS)),patch('blockblast.desktop.save'),patch('blockblast.desktop.BotWorker',side_effect=Worker)]
        self.mocks=[p.start() for p in self.patches]
        self.window=Window(discover=False);self.window.discovered([('serial','Phone')],'')
    def tearDown(self):
        self.window.session_active=False;self.window.close()
        for p in reversed(self.patches):p.stop()
        self.directory.cleanup()
    def test_trial_limits_only_the_worker_and_preserves_normal_settings(self):
        self.window.start_trial()
        self.assertEqual(self.window.worker.settings['max_moves'],1)
        self.assertEqual(self.window.settings['max_moves'],DEFAULTS['max_moves'])
        self.assertFalse(self.window._trial_next)

    def test_speed_is_removed_and_legacy_file_migrates(self):
        self.assertNotIn('speed',self.window.fields)
        path=self.root/'old.json';path.write_text(json.dumps({'speed':'safe','max_moves':12}))
        values=load(path);self.assertNotIn('speed',values);self.assertEqual(values['max_moves'],12)
    def test_active_and_paused_session_locks_fields_save_reset_and_device(self):
        self.window.start_bot();worker=self.window.worker
        self.assertFalse(self.window.settings_editor.isEnabled())
        self.assertFalse(self.window.devices.isEnabled())
        self.assertFalse(self.window.refresh_button.isEnabled())
        self.assertFalse(self.window.save_settings())
        self.window.reset_settings();self.assertFalse(self.window.settings_dirty)
        self.window.toggle_pause();self.assertTrue(worker.control.pause_event.is_set())
        self.assertFalse(self.window.settings_editor.isEnabled())
        self.window.discovered([('other','Other')],'');self.assertEqual(self.window.devices.currentData(),'serial')
        self.assertEqual(self.mocks[2].call_count,0)
    def test_double_start_only_creates_one_worker(self):
        self.window.start_bot();self.window.start_bot();self.assertEqual(self.mocks[3].call_count,1)
    def test_unsaved_settings_validated_and_saved_before_start(self):
        self.window.fields['max_moves'].setValue(13)
        self.assertTrue(self.window.settings_dirty)
        self.window.start_bot()
        self.assertEqual(self.window.worker.settings['max_moves'],13)
        self.assertEqual(self.mocks[2].call_count,1)
        self.assertFalse(self.window.settings_dirty)
    def test_stop_disables_pause_and_start_until_worker_exits(self):
        self.window.start_bot();worker=self.window.worker;self.window.stop_bot()
        self.assertTrue(worker.control.stop_event.is_set())
        self.assertFalse(self.window.pause_action.isEnabled());self.assertFalse(self.window.start_action.isEnabled())
        self.window.toggle_pause();self.assertFalse(worker.control.pause_event.is_set())
        self.window.bot_event('status',{'status':'running','reason':'late message'})
        self.assertIn('Останавливаю',self.window.status.text())
        worker.finish();self.assertTrue(self.window.settings_editor.isEnabled());self.assertTrue(self.window.start_action.isEnabled())
    def test_close_while_running_requests_stop_and_prevents_new_start(self):
        self.window.show();self.window.start_bot();worker=self.window.worker
        self.window.close();self.assertTrue(self.window.closing);self.assertTrue(worker.control.stop_event.is_set())
        self.window.start_bot();self.assertEqual(self.mocks[3].call_count,1)
        worker.finish();self.assertFalse(self.window.isVisible())
    def test_invalid_profile_does_not_leave_controls_locked(self):
        self.window.fields['profile'].setText('missing.json');self.window.start_bot()
        self.assertFalse(self.window.session_active);self.assertTrue(self.window.settings_editor.isEnabled())
        self.assertEqual(self.mocks[3].call_count,0)


@unittest.skipIf(sys.platform=='win32','Linux abstract socket implementation')
class DeviceLeaseTests(unittest.TestCase):
    def test_busy_phone_reports_error_and_closes_socket(self):
        import errno
        from blockblast.runtime import DeviceLease
        with patch('socket.socket') as factory:
            factory.return_value.bind.side_effect=OSError(errno.EADDRINUSE,'busy')
            with self.assertRaisesRegex(RuntimeError,'другим экземпляром'):
                DeviceLease('test')
            factory.return_value.close.assert_called_once()
    def test_context_releases_phone(self):
        from blockblast.runtime import DeviceLease
        with patch('socket.socket') as factory:
            with DeviceLease('test'):pass
            factory.return_value.close.assert_called_once()
