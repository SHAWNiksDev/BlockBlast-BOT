import unittest,json
from pathlib import Path
from PIL import Image
from blockblast.vision import read
from blockblast.engine import solve,rescue_plan,place
from blockblast.__main__ import destination
ROOT=Path(__file__).resolve().parent.parent
class TightPlacementTests(unittest.TestCase):
    def test_rescue_places_all_three_legally(self):
        pieces={0:((0,0),(1,0)),1:((0,0),(0,1),(1,1)),2:((0,0),(1,1))}
        plan=rescue_plan(0,pieces)
        self.assertEqual(len(plan),3)
        board=0
        for move in plan:
            self.assertFalse(board&move.mask)
            board,_=place(board,move.mask)
