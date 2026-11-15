"""Bounded project-local storage and a summary also printed on interruption."""
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime,timedelta
import json
import io
import gzip
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import re
import shutil
import time
from .storage import write_json

RUN_NAME = re.compile(r'(?:run-)?\d{8}-\d{6}-\d{6}')


def new_session_directory(parent):
    # Windows clocks can return the same microsecond on successive calls.
    # mkdir is the arbiter, including when two app instances start together.
    stamp=datetime.now()
    for offset in range(1000000):
        path=parent/(stamp+timedelta(microseconds=offset)).strftime('run-%Y%m%d-%H%M%S-%f')
        try:
            path.mkdir(parents=True)
            return path
        except FileExistsError:
            if not parent.is_dir():raise
    raise OSError('Не удалось создать уникальную папку сессии')

@dataclass
class Stats:
    started_at: str = field(default_factory=lambda: datetime.now().astimezone().isoformat(timespec='seconds'))
    started: float = field(default_factory=time.monotonic)
    paused_seconds: float = 0.0
    moves: int = 0
    attempts: int = 0
    rejected: int = 0
    lines: int = 0
    max_clear: int = 0
    score: int | None = None
    start_score: int | None = None
    best: int | None = None
    pending_score: int | None = None
    pending_best: int | None = None
    history: deque = field(default_factory=lambda: deque(maxlen=10))

    @staticmethod
    def _valid(value):
        return value is not None and 0 <= value < 10**12

    def update_score(self, score, best):
        """Accept OCR values defensively.

        A single misread digit used to turn the record 150000 into 350000 and
        that value stayed forever (the visible score is much lower, so the
        record could not really change).  Suspicious jumps are confirmed by a
        second read; the record is only allowed to grow once the confirmed
        current score reaches it.
        """
        if self._valid(score):
            if self.score is None:
                self.score = score
                if self.start_score is None:
                    self.start_score = score
            elif score >= self.score:
                jump = score-self.score
                suspicious = jump > max(20000, int(self.score*.35))
                if score == self.score or not suspicious or score == self.pending_score:
                    self.score = score
                    self.pending_score = None
                    if self.start_score is None:
                        self.start_score = score
                else:
                    self.pending_score = score
        if self._valid(best):
            if self.best is None:
                self.best = max(n for n in (best, self.score) if n is not None)
                self.pending_best = None
            elif self.score is None or self.score >= self.best:
                old = self.best
                candidate = max(n for n in (old, best, self.score) if n is not None)
                if candidate <= old:
                    self.pending_best = None
                elif candidate == self.score or best == self.pending_best:
                    self.best = candidate
                    self.pending_best = None
                else:
                    self.pending_best = best
            # While the accepted score is below the stored record, the record
            # cannot legitimately change.  Ignore OCR noise.
        if self.score is not None and self.best is not None and self.score > self.best:
            self.best = self.score

    def snapshot(self, reason):
        elapsed = time.monotonic()-self.started
        return {'started_at':self.started_at,'ended_at':datetime.now().astimezone().isoformat(timespec='seconds'),'reason':reason,'moves':self.moves,'attempts':self.attempts,
                'rejected':self.rejected,'lines':self.lines,'max_clear':self.max_clear,
                'score':self.score,'start_score':self.start_score,
                'gained':self.score-self.start_score if self.score is not None else None,
                'best':self.best,'seconds':round(elapsed,2),
                'paused_seconds':round(self.paused_seconds,2),
                'active_seconds':round(max(0,elapsed-self.paused_seconds),2),
                'moves_per_minute':round(60*self.moves/max(elapsed-self.paused_seconds,.001),1),
                'last_actions':list(self.history)}

