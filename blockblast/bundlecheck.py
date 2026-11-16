"""Offline validation of a frozen app, including native helpers and Qt rendering."""
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont
from .config import ROOT
from .runtime import DeviceLease, process_options
from .score import ScoreReader
from .storage import write_json


def check_components():
    report={'root':str(ROOT),'tools':{}}
    from .calibration import region_profile
    region_profile((400,600),(10,10,210,210),(10,250,390,350),20)
    report['phone_setup']=True
    from PySide6.QtGui import QFont,QRawFont
    font=QRawFont.fromFont(QFont('DejaVu Sans'))
    if not font.isValid() or not all(font.supportsCharacter(ord(char)) for char in 'BlockBlast 0123456789 Привет ё Українська їєґ —'):
        raise RuntimeError('Interface font does not support the application languages')
    report['fonts']=True
    for name,flag in (('adb','version'),('ffmpeg','-version'),('tesseract','--version')):
        binary=shutil.which(name)
        if binary is None:
            raise RuntimeError(name+' is missing')
        Path(binary).resolve().relative_to((ROOT/'tools/bin').resolve())
        result=subprocess.run([binary,flag],capture_output=True,timeout=15,**process_options())
        if result.returncode:
            raise RuntimeError(name+': '+result.stderr.decode(errors='replace'))
        report['tools'][name]=result.stdout.decode(errors='replace').splitlines()[0]
    reader=ScoreReader()
    image=Image.new('RGB',(420,120),'white')
    font=ImageFont.truetype(str(Path(__file__).parent/'assets/fonts/DejaVuSans.ttf'),72)
    ImageDraw.Draw(image).text((16,8),'12345',font=font,fill='black')
    payload=io.BytesIO();image.save(payload,format='PNG')
    result=subprocess.run(['tesseract','stdin','stdout','-l',reader.language,'--psm','7',
                           '-c','tessedit_char_whitelist=0123456789'],input=payload.getvalue(),
                          capture_output=True,timeout=15,**reader._process_options())
    if result.returncode or result.stdout.strip()!=b'12345':
        raise RuntimeError('Bundled OCR failed on a generated sample')
    report['ocr']='12345'
    data=io.BytesIO()
    Image.new('RGB',(12,12),(19,92,141)).save(data,format='PNG')
    decoded=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','image2pipe',
                            '-i','pipe:0','-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],
                           input=data.getvalue(),capture_output=True,timeout=15,**process_options())
    if decoded.returncode or decoded.stdout!=bytes((19,92,141))*144:
        raise RuntimeError('FFmpeg binary pipe roundtrip failed: '+decoded.stderr.decode(errors='replace'))
    report['video_pipe']=True
    with DeviceLease('bundle-self-test'):
        try:
            second=DeviceLease('bundle-self-test')
        except RuntimeError:
            report['device_lease']=True
        else:
            second.close()
            raise RuntimeError('The same device can be controlled twice')
    with DeviceLease('bundle-self-test'):
        pass
    with tempfile.TemporaryDirectory(prefix='blockblast-данные-') as directory:
        path=Path(directory)/'настройки.json'
        write_json(path,{'язык':'Українська'})
        if json.loads(path.read_text(encoding='utf-8'))!={'язык':'Українська'}:
            raise RuntimeError('UTF-8 settings roundtrip failed')
    report['utf8_settings']=True
    report['ok']=True
    return report


def run(app, window_class, path):
    """Return a process exit code and write a report even in a windowed EXE."""
    from PySide6.QtCore import QTimer
    try:
        report=check_components()
    except Exception as exc:
        write_json(path,{'ok':False,'error':str(exc)})
        return 1
    window=window_class(discover=False)
    window.show()
    def capture():
        try:
            if not window.grab().save(str(path.with_suffix('.png'))):
                raise RuntimeError('Qt window capture failed')
            report['ui']=True
            write_json(path,report)
            window.close()
            app.exit(0)
        except Exception as exc:
            write_json(path,report|{'ok':False,'error':str(exc)})
            window.close()
            app.exit(1)
    QTimer.singleShot(700,capture)
    return app.exec()
