"""Latest-frame H.264 capture. No recording files, no frame backlog."""
from .runtime import process_options
from collections import deque
import shutil
import subprocess
import threading
import time
from PIL import Image


class VideoCapture:
    """Decode the phone stream at its native size and publish only the latest frame.

    The decoder output is intentionally *not* upscaled to the phone resolution.
    Vision scales profile geometry instead; upscaling every frame was both slow
    (about 0.1 s per 540x1200 -> 1080x2400 frame) and made the caller work with
    a frame backlog.  ``frame.info['capture_scale']`` tells the recognizer the
    ratio between stream pixels and profile pixels.
    """

    def __init__(self, adb, size, width=540, fps=12, bitrate=4000000, segment_seconds=120):
        if not shutil.which('ffmpeg'):
            raise RuntimeError('Для видеопотока нужен ffmpeg; доступен режим capture=screenshot.')
        self.adb=adb
        self.size=(max(2,int(size[0])),max(2,int(size[1])))
        self.width=max(2,min(int(width),self.size[0])//2*2)
        self.height=max(2,round(self.size[1]*self.width/self.size[0]/2)*2)
        self.frame_scale=self.width/self.size[0]
        self.fps=max(1,int(fps))
        self.bitrate=int(bitrate)
        self.segment_seconds=max(10,int(segment_seconds))
        self.condition=threading.Condition()
        self.lock=threading.Lock()
        self.frame=None
        self.sequence=0
        self.delivered=0
        self.closed=False
        self.error=None
        self.processes=[]
        self.remote_pid=None
        self.messages=deque(maxlen=12)
        self.published_at=0.0
        self.thread=threading.Thread(target=self._run,name='blockblast-video',daemon=True)
        self.thread.start()

    def _stderr(self, pipe, remote=False):
        try:
            for raw in pipe:
                line=raw.decode(errors='replace').strip()
                if remote and line.startswith('BLOCKBLAST_STREAM_PID:'):
                    value=line.split(':',1)[1]
                    if value.isdigit():
                        self.remote_pid=int(value)
                        if self.closed:
                            self._kill_remote(self.remote_pid)
                elif self.closed:
                    break
                elif line:
                    self.messages.append(line)
        except (OSError,ValueError):
            pass
        finally:
            try:
                pipe.close()
            except OSError:
                pass

    @staticmethod
    def _read_exact(pipe, count):
        chunks=bytearray()
        while len(chunks)<count:
            part=pipe.read(count-len(chunks))
            if not part:
                break
            chunks.extend(part)
        return bytes(chunks)

    def _run(self):
        try:
            while not self.closed:
                # A short finite recording also bounds a recorder if the host crashes.
                # The thread restarts the stream at EOF for arbitrarily long games.
                command=(f'echo BLOCKBLAST_STREAM_PID:$$ >&2; exec screenrecord --output-format=h264 '
                         f'--size {self.width}x{self.height} --bit-rate {self.bitrate} --time-limit {self.segment_seconds} -')
                # Register each process under the close lock before creating the next.
                # A decoder launch failure must still close the already running ADB.
                with self.lock:
                    if self.closed:
                        return
                    self.remote_pid=None
                    source=subprocess.Popen([self.adb.executable,'-s',self.adb.serial,'shell','-T',command],
                                            stdout=subprocess.PIPE,stderr=subprocess.PIPE,**process_options())
                    self.processes=[source]
                    threading.Thread(target=self._stderr,args=(source.stderr,True),daemon=True).start()
                    decoder=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-threads','1',
                                              '-flags','low_delay','-probesize','32','-analyzeduration','0',
                                              '-f','h264','-i','pipe:0','-vf',f'fps={self.fps}',
                                              '-threads','1','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],
                                             stdin=source.stdout,stdout=subprocess.PIPE,stderr=subprocess.PIPE,**process_options())
                    self.processes.append(decoder)
                    source.stdout.close()
                    threading.Thread(target=self._stderr,args=(decoder.stderr,False),daemon=True).start()
                before=self.sequence
                frame_bytes=self.width*self.height*3
                try:
                    while not self.closed:
                        data=self._read_exact(decoder.stdout,frame_bytes)
                        if len(data)!=frame_bytes:
                            break
                        now=time.monotonic()
                        if now-self.published_at<1/self.fps:
                            continue
                        self.published_at=now
                        frame=Image.frombytes('RGB',(self.width,self.height),data)
                        frame.info['capture_scale']=self.frame_scale
                        with self.condition:
                            self.frame=frame
                            self.sequence+=1
                            self.condition.notify_all()
                finally:
                    self._stop_processes()
                if self.sequence==before and not self.closed:
                    raise RuntimeError('Видеопоток не выдаёт кадры: '+'; '.join(self.messages))
                # A segment ends every ``segment_seconds``; restart with no frame loss
                # beyond the normal screenrecord startup.
        except Exception as exc:
            self._stop_processes()
            with self.condition:
                if not self.closed:
                    self.error=exc
                self.condition.notify_all()

    def _stop_processes(self, force=False):
        with self.lock:
            processes=list(self.processes)
            self.processes=[]
        for proc in reversed(processes):
            if proc.poll() is None:
                try:
                    proc.kill() if force else proc.terminate()
                except OSError:
                    pass
        for proc in processes:
            try:
                proc.wait(timeout=1.5 if force else 2)
            except subprocess.TimeoutExpired:
                try:proc.kill()
                except OSError:pass
                try:proc.wait(timeout=1)
                except subprocess.TimeoutExpired:pass
            for pipe in (proc.stdout,proc.stderr):
                if pipe:
                    try:pipe.close()
                    except OSError:pass

    def _kill_remote(self,pid):
        """Never let a blocking adb call prolong close()."""
        try:
            subprocess.run([self.adb.executable,'-s',self.adb.serial,'shell','kill','-2',str(pid)],
                           capture_output=True,timeout=2,**process_options())
        except (OSError,subprocess.TimeoutExpired):
            pass

    def get(self, timeout=5):
        deadline=time.monotonic()+timeout
        with self.condition:
            while self.sequence<=self.delivered and not self.error and not self.closed:
                remaining=deadline-time.monotonic()
                if remaining<=0:
                    raise RuntimeError('Нет новых кадров видеопотока; проверьте ADB.')
                self.condition.wait(remaining)
            if self.error:
                raise RuntimeError(str(self.error)) from self.error
            if self.closed:
                raise RuntimeError('Видеопоток закрыт')
            self.delivered=self.sequence
            return self.frame.copy()

    def latest(self, min_sequence=0, timeout=1.5):
        """Return the newest frame newer than ``min_sequence``.

        Used by gesture correction.  A short timeout keeps a stalled stream from
        freezing a held gesture; callers can fall back to a screenshot.
        """
        deadline=time.monotonic()+timeout
        with self.condition:
            while self.sequence<=min_sequence and not self.error and not self.closed:
                remaining=deadline-time.monotonic()
                if remaining<=0:
                    raise RuntimeError('Нет свежего кадра видеопотока')
                self.condition.wait(remaining)
            if self.error:
                raise RuntimeError(str(self.error)) from self.error
            if self.closed or self.frame is None:
                raise RuntimeError('Видеопоток закрыт')
            return self.frame.copy()

    def close(self):
        self.closed=True
        with self.condition:
            self.condition.notify_all()
        # Stop only the PID emitted by this capture process, never all recorders.
        # Do it in the background: adb can be busy with the stream.
        remote=self.remote_pid
        if remote is not None:
            threading.Thread(target=self._kill_remote,args=(remote,),daemon=True).start()
        self._stop_processes(force=True)
        self.thread.join(timeout=3)
        self._stop_processes(force=True)
