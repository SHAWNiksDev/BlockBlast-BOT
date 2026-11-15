"""Live-device regression: real GUI worker, notification shade, Home and manual pause."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json
from pathlib import Path
import sys
import time
from datetime import datetime
import shutil
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from blockblast.desktop import Window
from blockblast.adb import ADB
from blockblast.config import load,ROOT

adb=ADB()
ready,why=adb.screen_status()
if not ready:
    raise SystemExit(why)
settings=load()|{'max_moves':9,'score_every':3,'show_board':False,'save_screenshots':False,'console_logs':True,'capture':'stream'}
qa_root=ROOT/'artifacts'/('qa-desktop-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
qa_root.mkdir(parents=True)
shutil.copytree(ROOT/'profiles',qa_root/'profiles')
app=QApplication([])
patcher=patch('blockblast.desktop.load',return_value=settings)
patcher.start()
root_patcher=patch('blockblast.desktop.ROOT',qa_root);root_patcher.start()
backend_patcher=patch('blockblast.desktop_backend.ROOT',qa_root);backend_patcher.start()
window=Window(discover=False)
window.discovered([(adb.serial,'Android · QA')],'')
window.show()
phase=0
since=time.monotonic()
started=since
paused_moves=None
checks=[]
error=None


def advance():
    global phase,since,paused_moves,error
    try:
        worker=window.worker
        if not worker:
            return
        c=worker.control
        moves=c.stats.get('moves',0)
        now=time.monotonic()
        if now-started>150:
            raise RuntimeError('QA timeout')
        if phase==0 and moves>=2:
            adb.run('shell','cmd','statusbar','expand-notifications')
            phase=1;since=now
            print('opened shade',flush=True)
        elif phase==1 and c.status=='paused':
            paused_moves=moves;since=now;phase=2
            print('shade pause',moves,c.reason,flush=True)
        elif phase==2 and now-since>(6 if '--long-pause' in sys.argv else 3):
            assert moves==paused_moves,'Moved under notification shade'
            checks.append('shade_paused_no_moves')
            adb.run('shell','cmd','statusbar','collapse')
            phase=3;since=now
        elif phase==3 and moves>=4:
            checks.append('shade_resumed')
            adb.run('shell','input','keyevent','3')
            phase=4;since=now
            print('went Home',flush=True)
        elif phase==4 and c.status=='paused':
            paused_moves=moves;since=now;phase=5
            print('Home pause',moves,c.reason,flush=True)
        elif phase==5 and now-since>(17 if '--long-pause' in sys.argv else 3):
            assert moves==paused_moves,'Moved while on Home'
            checks.append('home_paused_no_moves')
            activity=adb.run('shell','cmd','package','resolve-activity','--brief','com.block.juggle').decode().strip().splitlines()[-1]
            adb.run('shell','am','start','-n',activity)
            phase=6;since=now
        elif phase==6 and moves>=6:
            checks.append('home_resumed')
            window.toggle_pause()
            phase=7;since=now
        elif phase==7 and c.status=='paused':
            paused_moves=moves;since=now;phase=8
        elif phase==8 and now-since>1:
            assert moves==paused_moves,'Moved while manually paused'
            checks.append('manual_paused_no_moves')
            window.toggle_pause()
            phase=9
        elif phase==9 and moves>=7:
            checks.append('manual_resumed')
            window.grab().save(str(qa_root/'desktop-live.png'))
            phase=10
        if not worker.isRunning():
            assert c.stats.get('moves')==9,repr(c.stats)
            assert phase>=10,f'Incomplete phases: {phase}'
            checks.append('finished_9_moves')
            report={'checks':checks,'stats':c.stats,'status':c.status}
            (qa_root/'desktop-qa.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
            print(json.dumps(report,ensure_ascii=False),flush=True)
            timer.stop();window.close();app.quit()
    except Exception as exc:
        error=exc
        print('QA ERROR',repr(exc),flush=True)
        timer.stop()
        window.stop_bot()
        QTimer.singleShot(6000,app.quit)

window.start_bot()
timer=QTimer()
timer.timeout.connect(advance)
timer.start(150)
app.exec()
if window.worker and window.worker.isRunning():
    window.worker.control.stop_event.set()
    window.worker.wait(15000)
patcher.stop()
root_patcher.stop();backend_patcher.stop()
if error:
    raise error
