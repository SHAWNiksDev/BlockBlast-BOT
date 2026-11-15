from copy import deepcopy
import unittest
from blockblast.stability import StableState
from blockblast.vision import State,Piece

class StabilityTests(unittest.TestCase):
    def state(self,shape=((0,0),),box=(100,100,150,150)):
        return State(0,{0:Piece(shape,(125,125),box)},(61,580,1019,1539),(1080,2400))

    def test_partial_deal_not_locked_in(self):
        observer=StableState(3,.2)
        partial=self.state()
        actual=self.state(((0,0),(1,0),(1,1)))
        self.assertFalse(observer.observe(partial,0))
        self.assertFalse(observer.observe(partial,.1))
        self.assertFalse(observer.observe(actual,.15))
        self.assertFalse(observer.observe(actual,.25))
        self.assertTrue(observer.observe(actual,.36))

    def test_same_shape_still_moving_does_not_count_as_stable(self):
        observer=StableState(3,.2)
        self.assertFalse(observer.observe(self.state(),0))
        moving=self.state(box=(110,110,160,160))
        self.assertFalse(observer.observe(moving,.15))
        self.assertFalse(observer.observe(moving,.25))
        self.assertTrue(observer.observe(moving,.36))

    def test_invalid_frame_resets_consensus(self):
        observer=StableState(3,.2)
        state=self.state()
        observer.observe(state,0)
        observer.observe(state,.1)
        observer.reset()
        self.assertFalse(observer.observe(state,1))

    def test_changed_board_resets_consensus(self):
        observer=StableState(3,.2)
        state=self.state()
        observer.observe(state,0)
        observer.observe(state,.1)
        state=deepcopy(state)
        state.board=1
        self.assertFalse(observer.observe(state,.3))
