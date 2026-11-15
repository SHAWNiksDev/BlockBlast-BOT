import unittest
from blockblast.engine import ROWS,COLS,FULL,place,placements,solve

class EngineTests(unittest.TestCase):
    def test_cross_clears_simultaneously(self):
        board = (ROWS[0]|COLS[0]) ^ 1
        after,lines = place(board,1)
        self.assertEqual((after,lines),(0,2))

    def test_no_gravity(self):
        above = 1 << 8
        after,lines = place((ROWS[7]^ (1<<63))|above,1<<63)
        self.assertEqual((after,lines),(above,1))

    def test_overlap_rejected(self):
        with self.assertRaises(ValueError): place(1,1)

    def test_diagonal_orientation_and_edges(self):
        moves=placements(((0,0),(1,1)))
        self.assertEqual(len(moves),49)
        self.assertTrue(all(mask.bit_count()==2 and not mask&~FULL for _,_,mask in moves))
        self.assertIn((0,0,1|(1<<9)),moves)
        self.assertNotIn((0,0,2|(1<<8)),moves)

    def test_small_piece_unlocks_large(self):
        board=(ROWS[0]|COLS[0])^1
        pieces={0:tuple((0,c) for c in range(8)),1:((0,0),)}
        plan=solve(board,pieces)
        self.assertEqual(len(plan),2)
        self.assertEqual(plan[0].slot,1)
        for move in plan:
            self.assertFalse(board&move.mask)
            board,_=place(board,move.mask)
        self.assertEqual(board,0)

    def test_no_legal_move(self):
        self.assertEqual(solve(FULL,{0:((0,0),)}),())

    def test_rejected_first_placement_excluded(self):
        pieces={0:((0,0),)}
        first=solve(0,pieces)[0]
        second=solve(0,pieces,forbidden={(first.slot,first.row,first.col)})[0]
        self.assertNotEqual((first.row,first.col),(second.row,second.col))
