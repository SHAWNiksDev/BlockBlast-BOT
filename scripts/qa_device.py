"""Bounded gameplay check on a real phone; keep reports apart from user history."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from blockblast.adb import ADB
from blockblast.config import DEFAULTS, ROOT
from blockblast.__main__ import play
from blockblast.profile import load_profile
from blockblast.runtime import DeviceLease, RunControl
from blockblast.storage import write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial')
    parser.add_argument('--moves', type=int, default=30)
    parser.add_argument('--timeout', type=float, default=240)
    parser.add_argument('--capture', choices=('auto', 'stream', 'screenshot'), default='auto')
    parser.add_argument('--profile', type=Path, default=ROOT/'profiles/default.json')
    parser.add_argument('--pause-at', type=int, default=0, help='Pause for two seconds after N moves')
    args = parser.parse_args()
    if args.moves < 1 or not 1 <= args.timeout <= 3600 or not 0 <= args.pause_at < args.moves:
        parser.error('Use positive moves and timeout (1..3600), pause-at less than moves')
    adb = ADB(args.serial)
    adb.check_foreground('com.block.juggle')
    profile = load_profile(args.profile)
    root = ROOT/'artifacts'/('qa-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    root.mkdir(parents=True)
    started = time.monotonic()
    done = threading.Event()
    timed_out = threading.Event()
    pause_started = None
    pause_attempts = None
    pause_ok = False
    pause_requested = False

    def notify(kind, data):
        nonlocal pause_started, pause_attempts, pause_ok, pause_requested
        if kind == 'stats':
            if (args.pause_at and not pause_requested and data['moves'] >= args.pause_at):
                pause_requested = True
                control.pause_event.set()
        if kind == 'status':
            print(data, flush=True)
            if data['status'] == 'paused' and control.pause_event.is_set() and pause_started is None:
                pause_started = time.monotonic()
                pause_attempts = control.stats.get('attempts', 0)

    control = RunControl(notify)

    def watch():
        nonlocal pause_ok
        while not done.wait(.1):
            now = time.monotonic()
            if now-started >= args.timeout:
                timed_out.set()
                control.stop_event.set()
                return
            if pause_started is not None and control.pause_event.is_set() and now-pause_started >= 2:
                pause_ok = control.stats.get('attempts', 0) == pause_attempts
                control.pause_event.clear()

    settings = DEFAULTS | {'max_moves': args.moves, 'capture': args.capture, 'show_board': False}
    error = None
    with DeviceLease(adb.serial):
        thread = threading.Thread(target=watch, daemon=True)
        thread.start()
        try:
            play(adb, profile, settings, root=root, control=control)
        except Exception as exc:
            error = str(exc)
        finally:
            done.set()
            thread.join(2)
    report = {'stats': control.stats, 'status': control.status, 'capture': args.capture,
              'timeout': timed_out.is_set(), 'pause_checked': pause_ok,
              'error': error}
    write_json(root/'report.json', report)
    print('Report:', root/'report.json', flush=True)
    return int(error is not None or timed_out.is_set() or control.stats.get('moves') != args.moves
               or (args.pause_at > 0 and not pause_ok))


if __name__ == '__main__':
    sys.exit(main())
