"""Receiver-register transport and paired-slot inventory (HID++ 1.0).

Protocol reference: pwr-Solaar/Solaar, lib/logitech_receiver/{receiver,
notifications,hidpp10,base_usb}.py at e7304c4c451cc9bb4f206a914844525e67856a28.
Solaar is Copyright Daniel Pavel and Solaar contributors, GPL-2.0-or-later.
This implementation is part of LogiOptions, GPL-3.0-only.
"""
import os
import select
import time

from .discovery import interfaces
from .hidpp import LinuxHidppTransport

# Restrict writes to receiver families whose pairing protocol is known.
PRODUCTS = {0xC548: 'bolt', 0xC52B: 'unifying', 0xC532: 'unifying'}


class ReceiverError(RuntimeError):
    def __init__(self, code):
        self.code = code
        reason = {1: 'Unsupported receiver command', 2: 'Invalid receiver address',
                  3: 'Invalid receiver value', 5: 'Receiver is full', 7: 'Receiver is busy',
                  8: 'No device in this slot', 12: 'Incorrect verification code'}.get(code)
        super().__init__(reason or f'Receiver error 0x{code:02x}')


class ReceiverTransport(LinuxHidppTransport):
    def discard_notifications(self):
        with self.lock:
            self._drain_pending()
            self.notifications.clear()

    @staticmethod
    def is_notification(report):
        return LinuxHidppTransport.valid_report(report) and report[2] < 0x80

    def _queue_notification(self, report):
        if self.is_notification(report):
            self.notifications.append(report)

    def register(self, register, payload=b'', *, write=False, timeout=2):
        if type(register) is not int or register < 0 or register & ~0x2FF:
            raise ValueError('Invalid receiver register')
        if not isinstance(payload, bytes) or len(payload) > 16 or timeout <= 0:
            raise ValueError('Invalid receiver request')
        command = (0x80 if write else 0x81) | ((register >> 8) & 2)
        # Long reads use a short request and a long reply. Long writes (0x82)
        # always need the long report, even for a two-byte unpair command.
        size = 20 if command == 0x82 or len(payload) > 3 else 7
        header = bytes([0x11 if size == 20 else 0x10, 0xFF, command, register & 255])
        packet = (header + payload).ljust(size, b'\0')
        with self.lock:
            if self.fd is None:
                raise ValueError('Transport is closed')
            self._drain_pending()
            if os.write(self.fd, packet) != size:
                raise OSError('Incomplete receiver report write')
            if self.trace:
                self.trace('out', packet)
            deadline = time.monotonic() + timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not select.select([self.fd], [], [], remaining)[0]:
                    raise TimeoutError('Receiver reply timed out')
                try:
                    reply = self._read()
                except BlockingIOError:
                    continue
                if not self.valid_report(reply):
                    continue
                self._queue_notification(reply)
                if reply[1] != 0xFF:
                    continue
                if reply[2] == 0x8F and reply[3:5] == header[2:4]:
                    raise ReceiverError(reply[5])
                if reply[2:4] == header[2:4]:
                    # All slot information shares one register: match subregister
                    # too, so a late reply cannot describe a different slot.
                    if register == 0x2B5 and reply[4:5] != payload[:1]:
                        continue
                    return reply[4:]

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
                if self.is_notification(report):
                    return report


def receiver_interfaces():
    return [dict(i, kind=PRODUCTS[i['product']],
                 name='Logi Bolt receiver' if PRODUCTS[i['product']] == 'bolt' else 'Unifying receiver')
            for i in interfaces() if i['bus'] == 3 and i['product'] in PRODUCTS]


class Receiver:
    def __init__(self, transport, descriptor):
        product = descriptor.get('product')
        if product not in PRODUCTS or descriptor.get('bus') != 3:
            raise ValueError('Pairing supports Logi Bolt and Unifying USB receivers')
        self.transport = transport
        self.kind = PRODUCTS[product]

    def serial(self):
        if self.kind == 'bolt':
            data = self.transport.register(0x2FB)
            if len(data) < 4 or not any(data):
                raise ValueError('Invalid receiver identity')
            return data.hex()
        data = self.transport.register(0x2B5, b'\x03')
        if len(data) < 7 or data[0] != 3 or not any(data[1:5]):
            raise ValueError('Invalid receiver identity')
        return data[1:5].hex()

    def paired_device(self, slot):
        if type(slot) is not int or not 1 <= slot <= 6:
            raise ValueError('Receiver slot must be between 1 and 6')
        sub = (0x50 + slot) if self.kind == 'bolt' else (0x20 + slot - 1)
        try:
            info = self.transport.register(0x2B5, bytes([sub]))
        except ReceiverError as error:
            if error.code in (2, 3, 8):
                return None
            raise
        if len(info) < 8 or info[0] != sub:
            raise ValueError('Truncated paired-device information')
        # Include the per-device serial in the unpair token, never just the slot.
        if self.kind == 'bolt':
            token = info[1:8].hex()
            kind = info[1] & 15
        else:
            extra = self.transport.register(0x2B5, bytes([0x30 + slot - 1]))
            if len(extra) < 5 or extra[0] != 0x30 + slot - 1:
                raise ValueError('Truncated paired-device identity')
            token = info[3:5].hex() + ':' + extra[1:5].hex()
            kind = info[7] & 15
        name = f'Device in slot {slot}'
        try:
            if self.kind == 'bolt':
                data = self.transport.register(0x2B5, bytes([0x60 + slot, 1]))
                offset, length = 3, data[2]
            else:
                data = self.transport.register(0x2B5, bytes([0x40 + slot - 1]))
                offset, length = 2, data[1]
            decoded = data[offset:offset + length].decode('utf-8')
            if decoded.strip() and decoded.isprintable():
                name = decoded
        except (ReceiverError, TimeoutError, ValueError, IndexError):
            pass
        return dict(slot=slot, name=name, kind=kind, token=token)

    def inventory(self):
        return dict(serial=self.serial(), devices=[device for slot in range(1, 7)
                    if (device := self.paired_device(slot)) is not None])

    def unpair(self, slot, expected_serial, expected_token):
        if self.serial() != expected_serial:
            raise RuntimeError('Receiver changed. Refresh before removing a device.')
        device = self.paired_device(slot)
        if not device or device['token'] != expected_token:
            raise RuntimeError('Paired device changed. Refresh before removing it.')
        self.transport.register(0x2C1 if self.kind == 'bolt' else 0xB2,
                                bytes([3, slot]), write=True)
        if self.paired_device(slot) is not None:
            raise RuntimeError('Receiver did not confirm removal. Refresh to check the device.')
