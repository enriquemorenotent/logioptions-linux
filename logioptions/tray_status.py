"""Battery snapshots published by the existing device owner, without extra readers."""
import json
import os
import time
from pathlib import Path
from .device import Device
from .hidpp import LinuxHidppTransport


def status_path():
    return Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}')) / 'logioptions/batteries.json'


class BatteryCache:
    def __init__(self, devices):
        self.devices = [d for d in devices if 'path' in d and 'identity' in d]
        self.rows = [{ 'name': d['name'], 'percentage': d.get('battery', {}).get('percentage'),
                       'updated': time.time()} for d in self.devices]
        self.next_update = time.monotonic() + 60
        self.publish()

    def publish(self):
        path = status_path()
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.rows))
        temporary.replace(path)

    def refresh(self, transport, active_path):
        if time.monotonic() < self.next_update:
            return
        self.next_update = time.monotonic() + 60
        def read(t, descriptor, row):
            device = Device(t, descriptor['device_index'])
            if device.identity(timeout=.35) != descriptor['identity']:
                return
            row.update(percentage=device.battery_status()['percentage'], updated=time.time())
        for descriptor, row in zip(self.devices, self.rows):
            try:
                if descriptor['path'] == active_path:
                    read(transport, descriptor, row)
                else:
                    with LinuxHidppTransport(descriptor['path']) as other:
                        read(other, descriptor, row)
            except (OSError, RuntimeError, ValueError):
                pass  # Keep last reading, explicitly marked as old by the tray.
        self.publish()


def battery_labels(now=None):
    now = time.time() if now is None else now
    try:
        rows = json.loads(status_path().read_text())
        return [f"{row['name']}: {row['percentage']}%" + (' (last known)' if now-row['updated'] > 90 else '')
                if row['percentage'] is not None else f"{row['name']}: battery unavailable" for row in rows]
    except (OSError, ValueError, KeyError, TypeError):
        return []


def warning_reason(service_state, now=None):
    if service_state == 'Stopped':
        return 'Background service stopped'
    now = time.time() if now is None else now
    try:
        rows = json.loads(status_path().read_text())
        low = [row['name'] for row in rows
               if type(row.get('percentage')) is int and 0 <= row['percentage'] <= 20
               and 0 <= now - row['updated'] <= 90]
        return 'Low battery: ' + ', '.join(low) if low else None
    except (OSError, ValueError, KeyError, TypeError):
        return None
