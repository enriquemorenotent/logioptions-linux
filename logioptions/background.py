"""Background ring listener and cooperative access for the settings window."""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import signal
import threading

from .discovery import discover
from .ring import RingListener, available
from .preferences import restore_available, reconcile
from .tray_status import BatteryCache


def lockfile(name):
    directory = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}')) / 'logioptions'
    directory.mkdir(mode=0o700, exist_ok=True)
    return (directory / name).open('a+')


def acquire(file, blocking=True):
    try:
        fcntl.flock(file, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        return True
    except BlockingIOError:
        return False


@contextmanager
def foreground_access():
    # Hold the request throughout the operation. The daemon notices it, stops
    # its reader (restoring diversion), then releases the device lease.
    with lockfile('foreground') as request, lockfile('device') as lease:
        acquire(request)
        acquire(lease)
        yield


class BackgroundRing:
    def __init__(self, discover_devices=discover, ready=available, listener=RingListener, restore_settings=restore_available):
        self.discover = discover_devices
        self.ready = ready
        self.factory = listener
        self.restore_settings = restore_settings
        self.listener = None
        self.lease = None

    def stop(self):
        if self.listener:
            self.listener.stop()
            self.listener = None
        if self.lease:
            self.lease.close()
            self.lease = None

    def tick(self):
        with lockfile('foreground') as request:
            if not acquire(request, blocking=False):
                self.stop()
                return
            if self.listener and self.listener.thread.is_alive():
                return
            self.stop()
            lease = lockfile('device')
            if not acquire(lease, blocking=False):
                lease.close()
                return
            self.lease = lease
            try:
                try:
                    self.restore_settings()
                except Exception as error:
                    print(f'Device settings retry: {error}', flush=True)
                if not self.ready():
                    self.stop()
                    return
                devices, errors = self.discover()
                batteries = BatteryCache(devices)
                mouse = next((d for d in devices if any(c['control_id'] == 416
                             and c['flags'] & 0x20 for c in d.get('controls', []))), None)
                if mouse:
                    indices = [255] if mouse['device_index'] == 255 else list(range(1, 7))
                    def maintain(transport):
                        batteries.refresh(transport, mouse['path'])
                        reconcile(transport, indices, lambda message: print(message, flush=True))
                        restore_available(exclude=mouse['path'])
                    self.listener = self.factory(mouse, lambda message: print(message, flush=True),
                        maintenance=maintain)
                else:
                    self.stop()
            except Exception:
                self.stop()
                raise


def main():
    stopped = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stopped.set())
    with lockfile('service') as singleton:
        if not acquire(singleton, blocking=False):
            return
        worker = BackgroundRing()
        try:
            while not stopped.is_set():
                try:
                    worker.tick()
                except Exception as error:
                    print(f'Actions Ring retry: {error}', flush=True)
                stopped.wait(.2 if worker.listener else 2)
        finally:
            worker.stop()


if __name__ == '__main__':
    main()
