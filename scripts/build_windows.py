"""Build a Windows x86_64 portable ZIP with the same tools as the Linux app."""
import argparse
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from package_source import ROOT, sha256, source_files
from windows_tools import prepare
from PIL import Image,ImageDraw

DIST=ROOT/'dist'/'BlockBlast-BOT-windows-x86_64'


def main():
    if sys.platform!='win32' or platform.machine().lower() not in ('amd64','x86_64'):
        raise SystemExit('Build this package on 64-bit Windows')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tools',type=Path,default=ROOT/'.build/windows-tools')
    args=parser.parse_args()
    prepared=args.tools.resolve()
    if not all((prepared/'bin'/name/(name+'.exe')).is_file() for name in ('adb','ffmpeg','tesseract')):
        prepare(prepared)
    env=os.environ.copy()
    env['PYINSTALLER_CONFIG_DIR']=str(ROOT/'.build/cache-windows')
    icon=Image.new('RGBA',(256,256))
    draw=ImageDraw.Draw(icon)
    for x,y in ((36,36),(140,36),(36,140)):
        draw.rounded_rectangle((x,y,x+80,y+80),radius=16,fill='#7C8CFF')
    icon_path=ROOT/'.build/app.ico'
    icon_path.parent.mkdir(exist_ok=True)
    icon.save(icon_path,sizes=[(16,16),(32,32),(48,48),(128,128),(256,256)])
    subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--windowed',
                    '--name','BlockBlast BOT','--icon',str(icon_path),'--distpath',str(ROOT/'dist'),
                    '--workpath',str(ROOT/'.build/pyinstaller-windows'),'--specpath',str(ROOT/'.build'),
                    '--paths',str(ROOT),
                    '--add-data',str(ROOT/'blockblast/translations')+os.pathsep+'blockblast/translations',
                    '--add-data',str(ROOT/'blockblast/assets')+os.pathsep+'blockblast/assets',
                    '--exclude-module','tkinter','--exclude-module','matplotlib',
                    '--exclude-module','PySide6.QtWebEngineCore','--exclude-module','PySide6.QtQml',
                    str(ROOT/'desktop_entry.py')],cwd=ROOT,env=env,check=True)
    if DIST.exists():shutil.rmtree(DIST)
    (ROOT/'dist'/'BlockBlast BOT').rename(DIST)
    shutil.copytree(prepared,DIST/'tools')
    (DIST/'profiles').mkdir()
    shutil.copy2(ROOT/'profiles/default.json',DIST/'profiles/default.json')
    from blockblast.config import DEFAULTS
    (DIST/'settings.json').write_text(json.dumps(DEFAULTS,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for name in ('README.md','CHANGELOG.md','LICENSE'):
        if (ROOT/name).exists():shutil.copy2(ROOT/name,DIST/name)
    licenses=DIST/'licenses'
    licenses.mkdir()
    for name in ('PySide6','PySide6_Essentials','PySide6_Addons','shiboken6','numpy','Pillow'):
        try:distribution=metadata.distribution(name)
        except metadata.PackageNotFoundError:continue
        for entry in distribution.files or ():
            if any(part.lower() in ('licenses','license','copying') for part in entry.parts) or entry.name.lower().startswith(('license','copying','copyright')):
                path=Path(distribution.locate_file(entry))
                if path.is_file():
                    relative=Path(*[part for part in entry.parts if part not in ('..','.','/')])
                    target=licenses/name/relative
                    target.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copy2(path,target)
    for path in source_files():
        target=DIST/'source'/path.relative_to(ROOT)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target)
    (DIST/'PORTABLE.txt').write_text('''BlockBlast BOT — Windows x86_64 portable

Распакуйте ZIP целиком и запустите BlockBlast BOT.exe.
Не отделяйте EXE от папок _internal, tools и profiles.
Python, Qt, ADB, FFmpeg и Tesseract устанавливать отдельно не нужно.
Настройки и история сохраняются рядом с программой: выбирайте папку с правом записи.

Нужны Windows 10/11 x64, USB-отладка на Android и разрешение подключения на телефоне.
Для некоторых телефонов нужен USB-драйвер производителя. Программа не устанавливает драйверы.
Личного профиля телефона нет. Проверьте распознавание и откалибруйте жесты перед запуском.

Лицензии Python-компонентов: licenses; нативных инструментов: tools/licenses.
Точные версии, источники и контрольные суммы инструментов: tools/manifest.json.
Исходники и скрипты сборки включены в source.
''',encoding='utf-8')
    archive=Path(shutil.make_archive(str(ROOT/'dist'/'BlockBlast-BOT-windows-x86_64'),
                                   'zip',root_dir=DIST.parent,base_dir=DIST.name))
    archive.with_name(archive.name+'.sha256').write_text(sha256(archive)+'  '+archive.name+'\n',encoding='utf-8')
    print(archive)


if __name__=='__main__':
    main()
