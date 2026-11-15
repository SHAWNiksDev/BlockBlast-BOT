import json
from pathlib import Path
import unittest
from PIL import Image, ImageDraw
from blockblast.vision import read
from blockblast.engine import Move
from blockblast.__main__ import destination

ROOT=Path(__file__).resolve().parent.parent

class VisionTests(unittest.TestCase):

    def test_menu_rejected(self):
        with self.assertRaises(ValueError):
            read(Image.new('RGB',(1080,2400),(50,75,130)))



    def test_wrong_screen_size_rejected(self):
        with self.assertRaises(ValueError):
            read(Image.new('RGB',(720,1600)),{'screen_size':[1080,2400]})
