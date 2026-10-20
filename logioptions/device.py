"""Device reads and explicit settings changes using recovered HID++ operations."""
from .hidpp import LinuxHidppTransport, _integer
from .haptics import HapticCommand, FEATURE_ID, set_config, play_waveform


class UnsupportedFeature(RuntimeError):
    pass


class Device:
    def __init__(self, transport: LinuxHidppTransport, device_index: int):
        self.transport = transport
        self.device_index = _integer(device_index, 255, 'device index')
        self.features = {0: dict(index=0, flags=0, version=None)}

    def feature(self, feature_id):
        if feature_id not in self.features:
            self.features[feature_id] = self.transport.lookup_feature(self.device_index, feature_id)
        entry = self.features[feature_id]
        if feature_id and not entry['index']:
            raise UnsupportedFeature(f'Device does not advertise feature 0x{feature_id:04x}')
        return entry

    def request(self, feature_id, function, payload=b''):
        index = self.feature(feature_id)['index']
        return self.transport.request(self.device_index, index, function, payload)[4:]

    def name(self):
        count = self.request(0x0005, 0)[0]
        chunks = bytearray()
        while len(chunks) < count:
            reply = self.request(0x0005, 1, bytes([len(chunks)]))
            chunk = reply[:count - len(chunks)]
            if not chunk:
                raise ValueError('Empty device name chunk')
            chunks.extend(chunk)
        return bytes(chunks).decode('utf-8')

    def kind_code(self):
        return self.request(0x0005, 2)[0]

    def feature_list(self):
        count = self.request(0x0001, 0)[0]
        rows = []
        for index in range(count + 1):
            data = self.request(0x0001, 1, bytes([index]))
            if len(data) < 4:
                raise ValueError('Truncated feature-set entry')
            feature_id = int.from_bytes(data[:2], 'big')
            entry = dict(index=index, flags=data[2], version=data[3])
            self.features[feature_id] = entry
            rows.append(dict(id=f'{feature_id:04X}', **entry))
        return rows

    def battery_status(self):
        data = self.request(0x1004, 1)
        return dict(percentage=data[0] if data[0] <= 100 else None, raw_status_hex=data.hex())

    def haptic_config_bytes(self):
        data = self.request(0x19B0, 1)
        if len(data) < 2:
            raise ValueError('Truncated haptic configuration')
        return data

    def haptic_config(self):
        raw = self.haptic_config_bytes()
        return dict(flags=raw[0], enabled=bool(raw[0] & 1),
                    power_save=bool(raw[0] & 2), level=raw[1])

    def set_haptic_feedback(self, enabled, level):
        if not isinstance(enabled, bool):
            raise ValueError('Feedback enabled must be boolean')
        level = _integer(level, 100, 'haptic strength')
        if level < 1:
            raise ValueError('Haptic strength must be between 1 and 100')
        before = self.haptic_config_bytes()
        flags = (before[0] & ~1) | int(enabled)
        self.execute_haptic(set_config(flags & ~2, bool(flags & 2), level))
        actual = self.haptic_config()
        if actual['flags'] != flags or actual['level'] != level:
            raise ValueError('The device did not accept the feedback setting')
        return actual

    def test_haptic_feedback(self, enabled, level):
        if not enabled:
            raise ValueError('Enable feedback before testing a vibration')
        actual = self.set_haptic_feedback(enabled, level)
        self.execute_haptic(play_waveform(7))
        return actual

    def execute_haptic(self, command: HapticCommand):
        if not isinstance(command, HapticCommand) or command.feature_id != FEATURE_ID:
            raise ValueError('Expected a recovered haptic feature command')
        return self.request(command.feature_id, command.function, command.payload)

    def dpi(self, sensor=0):
        sensor = _integer(sensor, 255, 'sensor')
        data = self.request(0x2201, 2, bytes([sensor]))
        if len(data) < 3 or data[0] != sensor:
            raise ValueError('Truncated DPI response')
        return dict(sensor=sensor, current=int.from_bytes(data[1:3], 'big'), raw_hex=data.hex())

    def dpi_limits(self, sensor=0):
        sensor = _integer(sensor, 255, 'sensor')
        data = self.request(0x2201, 1, bytes([sensor]))
        if len(data) < 5 or data[0] != sensor:
            raise ValueError('Invalid DPI-list response')
        values, step = [], 0
        for offset in range(1, len(data) - 1, 2):
            high, low = data[offset:offset + 2]
            value = high << 8 | low
            if not value:
                break
            if high == 0xE0:
                step = low
            else:
                values.append(value)
        if not values or (step and (len(values) != 2 or values[0] > values[1])):
            raise ValueError('Invalid device DPI list/range')
        return dict(values=values, step=step, raw_hex=data.hex())

    def set_dpi(self, dpi, *, sensor=0, level_byte=0):
        dpi = _integer(dpi, 65535, 'DPI')
        sensor = _integer(sensor, 255, 'sensor')
        level_byte = _integer(level_byte, 255, 'DPI level byte')
        limits = self.dpi_limits(sensor)
        values, step = limits['values'], limits['step']
        allowed = (len(values) == 2 and values[0] <= dpi <= values[1] and (dpi - values[0]) % step == 0) if step else dpi in values
        if not allowed:
            raise ValueError('Requested DPI is not in the device-advertised list/range')
        payload = bytes([sensor]) + dpi.to_bytes(2, 'big')
        if self.feature(0x2201)['version'] >= 2:
            payload += bytes([level_byte])
        return self.request(0x2201, 3, payload)

    def smartshift(self):
        data = self.request(0x2111, 1)
        if len(data) < 3:
            raise ValueError('Truncated SmartShift response')
        return dict(mode_code=data[0], threshold=data[1], torque=data[2], raw_hex=data.hex())

    def set_smartshift_bytes(self, mode, threshold, torque):
        payload = bytes([_integer(mode, 255, 'mode'), _integer(threshold, 255, 'threshold'), _integer(torque, 255, 'torque')])
        return self.request(0x2111, 2, payload)

    def controls(self):
        count = self.request(0x1B04, 0)[0]
        rows = []
        for index in range(count):
            data = self.request(0x1B04, 1, bytes([index]))
            if len(data) < 9:
                raise ValueError('Truncated control-info response')
            rows.append(dict(index=index, control_id=int.from_bytes(data[:2], 'big'),
                             task_id=int.from_bytes(data[2:4], 'big'),
                             flags=data[4] | data[8] << 8, position=data[5],
                             group=data[6], group_mask=data[7], raw_hex=data.hex()))
        return rows

    def control_reporting(self, control_id):
        control_id = _integer(control_id, 65535, 'control ID')
        data = self.request(0x1B04, 2, control_id.to_bytes(2, 'big'))
        if len(data) < 6 or int.from_bytes(data[:2], 'big') != control_id:
            raise ValueError('Invalid control-reporting response')
        return dict(control_id=control_id, flags=data[2], remapped_to=int.from_bytes(data[3:5], 'big'),
                    flags_extra=data[5], raw_hex=data.hex())

    def set_control_reporting_bytes(self, control_id, flags, remapped_to, flags_extra=0):
        control_id = _integer(control_id, 65535, 'control ID')
        remapped_to = _integer(remapped_to, 65535, 'remapped control ID')
        payload = (control_id.to_bytes(2, 'big') + bytes([_integer(flags, 255, 'reporting flags')])
                   + remapped_to.to_bytes(2, 'big') + bytes([_integer(flags_extra, 255, 'extra flags')]))
        return self.request(0x1B04, 3, payload)

    def remap_control(self, control_id, target_id):
        controls = {row['control_id']: row for row in self.controls()}
        if control_id not in controls or target_id not in controls:
            raise ValueError('Control is not in the device control table')
        source, target = controls[control_id], controls[target_id]
        if not source['flags'] & 0x10:
            raise ValueError('Control does not advertise hardware reprogramming')
        if target['group'] < 1 or not source['group_mask'] & (1 << (target['group'] - 1)):
            raise ValueError('Destination is outside the source control group mask')
        return self.set_control_reporting_bytes(control_id, 0, target_id)

    def inspect(self):
        result = dict(device_index=self.device_index, name=self.name(), kind_code=self.kind_code(), features=self.feature_list())
        if 0x1004 in self.features:
            result['battery'] = self.battery_status()
        if 0x19B0 in self.features:
            result['haptic_config_hex'] = self.haptic_config_bytes().hex()
        return result
