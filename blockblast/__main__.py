import argparse
import math
from pathlib import Path
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
from .adb import ADB, AppNotReady
from .config import ROOT, CONFIG_PATH, TIMING, load, validate, edit
from .engine import solve, place
from .score import ScoreReader
from .session import Session, Stats, clean
from .vision import read, annotate
from .capture import VideoCapture
from .stability import StableState, matches_result
from .runtime import RunControl, BotStopped, DeviceLease, RunFinished
from .motion import drag_verified
from .profile import load_profile, validate_profile


def display_number(value):
    return f'{value:,}'.replace(',',' ') if value is not None else '?'


def print_state(state, stats=None):
    if stats:
        print(f'\nПоле после {stats.moves} ходов | Очки: {display_number(stats.score)} | '
              f'Рекорд: {display_number(stats.best)} | Линий: {stats.lines}')
    for r in range(8):
        print(' '.join('■' if state.board >> (8*r+c)&1 else '·' for c in range(8)))
    for slot,p in state.pieces.items():
        print(f'Фигура {slot+1}: {p.shape}')
    sys.stdout.flush()

def destination(state, piece, move, profile, bias=None):
    gain = profile.get('drag_gain',1.5)
    lift = profile.get('lift_cells',2.25)*state.cell
    x0,y0,x1,y1 = piece.box
    center = ((x0+x1)/2,(y0+y1)/2)
    width = max(c for r,c in piece.shape)+1
    height = max(r for r,c in piece.shape)+1
    bias=profile.get('release_bias_cells',.25) if bias is None else bias
    # Never aim outside the board.  The old ``+.12`` overshoot made edge
    # placements land 10-15 px past the border; the game clamped the piece,
    # while visual correction kept trying to push it further.
    bx=max(0.0,min(bias,8-move.col-width))
    by=max(0.0,min(bias,8-move.row-height))
    target = (state.bounds[0]+(move.col+width/2+bx)*state.cell,
              state.bounds[1]+(move.row+height/2+by)*state.cell)
    end = (piece.center[0]+(target[0]-center[0])/gain,
           piece.center[1]+(target[1]+lift-center[1])/gain)
    # A slightly wrong profile must not terminate a whole game.  Clamp the
    # finger to the display; the measured gesture correction and board check
    # decide whether the placement is valid.
    if not (0<end[0]<state.size[0] and 0<end[1]<state.size[1]):
        end=(min(max(end[0],1),state.size[0]-1),min(max(end[1],1),state.size[1]-1))
    return end


def parse_args(argv=None):
    parser=argparse.ArgumentParser(description='Block Blast ADB: настройки, поле, очки, ограниченное хранение логов.')
    parser.add_argument('command',choices=['play','inspect','doctor','settings','clean'])
    parser.add_argument('--config',type=Path,default=CONFIG_PATH)
    parser.add_argument('--set',action='append',default=[],metavar='KEY=VALUE',help='Для settings: изменить настройку без меню')
    parser.add_argument('--serial')
    parser.add_argument('--adb',default='adb')
    parser.add_argument('--profile',type=Path)
    parser.add_argument('--image',type=Path)
    parser.add_argument('--moves',type=int,help='Лимит успешных ходов; 0 = без лимита')
    parser.add_argument('--beam',type=int)
    parser.add_argument('--capture',choices=['auto','stream','screenshot'])
    parser.add_argument('--delay',type=float,help='Интервал проверки результата в секундах')
    parser.add_argument('--logs',action=argparse.BooleanOptionalAction,default=None,help='Включить/отключить логи консоли и файлов')
    for flag in ('console-logs','file-logs','board','screenshots','score'):
        parser.add_argument('--'+flag,action=argparse.BooleanOptionalAction,default=None)
    parser.add_argument('--screenshots-only',action='store_true',help='clean: удалить только сохранённые скриншоты')
    parser.add_argument('--dry-run',action='store_true',help='clean: показать объём без удаления')
    args=parser.parse_args(argv)
    if args.image and args.command!='inspect':
        parser.error('--image доступен только для inspect')
    if args.delay is not None and (not math.isfinite(args.delay) or args.delay<.02):
        parser.error('--delay должен быть >= 0.02')
    return args


