from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
from blockblast.score import ScoreReader
from blockblast.session import Stats

ROOT=Path(__file__).resolve().parent.parent

class ScoreTests(unittest.TestCase):


    def test_disabled_reader_does_not_guess_score(self):
        self.assertEqual(ScoreReader(False).read(Image.new('RGB',(1080,2400)),(61,580,1019,1539),{}),(None,None))
