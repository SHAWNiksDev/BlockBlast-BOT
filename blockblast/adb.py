import io
import re
import subprocess
from PIL import Image
from .runtime import process_options

class AppNotReady(RuntimeError):
    pass

def parse_screen_status(data, package="com.block.juggle"):
    focus=re.search(r"mCurrentFocus=(.*)",data)
    focused=focus.group(1).strip() if focus else ""
    if re.search(r"(?:screenState=SCREEN_STATE_OFF|interactiveState=INTERACTIVE_STATE_ASLEEP|mShowingLockscreen=true|mKeyguardShowing=true)",data):
        return False,"Экран заблокирован или выключен"
    if any(name in focused for name in ("NotificationShade","StatusBar","QuickSettings")):
        return False,"Открыта шторка уведомлений"
    if package+"/" not in focused:
        return False,"Ожидаю возвращения в Block Blast"
    for section in re.split(r"(?=  Window #)",data):
        if re.match(r"  Window #\d+.*(?:NotificationShade|StatusBar|QuickSettings)",section) and re.search(r"\bisVisible=true",section):
            return False,"Открыта шторка уведомлений"
    return True,"Block Blast на экране"


class ADB:
    def __init__(self, serial=None, executable='adb'):
        self.executable = executable
        listing = self.run('devices').decode()
        devices = re.findall(r'^([^\s]+)\s+device$', listing, re.M)
        if serial is None:
            if len(devices) != 1:
                raise RuntimeError(f'Нужен ровно один доступный телефон, найдено {len(devices)}. Используйте --serial.')
            serial = devices[0]
        if serial not in devices:
            raise RuntimeError(f'Устройство {serial} не доступно. Проверьте adb devices и разрешение USB-отладки.')
        self.serial = serial

    def run(self, *args):
        cmd = [self.executable]
        if getattr(self, 'serial', None):
            cmd += ['-s', self.serial]
        try:
            result = subprocess.run(cmd+list(map(str,args)), capture_output=True, timeout=8, **process_options())
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError('ADB не ответил за 8 секунд') from exc
        except FileNotFoundError as exc:
            raise RuntimeError('ADB не найден. Установите Android platform-tools.') from exc
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors='replace').strip())
        return result.stdout

    def screenshot(self):
        return Image.open(io.BytesIO(self.run('exec-out','screencap','-p'))).convert('RGB')

    def screen_status(self, package='com.block.juggle'):
        data=self.run('shell','dumpsys','window').decode(errors='replace')
        return parse_screen_status(data,package)

    def check_foreground(self, package):
        ready,reason=self.screen_status(package)
        if not ready:
            raise AppNotReady(reason)

    def drag(self, start, end, duration=450):
        self.run('shell','input','touchscreen','swipe',round(start[0]),round(start[1]),round(end[0]),round(end[1]),duration)

    def drag_precise(self, start, end, grab=.08, release=.08):
        # A pause after DOWN lets Cocos finish enlarging the grabbed piece.
        # Smooth interpolation points prevent touch drop/teleportation glitches in game engine.
        sx,sy,ex,ey = map(round,(*start,*end))
        grab,release=max(.03,float(grab)),max(.04,float(release))
        mx1,my1 = round(sx+(ex-sx)*0.4), round(sy+(ey-sy)*0.4)
        mx2,my2 = round(sx+(ex-sx)*0.8), round(sy+(ey-sy)*0.8)
        released=False
        try:
            self.run('shell', f'input touchscreen motionevent DOWN {sx} {sy}; sleep {grab:.3f}; input touchscreen motionevent MOVE {mx1} {my1}; input touchscreen motionevent MOVE {mx2} {my2}; input touchscreen motionevent MOVE {ex} {ey}; sleep {release:.3f}; input touchscreen motionevent UP {ex} {ey}')
            released=True
        finally:
            if not released:
                self.run('shell','input','touchscreen','motionevent','UP',ex,ey)