def effective_settings(args):
    values=load(args.config)
    mapping={'moves':'max_moves','beam':'beam','board':'show_board',
             'screenshots':'save_screenshots','score':'read_score',
             'console_logs':'console_logs','file_logs':'file_logs','capture':'capture'}
    if args.logs is not None:
        values.update(console_logs=args.logs,file_logs=args.logs)
    for arg,key in mapping.items():
        value=getattr(args,arg)
        if value is not None:
            values[key]=value
    return validate(values)


def play(adb, profile, settings, delay=None, root=ROOT, control=None, quiet=False):
    profile=validate_profile(profile)
    settings=validate(settings)
    if delay is not None and (not math.isfinite(delay) or delay<.02):
        raise ValueError('--delay должен быть >= 0.02')
    control=control or RunControl()
    def session_record(record):
        control.emit('activity',record=record)
        if record['event']=='storage_warning' and not quiet:
            print('Запись истории отключена: '+record['message']+'. Игра продолжается.',file=sys.stderr,flush=True)
    session=Session(root,settings,callback=session_record)
    stats=Stats()
    reader=ScoreReader(settings['read_score'])
    score_pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='score') if reader.available else None
    score_job=None
    timing=dict(TIMING)
    if delay is not None:
        timing['poll']=delay
    reason='Завершено'
    last_image=None
    state=None
    video=None
    screen_size=tuple(profile.get('screen_size') or ()) or None
    last_foreground=0.0
    next_stream_retry=0.0
    def log(text, message=None, **params):
        control.emit('log',text=text,message=message,params=params)
        if not quiet and settings['console_logs']:
            print(f'[{time.strftime("%H:%M:%S")}] {text}',flush=True)
    def active_time():
        return time.monotonic()-control.pause_total

    def ensure_ready():
        nonlocal last_foreground
        paused_at=None
        while True:
            control.check()
            try:
                if control.pause_event.is_set():
                    ready,why=False,'Пауза по кнопке'
                elif hasattr(adb,'screen_status'):
                    ready,why=adb.screen_status('com.block.juggle')
                else:
                    adb.check_foreground('com.block.juggle')
                    ready,why=True,''
            except RuntimeError as exc:
                ready,why=False,'Телефон недоступен: '+str(exc)
            if ready:
                if paused_at is not None:
                    duration=time.monotonic()-paused_at
                    control.pause_total+=duration
                    stats.paused_seconds=control.pause_total
                    control.resume_epoch+=1
                    session.event('resumed',seconds=round(duration,2))
                    log('Игра снова доступна. Проверяю поле и продолжаю.', 'resumed')
                last_foreground=time.monotonic()
                if paused_at is not None or control.status in ('idle','connecting'):
                    control.emit('status',status='running',reason='Игра на экране')
                return
            if not settings['auto_pause'] and not control.pause_event.is_set():
                raise AppNotReady(why)
            if paused_at is None:
                paused_at=time.monotonic()
                session.event('paused',reason=why)
                log('Автопауза: '+why, 'paused')
            if control.status!='paused' or control.reason!=why:
                control.emit('status',status='paused',reason=why)
            try:
                control.wait(.3)
            except BotStopped:
                control.pause_total+=time.monotonic()-paused_at
                stats.paused_seconds=control.pause_total
                raise

    def capture():
        nonlocal video,last_foreground,next_stream_retry
        control.check()
        now=time.monotonic()
        if control.pause_event.is_set() or not video or now-last_foreground>=2.5:
            ensure_ready()
            last_foreground=time.monotonic()
        if video:
            try:
                image=video.get(timeout=3)
                control.frame=image
                return image
            except RuntimeError as exc:
                if settings['capture']=='stream':
                    # Reconnect an interrupted stream on the next capture.
                    video.close()
                    video=VideoCapture(adb,screen_size or control.frame.size,settings['stream_width'],settings['stream_fps'])
                    control.video=video
                    image=video.get(timeout=8)
                    control.frame=image
                    return image
                video.close()
                video=None
                control.video=None
                next_stream_retry=time.monotonic()+15
                session.event('capture_fallback',message=str(exc))
                log('Видеопоток недоступен; продолжаю через скриншоты.', 'capture_fallback')
        image=adb.screenshot()
        control.frame=image
        return image

    def maybe_restart_stream():
        """Recover from a transient stream failure without slowing every frame."""
        nonlocal video,next_stream_retry
        if video is not None or settings['capture']=='screenshot' or control.frame is None:
            return
        now=time.monotonic()
        if now<next_stream_retry:
            return
        next_stream_retry=now+20
        candidate=None
        try:
            candidate=VideoCapture(adb,screen_size or control.frame.size,settings['stream_width'],settings['stream_fps'])
            candidate.get(timeout=4)
        except RuntimeError as exc:
            if candidate is not None:
                candidate.close()
            session.event('capture_fallback',message=str(exc))
            return
        video=candidate
        control.video=video
        session.event('capture_started',width=video.width,fps=settings['stream_fps'])
        log(f'Видеопоток восстановлен, ширина {video.width} px, до {settings["stream_fps"]} кадров/с.',
            'capture_started',width=video.width,fps=settings['stream_fps'])

    def observer():
        return StableState(settings['stable_frames'],settings['settle_time'])

    def stable_read(expected_board=None, expected_pieces=None, full_tray=False,
                    recovery_seconds=1.2, timeout=None):
        consensus=observer()
        recovery=observer()
        empty=observer()
        deadline=active_time()+(timeout if timeout is not None else max(settings['verify_timeout'],settings['animation_timeout']))
        detail='нет распознанных кадров'
        epoch=control.resume_epoch
        field_wait=None
        def waiting(message):
            nonlocal field_wait
            if field_wait is None:field_wait=active_time()
            if control.status!='paused' or control.reason!=message:
                control.emit('status',status='paused',reason=message)
        try:
            while True:
                control.check()
                image=capture()
                try:
                    candidate=read(image,profile)
                except ValueError as exc:
                    detail=str(exc);consensus.reset();recovery.reset();empty.reset()
                    if active_time()>=deadline:
                        if not settings['auto_pause']:break
                        waiting('Ожидаю игровое поле: закройте меню или окно')
                    control.wait(timing['poll']);continue
                shapes={k:p.shape for k,p in candidate.pieces.items()}
                if shapes:
                    empty.reset()
                elif empty.observe(candidate,active_time()) and active_time()>=deadline and active_time()-empty.since>=1.5:
                    # Empty tray alone does not prove game-over. Bound the wait
                    # and finish without sending another gesture or claiming a loss.
                    raise RunFinished('Лоток остаётся пустым. Проверьте игру и запустите бота заново.')
                valid=bool(shapes) and (expected_board is None or candidate.board==expected_board or control.resume_epoch!=epoch)
                valid=valid and (expected_pieces is None or shapes==expected_pieces)
                valid=valid and (not full_tray or set(shapes)=={0,1,2})
                detail=f'board={candidate.board}; shapes={shapes}'
                now=active_time()
                if valid and consensus.observe(candidate,now):
                    control.emit('status',status='running',reason='Поле готово')
                    return image,candidate
                if not valid:consensus.reset()
                # Milestone rewards, palette changes and manual moves may change
                # the actual board/tray outside the predicted move. Never wait
                # forever for a state that no longer exists. Only adopt a fully
                # recognized playable position after prolonged temporal consensus.
                if not valid and shapes:
                    stable=recovery.observe(candidate,now)
                    if recovery_seconds is not None and stable and now-recovery.since>=max(recovery_seconds,settings['settle_time']*2):
                        session.event('board_resync',expected_board=expected_board,board=candidate.board,
                                      pieces=shapes,reason='stable_actual_position')
                        control.emit('target',mask=None)
                        control.emit('status',status='running',reason='Поле готово')
                        return image,candidate
                else:recovery.reset()
                if active_time()>=deadline:
                    # When a concrete gesture result was expected, do not adopt
                    # a mid-animation board.  Wait the full (bounded) timeout,
                    # then accept the actual stable position if it persisted.
                    if (recovery_seconds is None and recovery.count>=consensus.frames and shapes
                            and active_time()-recovery.since>=max(1.2,settings['settle_time']*2)):
                        session.event('board_resync',expected_board=expected_board,board=candidate.board,
                                      pieces=shapes,reason='expected_state_timeout')
                        control.emit('target',mask=None)
                        control.emit('status',status='running',reason='Поле готово')
                        return image,candidate
                    if not settings['auto_pause']:break
                    waiting('Жду окончания анимации или возвращения к игре')
                control.wait(max(timing['stable'],timing['poll']))
        finally:
            if field_wait is not None:
                control.pause_total+=max(0,active_time()-field_wait)
                stats.paused_seconds=control.pause_total
        session.event('unstable_screen',expected_board=expected_board,expected_pieces=expected_pieces,observed=detail)
        raise RuntimeError('Не дождался стабильного игрового экрана: '+detail)

    def check_new_game(image, fresh, resumed=False):
        # Only inspect a possible reset on an independently changed position or
        # resume. Ordinary low OCR readings remain rejected by Stats.
        if stats.score is None or not reader.available:
            if resumed and state is not None and fresh.board!=state.board:
                raise RunFinished('Позиция изменилась во время паузы. Запустите бота заново.')
            return
        first=reader.read(image,fresh.bounds,profile)[0]
        if first is None or first>=stats.score:
            return
        control.wait(.2)
        second_image=capture()
        try:
            confirmed=read(second_image,profile)
        except ValueError:
            return
        if confirmed.signature()!=fresh.signature():
            return
        second=reader.read(second_image,fresh.bounds,profile)[0]
        if second is not None and first<=second<stats.score:
            session.event('new_game',previous_score=stats.score,observed_score=second)
            raise RunFinished('Обнаружена новая партия. Запустите бота заново.')

    def update_score(image):
        if state is not None:
            stats.update_score(*reader.read(image,state.bounds,profile))
    try:
        log(f'Автоматический темп; лимит: {settings["max_moves"] or "без лимита"}; '
            f'скриншоты: {"сохраняются" if settings["save_screenshots"] else "только в памяти"}', 'auto_pace', limit=settings['max_moves'])
        control.emit('status',status='connecting',reason='Подключаю телефон')
        if settings['read_score'] and not reader.available:
            log('OCR недоступен: счёт будет показан как ?. Нужен Tesseract 5+ с языковой моделью.', 'ocr_unavailable')
        first_image=capture()
        if screen_size is None and getattr(first_image,'size',None):
            screen_size=tuple(first_image.size)
        if settings['capture']!='screenshot':
            try:
                video=VideoCapture(adb,screen_size,settings['stream_width'],settings['stream_fps'])
                video.get(timeout=10)
                control.video=video
                log(f'Захват: видеопоток H.264, ширина {video.width}, до {settings["stream_fps"]} кадров/с.', 'capture_started', width=video.width, fps=settings['stream_fps'])
            except RuntimeError as exc:
                if video:
                    video.close()
                video=None
                if settings['capture']=='stream':
                    raise
                log(f'Видеопоток недоступен ({exc}); использую скриншоты.', 'capture_fallback')
        last_image,state=stable_read()
        control.verified_epoch=control.resume_epoch
        profile=dict(profile)
        profile.setdefault('board',list(state.bounds))
        update_score(first_image)
        session.screenshot(last_image)
        session.event('start',settings=settings,profile=profile,board=state.board,score=stats.score,best=stats.best)
        control.emit('state',board=state.board,pieces={k:p.shape for k,p in state.pieces.items()})
        control.emit('stats',**stats.snapshot('Играю'))
        if settings['show_board'] and not quiet:
            print_state(state,stats)
        rejected=set()
        gesture_attempts={}
        failure_streak=0
        planned=()
        while not settings['max_moves'] or stats.moves<settings['max_moves']:
            # The field must still match the model; a new tray may have just
            # finished its appearance animation. Replan from its stable geometry.
            control.check()
            maybe_restart_stream()
            cycle_start=time.monotonic()
            if score_job is not None and score_job.done():
                try:stats.update_score(*score_job.result())
                except Exception:pass
                score_job=None
            if failure_streak>=min(6,max(2,settings['max_rejections']+1)):
                log('Пауза: несколько жестов не подтверждены. Автоматические попытки прекращены.', 'retry_pause')
                control.emit('target',mask=None)
                if not control.can_resume:
                    raise RunFinished('Жесты не подтверждены. Проверьте экран и запустите бота заново.')
                control.pause_event.set()
                ensure_ready()
                failure_streak=0;rejected.clear();gesture_attempts.clear();planned=()
            if control.pause_event.is_set():
                ensure_ready()
            resumed=control.resume_epoch!=getattr(control,'verified_epoch',-1)
            if resumed:
                last_image,fresh=stable_read()
            else:
                last_image=capture()
                try:
                    fresh=read(last_image,profile)
                except ValueError:
                    fresh=None
                if fresh is None or fresh.signature()!=state.signature():
                    last_image,fresh=stable_read(expected_board=state.board if control.resume_epoch==getattr(control,'verified_epoch',-1) else None)
            if resumed or fresh.signature()!=state.signature():
                check_new_game(last_image,fresh,resumed=resumed)
            control.verified_epoch=control.resume_epoch
            read_done=time.monotonic()
            if fresh.signature()!=state.signature():
                session.event('tray_resync',board=state.board,
                              previous={k:p.shape for k,p in state.pieces.items()},
                              current={k:p.shape for k,p in fresh.pieces.items()})
                planned=()
                rejected.clear()
                log('Анимация фигур завершилась: обновляю лоток и план.', 'tray_resync')
            state=fresh
            control.emit('state',board=state.board,pieces={k:p.shape for k,p in state.pieces.items()})
            if not planned:
                planned=solve(state.board,{k:p.shape for k,p in state.pieces.items()},settings['beam'],rejected)
            plan_done=time.monotonic()
            if not planned:
                if rejected:
                    control.emit('target',mask=None)
                    log('Допустимые ходы есть, но жесты не приняты. Пауза: проверьте экран и нажмите Продолжить.', 'check_pause')
                    if not control.can_resume:
                        raise RunFinished('Жесты не подтверждены. Проверьте экран и запустите бота заново.')
                    control.pause_event.set()
                    ensure_ready()
                    rejected.clear()
                    gesture_attempts.clear()
                    continue
                reason='Нет доступных ходов'
                break
            move_epoch=control.resume_epoch
            move=planned[0]
            expected,lines=place(state.board,move.mask)
            key=(move.slot,move.row,move.col)
            variants=(profile.get('release_bias_cells',.25),.10,.40,0.0)
            variant=gesture_attempts.get(key,0)%len(variants)
            end=destination(state,state.pieces[move.slot],move,profile,variants[variant])
            ensure_ready()
            control.check()
            if control.resume_epoch!=move_epoch:
                planned=()
                continue
            control.emit('target',mask=move.mask)
            stats.attempts+=1
            control.emit('stats',**stats.snapshot('Выполняю ход'))
            action=f'Фигура {move.slot+1} → строка {move.row+1}, столбец {move.col+1}; линий {lines}'
            log(f'Ход {stats.moves+1}, попытка {stats.attempts}: {action}', 'attempt')
            session.event('attempt',attempt=stats.attempts,slot=move.slot,row=move.row,col=move.col,
                          before=state.board,expected=expected,start=state.pieces[move.slot].center,end=end)
            motion_start=time.monotonic()
            retry=gesture_attempts.get(key,0)>0
            # With a live stream, measure the held piece on every move.  A blind
            # first gesture was the main source of off-target releases.  Without
            # a stream, keep the cheaper blind first attempt and verify retries.
            if hasattr(adb,'run') and (control.video is not None or retry):
                motion=drag_verified(adb,last_image,state,state.pieces[move.slot],move,end,profile,control,
                                     timing['grab'],timing['release'],bias=variants[variant])
                if motion.corrections or not motion.released:
                    session.event('motion',released=motion.released,corrections=motion.corrections,reason=motion.reason)
                if not motion.released:
                    log('Жест отменён: '+motion.reason, 'gesture_cancelled', reason=motion.reason)
                    stats.rejected+=1;failure_streak+=1
                    gesture_attempts[key]=gesture_attempts.get(key,0)+1
                    if gesture_attempts[key]>=len(variants):
                        rejected.add(key)
                    control.emit('target',mask=None)
                    control.emit('stats',**stats.snapshot('Жест отменён'))
                    session.event('rejected',attempt=stats.attempts,reason=motion.reason)
                    planned=()
                    continue
            else:
                adb.drag_precise(state.pieces[move.slot].center,end,timing['grab'],timing['release'])
            gesture_done=time.monotonic()
            session.event('timing',stage='gesture',seconds=round(gesture_done-motion_start,4))
            matched=False
            after=None
            remaining={k:p.shape for k,p in state.pieces.items() if k!=move.slot}
            consensus=StableState(2,.08) if remaining else observer()
            unchanged=observer()
            unexpected=StableState(max(3,settings['stable_frames']),max(1.2,settings['settle_time']*2))
            verification_started=active_time()
            deadline=active_time()+max(settings['verify_timeout'],settings['animation_timeout'])
            empty_tray_since=None
            while active_time()<deadline:
                control.check()
                time.sleep(timing['poll'])
                last_image=capture()
                try:
                    after=read(last_image,profile)
                except ValueError:
                    after=None
                    consensus.reset();unexpected.reset();empty_tray_since=None
                    continue
                remaining={k:p.shape for k,p in state.pieces.items() if k!=move.slot}
                # The third piece of a tray is normally followed by three new
                # pieces.  If the board already matches and the tray is empty
                # for a moment, this may be the game-over screen; give the
                # normal deal animation a short grace period instead of
                # waiting for a tray that will never appear.
                if not remaining and after.board==expected and not after.pieces:
                    if empty_tray_since is None:empty_tray_since=active_time()
                    elif active_time()-empty_tray_since>=max(1.5,settings['settle_time']*3):
                        matched=True
                        break
                else:empty_tray_since=None
                if matches_result(after,expected,remaining):
                    if consensus.observe(after):
                        matched=True
                        break
                else:
                    consensus.reset()
                if after.pieces and after.signature()!=state.signature():
                    if unexpected.observe(after,active_time()):break
                else:unexpected.reset()
                if after.signature()==state.signature():
                    rejection_wait=.7 if control.resume_epoch!=move_epoch else min(1.8,settings['verify_timeout'])
                    if unchanged.observe(after) and active_time()-verification_started>=rejection_wait:
                        break
                else:
                    unchanged.reset()
            if not matched and (after is None or after.signature()!=state.signature()):
                control.emit('status',status='paused',reason='Экран закрыт или ход ещё не подтверждён. Жду игру.')
                # A line-clear animation can keep a half-finished board on
                # screen for several seconds.  Do not adopt that transient:
                # wait for the exact expected position first, and only after a
                # bounded timeout fall back to the actual stable board.
                last_image,after=stable_read(
                    expected_board=expected,expected_pieces=remaining or None,
                    full_tray=not remaining,recovery_seconds=None,
                    timeout=max(settings['verify_timeout'],min(settings['animation_timeout'],8.0)))
                matched=matches_result(after,expected,remaining)
            session.screenshot(last_image)
            if not matched:
                planned=()
                stats.rejected+=1
                failure_streak+=1
                control.emit('stats',**stats.snapshot('Жест не принят'))
                session.event('rejected',attempt=stats.attempts,observed=after.board if after else None)
                stats.history.append(f'Отклонено: {action}')
                if control.resume_epoch!=move_epoch:
                    last_image,fresh=stable_read()
                    check_new_game(last_image,fresh,resumed=True)
                    state=fresh
                    planned=()
                    rejected.clear()
                    session.event('resync_after_pause',board=state.board)
                    log('Жест прервался при выходе из игры. Позиция распознана заново.', 'resync')
                    continue
                if after is not None and after.signature()==state.signature() :
                    gesture_attempts[key]=gesture_attempts.get(key,0)+1
                    if gesture_attempts[key]>=len(variants):
                        rejected.add(key)
                        log('Жесты не приняты; проверяю другое размещение.', 'retry_other')
                    else:
                        log('Поле не изменилось. Повторяю допустимый ход с поправкой точки отпускания.', 'retry_adjust')
                    continue
                # Replan from the actual stable position instead of either
                # sending the stale plan again or stopping after an in-game reset.
                last_image,fresh=stable_read()
                check_new_game(last_image,fresh)
                session.event('board_resync',expected_board=expected,board=fresh.board,
                              pieces={k:p.shape for k,p in fresh.pieces.items()},reason='unexpected_gesture_result')
                state=fresh;planned=();rejected.clear();gesture_attempts.clear()
                control.emit('target',mask=None)
                control.emit('state',board=state.board,pieces={k:p.shape for k,p in state.pieces.items()})
                control.verified_epoch=control.resume_epoch
                continue
            gesture_attempts.clear()
            failure_streak=0
            stats.moves+=1
            stats.lines+=lines
            stats.max_clear=max(stats.max_clear,lines)
            stats.history.append(f'Ход {stats.moves}: {action}')
            state=after
            rejected.clear()
            # The rest of the plan is valid only for the verified, unchanged tray.
            planned=planned[1:] if remaining else ()
            control.verified_epoch=control.resume_epoch
            control.emit('target',mask=None)
            if stats.moves%settings['score_every']==0 and score_pool is not None and score_job is None:
                score_job=score_pool.submit(reader.read,last_image,state.bounds,dict(profile))
            session.event('move',move=stats.moves,attempt=stats.attempts,slot=move.slot,row=move.row,
                          col=move.col,lines=lines,board=state.board,score=stats.score,best=stats.best)
            confirm_done=time.monotonic()
            session.event('timing',stage='cycle',read=round(read_done-cycle_start,3),
                          plan=round(plan_done-read_done,3),gesture=round(gesture_done-motion_start,3),
                          verify=round(confirm_done-gesture_done,3),seconds=round(confirm_done-cycle_start,3))
            control.emit('state',board=state.board,pieces={k:p.shape for k,p in state.pieces.items()})
            control.emit('stats',**stats.snapshot('Играю'))
            if settings['show_board'] and not quiet:
                print_state(state,stats)
            else:
                log(f'Подтверждено. Очки: {display_number(stats.score)}; рекорд: {display_number(stats.best)}', 'move')
        else:
            reason='Достигнут лимит ходов'
        # Final stable screenshot catches score counter animations and score_every > 1.
        previous_numbers=None
        score_wait_started=time.monotonic()
        for _ in range(4 if reader.available else 1):
            time.sleep(max(.2,timing['poll']))
            last_image=adb.screenshot() if video else capture()
            numbers=reader.read(last_image,state.bounds,profile)
            stats.update_score(*numbers)
            if numbers[0] is not None and numbers==previous_numbers and time.monotonic()-score_wait_started>=.9:
                break
            previous_numbers=numbers
    except RunFinished as exc:
        reason=str(exc)
    except (KeyboardInterrupt,BotStopped):
        reason='Остановлено пользователем (Ctrl+C / кнопка Стоп)'
    except Exception as exc:
        reason=f'Ошибка: {exc}'
        session.event('error',message=str(exc))
        raise
    finally:
        if score_pool is not None:
            score_pool.shutdown(wait=True,cancel_futures=True)
        if video:
            video.close()
        control.video=None
        control.emit('target',mask=None)
        report=session.finish(stats,reason)
        control.emit('stats',**report)
        control.emit('status',status='error' if reason.startswith('Ошибка') else 'finished',reason=reason)
        if not quiet:
            print(f'\nИтог: {reason}\n'
              f'Ходов: {stats.moves}; попыток: {stats.attempts}; отклонено: {stats.rejected}; '
              f'линий: {stats.lines}; максимум за ход: {stats.max_clear}\n'
              f'Очки: {display_number(stats.score)}; за запуск: {display_number(report["gained"])}; '
              f'рекорд: {display_number(stats.best)}\n'
              f'Время: {report["seconds"]:.1f} с; темп: {report["moves_per_minute"]} ход/мин',flush=True)
        if not quiet and settings['console_logs'] and stats.history:
            print('Последние действия:\n'+'\n'.join(stats.history))
        if not quiet and session.directory:
            print(f'Файлы сессии: {session.directory}')


