"""Run a packaged GUI and native helpers, then repeat from a Unicode path."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from package_source import ROOT


def verify(bundle,report):
    name='BlockBlast BOT.exe' if sys.platform=='win32' else 'BlockBlast BOT'
    executable=bundle/name
    env=os.environ.copy()
    env['QT_QPA_PLATFORM']='offscreen'
    result=subprocess.run([str(executable),'--packaging-test',str(report)],
                          capture_output=True,timeout=90,env=env)
    data=json.loads(report.read_text(encoding='utf-8')) if report.exists() else {}
    if result.returncode or not data.get('ok') or not data.get('ui') or not report.with_suffix('.png').exists():
        raise RuntimeError(json.dumps(data,ensure_ascii=False)+'\n'+result.stderr.decode(errors='replace')[-4000:])
    print(json.dumps(data,ensure_ascii=False),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    args=parser.parse_args()
    bundle=args.bundle.resolve()
    reports=ROOT/'.build/bundle-reports'
    reports.mkdir(parents=True,exist_ok=True)
    verify(bundle,reports/'normal.json')
    with tempfile.TemporaryDirectory(prefix='blockblast-portable-') as folder:
        relocated=Path(folder)/'Папка с пробелами'/bundle.name
        shutil.copytree(bundle,relocated,symlinks=True)
        verify(relocated,reports/'relocated.json')


if __name__=='__main__':
    main()
