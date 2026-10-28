"""Linux HID++ transport with correlated requests and bounded report sizes.

The feature-call header and root lookup payload were traced in the official 2.8
agent. See research/HIDPP.md. This module does not pair devices or alter settings
on construction. Callers choose each feature operation explicitly.
"""
import os
import fcntl
from collections import deque
from pathlib import Path
import select
import stat
import threading
import time


def _integer(value, maximum, name):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        raise ValueError(f'Invalid {name}')
    return value


def encode_report(device_index, feature_index, function, software_id, payload=b''):
    device_index = _integer(device_index, 255, 'device index')
    feature_index = _integer(feature_index, 255, 'feature index')
    function = _integer(function, 15, 'function')
    software_id = _integer(software_id, 15, 'software ID')
    if software_id == 0:
        raise ValueError('Software ID zero is reserved for notifications')
    if not isinstance(payload, bytes) or len(payload) > 16:
        raise ValueError('Expected at most 16 payload bytes')
    report_id, size = (0x10, 7) if len(payload) <= 3 else (0x11, 20)
    return (bytes([report_id, device_index, feature_index, function << 4 | software_id]) + payload).ljust(size, b'\0')


def root_lookup_payload(feature_id):
    return _integer(feature_id, 65535, 'feature ID').to_bytes(2, 'big')


class HidppError(RuntimeError):
    def __init__(self, report):
        self.report = report
        self.code = report[5]
        super().__init__(f'HID++ error 0x{self.code:02x}: {report.hex()}')


class LinuxHidppTransport:
    def __init__(self, path, *, software_id=1, trace=None):
        path = Path(path)
        if not path.name.startswith('hidraw') or not path.name[6:].isdigit():
            raise ValueError('Expected a hidraw device')
        properties = (Path('/sys/class/hidraw') / path.name / 'device/uevent').read_text()
        identity = next(line.split('=', 1)[1] for line in properties.splitlines() if line.startswith('HID_ID='))
        if int(identity.split(':')[1], 16) != 0x046D:
            raise ValueError('Device is not Logitech')
        if not stat.S_ISCHR(path.stat().st_mode):
            raise ValueError('Expected a character device')
        self.software_id = _integer(software_id, 15, 'software ID')
        if not self.software_id:
            raise ValueError('Software ID zero is reserved')
        self.trace = trace
        self.lock = threading.Lock()
        self.notifications = deque(maxlen=1024)
        self.fd = os.open(path, os.O_RDWR | os.O_NONBLOCK | os.O_CLOEXEC)
        try:
            # Serialize our own processes. Solaar uses IDs 2..15; default ID 1
            # keeps its replies separate without stopping the user's service.
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.close()
            raise OSError('Another device operation is running; try again when it finishes') from None

    @staticmethod
    def valid_report(report):
        return bool(report) and len(report) == {0x10: 7, 0x11: 20}.get(report[0])

    def _read(self):
        report = os.read(self.fd, 64)
        if not report:
            raise OSError('HID device disconnected')
        if self.trace:
            self.trace('in', report)
        return report

    def _queue_notification(self, report):
        if self.valid_report(report) and report[3] & 15 == 0:
            self.notifications.append(report)

    def _drain_pending(self):
        # A reply already queued before a new request cannot answer that request.
        # Retain genuine notifications instead of losing button presses.
        for _ in range(1024):
            if not select.select([self.fd], [], [], 0)[0]:
                return
            try:
                self._queue_notification(self._read())
            except BlockingIOError:
                return
        raise OSError('Device report queue did not drain; retry the operation')

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def request(self, device_index, feature_index, function, payload=b'', *, timeout=2):
        if timeout <= 0:
            raise ValueError('Timeout must be positive')
        packet = encode_report(device_index, feature_index, function, self.software_id, payload)
        with self.lock:
            if self.fd is None:
                raise ValueError('Transport is closed')
            self._drain_pending()
            if os.write(self.fd, packet) != len(packet):
                raise OSError('Incomplete HID report write')
            if self.trace:
                self.trace('out', packet)
            deadline = time.monotonic() + timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not select.select([self.fd], [], [], remaining)[0]:
                    raise TimeoutError('HID++ reply timed out')
                try:
                    report = self._read()
                except BlockingIOError:
                    continue
                if not self.valid_report(report):
                    continue
                self._queue_notification(report)
                if report[1] != device_index:
                    continue
                if report[2] in (0xFF, 0x8F) and report[3:5] == packet[2:4]:
                    raise HidppError(report)
                if report[2:4] == packet[2:4]:
                    return report

    def lookup_feature(self, device_index, feature_id, *, timeout=2):
        payload = root_lookup_payload(feature_id)
        for _ in range(3):
            report = self.request(device_index, 0, 0, payload, timeout=timeout)
            index = report[4]
            if index:
                # ROOT replies do not echo the requested feature ID. A late
                # firmware lookup can otherwise route name reads to firmware
                # info (whose first entity starts with b'\x01BL'). FEATURE SET
                # is the mandatory feature at index 1; reverse-check the index
                # before caching or using it, including for settings writes.
                entry = self.request(device_index, 1, 1, bytes([index]), timeout=timeout)
                if entry[4:6] != payload:
                    continue
            return dict(index=index, flags=report[5], version=report[6], report_hex=report.hex())
        raise TimeoutError(f'Could not verify HID++ feature 0x{feature_id:04x}; retry the operation')

    def read_notification(self, *, timeout=1):
        if timeout <= 0:
            raise ValueError('Timeout must be positive')
        with self.lock:
            if self.fd is None:
                raise ValueError('Transport is closed')
            if self.notifications:
                return self.notifications.popleft()
            deadline = time.monotonic() + timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not select.select([self.fd], [], [], remaining)[0]:
                    return None
                try:
                    report = self._read()
                except BlockingIOError:
                    continue
                if self.valid_report(report) and report[3] & 15 == 0:
                    return report
