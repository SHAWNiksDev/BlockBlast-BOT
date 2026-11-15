"""Validated project-local settings; CLI values override this file."""
import json
import math
import sys
from pathlib import Path

ROOT = Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / 'settings.json'
DEFAULTS = {
    'max_moves': 0, 'beam': 180,
    'show_board': True, 'console_logs': True, 'file_logs': True,
    'save_screenshots': False, 'read_score': True, 'score_every': 3,
    'max_sessions': 50, 'max_history_mb': 100, 'max_screenshots': 20, 'max_log_mb': 2,
    'verify_timeout': 5.0, 'max_rejections': 5,
    'profile': 'profiles/default.json',
    'capture': 'auto', 'stream_width': 540, 'stream_fps': 12,
    'animation_timeout': 15.0, 'stable_frames': 3, 'settle_time': .2,
    'auto_pause': True, 'language': 'ru', 'theme': 'dark',
}
TIMING = {'grab': .06, 'release': .08, 'poll': .02, 'stable': .02}
LABELS = {
    'language': 'Язык интерфейса: ru / en / uk', 'theme': 'Тема интерфейса: dark / light',
    'max_history_mb': 'Общий лимит истории, МБ',
    'auto_pause': 'Автопауза при выходе, шторке или меню',
    'capture': 'Захват: auto / stream / screenshot',
    'stream_width': 'Ширина видеопотока в пикселях', 'stream_fps': 'Кадров/с для распознавания',
    'animation_timeout': 'Максимум секунд ожидания анимации',
    'stable_frames': 'Кадров для подтверждения стабильности',
    'settle_time': 'Минимум секунд стабильности фигур',
    'max_moves': 'Лимит ходов (0 = без лимита)',
    'beam': 'Ширина поиска (больше = тщательнее, медленнее)',
    'show_board': 'Показывать поле после каждого хода', 'console_logs': 'Логи действий в консоли',
    'file_logs': 'Сохранять логи и итоговый отчёт', 'save_screenshots': 'Сохранять скриншоты',
    'read_score': 'Читать очки и рекорд с экрана', 'score_every': 'Читать очки каждые N ходов',
    'max_sessions': 'Хранить последние N сессий', 'max_screenshots': 'Максимум скриншотов на сессию',
    'max_log_mb': 'Лимит МБ на файл лога', 'verify_timeout': 'Секунд на проверку хода',
    'max_rejections': 'Допустимое число отклонённых размещений подряд', 'profile': 'Профиль телефона',
}

def validate(values):
    if not isinstance(values, dict):
        raise ValueError('Настройки должны быть объектом JSON')
    unknown = set(values) - set(DEFAULTS)
    if unknown:
        raise ValueError(f'Неизвестные настройки: {", ".join(sorted(unknown))}')
    result = DEFAULTS | values
    for key, default in DEFAULTS.items():
        value = result[key]
        if type(default) is bool:
            valid = type(value) is bool
        elif type(default) is int:
            valid = type(value) is int
        elif type(default) is float:
            valid = type(value) in (float, int)
        else:
            valid = type(value) is str
        if not valid or (type(value) is float and not math.isfinite(value)):
            raise ValueError(f'Некорректный тип настройки {key}')
    if result['language'] not in ('ru','en','uk') or result['theme'] not in ('dark','light'):
        raise ValueError('language: ru / en / uk; theme: dark / light')
    if result['capture'] not in ('auto','stream','screenshot'):
        raise ValueError('capture: выберите auto, stream или screenshot')
    if not 2<=result['stable_frames']<=20 or not .05<=result['settle_time']<=5:
        raise ValueError('stable_frames: 2..20, settle_time: 0.05..5')
    if not 240<=result['stream_width']<=2160 or not 2<=result['stream_fps']<=60:
        raise ValueError('stream_width: 240..2160, stream_fps: 2..60')
    if not 1<=result['animation_timeout']<=120:
        raise ValueError('animation_timeout: 1..120')
    if result['max_moves'] < 0 or result['max_rejections'] < 0:
        raise ValueError('Лимиты ходов и отказов не могут быть отрицательными')
    for key in ('beam', 'score_every', 'max_sessions', 'max_screenshots', 'max_log_mb', 'max_history_mb'):
        if result[key] < 1:
            raise ValueError(f'{key} должен быть >= 1')
    if not .2 <= result['verify_timeout'] <= 120:
        raise ValueError('verify_timeout должен быть от 0.2 до 120')
    return result

def load(path=CONFIG_PATH):
    path=Path(path)
    values=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    if not isinstance(values,dict):
        raise ValueError('Настройки должны быть объектом JSON')
    values.pop('speed',None)  # Migrate releases that exposed manual speed presets.
    return validate(values)

def save(values, path=CONFIG_PATH):
    # Write through a sibling temporary file: a crash or full disk must not
    # leave settings.json truncated on the next start.
    from .storage import write_json
    write_json(path,validate(values))

def edit(path=CONFIG_PATH, changes=()):
    values = load(path)
    for change in changes:
        key, sep, raw = change.partition('=')
        if not sep or key not in DEFAULTS:
            raise ValueError('Используйте --set имя=значение из settings.json')
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            value = raw
        values = validate(values | {key: value})
    if changes:
        save(values, path)
        return
    keys = list(DEFAULTS)
    while True:
        print('\nНастройки бота:')
        for i,key in enumerate(keys,1):
            print(f'{i:2}. {LABELS[key]}: {values[key]}')
        choice = input('\nНомер настройки; Enter — сохранить и выйти: ').strip()
        if not choice:
            save(values,path)
            return
        try:
            index = int(choice)-1
            if not 0 <= index < len(keys):
                raise ValueError('Нет такого номера')
            key=keys[index]
            if type(values[key]) is bool:
                new = not values[key]
            else:
                raw=input('Новое значение: ').strip()
                new=type(DEFAULTS[key])(raw)
            values=validate(values | {key:new})
        except ValueError as exc:
            print(f'Ошибка: {exc}')
