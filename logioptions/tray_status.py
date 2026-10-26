"""Status snapshots published by the receiver owner, without competing readers."""
import errno
import json
import time
from pathlib import Path
from .device import Device
from .hidpp import LinuxHidppTransport
from .device_status import status_path, read_rows, valid_percentage, view


class BatteryCache:
    def __init__(self, devices):
        previous = {row['identity']:row for row in read_rows() if isinstance(row.get('identity'),str)}
        self.devices = [d for d in devices if 'path' in d and 'identity' in d]
        present = {d['identity'] for d in self.devices}
        # Retain descriptors so sleeping/disconnected devices do not disappear.
        self.devices += [dict(identity=identity,**{k:row[k] for k in ('path','device_index','name')})
                         for identity,row in previous.items() if identity not in present
                         and isinstance(row.get('path'),str) and type(row.get('device_index')) is int]
        now = time.time()
        self.rows = []
        for device in self.devices:
            row = dict(previous.get(device['identity'],{}), identity=device['identity'],name=device['name'],
                       path=device['path'],device_index=device['device_index'],checked=now)
            if 'kind_code' in device: row['kind_code']=device['kind_code']
            if device['identity'] in present:
                row.update(last_seen=now,state='connected')
                percentage = device.get('battery',{}).get('percentage')
                if valid_percentage(percentage): row.update(percentage=percentage,updated=now,battery_updated=now)
            else:
                row['state']='unresponsive' if Path(device['path']).exists() else 'disconnected'
            row.setdefault('percentage',None)
            self.rows.append(row)
        self.next_update = time.monotonic() + 30
        self.publish()

    def publish(self):
        path = status_path()
        path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.rows))
        temporary.replace(path)

    def refresh(self, transport, active_path):
        if time.monotonic() < self.next_update: return
        self.next_update = time.monotonic()+30
        def read(t, descriptor, row):
            device = Device(t,descriptor['device_index'])
            if device.identity(timeout=.35) != descriptor['identity']:
                row['state']='disconnected'
                return
            row.update(state='connected',last_seen=time.time())
            try:
                percentage=device.battery_status()['percentage']
                if valid_percentage(percentage):
                    row.update(percentage=percentage,updated=time.time(),battery_updated=time.time())
            except (OSError,RuntimeError,ValueError,KeyError):
                pass  # A successful identity read still establishes connectivity.
        for descriptor,row in zip(self.devices,self.rows):
            row['checked']=time.time()
            try:
                if descriptor['path']==active_path:
                    read(transport,descriptor,row)
                elif not Path(descriptor['path']).exists():
                    row['state']='disconnected'
                else:
                    with LinuxHidppTransport(descriptor['path']) as other: read(other,descriptor,row)
            except OSError as error:
                row['state']='disconnected' if error.errno in (errno.ENOENT,errno.ENODEV,errno.ENXIO) else 'unresponsive'
            except (RuntimeError,ValueError,TimeoutError):
                row['state']='unresponsive'
        self.publish()


def battery_labels(now=None):
    return [f"{''.join(c for c in row['name'] if c.isprintable())}: {view(row,now)['text']}" for row in read_rows()]


def warning_reason(service_state, now=None):
    if service_state=='Stopped': return 'Background service stopped'
    low=[]
    for row in read_rows():
        state=view(row,now)
        if state['state']=='connected' and valid_percentage(state['percentage']) and state['percentage']<=20 and state['battery_age'] is not None and state['battery_age']<=90:
            low.append(row['name'])
    return 'Low battery: '+', '.join(low) if low else None
