import io
import unittest
from unittest.mock import patch
from blockblast.capture import VideoCapture

class FragmentedPipe:
    def __init__(self):
        self.parts=iter([b'ab',b'cd',b'ef',b''])
    def read(self,count):
        return next(self.parts)

class CaptureTests(unittest.TestCase):
    def test_pipe_partial_reads_assembled(self):
        self.assertEqual(VideoCapture._read_exact(FragmentedPipe(),6),b'abcdef')

    def test_pipe_eof_returns_partial_frame(self):
        self.assertEqual(VideoCapture._read_exact(io.BytesIO(b'abc'),6),b'abc')

    def test_ffmpeg_missing_does_not_start_recorder(self):
        with patch('blockblast.capture.shutil.which',return_value=None),patch('blockblast.capture.subprocess.Popen') as start:
            with self.assertRaises(RuntimeError):
                VideoCapture(None,(1080,2400))
            start.assert_not_called()