def main(argv=None):
    args=parse_args(argv)
    if args.command=='settings':
        edit(args.config,args.set)
        print(f'Настройки сохранены: {args.config}')
        return
    if args.command=='clean':
        count,size=clean(ROOT,args.screenshots_only,args.dry_run)
        print(f'{"Будет удалено" if args.dry_run else "Удалено"}: {count} объектов, {size/1024/1024:.2f} МБ. Тестовые примеры сохранены.')
        return
    settings=effective_settings(args)
    profile_path=args.profile or ROOT/settings['profile']
    profile=load_profile(profile_path) if profile_path else {}
    adb=None if args.image else ADB(args.serial,args.adb)
    if args.command=='play':
        with DeviceLease(adb.serial):
            play(adb,profile,settings,args.delay)
        return
    if not args.image:
        adb.check_foreground('com.block.juggle')
    image=Image.open(args.image).convert('RGB') if args.image else adb.screenshot()
    state=read(image,profile)
    reader=ScoreReader(settings['read_score'])
    score,best=reader.read(image,state.bounds,profile)
    print(f'Экран: {image.width}×{image.height}; очки: {display_number(score)}; рекорд: {display_number(best)}')
    print_state(state)
    if args.command=='inspect':
        for move in solve(state.board,{k:p.shape for k,p in state.pieces.items()},settings['beam']):
            print(f'План: фигура {move.slot+1}, строка {move.row+1}, столбец {move.col+1}')
    session=Session(ROOT,settings)
    try:
        session.screenshot(image)
        if settings['save_screenshots']:
            from io import BytesIO
            data=BytesIO()
            annotate(image,state,data)
            data.seek(0)
            session.screenshot(Image.open(data))
        session.event(args.command,score=score,best=best,board=state.board)
    finally:
        session.close()


if __name__=='__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nОстановлено пользователем.')
    except (RuntimeError,ValueError,OSError) as exc:
        print(f'Ошибка: {exc}',file=sys.stderr)
        sys.exit(1)
