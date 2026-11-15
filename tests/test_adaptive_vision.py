"""Recognition must survive theme exposure changes without moving the lattice."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageDraw

from blockblast.engine import FULL
from blockblast.profile import load_profile
from blockblast.vision import read
from blockblast.score import ScoreReader

ROOT = Path(__file__).resolve().parents[1]
PROFILE = load_profile(ROOT/'profiles/default.json')


class AdaptiveVisionTests(unittest.TestCase):
    def test_bundled_model_is_used_independently_of_host_language(self):
        reader=ScoreReader(False)
        self.assertEqual(Path(reader.environment['TESSDATA_PREFIX']),ROOT/'blockblast/assets/tessdata')


    def test_old_ocr_is_disabled_instead_of_returning_wrong_digits(self):
        with patch('blockblast.score.shutil.which',return_value='/usr/bin/tesseract'), \
             patch('blockblast.score.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=b'tesseract 4.1.1')):
            self.assertFalse(ScoreReader().available)
