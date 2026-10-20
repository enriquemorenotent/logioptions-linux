from collections import deque
import socket
import threading
import unittest

from logioptions.hidpp import LinuxHidppTransport, HidppError


class TransportTests(unittest.TestCase):
    def setUp(self):
        client, self.peer = socket.socketpair(type=socket.SOCK_DGRAM)
        client.setblocking(False)
        self.peer.settimeout(1)
        self.transport = object.__new__(LinuxHidppTransport)
        self.transport.fd = client.detach()
        self.transport.software_id = 1
        self.transport.trace = None
        self.transport.lock = threading.Lock()
        self.transport.notifications = deque(maxlen=1024)

    def tearDown(self):
        self.transport.close()
        self.peer.close()

    def exchange(self, replies, operation):
        failures = []
        def receiver():
            try:
                request = self.peer.recv(64)
                self.assertEqual(request[:4], bytes.fromhex('10020b11'))
                for reply in replies:
                    self.peer.send(bytes.fromhex(reply))
            except Exception as error:
                failures.append(error)
        thread = threading.Thread(target=receiver)
        thread.start()
        try:
            return operation()
        finally:
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
            if failures:
                raise failures[0]

    def test_stale_and_other_client_replies_cannot_answer_new_request(self):
        self.peer.send(bytes.fromhex('11020b11010a0000000000000000000000000000'))
        fresh = '11020b11015a0000000000000000000000000000'
        result = self.exchange([
            '11020b1e013c0000000000000000000000000000',  # Solaar's ID
            '11020b1101',  # truncated
            fresh,
        ], lambda: self.transport.request(2, 11, 1, timeout=.5))
        self.assertEqual(result.hex(), fresh)

    def test_notifications_survive_requests(self):
        press = '11020d0001a00000000000000000000000000000'
        release = '11020d0000000000000000000000000000000000'
        self.peer.send(bytes.fromhex(press))
        self.exchange([release, '11020b11013c0000000000000000000000000000'],
                      lambda: self.transport.request(2, 11, 1, timeout=.5))
        self.assertEqual(self.transport.read_notification().hex(), press)
        self.assertEqual(self.transport.read_notification().hex(), release)

    def test_both_error_formats_and_timeout(self):
        for reply in ['1102ff0b11070000000000000000000000000000', '10028f0b110400']:
            with self.subTest(reply=reply), self.assertRaises(HidppError):
                self.exchange([reply], lambda: self.transport.request(2, 11, 1, timeout=.1))
        with self.assertRaises(TimeoutError):
            self.exchange([], lambda: self.transport.request(2, 11, 1, timeout=.02))
