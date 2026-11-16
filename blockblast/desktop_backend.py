import subprocess
from PySide6.QtCore import QThread,Signal
from .config import ROOT
from .runtime import RunControl,process_options,DeviceLease
from .adb import ADB
from .__main__ import play
from .profile import load_profile
class BotWorker(QThread):
    event=Signal(str,object)
    def __init__(self,serial,settings):
        super().__init__()
        self.serial=serial
        self.settings=dict(settings)
        self.control=RunControl(lambda kind,data:self.event.emit(kind,data),can_resume=True)
    def run(self):
        try:
            adb=ADB(self.serial)
            profile=load_profile(ROOT/self.settings['profile'])
            with DeviceLease(adb.serial):
                play(adb,profile,self.settings,root=ROOT,control=self.control,quiet=True)
        except Exception as exc:
            self.control.emit('status',status='error',reason=str(exc))


class Discovery(QThread):
    result=Signal(object,str)
    def run(self):
        try:
            import re
            result=subprocess.run(['adb','devices','-l'],capture_output=True,timeout=8,**process_options())
            if result.returncode:
                raise RuntimeError(result.stderr.decode(errors='replace'))
            devices=[]
            listing=result.stdout.decode(errors='replace')
            for line in listing.splitlines():
                match=re.match(r'(\S+)\s+device\s*(.*)',line)
                if match:
                    model=re.search(r'model:(\S+)',match[2])
                    devices.append((match[1],model[1].replace('_',' ') if model else 'Android'))
            error=''
            if not devices:
                if re.search(r'^\S+\s+unauthorized\b',listing,re.M):
                    error='Разблокируйте телефон и подтвердите запрос «Разрешить отладку по USB». Затем нажмите «Обновить».'
                elif re.search(r'^\S+\s+offline\b',listing,re.M):
                    error='Телефон не отвечает (offline). Переподключите USB-кабель и нажмите «Обновить».'
                else:error='Подключите телефон кабелем с передачей данных, включите USB-отладку и разрешите подключение.'
            self.result.emit(devices,error)
        except Exception as exc:
            self.result.emit([],str(exc))
