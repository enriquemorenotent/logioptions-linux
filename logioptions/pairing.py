"""Cancellable Bolt/Unifying pairing, including Bolt physical authentication.

Receiver protocol reference and attribution are recorded in receiver.py.
All calls run while the caller holds background.foreground_access().
"""
import threading
import time
import logging

LOG = logging.getLogger(__name__)


class PairingCancelled(RuntimeError):
    pass


def verification_instructions(passkey, authentication):
    if len(passkey) != 6 or not passkey.isascii() or not passkey.isdecimal():
        raise ValueError('Invalid Bolt verification code')
    if authentication & 1:
        return f'Type {passkey} on the keyboard being paired, then press Enter.'
    value = int(passkey)
    if value >= 1024:
        raise ValueError('Invalid mouse verification code')
    clicks = ' → '.join('Right' if bit == '1' else 'Left' for bit in f'{value:010b}')
    return f'On the mouse being paired, click:\n{clicks}\nThen press the left and right buttons together.'


class PairingSession:
    def __init__(self, receiver, expected_serial, emit, *, cancelled=None,
                 timeout=30, verification_timeout=120, clock=time.monotonic):
        self.receiver = receiver
        self.transport = receiver.transport
        self.expected_serial = expected_serial
        self.emit = emit
        self.cancelled = cancelled if cancelled is not None else threading.Event()
        self.accepted = threading.Event()
        self.timeout = timeout
        self.verification_timeout = verification_timeout
        self.clock = clock
        self.discovery_open = False
        self.pairing_open = False

    def cancel(self):
        self.cancelled.set()

    def accept(self):
        self.accepted.set()

    def check(self, deadline):
        if self.cancelled.is_set():
            raise PairingCancelled('Pairing cancelled.')
        if self.clock() >= deadline:
            raise TimeoutError('Pairing timed out. Put the device in pairing mode and try again.')

    def notify(self, state, text, **extra):
        # Deliberately exclude instruction text: it contains the passcode.
        LOG.info('Pairing phase: %s%s', state, ' · ' + extra['progress'] if extra.get('progress') else '')
        self.emit(dict(state=state, text=text, **extra))

    def run(self):
        inventory = self.receiver.inventory()
        if inventory['serial'] != self.expected_serial:
            raise RuntimeError('Receiver changed. Refresh before pairing.')
        if len(inventory['devices']) >= 6:
            raise RuntimeError('Receiver is full. Remove a paired device first.')
        old_flags = self.transport.register(0)
        if len(old_flags) != 3:
            raise ValueError('Invalid receiver notification flags')
        # Match Logitech Web Connect's bootHidppRap: preserve existing flags,
        # enable device reporting (0x10 in byte 0) and receiver wireless events
        # (0x01 in byte 1). Do not replace them with Solaar's initialization.
        flags = bytes([old_flags[0] | 0x10, old_flags[1] | 1, old_flags[2]])
        LOG.info('Pairing notifications: %s -> %s', old_flags.hex(), flags.hex())
        try:
            if flags != old_flags:
                self.transport.register(0, flags, write=True)
            # Web Connect requests the receiver's current device-arrival state
            # after initializing reporting, before it starts discovery.
            self.transport.register(2, b'\x02', write=True)
            self.transport.discard_notifications()
            self.check(self.clock() + self.timeout)
            if self.receiver.kind == 'bolt':
                return self._bolt()
            return self._unifying(inventory['devices'])
        finally:
            errors = []
            commands = []
            if self.pairing_open:
                commands.append((0x2C1, b'\x02\x00' + bytes(8)) if self.receiver.kind == 'bolt'
                                else (0xB2, b'\x02\x00\x00'))
            if self.discovery_open:
                commands.append((0xC0, b'\x00\x02'))
            for register, payload in commands:
                try:
                    self.transport.register(register, payload, write=True)
                except Exception as error:
                    errors.append(str(error))
            if flags != old_flags:
                try:
                    self.transport.register(0, old_flags, write=True)
                except Exception as error:
                    errors.append(str(error))
            if errors:
                raise RuntimeError('Receiver cleanup could not be confirmed. Refresh to check pairing status. '
                                   + '; '.join(errors))

    def _bolt(self):
        self.discovery_open = True  # Also clean up a start command that times out.
        # Web Connect passes zero for the receiver's discovery timeout. Keep
        # our own bounded host deadline independently of this wire parameter.
        self.transport.register(0xC0, b'\x00\x01', write=True)
        self.notify('searching', 'Hold the device’s Easy-Switch button until its channel light blinks quickly. Looking for a Bolt device…')
        deadline = self.clock() + self.timeout
        candidate = {}
        counter = None
        pairing = False
        verification_text = None
        keypresses = 0
        while True:
            self.check(deadline)
            report = self.transport.read_notification(timeout=.1)
            if report is None or report[1] != 0xFF:
                continue
            event, address, data = report[2], report[3], report[4:]
            if event in (0x53, 0x54):
                LOG.info('Receiver %s status=%d error=%d', 'discovery' if event == 0x53 else 'pairing', address, data[0])
                if event == 0x53:
                    self.discovery_open = address == 0
                else:
                    self.pairing_open = address == 0
                if data[0]:
                    reason = 'Device timed out' if data[0] == 1 else 'Device verification failed'
                    raise RuntimeError(reason + '. Try pairing again.')
                if event == 0x53 and address != 0 and not pairing:
                    raise TimeoutError('No Bolt device found. Put the device in pairing mode and try again.')
                if event == 0x54:
                    if address == 2:
                        if not pairing or len(data) < 8 or not 1 <= data[7] <= 6:
                            raise ValueError('Invalid Bolt pairing completion')
                        device = self.receiver.paired_device(data[7])
                        if device is None:
                            raise RuntimeError('Pairing reported success but no paired device could be read. Refresh to check.')
                        self.discovery_open = False
                        return device
                    # A non-error status is not a terminal failure. Wait for
                    # explicit completion (2), a receiver error, or our deadline.
            elif event == 0x4F and not pairing:
                if len(data) < 3:
                    raise ValueError('Truncated Bolt discovery')
                packet_counter = address + (data[0] << 8)
                if counter is None:
                    counter = packet_counter
                if counter != packet_counter:
                    continue
                if data[1] == 0:
                    if len(data) < 15:
                        raise ValueError('Truncated Bolt device information')
                    candidate.update(kind=data[3], address=data[6:12], authentication=data[14])
                elif data[1] == 1:
                    length = data[2]
                    if not 0 < length <= len(data) - 3:
                        raise ValueError('Invalid Bolt device name length')
                    name = data[3:3 + length].decode('utf-8')
                    if not name.strip() or not name.isprintable():
                        raise ValueError('Invalid Bolt device name')
                    candidate['name'] = name
                if all(k in candidate for k in ('name', 'address', 'authentication', 'kind')):
                    self.notify('found', f'Found {candidate["name"]}. Pair this device?', name=candidate['name'])
                    while not self.accepted.wait(.1):
                        self.check(deadline)
                    self.check(deadline)
                    # The vendor selects 10 bits for two-button authentication
                    # (method 2), otherwise 20; it does not infer this from kind.
                    entropy = 10 if candidate['authentication'] == 2 else 20
                    LOG.info('Pairing authentication method=%d entropy=%d', candidate['authentication'], entropy)
                    payload = b'\x01\x00' + candidate['address'] + bytes([candidate['authentication'], entropy])
                    pairing = True
                    self.pairing_open = True
                    # A new phase gets enough time to complete physical verification.
                    deadline = self.clock() + self.verification_timeout
                    self.transport.register(0x2C1, payload, write=True)
                    self.notify('pairing', f'Connecting to {candidate["name"]}…')
            elif event == 0x4D and pairing:
                verification_text = verification_instructions(data[:6].decode('ascii'), candidate['authentication'])
                keypresses = 0
                self.notify('verify', verification_text, progress='Waiting for input on the device being paired.', entered=0)
            elif event == 0x4E and pairing and verification_text:
                # These are receiver-reported entry events, not host keystrokes.
                # Ignore activity from a different device; never record digits.
                if data[:6] != candidate['address']:
                    continue
                if address == 0:
                    keypresses = 0
                    progress = 'Ready. Enter the code on the device being paired.'
                elif address == 1:
                    keypresses += 1
                    expected = 6 if candidate['authentication'] & 1 else 10
                    progress = f'Input detected · {keypresses} of {expected} keypresses. '
                    progress += ('Press Enter after all six digits.' if candidate['authentication'] & 1
                                 else 'Press both buttons together after the sequence.')
                elif address == 4:
                    progress = 'Code submitted. Waiting for the receiver to verify it…'
                else:
                    progress = 'Input activity detected on the device being paired.'
                self.notify('verify', verification_text, progress=progress, entered=keypresses, submitted=address == 4)

    def _unifying(self, devices):
        previous = {d['slot']: d['token'] for d in devices}
        self.pairing_open = True
        self.transport.register(0xB2, bytes([1, 0, self.timeout]), write=True)
        self.notify('searching', 'Turn the Unifying device off and on, or hold its Easy-Switch button until the channel light blinks quickly. Only put the device you want to add in pairing mode.')
        deadline = self.clock() + self.timeout + 2
        while True:
            self.check(deadline)
            report = self.transport.read_notification(timeout=.1)
            if report is None:
                continue
            event, address, data = report[2], report[3], report[4:]
            if report[1] == 0xFF and event == 0x4A:
                self.pairing_open = bool(address & 1)
                if data[0]:
                    reason = {1: 'Device timed out', 2: 'Device is not compatible with this receiver',
                              3: 'Receiver is full', 6: 'Pairing sequence timed out'}.get(data[0], 'Pairing failed')
                    raise RuntimeError(reason)
                if not address & 1:
                    # The connection notification can arrive before or after lock
                    # closure. Read the actual slot table instead of guessing.
                    for device in self.receiver.inventory()['devices']:
                        if previous.get(device['slot']) != device['token']:
                            return device
                    raise RuntimeError('Pairing ended without a new device. Try again.')
            if 1 <= report[1] <= 6 and event == 0x41:
                device = self.receiver.paired_device(report[1])
                if device and previous.get(device['slot']) != device['token']:
                    return device
