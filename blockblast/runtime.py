"""Cooperative stop/pause and bounded, UI-independent runtime notifications."""
from collections import deque
import os
from pathlib import Path
import sys
import threading
import subprocess

class BotStopped(Exception):
    pass

class RunFinished(Exception):
    """A controlled end with a user-facing reason, preserving the final report."""


class RunControl:
    def __init__(self, callback=None, can_resume=False):
        self.can_resume=can_resume
        self.stop_event=threading.Event()
        self.pause_event=threading.Event()
        self.callback=callback
        self.frame=None
        self.video=None
        self.status='idle'
        self.reason=''
        self.stats={}
        self.board=None
        self.pieces={}
        self.target=None
        self.events=deque(maxlen=500)
        self.pause_total=0.0
        self.resume_epoch=0

    def check(self):
        if self.stop_event.is_set():
            raise BotStopped()

    def wait(self, seconds):
        if self.stop_event.wait(max(0,seconds)):
            raise BotStopped()

    def emit(self, kind, **data):
        self.events.append((kind,data))
        if kind=='status':
            self.status=data['status']
            self.reason=data.get('reason','')
        elif kind=='stats':
            self.stats=data
        elif kind=='state':
            self.board=data['board']
            self.pieces=data.get('pieces',{})
        elif kind=='target':
            self.target=data.get('mask')
        if self.callback:
            self.callback(kind,data)

    def preview(self):
        video=self.video
        if video and video.frame is not None:
            return video.frame
        return self.frame


def configure_portable():
    if getattr(sys,'frozen',False):
        root=Path(sys.executable).resolve().parent
        tools=root/'tools'
        if tools.exists():
            paths=[tools/'bin']
            if sys.platform=='win32':
                paths.extend(tools/'bin'/name for name in ('adb','ffmpeg','tesseract'))
            os.environ['PATH']=os.pathsep.join(map(str,paths))+os.pathsep+os.environ.get('PATH','')
            os.environ['TESSDATA_PREFIX']=str(tools/'tessdata')


def tool_env():
    env=os.environ.copy()
    if getattr(sys,'frozen',False) and sys.platform.startswith('linux'):
        root=Path(sys.executable).resolve().parent
        env['LD_LIBRARY_PATH']=str(root/'tools'/'lib')
    return env


def process_options(env=None):
    """Keep native helpers quiet in a Windows desktop build."""
    options={'env':tool_env() if env is None else env}
    if sys.platform=='win32':
        options['creationflags']=subprocess.CREATE_NO_WINDOW
    return options


class DeviceLease:
    """One controller per phone: a Windows named object or Linux abstract socket."""
    def __init__(self,serial):
        import socket,hashlib,errno
        if sys.platform=='win32':
            import ctypes
            from ctypes import wintypes
            kernel=ctypes.WinDLL('kernel32',use_last_error=True)
            kernel.CreateMutexW.argtypes=(ctypes.c_void_p,wintypes.BOOL,wintypes.LPCWSTR)
            kernel.CreateMutexW.restype=wintypes.HANDLE
            kernel.CloseHandle.argtypes=(wintypes.HANDLE,)
            kernel.CloseHandle.restype=wintypes.BOOL
            name='Local\\BlockBlastBOT-'+hashlib.sha256(serial.encode()).hexdigest()
            ctypes.set_last_error(0)
            self.handle=kernel.CreateMutexW(None,False,name)
            error=ctypes.get_last_error()
            if not self.handle:
                raise ctypes.WinError(error)
            self._close_handle=kernel.CloseHandle
            if error==183:  # ERROR_ALREADY_EXISTS; close only our extra handle.
                self.close()
                raise RuntimeError('Этот телефон уже управляется другим экземпляром BlockBlast BOT. Сначала остановите его.')
            return
        self.socket=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        name='\0BlockBlastBOT-'+str(os.getuid())+'-'+hashlib.sha256(serial.encode()).hexdigest()[:24]
        try:
            self.socket.bind(name)
        except OSError as exc:
            self.socket.close()
            if exc.errno==errno.EADDRINUSE:
                raise RuntimeError('Этот телефон уже управляется другим экземпляром BlockBlast BOT. Сначала остановите его.') from exc
            raise
    def __enter__(self):return self
    def close(self):
        if getattr(self,'handle',None):
            self._close_handle(self.handle)
            self.handle=None
        elif hasattr(self,'socket'):
            self.socket.close()
    def __exit__(self,*args):self.close()
