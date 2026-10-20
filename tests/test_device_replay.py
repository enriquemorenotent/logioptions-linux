import json
from pathlib import Path
import unittest

from logioptions.device import Device
from logioptions.hidpp import LinuxHidppTransport, encode_report
from logioptions.haptics import play_waveform

ROOT = Path(__file__).resolve().parents[1]


class ReplayTransport:
    lookup_feature = LinuxHidppTransport.lookup_feature

    def __init__(self, testcase, traffic):
        self.testcase = testcase
        self.traffic = traffic
        self.position = 0

    def request(self, device_index, feature_index, function, payload=b'', **kwargs):
        packet = encode_report(device_index, feature_index, function, 14, payload)
        outgoing = self.traffic[self.position]
        self.testcase.assertEqual(outgoing, dict(direction='out', hex=packet.hex()))
        self.position += 1
        while self.position < len(self.traffic):
            row = self.traffic[self.position]
            self.position += 1
            self.testcase.assertEqual(row['direction'], 'in')
            report = bytes.fromhex(row['hex'])
            if report[1:4] == packet[1:4]:
                return report
        raise AssertionError('Recorded request has no correlated reply')


class DeviceReplayTests(unittest.TestCase):
    def load_recording(self, prefix):
        traffic = ROOT / 'artifacts' / (prefix + '-traffic.jsonl')
        result = ROOT / 'artifacts' / (prefix + '.json')
        if not traffic.exists() or not result.exists():
            self.skipTest('Requires physical-device capture: ' + prefix)
        transport = ReplayTransport(self, [json.loads(line) for line in traffic.read_text().splitlines()])
        return transport, json.loads(result.read_text())

    def test_user_confirmed_haptic_command_matches_capture(self):
        transport, expected = self.load_recording('linux-mx-master-4-haptic-play-retry')
        device = Device(transport, 2)
        self.assertEqual(device.name(), expected['name'])
        response = device.execute_haptic(play_waveform(expected['waveform']))
        self.assertEqual(response.hex(), expected['response_hex'])
        self.assertEqual(transport.position, len(transport.traffic))

    def test_dpi_write_read_restore_matches_capture(self):
        transport, expected = self.load_recording('linux-dpi-roundtrip')
        device = Device(transport, 2)
        self.assertEqual(device.name(), expected['name'])
        self.assertEqual(device.dpi(), expected['before'])
        self.assertEqual(device.dpi_limits(), expected['limits'])
        device.set_dpi(expected['changed']['current'])
        self.assertEqual(device.dpi(), expected['changed'])
        device.set_dpi(expected['before']['current'])
        self.assertEqual(device.dpi(), expected['restored'])
        self.assertEqual(transport.position, len(transport.traffic))

    def test_smartshift_write_read_restore_matches_capture(self):
        transport, expected = self.load_recording('linux-smartshift-roundtrip')
        device = Device(transport, 2)
        self.assertEqual(device.name(), expected['name'])
        self.assertEqual(device.smartshift(), expected['before'])
        changed, before = expected['changed'], expected['before']
        device.set_smartshift_bytes(changed['mode_code'], changed['threshold'], changed['torque'])
        self.assertEqual(device.smartshift(), changed)
        device.set_smartshift_bytes(before['mode_code'], before['threshold'], before['torque'])
        self.assertEqual(device.smartshift(), expected['restored'])
        self.assertEqual(transport.position, len(transport.traffic))

    def test_hardware_remap_write_read_restore_matches_capture(self):
        transport, expected = self.load_recording('linux-remap-roundtrip')
        device = Device(transport, 2)
        self.assertEqual(device.name(), expected['name'])
        before = expected['before']
        self.assertEqual(device.control_reporting(before['control_id']), before)
        device.remap_control(before['control_id'], expected['changed']['remapped_to'])
        self.assertEqual(device.control_reporting(before['control_id']), expected['changed'])
        device.set_control_reporting_bytes(before['control_id'], 0, before['remapped_to'])
        self.assertEqual(device.control_reporting(before['control_id']), expected['restored'])
        self.assertEqual(transport.position, len(transport.traffic))
    def test_keyboard_inspection_matches_physical_capture(self):
        traffic = ROOT / 'artifacts/linux-keyboard-traffic.jsonl'
        inspection = ROOT / 'artifacts/linux-keyboard-inspection.json'
        if not traffic.exists() or not inspection.exists():
            self.skipTest('Requires the captured physical Bolt keyboard transaction')
        rows = [json.loads(line) for line in traffic.read_text().splitlines()]
        transport = ReplayTransport(self, rows)
        result = Device(transport, 1).inspect()
        self.assertEqual(result, json.loads(inspection.read_text()))
        self.assertEqual(result['name'], 'MX Keys for Business')
        self.assertEqual(transport.position, len(rows))

    def test_mouse_inspection_matches_physical_capture(self):
        traffic = ROOT / 'artifacts/linux-mx-master-4-traffic.jsonl'
        inspection = ROOT / 'artifacts/linux-mx-master-4-inspection.json'
        if not traffic.exists() or not inspection.exists():
            self.skipTest('Requires the captured physical MX Master 4 transaction')
        rows = [json.loads(line) for line in traffic.read_text().splitlines()]
        transport = ReplayTransport(self, rows)
        result = Device(transport, 2).inspect()
        self.assertEqual(result, json.loads(inspection.read_text()))
        self.assertEqual(result['name'], 'MX Master 4')
        self.assertEqual(transport.position, len(rows))
