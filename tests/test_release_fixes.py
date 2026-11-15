"""Release regressions: reject bad input and cancel gestures across UI changes."""
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PIL import Image, ImageDraw

from blockblast.adb import AppNotReady
from blockblast.capture import VideoCapture
from blockblast.config import DEFAULTS, load, validate
from blockblast.__main__ import main, parse_args, play
from blockblast.motion import drag_verified
from blockblast.profile import load_profile, validate_profile
from blockblast.runtime import RunControl
from blockblast.session import Session, Stats
from blockblast.storage import write_json
from blockblast.vision import read


class InputTests(unittest.TestCase):
    def test_config_requires_object(self):
        for value in ([], None, 'settings', 42):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate(value)
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder)/'settings.json'
                path.write_text(json.dumps(value))
                with self.assertRaises(ValueError):
                    load(path)

    def test_nonfinite_delays_fail_in_cli_and_api_before_adb(self):
        for value in ('nan', 'inf', '-inf'):
            with self.subTest(value=value), patch('sys.stderr', new=io.StringIO()):
                with self.assertRaises(SystemExit):
                    parse_args(['play', '--delay='+value])
                adb = Mock()
                with self.assertRaises(ValueError):
                    play(adb, {}, DEFAULTS, delay=float(value))
                self.assertEqual(adb.mock_calls, [])

    def test_bad_profile_geometry_rejected(self):
        for profile in ([], {'screen_size': []}, {'screen_size': [True, 2400]},
                        {'board': [0, 0, 100, 200]}, {'board': [0, 0, float('nan'), 800]},
                        {'tray': [-1, 100, 200, 300]}, {'drag_gain': 0},
                        {'tray_cell': -5}, {'lift_cells': float('inf')},
                        {'screen_size': [1080, 2400], 'tray': [0, 1500, 1200, 2000]}):
            with self.subTest(profile=profile), self.assertRaises(ValueError):
                validate_profile(profile)

    def test_valid_profile_and_empty_autodetection(self):
        self.assertEqual(validate_profile({}), {})
        profile = load_profile(Path(__file__).resolve().parents[1]/'profiles/default.json')
        self.assertEqual(profile, {})

    pass


class GreenPaletteTests(unittest.TestCase):
    pass

    pass

    pass


class GestureCancellationTests(unittest.TestCase):
    def run_gesture(self, foreground=None, pause_on_wait=False):
        frame = Image.new('RGB', (1080, 2400))
        adb = Mock()
        adb.check_foreground.side_effect = foreground
        control = RunControl()
        control.video = SimpleNamespace(sequence=1, latest=lambda **kw: frame)
        if pause_on_wait:
            control.wait = lambda _: control.pause_event.set()
        else:
            control.wait = lambda _: None
        piece = SimpleNamespace(center=(200, 1800), shape=((0, 0),), box=(175, 1775, 225, 1825))
        state = SimpleNamespace(cell=100, size=(1080, 2400))
        with patch('blockblast.motion.floating_bounds', return_value=None):
            result = drag_verified(adb, frame, state, piece, None, (300, 1200), {}, control)
        return adb, result

    def test_video_app_switch_cancels_and_releases_at_tray(self):
        adb, result = self.run_gesture([None, AppNotReady('Home')])
        self.assertFalse(result.released)
        self.assertEqual(result.reason, 'Home')
        self.assertEqual(adb.run.call_args.args[-3:], ('UP', 200, 1800))

    def test_video_manual_pause_cancels_before_moving(self):
        adb, result = self.run_gesture(pause_on_wait=True)
        self.assertFalse(result.released)
        self.assertEqual(result.reason, 'Пауза по кнопке')
        self.assertEqual([c.args[-3:] for c in adb.run.call_args_list],
                         [('DOWN', 200, 1800), ('MOVE', 200, 1800), ('UP', 200, 1800)])

    def test_foreground_loss_before_down_sends_no_touch(self):
        adb, result = self.run_gesture([AppNotReady('Home')])
        self.assertFalse(result.released)
        adb.run.assert_not_called()

    def test_late_recorder_pid_is_killed_after_close(self):
        video = object.__new__(VideoCapture)
        video.closed = True
        video._kill_remote = Mock()
        pipe = io.BytesIO(b'BLOCKBLAST_STREAM_PID:4321\n')
        video._stderr(pipe, remote=True)
        video._kill_remote.assert_called_once_with(4321)


class StorageLifecycleTests(unittest.TestCase):
    def test_missing_record_is_unknown_until_ocr_reads_it(self):
        stats = Stats()
        stats.update_score(13915, None)
        self.assertIsNone(stats.best)
        stats.update_score(13987, 125024)
        self.assertEqual(stats.best, 125024)
        stats.update_score(14000, None)
        self.assertEqual(stats.best, 125024)

    def test_failed_atomic_replace_preserves_previous_json_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'settings.json'
            write_json(path, {'previous': True})
            with patch('blockblast.storage.Path.replace', side_effect=OSError('disk full')):
                with self.assertRaises(OSError):
                    write_json(path, {'previous': False})
            self.assertEqual(json.loads(path.read_text()), {'previous': True})
            self.assertEqual(list(Path(folder).iterdir()), [path])

    pass
