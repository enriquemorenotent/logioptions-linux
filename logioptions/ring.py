"""One receiver reader for Actions Ring and global button actions.

The background service joins it before granting GUI access. Every diverted
control is restored on shutdown, including after a partially failed setup.
"""
import threading
import time
from .device import Device
from .events import ControlTracker
from .hidpp import LinuxHidppTransport


def shell_call(method, parameters=None):
    from gi.repository import Gio
    connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    return connection.call_sync('org.gnome.Shell', '/local/logioptions/Ring',
                                'local.logioptions.Ring', method, parameters, None,
                                Gio.DBusCallFlags.NONE, 1500, None)


def available():
    try:
        return shell_call('Ping').unpack() == ('ready',)
    except Exception:
        return False


class RingListener:
    def __init__(self, descriptor, status=lambda message: None, *, transport_factory=LinuxHidppTransport,
                 device_factory=Device, call=shell_call, health_interval=5, clock=time.monotonic,
                 maintenance=None, bindings=None, execute=None, button_api=None):
        from . import button_actions
        self.descriptor = descriptor
        self.status = status
        self.transport_factory = transport_factory
        self.device_factory = device_factory
        self.call = call
        self.health_interval = health_interval
        self.maintenance = maintenance
        self.bindings = bindings or (lambda: button_actions.for_device(descriptor.get('identity'))
                                     if descriptor.get('identity') else {})
        self.execute = execute or button_actions.dispatch
        self.button_api = button_api or button_actions.available
        self.clock = clock
        self.cancel = threading.Event()
        self.thread = threading.Thread(target=self._run, name='actions-ring', daemon=False)
        self.thread.start()

    def stop(self):
        self.cancel.set()
        self.thread.join(timeout=30)
        if self.thread.is_alive():
            raise RuntimeError('Button listener is still releasing the receiver; try again shortly')

    def _run(self):
        try:
            with self.transport_factory(self.descriptor['path']) as transport:
                device = self.device_factory(transport, self.descriptor['device_index'])
                before, active = {}, {}
                pressed_ring = set()
                identity = self.descriptor.get('identity')

                def verify_identity():
                    if identity and device.identity(timeout=.35) != identity:
                        raise RuntimeError('Mouse changed receiver slots; rediscover before assigning buttons')

                verify_identity()
                tracker = ControlTracker(device.device_index, device.feature(0x1B04)['index'])
                controls = self.descriptor.get('controls', [{'control_id':416, 'flags':0x20}])
                supported = {c['control_id'] for c in controls if c['flags'] & 0x20 and c['control_id'] not in (80,81)}

                def restore(cid):
                    old = before[cid]
                    verify_identity()
                    device.set_control_reporting_bytes(cid, 2 | (old['flags'] & 1), old['remapped_to'])
                    if device.control_reporting(cid) != old:
                        raise RuntimeError(f'Button {cid} restoration could not be verified')
                    del before[cid]

                def synchronize():
                    nonlocal active
                    try:
                        configured = self.bindings()
                    except (ValueError, OSError) as error:
                        self.status(f'Button actions unavailable: {error}')
                        configured = {}
                    if configured and not self.button_api():
                        self.status('Button actions need the updated GNOME extension loaded')
                        configured = {}
                    desired = {int(cid): action for cid, action in configured.items() if int(cid) in supported}
                    if 416 in supported:
                        desired.setdefault(416, {'type':'ring'})
                    # A held button keeps its edge history when actions change.
                    # Otherwise its next held report would repeat the new action.
                    for cid in list(pressed_ring):
                        if desired.get(cid) != active.get(cid):
                            self.call('Hide')
                            pressed_ring.discard(cid)
                    for cid in list(before):
                        if cid not in desired:
                            restore(cid)
                    for cid in desired:
                        if cid not in before:
                            before[cid] = device.control_reporting(cid)
                        state = device.control_reporting(cid)
                        if not state['flags'] & 1:
                            device.set_control_reporting_bytes(cid, 3, state['remapped_to'])
                            if not device.control_reporting(cid)['flags'] & 1:
                                raise RuntimeError(f'Button {cid} reporting could not be enabled')
                    active = desired

                try:
                    synchronize()
                    self.status('Actions Ring ready · press the thumb pad')
                    next_check = self.clock() + self.health_interval
                    while not self.cancel.is_set():
                        if self.clock() >= next_check:
                            verify_identity()
                            lost = any(not device.control_reporting(cid)['flags'] & 1 for cid in active)
                            synchronize()
                            if lost:
                                self.call('Hide')
                                self.status('Actions Ring recovered · button reporting restored')
                            if self.maintenance:
                                try:
                                    self.maintenance(transport)
                                except Exception as error:
                                    self.status(f'Device settings retry: {error}')
                            next_check = self.clock() + self.health_interval
                        report = transport.read_notification(timeout=0.1)
                        change = tracker.feed(report) if report else None
                        if change:
                            for cid in change.pressed:
                                action = active.get(cid)
                                if action:
                                    if action['type'] == 'ring':
                                        self.call('Show')
                                        pressed_ring.add(cid)
                                    else: self.execute(action)
                            for cid in change.released:
                                if cid in pressed_ring:
                                    self.call('Release')
                                    pressed_ring.discard(cid)
                finally:
                    try:
                        self.call('Hide')
                    finally:
                        errors = []
                        for cid in list(before):
                            try: restore(cid)
                            except Exception as error: errors.append(str(error))
                        if errors: raise RuntimeError('; '.join(errors))
        except Exception as error:
            self.status(f'Actions Ring stopped: {error}')
