"""Persistent thumb-pad reader for the GNOME Actions Ring.

Owns one transport while idle. The background service stops/joins it before
granting the GUI device access. Diversion is restored on every exit.
"""
import threading
import time
from .device import Device
from .events import ControlTracker
from .hidpp import LinuxHidppTransport


def shell_call(method):
    from gi.repository import Gio, GLib
    connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    return connection.call_sync('org.gnome.Shell', '/local/logioptions/Ring',
                                'local.logioptions.Ring', method, None, None,
                                Gio.DBusCallFlags.NONE, 1500, None)


def available():
    try:
        return shell_call('Ping').unpack() == ('ready',)
    except Exception:
        return False


class RingListener:
    def __init__(self, descriptor, status=lambda message: None, *, transport_factory=LinuxHidppTransport,
                 device_factory=Device, call=shell_call, health_interval=5, clock=time.monotonic):
        self.descriptor = descriptor
        self.status = status
        self.transport_factory = transport_factory
        self.device_factory = device_factory
        self.call = call
        self.health_interval = health_interval
        self.clock = clock
        self.cancel = threading.Event()
        self.thread = threading.Thread(target=self._run, name='actions-ring', daemon=False)
        self.thread.start()

    def stop(self):
        self.cancel.set()
        self.thread.join(timeout=10)
        if self.thread.is_alive():
            raise RuntimeError('Actions Ring is still releasing the receiver; try again shortly')

    def _run(self):
        try:
            with self.transport_factory(self.descriptor['path']) as transport:
                device = self.device_factory(transport, self.descriptor['device_index'])
                before = device.control_reporting(416)
                tracker = ControlTracker(device.device_index, device.feature(0x1B04)['index'])
                try:
                    device.set_control_reporting_bytes(416, 3, before['remapped_to'])
                    if not device.control_reporting(416)['flags'] & 1:
                        raise RuntimeError('Thumb pad reporting was not enabled')
                    self.status('Actions Ring ready · press the thumb pad')
                    next_check = self.clock() + self.health_interval
                    while not self.cancel.is_set():
                        if self.clock() >= next_check:
                            # A live reader thread does not prove the mouse still
                            # diverts the thumb pad after sleep or reconnection.
                            # Failed reads exit so the service can rediscover it.
                            state = device.control_reporting(416)
                            if not state['flags'] & 1:
                                device.set_control_reporting_bytes(416, 3, state['remapped_to'])
                                if not device.control_reporting(416)['flags'] & 1:
                                    raise RuntimeError('Thumb pad reporting could not be restored')
                                tracker = ControlTracker(device.device_index, device.feature(0x1B04)['index'])
                                self.call('Hide')
                                self.status('Actions Ring recovered · thumb pad reporting restored')
                            next_check = self.clock() + self.health_interval
                        report = transport.read_notification(timeout=0.1)
                        change = tracker.feed(report) if report else None
                        if change:
                            if 416 in change.pressed:
                                self.call('Show')
                            if 416 in change.released:
                                self.call('Release')
                finally:
                    try:
                        self.call('Hide')
                    finally:
                        device.set_control_reporting_bytes(416, 2 | (before['flags'] & 1), before['remapped_to'])
                        if device.control_reporting(416) != before:
                            raise RuntimeError('Thumb pad restoration could not be verified')
        except Exception as error:
            self.status(f'Actions Ring stopped: {error}')
