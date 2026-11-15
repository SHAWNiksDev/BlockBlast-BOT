"""Read complete retained timelines, including old rotated event logs."""
from datetime import datetime
import gzip
import json

def duration(seconds):
    n=max(0,int(seconds or 0));return f'{n//3600:02}:{n%3600//60:02}:{n%60:02}'

def date(value):
    try:return datetime.fromisoformat(value).strftime('%d.%m.%Y %H:%M:%S')
    except (ValueError,TypeError):return 'Не записано'

def records(folder):
    archive=folder/'timeline.jsonl.gz'
    paths=[archive] if archive.exists() else [p for p in (folder/'events.jsonl.1',folder/'events.jsonl') if p.exists()]
    for path in paths:
        opener=gzip.open if path.suffix=='.gz' else open
        try:
            with opener(path,'rt',encoding='utf-8') as file:
                for line in file:
                    try:yield json.loads(line)
                    except ValueError:continue
        except (OSError,EOFError):continue

def describe(event):
    kind=event.get('event');stamp=event.get('time','')
    try:stamp=datetime.fromisoformat(stamp).strftime('%H:%M:%S')
    except ValueError:pass
    if kind in ('attempt','move'):
        text=f'{"Попытка" if kind=="attempt" else "Ход"} {event.get("attempt" if kind=="attempt" else "move","?")}: фигура {event.get("slot",0)+1} → строка {event.get("row",0)+1}, столбец {event.get("col",0)+1}'
        if kind=='move':text+=f'; линий {event.get("lines",0)}, очки {event.get("score") if event.get("score") is not None else "—"}'
    elif kind=='motion':text=f'Проверка жеста: {event.get("reason","")}; поправок {event.get("corrections",0)}'
    elif kind=='start':text='Начало партии'
    elif kind=='summary':text='Завершение: '+event.get('reason','')
    elif kind=='rejected':text='Жест не принят, попытка '+str(event.get('attempt','?'))
    elif kind=='paused':text='Пауза: '+event.get('reason','')
    elif kind=='resumed':text='Продолжение после паузы '+duration(event.get('seconds'))
    else:text=str(event.get('message') or event.get('reason') or kind)
    return f'{stamp}  {text}'
