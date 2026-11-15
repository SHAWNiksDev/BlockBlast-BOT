"""Closed-loop positioning of a held piece, with bounded corrections and cancellation."""
from dataclasses import dataclass
import numpy as np
from .adb import AppNotReady

@dataclass
class MotionResult:
    released: bool
    corrections: int
    reason: str


def _frame_scale(frame, state):
    """Stream frame pixels per phone-screen pixel (1 for full screenshots)."""
    size=getattr(state,'size',None)
    if size and size[0]:
        return frame.shape[1]/float(size[0])
    return 1.0


def floating_bounds(before, held, piece, state, move, predicted=None):
    a=np.asarray(held.convert('RGB')).astype(np.int16)
    b=np.asarray(before.convert('RGB')).astype(np.int16)
    if a.shape!=b.shape:
        return None
    scale=_frame_scale(a,state)
    cell=state.cell*scale
    left,top,right,bottom=(v*scale for v in state.bounds)
    d=max(3,round(5*scale))
    x,y=round(piece.center[0]*scale),round(piece.center[1]*scale)
    y0=max(d,min(a.shape[0]-d,y));x0=max(d,min(a.shape[1]-d,x))
    color=np.median(b[y0-d:y0+d,x0-d:x0+d],axis=(0,1))
    mask=(np.linalg.norm(a-color,axis=2)<70)&(np.abs(a-b).max(2)>55)
    # Limit to board and its immediate surroundings, excluding the tray and score.
    # Do not clip the area above the board: the dragged piece is rendered above
    # the finger, so top-row placements would lose part of the sprite.
    mask[min(a.shape[0],round(bottom+cell*.8)):]=False
    mask[:,:max(0,round(left-cell*.2))]=False
    mask[:,min(a.shape[1],round(right+cell*.2)):]=False
    if predicted is not None:
        px,py=(v*scale for v in predicted)
        w=(max(c for r,c in piece.shape)+1)*cell
        h=(max(r for r,c in piece.shape)+1)*cell
        margin=max(round(30*scale),round(cell*.75))
        mask[:max(0,round(py-margin))]=False
        mask[min(a.shape[0],round(py+h+margin)):]=False
        mask[:,:max(0,round(px-margin))]=False
        mask[:,min(a.shape[1],round(px+w+margin)):]=False
    for i in range(64):
        if state.board>>i&1:
            x0=round(left+(i%8)*cell);y0=round(top+(i//8)*cell)
            mask[max(0,y0):min(a.shape[0],round(y0+cell)),max(0,x0):min(a.shape[1],round(x0+cell))]=False
    ys,xs=np.where(mask)
    if not len(xs):return None
    box=(int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1))
    width=max(c for r,c in piece.shape)+1;height=max(r for r,c in piece.shape)+1
    if abs((box[2]-box[0])-width*cell)>cell*.4 or abs((box[3]-box[1])-height*cell)>cell*.4:
        return None
    return box


def target_box_origin(state,move,box,bias=.25,scale=1.0):
    left,top,right,bottom=[v*scale for v in state.bounds];cell=state.cell*scale
    width,height=box[2]-box[0],box[3]-box[1]
    # A real drop target is the cell origin plus bias, clamped to the board.
    # There is no extra inset: the game itself snaps the piece to the border.
    x=min(left+(move.col+bias)*cell,right-width)
    y=min(top+(move.row+bias)*cell,bottom-height)
    return max(left,x),max(top,y)


def _snapshot(adb,control,min_sequence=0):
    """Fresh frame while holding a piece; raises if the active stream stalls."""
    video=getattr(control,'video',None)
    if video is not None:
        frame=video.latest(min_sequence=min_sequence,timeout=1.2)
        control.frame=frame
        return frame
    return adb.screenshot()


def drag_verified(adb,before,state,piece,move,end,profile,control,grab=.12,release=.10,bias=None):
    """Drag, visually measure the held piece and correct before releasing.

    ``before`` may be a stream frame.  In stream mode no extra adb screenshot is
    needed: fresh frames come from the running decoder, so verification is both
    more accurate and cheaper than the old retry-only path.
    """
    if bias is None:
        bias=profile.get('release_bias_cells',.25)
    video=getattr(control,'video',None)
    use_video=video is not None
    if use_video:
        try:
            before=_snapshot(adb,control)
        except RuntimeError:
            # Stream died just before the gesture: continue with a consistent
            # full-resolution before-frame instead of mixing frame sizes.
            use_video=False
            before=adb.screenshot()
    elif before is None:
        before=adb.screenshot()
    start=piece.center;point=list(end);gain=profile.get('drag_gain',1.5)
    corrections=0;released=False
    touched=False
    def event(kind,point):
        adb.run('shell','input','touchscreen','motionevent',kind,round(point[0]),round(point[1]))
    def ensure_active():
        control.check()
        if control.pause_event.is_set():
            raise AppNotReady('Пауза по кнопке')
        adb.check_foreground('com.block.juggle')
    def drop():
        nonlocal released
        ensure_active()
        event('UP',point)
        released=True
    try:
        ensure_active()
        touched=True
        event('DOWN',start);control.wait(max(.1,grab))
        ensure_active()
        sequence=video.sequence if use_video else 0
        event('MOVE',point)
        # The game eases the picked-up piece towards the finger.  A video frame
        # taken too early shows it halfway and the measured box is useless.
        control.wait(max(.14,release*2))
        for attempt in range(4):
            ensure_active()
            try:
                held=_snapshot(adb,control,sequence+1) if use_video else adb.screenshot()
            except RuntimeError:
                return MotionResult(False,corrections,'Видеопоток недоступен во время жеста')
            if use_video:
                sequence=video.sequence
            control.frame=held
            width=max(c for r,c in piece.shape)+1;height=max(r for r,c in piece.shape)+1
            cx=(piece.box[0]+piece.box[2])/2+gain*(point[0]-start[0])
            cy=(piece.box[1]+piece.box[3])/2+gain*(point[1]-start[1])-profile.get('lift_cells',2.25)*state.cell
            predicted=(cx-width*state.cell/2,cy-height*state.cell/2)
            box=floating_bounds(before,held,piece,state,move,predicted)
            if box is None:
                # The planned point is calibrated; a missed visual detection is
                # not a reason to return a valid piece to the tray.  Try a few
                # more rendered frames, then release at the planned point and
                # let the normal board verification decide.
                if attempt<3:
                    control.wait(.08)
                    continue
                drop()
                return MotionResult(True,corrections,'Положение не проверено, отпускаю по расчётной точке')
            screen=getattr(state,'size',None) or (held.width,held.height)
            scale=held.width/float(screen[0] or held.width)
            tx,ty=target_box_origin(state,move,box,bias,scale)
            dx,dy=tx-box[0],ty-box[1]
            if max(abs(dx),abs(dy))<=max(3,round(8*scale)):
                drop()
                return MotionResult(True,corrections,'Положение фигуры проверено по кадру')
            point[0]+=dx/(gain*scale);point[1]+=dy/(gain*scale)
            if not (0<point[0]<screen[0] and 0<point[1]<screen[1]):
                return MotionResult(False,corrections,'Поправка вышла за экран')
            sequence=video.sequence if use_video else 0
            ensure_active()
            event('MOVE',point);corrections+=1
            control.wait(max(.12,release*1.5))
        # Best-effort release at the closest commanded point.  The game and the
        # board verification remain the source of truth for the move.
        drop()
        return MotionResult(True,corrections,'Точка отпускания скорректирована не полностью')
    except AppNotReady as exc:
        return MotionResult(False,corrections,str(exc))
    finally:
        if touched and not released:
            # Return to the tray before release; never release an uncertain board position.
            try:
                try:event('MOVE',start)
                finally:event('UP',start)
            except Exception:
                pass
