from .runtime import tool_env,process_options
"""Read actual UI numbers with Tesseract via stdin/stdout, no temporary files."""
import io
import re
from pathlib import Path
import shutil
import subprocess
import sys
import numpy as np
from PIL import Image, ImageOps

class ScoreReader:
    def __init__(self, enabled=True):
        self.environment=tool_env() | {'OMP_THREAD_LIMIT':'1'}
        bundled=Path(__file__).parent/'assets'/'tessdata'
        self.model_directory=bundled if (bundled/'afr.traineddata').is_file() else None
        if (bundled/'afr.traineddata').is_file():
            self.environment['TESSDATA_PREFIX']=str(bundled)
        self.available = enabled and shutil.which('tesseract') is not None
        self.language = None
        if self.available:
            try:
                version=subprocess.run(['tesseract','--version'],capture_output=True,timeout=3,**self._process_options())
                major=re.search(r'tesseract\s+v?(\d+)',version.stdout.decode(errors='replace'),re.I)
                if version.returncode or major is None or int(major[1])<5:
                    self.available=False
                    return
                result=subprocess.run(['tesseract','--list-langs'],capture_output=True,timeout=3,**self._process_options())
                langs=result.stdout.decode().splitlines()[1:]
                self.language='afr' if 'afr' in langs else ('eng' if 'eng' in langs else next((x for x in langs if x!='osd'),None))
            except (OSError,subprocess.TimeoutExpired):
                pass
            self.available=self.language is not None

    def _process_options(self):
        options=process_options(self.environment)
        if sys.platform=='win32' and self.model_directory is not None:
            # MinGW builds do not consistently handle non-ASCII model paths.
            # CreateProcess accepts a Unicode cwd; Tesseract then opens a plain
            # relative filename, including after relocation into a user's folder.
            options['cwd']=str(self.model_directory)
            options['env']=self.environment|{'TESSDATA_PREFIX':'.'}
        return options

    def _mask_number(self, crop, mask, modes):
        """OCR one binary mask; returns (value, status)."""
        cols=np.flatnonzero(mask.any(0))
        if not len(cols):
            return None,'none'
        groups=np.split(cols,np.where(np.diff(cols)>1)[0]+1)
        heights={i:int(np.flatnonzero(mask[:,g].any(1)).size) for i,g in enumerate(groups)}
        # A tall crown/edge outline must not become the height reference and
        # filter out shorter digits (the blue palette).  Use wide groups as the
        # reference; glyphs must also be wide enough for their height.
        wide=[heights[i] for i,g in enumerate(groups) if len(g)>=10]
        max_height=max(wide or heights.values(),default=0)
        for i,g in enumerate(groups):
            width=len(g);height=heights[i]
            if width<5 or height<max_height*.65 or width<height*.15:
                mask[:,g]=False
        ys,xs=np.where(mask)
        if not len(xs):
            return None,'failed'
        binary=Image.fromarray(np.where(mask,0,255).astype('uint8'))
        binary=binary.crop((xs.min(),ys.min(),xs.max()+1,ys.max()+1))
        binary=ImageOps.expand(binary,border=20,fill=255)
        if binary.height<45:
            binary=binary.resize((binary.width*2,binary.height*2))
        data=io.BytesIO()
        binary.save(data,format='PNG')
        values=[]
        for mode in modes:
            try:
                result=subprocess.run(['tesseract','stdin','stdout','-l',self.language,'--psm',mode,'-c',
                                       'tessedit_char_whitelist=0123456789'],input=data.getvalue(),
                                      capture_output=True,timeout=3,**self._process_options())
            except (OSError,subprocess.TimeoutExpired):
                return None,'failed'
            value=result.stdout.decode().strip()
            if result.returncode!=0 or not value.isdigit():
                return None,'failed'
            actual_groups=[g for g in groups if mask[:,g].any()]
            if len(value)!=len(actual_groups):
                digits=[]
                for group in actual_groups:
                    part=Image.fromarray(np.where(mask[:,group[0]:group[-1]+1],0,255).astype('uint8'))
                    rows=np.flatnonzero(np.asarray(part).min(1)<128)
                    if not len(rows):return None,'failed'
                    part=ImageOps.expand(part.crop((0,int(rows.min()),part.width,int(rows.max()+1))),20,fill=255)
                    raw=io.BytesIO();part.save(raw,format='PNG')
                    try:
                        single=subprocess.run(['tesseract','stdin','stdout','-l',self.language,'--psm','10','-c','tessedit_char_whitelist=0123456789'],input=raw.getvalue(),capture_output=True,timeout=3,**self._process_options())
                    except (OSError,subprocess.TimeoutExpired):return None,'failed'
                    digit=single.stdout.decode().strip()
                    if len(digit)!=1 or not digit.isdigit():return None,'failed'
                    digits.append(digit)
                value=''.join(digits)
            values.append(int(value))
        return (values[0] if len(set(values))==1 else None),('ok' if len(set(values))==1 else 'ambiguous')

    def number(self, image, box, gold=False, upscale=1.0):
        crop_image=image.crop(tuple(map(round,box)))
        if upscale>1.01:
            # A stream frame is smaller than the calibrated profile.  Upscaling
            # only the small score crop keeps OCR as accurate as a full-size
            # screenshot without resizing the whole video frame.
            crop_image=crop_image.resize((max(1,round(crop_image.width*upscale)),
                                         max(1,round(crop_image.height*upscale))),
                                       Image.Resampling.LANCZOS)
        crop=np.asarray(crop_image.convert('RGB')).astype(int)
        if not crop.size:
            return None
        if gold:
            primary=(crop[:,:,0]>170)&(crop[:,:,1]>85)&(crop[:,:,2]<120)
            modes=('7','8')
        else:
            primary=(crop.min(2)>200)&(crop.max(2)-crop.min(2)<45)
            modes=('7',)
        value,status=self._mask_number(crop.copy(),primary,modes)
        if value is not None and not (gold and len(str(value))==1):
            return value
        if status=='ambiguous':
            # The expected mask found glyphs but the two OCR modes disagreed.
            # Do not hide that with another mask.
            return None
        # Newer game palettes (the blue one) draw the score in dark blue.  The
        # white/gold masks then see nothing (or only the crown), so try dark
        # glyphs as a fallback.  Cyan diamonds and the gold crown are excluded
        # because their brightest channel is above 210.
        dark=crop.max(axis=2)<210
        alt,saw_alt=self._mask_number(crop.copy(),dark,('7','8') if gold else ('7',))
        if alt is not None and (value is None or len(str(alt))>=len(str(value))):
            return alt
        # Milestone themes also use lime, cyan and magenta text. Separate
        # bright channel combinations from the background, then require both
        # OCR modes to agree. A single coloured diamond is not a number row.
        candidates=[]
        for channels in ((0,),(1,),(2,),(0,1),(0,2),(1,2)):
            selected=crop[:,:,channels].min(axis=2)
            others=tuple(i for i in range(3) if i not in channels)
            rest=crop[:,:,others].max(axis=2)
            mask=(selected>180)&(selected-rest>30)
            if not .002<float(mask.mean())<.45:
                continue
            cols=np.flatnonzero(mask.any(0))
            groups=np.split(cols,np.where(np.diff(cols)>1)[0]+1)
            if len(groups)<2:
                continue
            candidates.append((len(groups),mask))
        for _,mask in sorted(candidates,key=lambda item:item[0],reverse=True):
            colored,status=self._mask_number(crop.copy(),mask,('7','8'))
            if colored is not None:
                return colored
        return value

    def read(self, image, bounds, profile):
        if not self.available:
            return None,None
        w,h=image.size
        screen=profile.get('screen_size')
        scale=w/float(screen[0]) if screen and screen[0] else float(image.info.get('capture_scale',1.0) or 1.0)
        top=bounds[1]*scale
        upscale=1.0/scale if scale<.99 else 1.0
        if profile.get('score_box'):
            score=[v*scale for v in profile['score_box']]
        else:
            score=[w*.12,top*.50,w*.88,top*.88]
        if profile.get('record_box'):
            best=[v*scale for v in profile['record_box']]
        else:
            best=[w*.13,top*.27,w*.55,top*.44]
        return self.number(image,score,upscale=upscale),self.number(image,best,True,upscale=upscale)
