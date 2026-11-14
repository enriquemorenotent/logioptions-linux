from collections import deque
import threading
import unittest
from unittest.mock import Mock

from logioptions.pairing import PairingSession, PairingCancelled, verification_instructions


def notification(event, address=0, data=b'', device=255):
    return (bytes([0x11, device, event, address]) + data).ljust(20, b'\0')


def discovered(name='MX Master 4', authentication=2, kind=2, counter=7):
    data = bytearray(16)
    data[0] = counter >> 8
    data[3] = kind
    data[6:12] = bytes.fromhex('010203040506')
    data[14] = authentication
    return [notification(0x4F, counter & 255, data),
            notification(0x4F, counter & 255, bytes([counter >> 8, 1, len(name)]) + name.encode())]


class FakeTransport:
    def __init__(self, events, flags=b'\x10\x00\x02'):
        self.events = deque(events)
        self.calls = []
        self.flags = flags
        self.on_read = lambda: None
        self.on_register = lambda *args: None

    def register(self, register, payload=b'', *, write=False):
        self.calls.append((register, payload, write))
        self.on_register(register, payload, write)
        return self.flags if register == 0 and not write else bytes(3)

    def read_notification(self, **kwargs):
        self.on_read()
        return self.events.popleft() if self.events else None

    def discard_notifications(self):
        pass


