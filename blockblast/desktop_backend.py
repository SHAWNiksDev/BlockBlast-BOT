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
            for line in result.stdout.decode().splitlines():
                match=re.match(r'(\S+)\s+device\s*(.*)',line)
                if match:
                    model=re.search(r'model:(\S+)',match[2])
                    devices.append((match[1],model[1].replace('_',' ') if model else 'Android'))
            self.result.emit(devices,'' if devices else 'Подключите телефон и разрешите USB-отладку')
        except Exception as exc:
            self.result.emit([],str(exc))
