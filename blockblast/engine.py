"""64-bit board, simultaneous line clears, three-piece beam search."""
from dataclasses import dataclass
from functools import lru_cache

FULL = (1 << 64) - 1
ROWS = tuple(255 << (8*r) for r in range(8))
COLS = tuple(sum(1 << (8*r+c) for r in range(8)) for c in range(8))

@dataclass(frozen=True)
class Move:
    slot: int
    row: int
    col: int
    mask: int

@lru_cache(maxsize=256)
def placements(shape):
    height = max(r for r,c in shape)+1
    width = max(c for r,c in shape)+1
    return tuple((r,c,sum(1 << ((r+dy)*8+c+dx) for dy,dx in shape))
                 for r in range(9-height) for c in range(9-width))

def place(board, mask):
    if board & mask:
        raise ValueError('Overlapping placement')
    occupied = board | mask
    lines = [line for line in ROWS+COLS if occupied & line == line]
    clear = 0
    for line in lines:
        clear |= line
    return occupied & ~clear, len(lines)

MASKS_3X3 = tuple(m for _, _, m in placements(tuple((r, c) for r in range(3) for c in range(3))))
MASKS_5X1 = tuple(m for _, _, m in placements(tuple((0, c) for c in range(5))))
MASKS_1X5 = tuple(m for _, _, m in placements(tuple((r, 0) for r in range(5))))
MASKS_2X3 = tuple(m for _, _, m in placements(tuple((r, c) for r in range(2) for c in range(3))))
MASKS_3X2 = tuple(m for _, _, m in placements(tuple((r, c) for r in range(3) for c in range(2))))
MASKS_2X2 = tuple(m for _, _, m in placements(((0, 0), (0, 1), (1, 0), (1, 1))))
MASKS_L3 = tuple(m for s in (
    ((0, 0), (1, 0), (2, 0), (2, 1), (2, 2)),
    ((0, 0), (0, 1), (0, 2), (1, 0), (2, 0)),
    ((0, 2), (1, 2), (2, 2), (2, 1), (2, 0)),
    ((0, 0), (0, 1), (0, 2), (1, 2), (2, 2))
) for _, _, m in placements(s))

@lru_cache(maxsize=100000)
def evaluate(board):
    empty = FULL ^ board
    k = board.bit_count()

    # Killer piece survivability:
    c3 = sum(not (board & m) for m in MASKS_3X3)
    p_3x3 = -70.0 if c3 == 0 else min(c3, 4) * 5.0

    c5h = sum(not (board & m) for m in MASKS_5X1)
    p_5h = -40.0 if c5h == 0 else min(c5h, 3) * 3.5

    c5v = sum(not (board & m) for m in MASKS_1X5)
    p_5v = -40.0 if c5v == 0 else min(c5v, 3) * 3.5

    cl3 = sum(not (board & m) for m in MASKS_L3)
    p_l3 = -25.0 if cl3 == 0 else min(cl3, 4) * 2.0

    c2 = sum(not (board & m) for m in MASKS_2X2)
    p_2x2 = min(c2, 8) * 1.5

    crect = sum(not (board & m) for m in MASKS_2X3) + sum(not (board & m) for m in MASKS_3X2)
    p_rect = min(crect, 6) * 0.8

    adjacent = ((empty << 1) & ~COLS[0]) | ((empty >> 1) & ~COLS[7]) | (empty << 8) | (empty >> 8)
    isolated = (empty & ~adjacent).bit_count()

    fragmentation = ((board^(board>>1)) & (FULL^COLS[7])).bit_count() + ((board^(board>>8)) & (FULL^ROWS[7])).bit_count()

    line_potential = 0.0
    for line in ROWS + COLS:
        cnt = (board & line).bit_count()
        if cnt == 7: line_potential += 8.0
        elif cnt == 6: line_potential += 4.0
        elif cnt == 5: line_potential += 1.5

    overfill = max(0, k - 28)
    density_penalty = k * 2.2 + (overfill ** 1.8) * 0.8
    if k < 6:
        density_penalty += (6 - k) * 3.0

    return (p_3x3 + p_5h + p_5v + p_l3 + p_2x2 + p_rect
            - isolated * 18.0 - fragmentation * 0.4
            + line_potential - density_penalty)

def solve(board, pieces, beam=180, forbidden=()):
    """Prefer placing every visible piece, then clears and future free space."""
    states = [(evaluate(board), board, tuple(pieces), (), 0.0)]
    best = None
    for depth in range(len(pieces)):
        candidates = {}
        for _, current, remaining, path, reward in states:
            for slot in remaining:
                for row,col,mask in placements(pieces[slot]):
                    if not path and (slot,row,col) in forbidden:
                        continue
                    if current & mask:
                        continue
                    after, lines = place(current, mask)
                    gain = reward + 25*lines + 12*lines*lines + (18 if lines > 0 else 0) + (25 if not after and lines else 0)
                    score = evaluate(after)+gain
                    rest = tuple(x for x in remaining if x != slot)
                    key = (after, rest)
                    entry = (score, after, rest, path+(Move(slot,row,col,mask),), gain)
                    if key not in candidates or candidates[key][0] < score:
                        candidates[key] = entry
        if not candidates:
            break
        states = sorted(candidates.values(), key=lambda x:x[0], reverse=True)[:beam]
        best = states[0]
    result=best[3] if best else ()
    if len(result)<len(pieces):
        recovered=rescue_plan(board,pieces,forbidden=forbidden)
        if recovered is not None:
            return recovered
    return result


def rescue_plan(board,pieces,budget=150000,forbidden=()):
    """Search all piece orders if beam pruning failed to fit the entire tray."""
    seen=set()
    nodes=0
    def visit(current,remaining,is_first=True):
        nonlocal nodes
        if not remaining:
            return ()
        key=(current,remaining)
        if key in seen or nodes>=budget:
            return None
        seen.add(key)
        nodes+=1
        options=[]
        for slot in remaining:
            for row,col,mask in placements(pieces[slot]):
                if is_first and (slot,row,col) in forbidden:
                    continue
                if not current&mask:
                    after,lines=place(current,mask)
                    options.append((lines*30+evaluate(after),slot,row,col,mask,after))
        options.sort(reverse=True)
        for _,slot,row,col,mask,after in options:
            rest=visit(after,tuple(i for i in remaining if i!=slot),is_first=False)
            if rest is not None:
                return (Move(slot,row,col,mask),)+rest
        return None
    return visit(board,tuple(sorted(pieces)))
