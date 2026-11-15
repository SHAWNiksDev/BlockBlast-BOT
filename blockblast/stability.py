"""Temporal consensus: shapes and geometry must finish animating."""
import time

class StableState:
    def __init__(self, frames=3, seconds=.2):
        self.frames=frames
        self.seconds=seconds
        self.reset()

    def reset(self):
        self.previous=None
        self.anchor=None
        self.count=0
        self.since=0

    def observe(self, state, now=None):
        now=time.monotonic() if now is None else now
        same=self.previous is not None and state.signature()==self.previous.signature()
        if same:
            tolerance=max(2,state.cell*.025)
            same=all(max(abs(a-b) for a,b in zip(piece.box,self.anchor.pieces[slot].box))<=tolerance
                     for slot,piece in state.pieces.items())
        if not same:
            self.count=1
            self.anchor=state
            self.since=now
        else:
            self.count+=1
        self.previous=state
        return self.count>=self.frames and now-self.since>=self.seconds


def matches_result(state, board, remaining):
    """A move is confirmed by both board and tray, never by board alone."""
    if state.board!=board:return False
    shapes={slot:piece.shape for slot,piece in state.pieces.items()}
    return shapes==remaining if remaining else set(shapes)=={0,1,2}
