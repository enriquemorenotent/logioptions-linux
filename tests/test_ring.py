import threading
import unittest
from logioptions.ring import RingListener


class Transport:
    def __init__(self, path):
        self.reports = [bytes.fromhex('11020d0001a00000000000000000000000000000'),
                        bytes.fromhex('11020d0000000000000000000000000000000000')]
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read_notification(self, timeout):
        if self.reports: return self.reports.pop(0)
        threading.Event().wait(.01)


class Device:
    instances = []
    def __init__(self, transport, index):
        self.device_index = index
        self.state = {'flags': 0, 'remapped_to': 416}
        self.writes = []
        self.instances.append(self)
    def control_reporting(self, cid): return dict(self.state)
    def feature(self, feature): return {'index': 13}
    def set_control_reporting_bytes(self, cid, flags, remap):
        self.writes.append((cid, flags, remap))
        self.state = {'flags': flags & 1, 'remapped_to': remap}


class RingTests(unittest.TestCase):
    def test_press_release_and_shutdown_restore(self):
        calls, released = [], threading.Event()
        def call(method):
            calls.append(method)
            if method == 'Release': released.set()
        listener = RingListener({'path':'/dev/hidraw6', 'device_index':2},
                                transport_factory=Transport, device_factory=Device, call=call)
        self.assertTrue(released.wait(2))
        listener.stop()
        self.assertEqual(calls, ['Show', 'Release', 'Hide'])
        self.assertEqual(Device.instances[-1].writes, [(416,3,416), (416,2,416)])

    def test_shell_failure_restores_diversion(self):
        errors = []
        def fail(method): raise RuntimeError('shell unavailable')
        listener = RingListener({'path':'/dev/hidraw6', 'device_index':2}, errors.append,
                                transport_factory=Transport, device_factory=Device, call=fail)
        listener.thread.join(2)
        self.assertFalse(listener.thread.is_alive())
        self.assertEqual(Device.instances[-1].state['flags'], 0)
        self.assertIn('shell unavailable', errors[-1])

    def test_mouse_reset_is_rearmed_without_restarting_listener(self):
        recovered = threading.Event()
        class ResetDevice(Device):
            def control_reporting(self, cid):
                if len(self.writes) == 1 and not hasattr(self, 'reset_once'):
                    # Initial verification succeeds; the next read simulates
                    # reporting lost while the same receiver remains open.
                    self.reset_once = False
                elif getattr(self, 'reset_once', None) is False:
                    self.state['flags'] = 0
                    self.reset_once = True
                return dict(self.state)
        listener = RingListener({'path':'fake', 'device_index':2},
            lambda message: recovered.set() if 'recovered' in message else None,
            transport_factory=Transport, device_factory=ResetDevice,
            call=lambda method: None, health_interval=.01)
        try:
            self.assertTrue(recovered.wait(2))
            self.assertTrue(listener.thread.is_alive())
            self.assertEqual(ResetDevice.instances[-1].state['flags'], 1)
        finally:
            listener.stop()
        self.assertEqual(ResetDevice.instances[-1].state['flags'], 0)

    def test_health_read_failure_exits_for_service_rediscovery(self):
        class DisconnectedDevice(Device):
            reads = 0
            def control_reporting(self, cid):
                self.reads += 1
                if self.reads == 3:
                    raise TimeoutError('mouse disconnected')
                return dict(self.state)
        errors = []
        listener = RingListener({'path':'fake', 'device_index':2}, errors.append,
            transport_factory=Transport, device_factory=DisconnectedDevice,
            call=lambda method: None, health_interval=.01)
        listener.thread.join(2)
        self.assertFalse(listener.thread.is_alive())
        self.assertIn('mouse disconnected', errors[-1])
        self.assertEqual(DisconnectedDevice.instances[-1].state['flags'], 0)

    def test_maintenance_runs_with_receiver_without_restarting_listener(self):
        maintained=threading.Event()
        listener=RingListener({'path':'fake','device_index':2}, transport_factory=Transport,
            device_factory=Device, call=lambda method: None, health_interval=.01,
            maintenance=lambda transport: maintained.set())
        try:
            self.assertTrue(maintained.wait(2))
            self.assertTrue(listener.thread.is_alive())
        finally:
            listener.stop()
