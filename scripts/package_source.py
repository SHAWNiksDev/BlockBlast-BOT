"""Prepare a source release from an explicit list; omit local state and binaries."""
import hashlib
from pathlib import Path
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from blockblast import __version__

SOURCE_PATHS = ('blockblast', 'profiles/default.json', 'scripts', 'tests', 'docs', 'audit', '.github',
                'README.md', 'CHANGELOG.md', '.gitignore', 'desktop_entry.py',
                'run.sh', 'run-gui.sh', 'run.cmd', 'run-gui.cmd', 'requirements.txt',
                'requirements-desktop.txt', 'requirements-build.txt')


def source_files():
    for name in SOURCE_PATHS:
        path = ROOT/name
        for item in sorted(path.rglob('*')) if path.is_dir() else (path,):
            if (item.is_file() and not item.is_symlink()
                    and '__pycache__' not in item.parts and item.suffix != '.pyc'
                    and not item.relative_to(ROOT).as_posix().startswith(('tests/fixtures/','docs/images/'))):
                yield item
    license = ROOT/'LICENSE'
    if license.is_file():
        yield license


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as file:
        for chunk in iter(lambda: file.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    output = ROOT/'dist'
    output.mkdir(exist_ok=True)
    name = f'BlockBlast-BOT-{__version__}-source'
    archive = output/(name+'.tar.gz')
    with tarfile.open(archive, 'w:gz') as tar:
        for path in source_files():
            tar.add(path, arcname=str(Path(name)/path.relative_to(ROOT)), recursive=False)
    archive.with_name(archive.name+'.sha256').write_text(sha256(archive)+'  '+archive.name+'\n')
    print(archive)


if __name__ == '__main__':
    main()