class Session:
    def __init__(self, root, settings, callback=None):
        self.callback=callback
        self.root=Path(root)
        self.settings=settings
        self.directory=None
        self.logger=None
        self.timeline=None
        self._event_count=0
        self._screenshot_count=0
        self.storage_error=None
        self.storage_disabled=False
        try:
            if settings['file_logs'] or settings['save_screenshots']:
                self.directory=new_session_directory(self.root/'logs')
                folders=sorted(p for p in self.directory.parent.iterdir() if not p.is_symlink() and p.is_dir() and RUN_NAME.fullmatch(p.name))
                for folder in folders[:-settings['max_sessions']]:
                    shutil.rmtree(folder)
                folders=sorted(p for p in self.directory.parent.iterdir() if not p.is_symlink() and p.is_dir() and RUN_NAME.fullmatch(p.name))
                sizes={p:sum(f.stat().st_size for f in p.rglob('*') if f.is_file()) for p in folders}
                total=sum(sizes.values())
                for folder in folders:
                    if total<=settings.get('max_history_mb',100)*1024*1024 or folder==self.directory:break
                    total-=sizes[folder];shutil.rmtree(folder)
            if settings['file_logs']:
                self.timeline=gzip.open(self.directory/'timeline.jsonl.gz','at',encoding='utf-8')
                self.logger=logging.Logger(str(self.directory))
                handler=RotatingFileHandler(self.directory/'events.jsonl',maxBytes=settings['max_log_mb']*1024*1024,
                                            backupCount=1,encoding='utf-8')
                handler.setFormatter(logging.Formatter('%(message)s'))
                self.logger.addHandler(handler)

        except OSError as exc:
            self._storage_failed(exc)

    def _room(self, extra, reserve=16384):
        """Bound all retained session files, including the active gzip archive.

        Admission is conservative: reserve space before each write, and stop
        disk recording when the active session fills the budget. Live play and
        the in-memory report continue. Leave room for the final summary.
        """
        if self.directory is None:
            return False
        folders=sorted(p for p in self.directory.parent.iterdir()
                       if not p.is_symlink() and p.is_dir() and RUN_NAME.fullmatch(p.name))
        sizes={p:sum(f.stat().st_size for f in p.rglob('*')
                     if f.is_file() and not f.is_symlink()) for p in folders}
        total=sum(sizes.values())
        limit=self.settings.get('max_history_mb',100)*1024*1024
        for folder in folders:
            if total+extra+reserve<=limit:
                return True
            if folder!=self.directory:
                shutil.rmtree(folder)
                total-=sizes[folder]
        return total+extra+reserve<=limit

    def _storage_failed(self, exc):
        self.storage_disabled=True
        self.storage_error=str(exc)
        try:
            if self.timeline is not None:
                self.timeline.close()
        except OSError:
            pass
        self.timeline=None
        if self.logger is not None:
            for handler in list(self.logger.handlers):
                try:handler.close()
                except OSError:pass
                self.logger.removeHandler(handler)
            self.logger=None
        if self.callback:
            self.callback({'time':datetime.now().isoformat(timespec='seconds'),
                           'event':'storage_warning','message':self.storage_error})

    def event(self, kind, **data):
        record={'time':datetime.now().isoformat(timespec='seconds'),'event':kind,**data}
        if self.callback:self.callback(record)
        if self.logger:
            try:
                line=json.dumps(record,ensure_ascii=False)
                # Two copies (JSONL + gzip), buffering and gzip trailer overhead.
                if not self._room(2*len(line.encode('utf-8'))+1024):
                    self._storage_failed(OSError('Достигнут лимит истории'))
                    return
                self.logger.info(line)
                self.timeline.write(line+'\n')
                self._event_count+=1
                self.timeline.flush()
            except (OSError,ValueError) as exc:
                self._storage_failed(exc)

    def screenshot(self, image):
        if self.settings['save_screenshots'] and self.directory is not None and not self.storage_disabled:
            try:
                self._screenshot_count+=1
                path=self.directory/f'screen-{self._screenshot_count:012d}.png'
                data=io.BytesIO()
                image.save(data,format='PNG')
                if not self._room(data.tell()):
                    self._storage_failed(OSError('Достигнут лимит истории'))
                    return
                path.write_bytes(data.getvalue())
                for old in sorted(self.directory.glob('screen-*.png'))[:-self.settings['max_screenshots']]:
                    old.unlink()
            except OSError as exc:
                self._storage_failed(exc)

    def finish(self, stats, reason):
        report=stats.snapshot(reason)
        if self.storage_error:
            report['storage_error']=self.storage_error
        self.event('summary',**report)
        if self.settings['file_logs'] and self.directory is not None:
            try:
                summary=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
                if self._room(len(summary.encode('utf-8')),reserve=0):
                    write_json(self.directory/'summary.json',report)
                previous={}
                path=self.root/'stats.json'
                if path.exists():
                    try:
                        previous=json.loads(path.read_text(encoding='utf-8'))
                        if not isinstance(previous,dict):previous={}
                    except (ValueError,OSError):
                        pass
                # Damaged or hand-edited aggregate data must not break finish().
                previous={k:v for k,v in previous.items() if type(v) is int and v>=0}
                best=max(previous.get('best') or 0,stats.best or 0)
                data={'sessions':previous.get('sessions',0)+1,
                      'total_moves':previous.get('total_moves',0)+stats.moves,
                      'best':best,'last_session':report}
                write_json(path,data)
            except OSError as exc:
                self.storage_error=str(exc)
        self.close()
        return report

    def close(self):
        """Close diagnostic sessions without creating a gameplay summary."""
        if self.timeline:
            try:self.timeline.close()
            except OSError:pass
            self.timeline=None
        if self.logger:
            for handler in list(self.logger.handlers):
                try:handler.close()
                except OSError:pass
                self.logger.removeHandler(handler)
            self.logger=None


def clean(root, screenshots_only=False, dry_run=False):
    """Only known generated names; never traverse symlink session folders."""
    targets=[]
    root=Path(root)
    for name in ('artifacts','logs'):
        parent=root/name
        if not parent.exists():
            continue
        for path in parent.iterdir():
            if path.is_symlink():
                continue
            if path.is_dir() and RUN_NAME.fullmatch(path.name):
                if screenshots_only:
                    targets.extend(p for p in path.glob('*.png') if not p.is_symlink())
                else:
                    targets.append(path)
            elif name=='artifacts' and path.is_file() and path.suffix=='.png':
                # Legacy screenshots created during the original calibration.
                if path.stem in {'initial','drag-test','held','placed','red-held','red-placed','l-held','l-up','l-inset','l-center'}:
                    targets.append(path)
    size=sum(sum(p.stat().st_size for p in t.rglob('*') if p.is_file() and not p.is_symlink()) if t.is_dir() else t.stat().st_size for t in targets)
    if not dry_run:
        for target in targets:
            shutil.rmtree(target) if target.is_dir() else target.unlink()
    return len(targets),size
