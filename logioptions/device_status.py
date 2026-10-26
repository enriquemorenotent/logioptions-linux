"""Shared, conservative status presentation for the tray and settings window."""
import json
import math
import os
from pathlib import Path
import time

FRESH_FOR = 90


def status_path():
    return Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}')) / 'logioptions/batteries.json'


def read_rows():
    try:
        rows = json.loads(status_path().read_text())
        if not isinstance(rows, list): return []
        return [row for row in rows if isinstance(row,dict) and isinstance(row.get('name'),str)]
    except (OSError, ValueError):
        return []


def valid_percentage(value):
    return type(value) is int and 0 <= value <= 100


def age(timestamp, now):
    if type(timestamp) not in (int,float) or not math.isfinite(timestamp) or timestamp > now:
        return None
    return max(0,now-timestamp)


def age_label(seconds):
    if seconds is None: return 'at an unknown time'
    if seconds < 60: return 'just now'
    if seconds < 3600: return f'{int(seconds//60)} min ago'
    if seconds < 86400: return f'{int(seconds//3600)} hr ago'
    return f'{int(seconds//86400)} days ago'


def view(row, now=None):
    now = time.time() if now is None else now
    checked = age(row.get('checked',row.get('updated')),now)
    seen = age(row.get('last_seen',row.get('updated')),now)
    state = row.get('state','connected')
    if not isinstance(state,str): state='unavailable'
    if checked is None or checked > FRESH_FOR:
        state = 'stale'
    elif state == 'connected' and (seen is None or seen > FRESH_FOR):
        state = 'stale'
    status = {'connected':'Connected', 'unresponsive':'Not responding · may be asleep',
              'disconnected':'Disconnected', 'stale':'Status out of date'}.get(state,'Status unavailable')
    percentage = row.get('percentage')
    battery_age = age(row.get('battery_updated',row.get('updated')),now)
    battery = 'Battery unavailable'
    if valid_percentage(percentage):
        battery = f'{percentage}%'
        if battery_age is None or battery_age > FRESH_FOR or state != 'connected':
            battery += ' · last read ' + age_label(battery_age)
    return dict(state=state,status=status,battery=battery,percentage=percentage,
                battery_age=battery_age,last_seen=seen,
                text=f'{status} · {battery}')


def for_device(descriptor, now=None, rows=None):
    now = time.time() if now is None else now
    base = dict(name=descriptor['name'], state=descriptor.get('_state','connected'),
                checked=descriptor.get('_checked_at', descriptor.get('_seen_at',now)),
                last_seen=descriptor.get('_seen_at',now),
                percentage=descriptor.get('battery',{}).get('percentage'),
                battery_updated=descriptor.get('_battery_at',descriptor.get('_seen_at',now)))
    if descriptor.get('identity'):
        cached = next((row for row in (read_rows() if rows is None else rows)
                       if row.get('identity')==descriptor['identity']),None)
        if cached and age(cached.get('checked'),now) is not None and cached['checked'] >= base['checked']:
            base = cached
    return view(base,now)


def merge_devices(fresh, previous, now=None):
    """Keep known unavailable devices visible; never reuse their old controls."""
    now = time.time() if now is None else now
    devices = []
    cached_rows = read_rows()
    previous_batteries = {d.get('identity',d['key']):d for d in previous}
    present = set()
    for descriptor in fresh:
        descriptor = dict(descriptor,_seen_at=now,_checked_at=now,_state='connected')
        if valid_percentage(descriptor.get('battery',{}).get('percentage')):
            descriptor['_battery_at'] = now
        else:
            old = previous_batteries.get(descriptor.get('identity',descriptor['key']))
            cached = next((r for r in cached_rows if r.get('identity')==descriptor.get('identity')),None)
            if old and valid_percentage(old.get('battery',{}).get('percentage')):
                descriptor['battery'] = dict(old['battery'])
                descriptor['_battery_at'] = old.get('_battery_at',old.get('_seen_at',0))
            elif cached and valid_percentage(cached.get('percentage')):
                descriptor['battery'] = {'percentage':cached['percentage']}
                descriptor['_battery_at'] = cached.get('battery_updated',cached.get('updated',0))
        devices.append(descriptor)
        present.add(descriptor.get('identity',descriptor['key']))
    known = {d.get('identity',d['key']):d for d in previous}
    for row in cached_rows:
        if not row.get('identity') or row['identity'] in known: continue
        known[row['identity']] = dict(identity=row['identity'],name=row['name'],
            kind_code=row.get('kind_code',1 if 'key' in row['name'].lower() else 3),
            key='cached:'+row['identity'],path=row.get('path'),device_index=row.get('device_index'),
            battery={'percentage':row.get('percentage')},_seen_at=row.get('last_seen',row.get('updated',0)),
            _battery_at=row.get('battery_updated',row.get('updated',0)))
    for key, old in known.items():
        if key in present: continue
        # A missing receiver is definite. Silence with a receiver present is not.
        disconnected = old.get('path') and not Path(old['path']).exists()
        devices.append(dict(old,_missing=True,_checked_at=now,
                            _state='disconnected' if disconnected else 'unresponsive'))
    return devices
