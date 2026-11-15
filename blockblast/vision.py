"""Color/lattice recognition without fixed shape templates or OCR."""
from dataclasses import dataclass
import numpy as np
from PIL import ImageDraw
from .profile import validate_profile

@dataclass
class Piece:
    shape: tuple
    center: tuple
    box: tuple

@dataclass
class State:
    board: int
    pieces: dict
    bounds: tuple
    size: tuple

    @property
    def cell(self):
        return (self.bounds[2]-self.bounds[0])/8

    def signature(self):
        return self.board, tuple((k,v.shape) for k,v in self.pieces.items())


def runs(values):
    positions = np.flatnonzero(values)
    if not len(positions):
        return []
    groups = np.split(positions, np.where(np.diff(positions)>1)[0]+1)
    return [(int(g[0]), int(g[-1])+1) for g in groups]


def board_bounds(im):
    h,w = im.shape[:2]
    dark = im.max(axis=2)<85
    ys = np.flatnonzero(dark.sum(axis=1)>w*.74)
    groups = runs(np.isin(np.arange(h), ys))
    for top,bottom in sorted(groups, key=lambda p:p[1]-p[0], reverse=True):
        if not .3*w < bottom-top < 1.05*w:
            continue
        xs = runs(dark[(top+bottom)//2])
        for left,right in sorted(xs, key=lambda p:p[1]-p[0], reverse=True):
            if abs((right-left)-(bottom-top)) < w*.04 and right-left>w*.7:
                return left,top,right,bottom
    # The game changes its entire palette at score milestones. Find the board
    # by contrast against the screen background, without assuming blue/black.
    edge=max(2,w//40)
    background=np.median(np.concatenate((im[:,:edge],im[:,-edge:]),axis=1),axis=1)
    distinct=np.linalg.norm(im-background[:,None,:],axis=2)>50
    bands=runs(distinct.sum(axis=1)>w*.70)
    for top,bottom in sorted(bands,key=lambda pair:pair[1]-pair[0],reverse=True):
        if not .3*w<bottom-top<1.05*w:continue
        for left,right in sorted(runs(distinct[(top+bottom)//2]),key=lambda pair:pair[1]-pair[0],reverse=True):
            if abs((right-left)-(bottom-top))<w*.035 and right-left>w*.7:
                return left,max(top,bottom-(right-left)),right,bottom
    # Occupied cells break the wide dark bands. The grid itself is still one
    # connected dark component, so use its bounding box as a fallback.
    small = dark[::2,::2].copy()
    sh,sw = small.shape
    for yy in range(sh):
        for xx in range(sw):
            if not small[yy,xx]:
                continue
            stack = [(yy,xx)]
            small[yy,xx] = False
            lo_x=hi_x=xx
            lo_y=hi_y=yy
            count=0
            while stack:
                py,px = stack.pop()
                count += 1
                lo_x,hi_x=min(lo_x,px),max(hi_x,px)
                lo_y,hi_y=min(lo_y,py),max(hi_y,py)
                for ny,nx in ((py-1,px),(py+1,px),(py,px-1),(py,px+1)):
                    if 0<=ny<sh and 0<=nx<sw and small[ny,nx]:
                        small[ny,nx]=False
                        stack.append((ny,nx))
            bw,bh=(hi_x-lo_x+1)*2,(hi_y-lo_y+1)*2
            if bw>w*.7 and abs(bw-bh)<w*.035 and count>500:
                return lo_x*2,lo_y*2,(hi_x+1)*2,(hi_y+1)*2
    raise ValueError('Поле 8×8 не найдено: откройте классическую игру или задайте board в профиле.')


def scaled_profile(profile, scale):
    """Profile geometry in stream-image coordinates."""
    if scale==1:
        return profile
    local=dict(profile)
    for key in ('board','tray'):
        if local.get(key):
            local[key]=[v*scale for v in local[key]]
    if 'tray_cell' in local:
        local['tray_cell']=local['tray_cell']*scale
    return local


def block_relief(im, bounds, centers):
    """Recognize the light top and shaded bottom of a cube, regardless of hue."""
    left, top, right, _ = bounds
    cell = (right-left)/8
    result = []
    for index, center in enumerate(centers):
        row, col = divmod(index, 8)
        x, y = left+col*cell, top+row*cell
        x0, x1 = round(x+.35*cell), round(x+.65*cell)
        upper = np.median(im[round(y+.07*cell):round(y+.14*cell), x0:x1], axis=(0, 1))
        lower = np.median(im[round(y+.86*cell):round(y+.93*cell), x0:x1], axis=(0, 1))
        exposure = max(.25, min(1., float(max(upper.max(), center.max()))/200))
        result.append(min(np.mean(upper-center), np.mean(center-lower)) > 8*exposure
                      and np.linalg.norm(upper-lower) > 35*exposure)
    return np.asarray(result)


def read(image, profile=None, capture_scale=None):
    """Recognize a full-resolution screenshot or a scaled stream frame.

    Stream frames are published at their native resolution (540x1200 by
    default) but every returned coordinate is in phone-screen pixels, so the
    rest of the bot (gestures, score crops, GUI) is unchanged.
    """
    profile = validate_profile({} if profile is None else profile)
    source = image if image.mode=='RGB' else image.convert('RGB')
    w,h = source.size
    screen = profile.get('screen_size')
    scale = capture_scale
    if scale is None:
        scale = float(source.info.get('capture_scale',1.0) or 1.0)
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError('Некорректный масштаб кадра')
    if screen:
        sw,sh = screen
        if abs(w-sw*scale)>1 or abs(h-sh*scale)>1:
            raise ValueError('Разрешение экрана отличается от профиля. Выберите подходящий профиль.')
    else:
        scale = scale or 1.0
    local = scaled_profile(profile,scale)
    im = np.asarray(source).astype(np.int16)
    bounds = tuple(local.get('board') or board_bounds(im))
    left,top,right,bottom = bounds
    if abs(right-left-(bottom-top))>w*.04 or not (0<=left<right<=w and 0<=top<bottom<=h):
        raise ValueError('Некорректные границы поля')
    cell = (right-left)/8
    # Use the grid's local color as the reference. Empty pink/green cells can
    # be brighter than old colored blocks, so an absolute brightness test fails.
    points=[];neighbors=[]
    for r in range(1,8):
        for c in range(1,8):
            x,y=round(left+c*cell),round(top+r*cell)
            points.append(im[y,x])
            neighbors.append(np.median([im[round(y+dy*cell),round(x+dx*cell)]
                             for dx,dy in ((.10,.10),(-.10,.10),(.10,-.10),(-.10,-.10))],axis=0))
    points=np.asarray(points);grid_color=np.median(points,axis=0)
    contrast=np.linalg.norm(np.asarray(neighbors)-points,axis=1)
    # Occupied sprites cover some intersections. Their colours need not agree:
    # dense blue boards can have no dominant intersection colour at all.
    # Require the grid's spatial contrast across most of the lattice instead.
    contrast_threshold=6*max(.25,min(1.,float(grid_color.max())/90))
    if np.mean(contrast>=contrast_threshold)<.75:
        raise ValueError('Поле закрыто окном или анимацией')
    centers = []
    for r in range(8):
        for c in range(8):
            samples=[]
            d=max(1,round(cell*.055))
            # Number badges cover cell centres. Four off-centre face samples
            # retain the cube colour even when a badge resembles an empty cell.
            for dx,dy in ((.5,.5),(.25,.25),(.75,.25),(.25,.75),(.75,.75)):
                x,y=round(left+(c+dx)*cell),round(top+(r+dy)*cell)
                samples.append(np.median(im[y-d:y+d,x-d:x+d],axis=(0,1)))
            centers.append(np.median(samples,axis=0))
    centers = np.asarray(centers)
    dists_grid = np.linalg.norm(centers - grid_color, axis=1)
    # Light green empty cells are much brighter than their grid lines, while
    # green blocks can be closer to the grid in RGB distance. Empty cells keep
    # the grid's tint: compare channel differences before choosing a reference.
    tint_distance = np.std(centers-grid_color,axis=1)
    tint_ratio = tint_distance/np.maximum(dists_grid,1)
    relief = block_relief(im,bounds,centers)
    neutral_index = int(np.argmin(np.where(relief,np.inf,tint_ratio)))
    bright_cells = (not relief[neutral_index] and tint_ratio[neutral_index]<.15
                    and centers[neutral_index].max()<=max(1,float(grid_color.max()))*2
                    and dists_grid[neutral_index]>max(12,float(grid_color.max())*.3))
    if 'occupancy_distance' in profile:
        occupied = dists_grid > profile['occupancy_distance']
    elif bright_cells:
        exposure=max(.25,min(1.,float(centers.max())/200))
        occupied = np.linalg.norm(centers-centers[neutral_index],axis=1)>45*exposure
    elif dists_grid.min() > 65:
        occupied = np.ones(64, dtype=bool)
    else:
        empty_ref = centers[np.argmin(dists_grid)]
        dists_empty = np.linalg.norm(centers - empty_ref, axis=1)
        occupied = (dists_empty > 45) & (dists_grid > 35)
    if 'occupancy_distance' not in profile:
        occupied |= relief
    board = 0
    for i in range(64):
        if occupied[i]:
            board |= 1 << i
    tray = local.get('tray') or [round(w*.07),round(bottom+cell*.9),round(w*.93),round(min(h*.88,bottom+cell*3.7))]
    x0,y0,x1,y1 = map(int,tray)
    if not (0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h):
        raise ValueError('Область фигур за пределами экрана')
    pitch_prior = float(local.get('tray_cell') or cell*.45)
    pieces = {}
    for slot in range(3):
        a = round(x0+(x1-x0)*slot/3)
        b = round(x0+(x1-x0)*(slot+1)/3)
        crop = im[y0:y1,a:b]
        if not crop.size:
            raise ValueError('Область фигур за пределами экрана')
        bg = np.median(crop.reshape(-1,3),axis=0)
        distances = np.linalg.norm(crop-bg,axis=2)
        exposure=max(.2,min(1.,float(bg.max())/160))
        noise=float(np.median(distances))
        threshold=max(12*exposure,min(24*exposure,noise*1.5+4*exposure))
        # Estimate texture from the background majority of each tray slot.
        # This retains pastel centres even when the entire theme gets darker.
        foreground=distances>local.get('color_distance',threshold)
        mask = foreground & (crop.max(axis=2)>min(110,float(bg.max())*.9))
        # Dark faces may sit below the outline's brightness cutoff. Use them
        # to read the lattice, without adding shadows to its measured box.
        faces = foreground & (crop.max(axis=2)>min(110,float(bg.max())*.5))
        cols = runs(mask.sum(axis=0)>max(5,cell*.065))
        rows = runs(mask.sum(axis=1)>max(5,cell*.065))

        def solid(groups, axis, binary):
            # A couple of stray pixels (anti-aliasing, a shadow, the edge of a
            # neighbouring sprite) used to extend the bounding box.  That made
            # the piece look like it had a phantom empty row/column, so the bot
            # aimed one cell away.  Keep only runs with real cube area.
            kept=[]
            min_area=max(24.0,pitch_prior*pitch_prior*.07)
            for s,e in groups:
                span=e-s
                area=float(binary[:,s:e].sum()) if axis==0 else float(binary[s:e,:].sum())
                if span<pitch_prior*.28 and area<min_area*1.5:
                    continue
                if area<min_area:
                    continue
                kept.append((s,e))
            return kept

        cols=solid(cols,0,mask);rows=solid(rows,1,mask)
        face_cols=solid(runs(faces.sum(axis=0)>max(5,cell*.065)),0,faces)
        face_rows=solid(runs(faces.sum(axis=1)>max(5,cell*.065)),1,faces)
        if face_cols and face_rows:
            outline=(cols[0][0],rows[0][0],cols[-1][1],rows[-1][1]) if cols and rows else None
            filled=(face_cols[0][0],face_rows[0][0],face_cols[-1][1],face_rows[-1][1])
            # A shadow extends the outline a few pixels. A missing dark cube
            # extends it by nearly a cell; recover that row or column only.
            if outline is None or max(abs(a-b) for a,b in zip(outline,filled))>pitch_prior*.4:
                cols,rows=face_cols,face_rows
        if not cols or not rows:
            continue
        minx,maxx = cols[0][0],cols[-1][1]
        miny,maxy = rows[0][0],rows[-1][1]
        # The profile pitch is calibrated; snap the lattice to it and keep the
        # measured span for the actual cell size.
        nc=max(1,round((maxx-minx)/pitch_prior))
        nr=max(1,round((maxy-miny)/pitch_prior))
        if not (1<=nc<=5 and 1<=nr<=5):
            raise ValueError('Необычная фигура: проверьте профиль и скриншот')
        sx,sy = (maxx-minx)/nc,(maxy-miny)/nr
        shape = []
        for r in range(nr):
            for c in range(nc):
                cx,cy = round(minx+(c+.5)*sx),round(miny+(r+.5)*sy)
                d = max(2,round(min(sx,sy)*.18))
                if faces[cy-d:cy+d,cx-d:cx+d].mean()>.6:
                    shape.append((r,c))
        if not shape:
            raise ValueError('Фигура не распознана')
        # Normalize the polyomino.  A well-formed piece always touches all four
        # sides of its own bounding box; trim any empty border introduced by a
        # stray detection instead of planning for a shifted shape.
        rr=[r for r,c in shape];cc=[c for r,c in shape]
        r0,r1=min(rr),max(rr);c0,c1=min(cc),max(cc)
        if (r0,r1,c0,c1)!=(0,nr-1,0,nc-1):
            shape=tuple((r-r0,c-c0) for r,c in shape)
            minx=minx+c0*sx;maxx=minx+(c1-c0+1)*sx
            miny=miny+r0*sy;maxy=miny+(r1-r0+1)*sy
        box = (a+minx,y0+miny,a+maxx,y0+maxy)
        # Touch the center of an occupied square; bounding-box centers may be empty.
        ar,ac = shape[0]
        center = (a+minx+(ac+.5)*sx,y0+miny+(ar+.5)*sy)
        pieces[slot] = Piece(tuple(shape),center,box)
    screen_size = tuple(screen) if screen else (round(w/scale),round(h/scale))
    if scale!=1:
        inv=1/scale
        bounds=tuple(v*inv for v in bounds)
        pieces={slot:Piece(piece.shape,
                           (piece.center[0]*inv,piece.center[1]*inv),
                           tuple(v*inv for v in piece.box))
                for slot,piece in pieces.items()}
    return State(board,pieces,bounds,screen_size)


def annotate(image, state, path):
    out = image.copy()
    draw = ImageDraw.Draw(out)
    scale = image.width/state.size[0] if state.size and state.size[0] else 1.0
    x,y,_,_ = [v*scale for v in state.bounds]
    cell=state.cell*scale
    for r in range(8):
        for c in range(8):
            cx,cy = x+(c+.5)*cell,y+(r+.5)*cell
            color = 'red' if state.board & (1 << (8*r+c)) else 'lime'
            draw.ellipse((cx-6,cy-6,cx+6,cy+6),fill=color)
    for slot,piece in state.pieces.items():
        box=tuple(v*scale for v in piece.box)
        center=(piece.center[0]*scale,piece.center[1]*scale)
        draw.rectangle(box,outline='yellow',width=3)
        draw.text(center,str(slot+1),fill='white')
    out.save(path,format='PNG')
