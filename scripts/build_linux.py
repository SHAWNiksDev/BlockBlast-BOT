"""Build a relocatable Linux x86_64 folder, including native tools and dependencies."""
import json
from importlib import metadata
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile
from package_source import source_files, sha256

ROOT=Path(__file__).resolve().parent.parent
DIST=ROOT/'dist'/'BlockBlast-BOT-linux-x86_64'


def main():
    if sys.platform!='linux' or platform.machine()!='x86_64':
        raise SystemExit('Эта сборка предназначена только для Linux x86_64')
    env=os.environ.copy()
    env['PYTHONPATH']=str(ROOT/'.builddeps')+os.pathsep+str(ROOT)
    # Keep build caches in this project rather than ~/.cache/pyinstaller.
    env['PYINSTALLER_CONFIG_DIR']=str(ROOT/'.build'/'cache')
    subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir',
                    '--name','BlockBlast BOT','--distpath',str(ROOT/'dist'),
                    '--workpath',str(ROOT/'.build'/'pyinstaller'),'--specpath',str(ROOT/'.build'),
                    '--paths',str(ROOT),'--add-data',str(ROOT/'blockblast/translations')+':blockblast/translations','--add-data',str(ROOT/'blockblast/assets')+':blockblast/assets','--exclude-module','tkinter','--exclude-module','matplotlib',
                    '--exclude-module','PySide6.QtWebEngineCore','--exclude-module','PySide6.QtQml',
                    str(ROOT/'desktop_entry.py')],cwd=ROOT,env=env,check=True)
    if DIST.exists():
        shutil.rmtree(DIST)
    (ROOT/'dist'/'BlockBlast BOT').rename(DIST)
    (DIST/'profiles').mkdir()
    shutil.copy2(ROOT/'profiles/default.json',DIST/'profiles/default.json')
    from blockblast.config import DEFAULTS
    (DIST/'settings.json').write_text(json.dumps(DEFAULTS,ensure_ascii=False,indent=2)+'\n')
    shutil.copy2(ROOT/'README.md',DIST/'README.md')
    for name in ('CHANGELOG.md','LICENSE'):
        if (ROOT/name).exists():shutil.copy2(ROOT/name,DIST/name)
    tools=DIST/'tools'
    (tools/'bin').mkdir(parents=True)
    (tools/'lib').mkdir()
    manifest={}
    runtime_files=set()
    # ldd reports the full transitive dependency graph. Preserve SONAME filenames.
    excluded={'libc.so.6','libm.so.6','libpthread.so.0','libdl.so.2','librt.so.1','ld-linux-x86-64.so.2'}
    for name in ('adb','ffmpeg','tesseract'):
        binary=shutil.which(name)
        if not binary:
            raise RuntimeError(f'Не найден {name}')
        runtime_files.add(binary)
        shutil.copy2(binary,tools/'bin'/name)
        output=subprocess.check_output(['ldd',binary],text=True)
        libraries={m[1]:Path(m[2]) for m in re.finditer(r'(\S+) => (/\S+)',output)}
        runtime_files.update(str(path) for path in libraries.values())
        manifest[name]={'source':binary,'libraries':sorted(libraries)}
        for soname,path in libraries.items():
            if soname not in excluded:
                destination=tools/'lib'/soname
                if not destination.exists():
                    shutil.copy2(path.resolve(),destination)
    # Ship the same tested model as source runs and CI. System language packs
    # differ between distributions and can confuse the game's 9 with a 5.
    shutil.copytree(ROOT/'blockblast/assets/tessdata',tools/'tessdata')
    (tools/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    licenses=DIST/'licenses'
    licenses.mkdir()
    license_root=Path('/usr/share/licenses')
    for entry in license_root.iterdir() if license_root.exists() else ():
        if entry.name.lower() in ('ffmpeg','tesseract','android-tools','qt6-base','pyside6','python-pyside6','python','numpy','pillow'):
            shutil.copytree(entry,licenses/entry.name,dirs_exist_ok=True,ignore_dangling_symlinks=True)
    # Preserve license notices for all native runtime packages we copy.
    if shutil.which('pacman'):
        packages=subprocess.run(['pacman','-Qoq',*sorted(set(runtime_files))],capture_output=True,text=True).stdout.splitlines()
        packages=sorted(set(packages)|{'python-pyside6','python-pillow','python-numpy','python','qt6-base','qt6-wayland'})
        for package in packages:
            path=Path('/usr/share/licenses')/package
            if path.exists():
                shutil.copytree(path,licenses/package,dirs_exist_ok=True,ignore_dangling_symlinks=True)
        info=subprocess.run(['pacman','-Qi',*packages],capture_output=True,text=True).stdout
        (licenses/'components.txt').write_text(info)
        spdx=Path('/usr/share/licenses/spdx')
        if spdx.exists():
            for pattern in ('GPL-*.txt','LGPL-*.txt','Apache-*.txt','MIT.txt','BSD-*.txt'):
                for path in spdx.glob(pattern):
                    (licenses/'common').mkdir(exist_ok=True)
                    shutil.copy2(path,licenses/'common'/path.name)
    elif shutil.which('dpkg-query'):
        # Debian/Ubuntu keep notices in /usr/share/doc, not /usr/share/licenses.
        owners=subprocess.run(['dpkg-query','--search',*sorted(runtime_files)],capture_output=True,text=True)
        packages=sorted({line.partition(': ')[0] for line in owners.stdout.splitlines() if ': ' in line})
        for package in packages:
            notice=Path('/usr/share/doc')/package.split(':')[0]/'copyright'
            if notice.exists():
                target=licenses/package/'copyright'
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(notice,target)
        (licenses/'components.txt').write_text('\n'.join(packages)+'\n')
    # Wheels may provide their own notices independently of system packages.
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
    source=DIST/'source'
    for path in source_files():
        target=source/path.relative_to(ROOT)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target)
    glibc=platform.libc_ver()[1]
    (DIST/'PORTABLE.txt').write_text(f'''BlockBlast BOT — Linux x86_64 portable

Запуск: двойной щелчок по BlockBlast BOT или ./"BlockBlast BOT"
Установка Python, Qt, ADB, FFmpeg, Tesseract не требуется.
Настройки, история и логи хранятся рядом с исполняемым файлом.
Папку можно переносить целиком. Не отделяйте файл BlockBlast BOT от _internal и tools.
Скриншоты по умолчанию не сохраняются.

Сборка выполнена с glibc {glibc}. Более старые glibc не поддерживаются этой сборкой.
Нужны Linux x86_64, графическая сессия X11/Wayland и доступ пользователя к USB/ADB.
USB-права/udev принадлежат системе; приложение не изменяет их.
Windows-версия распространяется отдельным ZIP-архивом на странице релиза.

Встроенные компоненты сохраняют свои лицензии. См. licenses и tools/manifest.json.
Исходники приложения и скрипт сборки находятся в папке source.
''')
    archive=ROOT/'dist'/'BlockBlast-BOT-linux-x86_64.tar.gz'
    with tarfile.open(archive,'w:gz',compresslevel=3) as tar:
        tar.add(DIST,arcname=DIST.name)
    digest=sha256(archive)
    archive.with_suffix(archive.suffix+'.sha256').write_text(digest+'  '+archive.name+'\n')
    print(f'Готово: {DIST}\nАрхив: {archive}\nglibc >= {glibc}')

if __name__=='__main__':
    main()
