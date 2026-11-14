from collections import deque
import socket
import threading
import unittest
from unittest.mock import Mock, patch

from logioptions.receiver import ReceiverTransport, Receiver, ReceiverError, receiver_interfaces

BOLT = dict(product=0xC548, bus=3)
UNIFYING = dict(product=0xC52B, bus=3)


def report(command, address, data=b'', device=255, long=True):
    return (bytes([0x11 if long else 0x10, device, command, address]) + data).ljust(20 if long else 7, b'\0')


class ReceiverTransportTests(unittest.TestCase):
    def setUp(self):
        client, self.peer = socket.socketpair(type=socket.SOCK_DGRAM)
        client.setblocking(False)
        self.peer.settimeout(1)
        self.transport = object.__new__(ReceiverTransport)
        self.transport.fd = client.detach()
        self.transport.trace = None
        self.transport.lock = threading.Lock()
        self.transport.notifications = deque(maxlen=1024)

    def tearDown(self):
        self.transport.close()
        self.peer.close()

    def exchange(self, expected, replies, operation):
        failures = []
        def receiver():
            try:
                self.assertEqual(self.peer.recv(64), expected)
                for reply in replies:
                    self.peer.send(reply)
            except Exception as error:
                failures.append(error)
        thread = threading.Thread(target=receiver)
        thread.start()
        try:
            return operation()
        finally:
            thread.join(2)
            self.assertFalse(thread.is_alive())
            if failures:
                raise failures[0]

    def test_long_read_uses_short_request_matches_slot_and_queues_nonzero_address_events(self):
        notification = report(0x4F, 0x39, bytes(16))
        stale_slot = report(0x83, 0xB5, b'\x51' + bytes(15))
        valid = report(0x83, 0xB5, b'\x52\x02' + bytes(14))
        self.peer.send(stale_slot)
        result = self.exchange(bytes.fromhex('10ff83b5520000'),
                               [stale_slot, notification, valid],
                               lambda: self.transport.register(0x2B5, b'\x52', timeout=.1))
        self.assertEqual(result, valid[4:])
        self.assertEqual(self.transport.read_notification(), notification)

    def test_bolt_unpair_and_pair_packets_use_long_write(self):
        for payload in [b'\x03\x02', b'\x01\x00' + bytes.fromhex('010203040506') + b'\x01\x14']:
            packet = (b'\x11\xff\x82\xc1' + payload).ljust(20, b'\0')
            self.exchange(packet, [report(0x82, 0xC1)],
                          lambda: self.transport.register(0x2C1, payload, write=True, timeout=.1))

    def test_error_and_timeout_are_not_success(self):
        packet = bytes.fromhex('10ff81b2000000')
        with self.assertRaises(ReceiverError) as caught:
            self.exchange(packet, [bytes.fromhex('10ff8f81b20700')],
                          lambda: self.transport.register(0xB2, timeout=.05))
        self.assertEqual(caught.exception.code, 7)
        with self.assertRaises(TimeoutError):
            self.exchange(packet, [], lambda: self.transport.register(0xB2, timeout=.01))

    def test_discard_and_read_notifications_ignore_reply_packets(self):
        self.peer.send(report(0x4A, 1))
        self.transport.discard_notifications()
        self.peer.send(report(0x83, 0xB5))
        event = report(0x4A, 1)
        self.peer.send(event)
        self.assertEqual(self.transport.read_notification(timeout=.05), event)
        self.assertIsNone(self.transport.read_notification(timeout=.01))


class ReceiverInventoryTests(unittest.TestCase):
    def test_only_known_usb_receiver_families_are_writable(self):
        with patch('logioptions.receiver.interfaces', return_value=[
            dict(path='bolt', product=0xC548, bus=3), dict(path='unifying', product=0xC52B, bus=3),
            dict(path='bluetooth', product=0xC548, bus=5), dict(path='nano', product=0xC534, bus=3)]):
            self.assertEqual([i['path'] for i in receiver_interfaces()], ['bolt', 'unifying'])
        with self.assertRaises(ValueError):
            Receiver(Mock(), dict(product=0xC534, bus=3))

    def test_bolt_sleeping_device_inventory_uses_receiver_registers(self):
        transport = Mock()
        def read(register, payload=b'', **kwargs):
            if register == 0x2FB:
                return bytes.fromhex('01020304') + bytes(12)
            if payload == b'\x52':
                return bytes.fromhex('5202341201020304') + bytes(8)
            if payload == b'\x62\x01':
                return b'\x62\x01\x0bMX Master 4\0\0'
            raise ReceiverError(3)
        transport.register.side_effect = read
        inventory = Receiver(transport, BOLT).inventory()
        self.assertEqual(inventory['devices'], [dict(slot=2, name='MX Master 4', kind=2, token='02341201020304')])
        self.assertTrue(all(call.args[0] in (0x2FB, 0x2B5) for call in transport.register.call_args_list))

    def test_unifying_slot_numbering_and_serial_identity(self):
        transport = Mock()
        transport.register.side_effect = [bytes.fromhex('2400081234000002') + bytes(8),
                                         bytes.fromhex('3401020304') + bytes(11),
                                         b'\x44\x03M80' + bytes(11)]
        actual = Receiver(transport, UNIFYING).paired_device(5)
        self.assertEqual(actual, dict(slot=5, name='M80', kind=2, token='1234:01020304'))
        self.assertEqual([c.args[1] for c in transport.register.call_args_list], [b'\x24', b'\x34', b'\x44'])

    def test_unreadable_slot_is_not_silently_treated_as_empty(self):
        transport = Mock()
        for error in [TimeoutError('asleep'), ReceiverError(7), ValueError('bad')]:
            transport.register.side_effect = error
            with self.subTest(error=error), self.assertRaises(type(error)):
                Receiver(transport, BOLT).inventory()

    def test_unpair_verifies_receiver_and_slot_then_confirms_absence(self):
        for descriptor, register in [(BOLT, 0x2C1), (UNIFYING, 0xB2)]:
            receiver = Receiver(Mock(), descriptor)
            receiver.serial = Mock(return_value='receiver')
            receiver.paired_device = Mock(side_effect=[dict(token='device'), None])
            receiver.unpair(2, 'receiver', 'device')
            receiver.transport.register.assert_called_once_with(register, b'\x03\x02', write=True)
        for actual_serial, token in [('other receiver', 'device'), ('receiver', 'other device')]:
            receiver = Receiver(Mock(), BOLT)
            receiver.serial = Mock(return_value=actual_serial)
            receiver.paired_device = Mock(return_value=dict(token=token))
            with self.assertRaisesRegex(RuntimeError, 'changed'):
                receiver.unpair(2, 'receiver', 'device')
            receiver.transport.register.assert_not_called()
        receiver = Receiver(Mock(), BOLT)
        receiver.serial = Mock(return_value='receiver')
        receiver.paired_device = Mock(return_value=dict(token='device'))
        with self.assertRaisesRegex(RuntimeError, 'did not confirm'):
            receiver.unpair(2, 'receiver', 'device')
