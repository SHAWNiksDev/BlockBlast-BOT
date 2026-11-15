"""Validate phone geometry before recognition or device input."""
import json
import math
from pathlib import Path


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_profile(profile):
    if not isinstance(profile, dict):
        raise ValueError('Профиль телефона должен быть объектом JSON')
    screen = profile.get('screen_size')
    if screen is not None:
        if (not isinstance(screen, (list, tuple)) or len(screen) != 2
                or any(type(n) is not int or n < 16 for n in screen)):
            raise ValueError('screen_size: нужны ширина и высота экрана в пикселях')
    for key in ('board', 'tray', 'score_box', 'record_box'):
        box = profile.get(key)
        if box is None:
            continue
        if (not isinstance(box, (list, tuple)) or len(box) != 4
                or not all(_number(n) for n in box)):
            raise ValueError(f'{key}: нужны четыре конечные координаты')
        left, top, right, bottom = box
        if not (0 <= left < right and 0 <= top < bottom):
            raise ValueError(f'{key}: некорректные границы области')
        if screen and (right > screen[0] or bottom > screen[1]):
            raise ValueError(f'{key}: область выходит за screen_size')
        if key == 'board' and abs((right-left)-(bottom-top)) > (right-left)*.05:
            raise ValueError('board: поле должно быть квадратным')
    for key in ('tray_cell', 'drag_gain', 'color_distance', 'occupancy_distance',
                'lift_cells', 'release_bias_cells'):
        if key not in profile:
            continue
        value = profile[key]
        minimum = 0 if key in ('lift_cells', 'release_bias_cells') else 0.000001
        if not _number(value) or value < minimum:
            raise ValueError(f'{key}: некорректное числовое значение')
    return profile


def load_profile(path):
    return validate_profile(json.loads(Path(path).read_text(encoding='utf-8')))