class PairingTests(unittest.TestCase):
    def session(self, events, kind='bolt', **kwargs):
        self.transport = FakeTransport(events)
        self.device = dict(slot=2, name='MX Master 4', token='new')
        self.receiver = Mock(kind=kind, transport=self.transport)
        self.receiver.inventory.return_value = dict(serial='receiver', devices=[])
        self.receiver.paired_device.return_value = self.device
        self.events = []
        self.worker = PairingSession(self.receiver, 'receiver', self.events.append, **kwargs)
        return self.worker

    def test_bolt_requires_confirmation_then_shows_mouse_sequence_and_returns_verified_slot(self):
        done = bytearray(16)
        done[7] = 2
        worker = self.session([notification(0x53)] + discovered() + [
            notification(0x53, 1), notification(0x54), notification(0x4D, data=b'000005'),
            notification(0x54, 2, done)])
        def emit(event):
            self.events.append(event)
            if event['state'] == 'found':
                self.assertFalse(any(c[0] == 0x2C1 for c in self.transport.calls))
                worker.accept()
        worker.emit = emit
        self.assertEqual(worker.run(), self.device)
        self.assertEqual([e['state'] for e in self.events], ['searching', 'found', 'pairing', 'verify'])
        self.assertIn('Left → Right → Left → Right', self.events[-1]['text'])
        self.assertIn((0x2C1, bytes.fromhex('0100010203040506020a'), True), self.transport.calls)
        self.assertEqual(self.transport.calls[-1], (0, b'\x10\x00\x02', True))
        self.assertFalse(any(c[0] == 0x2C1 and c[1][0] == 2 for c in self.transport.calls))

    def test_keyboard_authentication_and_entropy(self):
        done = bytearray(16); done[7] = 1
        worker = self.session(discovered('MX KEYS B', 1, 1) + [notification(0x4D, data=b'123456'), notification(0x54, 2, done)])
        worker.accept()
        worker.run()
        self.assertIn('Type 123456', self.events[-1]['text'])
        self.assertIn((0x2C1, bytes.fromhex('01000102030405060114'), True), self.transport.calls)

    def test_discovery_fragments_from_different_candidates_are_not_mixed(self):
        fragments = discovered()
        wrong = discovered('Wrong mouse', counter=8)[1]
        worker = self.session([fragments[0], wrong, fragments[1]])
        def emit(event):
            self.events.append(event)
            if event['state'] == 'found':
                worker.cancel()
        worker.emit = emit
        with self.assertRaises(PairingCancelled):
            worker.run()
        self.assertEqual([e['name'] for e in self.events if e['state'] == 'found'], ['MX Master 4'])
        self.assertFalse(any(c[0] == 0x2C1 for c in self.transport.calls))
        self.assertIn((0xC0, b'\x00\x02', True), self.transport.calls)

    def test_cancellation_while_waiting_for_user_releases_receiver(self):
        worker = self.session(discovered())
        waiting = threading.Event()
        def emit(event):
            if event['state'] == 'found': waiting.set()
        worker.emit = emit
        result = []
        def run():
            try: worker.run()
            except Exception as error: result.append(error)
        thread = threading.Thread(target=run)
        thread.start()
        try:
            self.assertTrue(waiting.wait(1))
            worker.cancel()
            thread.join(1)
            self.assertFalse(thread.is_alive())
            self.assertIsInstance(result[0], PairingCancelled)
            self.assertIn((0xC0, b'\x00\x02', True), self.transport.calls)
            self.assertEqual(self.transport.calls[-1], (0, self.transport.flags, True))
        finally:
            worker.cancel(); thread.join(1)

    def test_cancellation_during_verification_cancels_pairing(self):
        worker = self.session(discovered() + [notification(0x4D, data=b'000005')])
        worker.accept()
        def emit(event):
            if event['state'] == 'verify': worker.cancel()
        worker.emit = emit
        with self.assertRaises(PairingCancelled): worker.run()
        self.assertIn((0x2C1, b'\x02\x00' + bytes(8), True), self.transport.calls)
        self.assertEqual(self.transport.calls[-1], (0, self.transport.flags, True))

    def test_bolt_authentication_error_and_malformed_discovery_are_not_success(self):
        for events, error in [(discovered() + [notification(0x54, 1, b'\x02')], RuntimeError),
                              ([notification(0x4F, data=b'\x00\x01\xff')], ValueError)]:
            worker = self.session(events)
            worker.accept()
            with self.subTest(events=events), self.assertRaises(error): worker.run()
            self.assertEqual(self.transport.calls[-1], (0, self.transport.flags, True))

    def test_discovery_timeout_closes_discovery_and_restores_flags(self):
        now = [0]
        worker = self.session([], clock=lambda: now[0])
        self.transport.on_read = lambda: now.__setitem__(0, now[0] + 10)
        with self.assertRaises(TimeoutError): worker.run()
        self.assertIn((0xC0, b'\x00\x02', True), self.transport.calls)
        self.assertEqual(self.transport.calls[-1], (0, self.transport.flags, True))

    def test_start_timeout_still_attempts_cleanup(self):
        worker = self.session([])
        def register(reg, data, write):
            if reg == 0xC0 and data[1] == 1:
                raise TimeoutError('start response lost')
        self.transport.on_register = register
        with self.assertRaisesRegex(TimeoutError, 'start response lost'): worker.run()
        self.assertIn((0xC0, b'\x00\x02', True), self.transport.calls)
        self.assertEqual(self.transport.calls[-1], (0, self.transport.flags, True))

    def test_cleanup_failure_is_reported_and_flag_restore_still_attempted(self):
        worker = self.session([])
        self.transport.on_read = worker.cancel
        def register(reg, data, write):
            if reg == 0xC0 and data[1] == 2:
                raise OSError('receiver disconnected')
        self.transport.on_register = register
        with self.assertRaisesRegex(RuntimeError, 'cleanup could not be confirmed'): worker.run()
        self.assertEqual(self.transport.calls[-1], (0, self.transport.flags, True))

    def test_receiver_changed_and_full_receiver_never_start_pairing(self):
        for inventory in [dict(serial='other', devices=[]), dict(serial='receiver', devices=[{}] * 6)]:
            worker = self.session([])
            self.receiver.inventory.return_value = inventory
            with self.subTest(inventory=inventory), self.assertRaises(RuntimeError): worker.run()
            self.assertEqual(self.transport.calls, [])

    def test_unifying_checks_new_slot_instead_of_existing_device_connecting(self):
        worker = self.session([notification(0x41, device=1), notification(0x41, device=2)], kind='unifying')
        previous = dict(slot=1, token='old')
        self.receiver.inventory.return_value['devices'] = [previous]
        self.receiver.paired_device.side_effect = [previous, self.device]
        self.assertEqual(worker.run(), self.device)
        self.assertIn((0xB2, bytes([1, 0, 30]), True), self.transport.calls)
        self.assertIn((0xB2, b'\x02\x00\x00', True), self.transport.calls)

    def test_unifying_lock_close_requires_verified_new_pairing(self):
        worker = self.session([notification(0x4A, 0)], kind='unifying')
        with self.assertRaisesRegex(RuntimeError, 'without a new device'): worker.run()
        worker = self.session([notification(0x4A, 0)], kind='unifying')
        self.receiver.inventory.side_effect = [dict(serial='receiver', devices=[]),
                                               dict(serial='receiver', devices=[self.device])]
        self.assertEqual(worker.run(), self.device)

    def test_unifying_device_error_and_already_enabled_flags(self):
        worker = self.session([notification(0x4A, 0, b'\x02')], kind='unifying')
        self.transport.flags = b'\x10\x01\x02'
        with self.assertRaisesRegex(RuntimeError, 'not compatible'): worker.run()
        self.assertFalse(any(c[0] == 0 and c[2] for c in self.transport.calls))

    def test_bad_authentication_codes_are_rejected(self):
        for code, auth in [('abc123', 1), ('123', 1), ('123456', 0), ('１２３４５６', 1)]:
            with self.subTest(code=code), self.assertRaises(ValueError): verification_instructions(code, auth)

    def test_pairing_uses_vendor_reporting_flags_and_restores_unknown_bits(self):
        worker = self.session([])
        self.transport.flags = b'\xa0\x01\x40'  # Wireless was already enabled.
        self.transport.on_read = worker.cancel
        with self.assertRaises(PairingCancelled): worker.run()
        self.assertIn((0, b'\xb0\x01\x40', True), self.transport.calls)
        self.assertEqual(self.transport.calls[-1], (0, b'\xa0\x01\x40', True))

    def test_vendor_discovery_and_authentication_parameters(self):
        done = bytearray(16); done[7] = 1
        # Keyboard authentication advertised with an unfamiliar kind must
        # retain the vendor's 20-bit challenge, rather than using mouse entropy.
        worker = self.session(discovered('Keyboard', 1, 0) + [notification(0x54, 2, done)])
        worker.accept()
        worker.run()
        self.assertIn((0xC0, b'\x00\x01', True), self.transport.calls)
        self.assertIn((2, b'\x02', True), self.transport.calls)
        pair_write = next(c for c in self.transport.calls if c[0] == 0x2C1 and c[1][0] == 1)
        self.assertEqual(pair_write[1][-2:], b'\x01\x14')

    def test_keyboard_reports_each_key_and_submission_and_waits_through_nonerror_status(self):
        device_address = bytes.fromhex('010203040506')
        done = bytearray(16); done[7] = 1
        worker = self.session(discovered('MX KEYS B', 1, 1) + [
            notification(0x4D, data=b'123456'), notification(0x4E, 0, device_address),
            *[notification(0x4E, 1, device_address) for _ in range(6)],
            notification(0x4E, 4, device_address), notification(0x54, 1),
            notification(0x54, 2, done)])
        worker.accept()
        self.assertEqual(worker.run(), self.device)
        verification = [e for e in self.events if e['state'] == 'verify']
        self.assertEqual([e['entered'] for e in verification], [0, 0, 1, 2, 3, 4, 5, 6, 6])
        self.assertTrue(verification[-1]['submitted'])
        self.assertIn('Code submitted', verification[-1]['progress'])
        self.assertTrue(all('123456' in e['text'] for e in verification))

    def test_progress_from_another_keyboard_is_ignored(self):
        done = bytearray(16); done[7] = 1
        worker = self.session(discovered('MX KEYS B', 1, 1) + [
            notification(0x4D, data=b'123456'), notification(0x4E, 1, bytes(6)),
            notification(0x54, 2, done)])
        worker.accept()
        worker.run()
        self.assertEqual(len([e for e in self.events if e['state'] == 'verify']), 1)
