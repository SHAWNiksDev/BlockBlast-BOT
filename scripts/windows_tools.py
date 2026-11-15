"""Download and stage the pinned native tools for a Windows portable build."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import urllib.request
import zipfile

from package_source import ROOT, sha256

PACKAGES = {
    'adb': {
        'url': 'https://dl.google.com/android/repository/platform-tools_r37.0.1-win.zip',
        'sha256': '45f4d63113e895ebde0c90f194099a4676b6ac653bd28d54314a9e022bbc1a99',
        'archive': 'platform-tools.zip',
    },
    'tesseract': {
        'url': 'https://github.com/tesseract-ocr/tesseract/releases/download/5.5.3/tesseract-ocr-w64-setup-5.5.3.20260724.exe',
        'sha256': 'bee9e3434bd94fd65387d9be28cd467a41f61b1275383b55b0f59a1331270ae4',
        'archive': 'tesseract.exe',
    },
    'ffmpeg': {
        'url': 'https://github.com/GyanD/codexffmpeg/releases/download/9.0.2/ffmpeg-9.0.2-essentials_build.7z',
        'sha256': '4705843ccaaf54257c16ad90f3e952ece33c17df964ecf7bfdbb0f49c7171077',
        'archive': 'ffmpeg.7z',
    },
}


def fetch(package, downloads):
    target=downloads/package['archive']
    if target.exists() and sha256(target)==package['sha256']:
        return target
    temporary=target.with_suffix(target.suffix+'.part')
    try:
        request=urllib.request.Request(package['url'],headers={'User-Agent':'BlockBlast-BOT-build'})
        with urllib.request.urlopen(request,timeout=90) as response, temporary.open('wb') as file:
            shutil.copyfileobj(response,file)
        if sha256(temporary)!=package['sha256']:
            raise RuntimeError('Checksum mismatch: '+package['url'])
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def unpack(archive, target):
    if archive.suffix=='.zip':
        with zipfile.ZipFile(archive) as file:
            file.extractall(target)
        return
    seven=shutil.which('7z')
    if not seven:
        raise RuntimeError('7-Zip is required to prepare Windows tools')
    result=subprocess.run([seven,'x','-y',str(archive),'-o'+str(target)],capture_output=True,text=True)
    # The signed NSIS installer has a harmless PE-header warning in 7-Zip.
    if result.returncode not in (0,1):
        raise RuntimeError(result.stdout[-2000:]+result.stderr[-2000:])


def prepare(output):
    downloads=ROOT/'.build'/'windows-downloads'
    downloads.mkdir(parents=True,exist_ok=True)
    if output.exists():
        shutil.rmtree(output)
    binaries=output/'bin'
    binaries.mkdir(parents=True)
    licenses=output/'licenses'
    for name,package in PACKAGES.items():
        archive=fetch(package,downloads)
        extracted=downloads/(name+'-extracted')
        if extracted.exists():shutil.rmtree(extracted)
        unpack(archive,extracted)
        executable=next(extracted.rglob(name+'.exe'))
        destination=binaries/name
        destination.mkdir()
        shutil.copy2(executable,destination/executable.name)
        for path in executable.parent.iterdir():
            if path.suffix.lower()=='.dll':shutil.copy2(path,destination/path.name)
        notice=licenses/name
        notice.mkdir(parents=True)
        for path in executable.parent.rglob('*'):
            relative=path.relative_to(executable.parent)
            if path.is_file() and (path.suffix.lower() in ('.txt','.md','.html')
                                   or path.name.upper() in ('LICENSE','COPYING','NOTICE','AUTHORS')):
                target=notice/relative
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(path,target)
        # FFmpeg's notices sit above bin/.
        if name=='ffmpeg':
            for path in executable.parent.parent.iterdir():
                if path.is_file():shutil.copy2(path,notice/path.name)
    shutil.copytree(ROOT/'blockblast/assets/tessdata',output/'tessdata')
    (output/'manifest.json').write_text(json.dumps(PACKAGES,indent=2)+'\n',encoding='utf-8')
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'.build/windows-tools')
    print(prepare(parser.parse_args().output))
