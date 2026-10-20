import json
from pathlib import Path
import unittest

from logioptions.events import ControlTracker
from logioptions.events import capture_control
from logioptions.device import Device
from test_device_replay import ReplayTransport


class ControlEventsTests(unittest.TestCase):
    def test_capture_restores_reporting_on_success_and_cancellation(self):
        capture = Path(__file__).resolve().parents[1] / 'artifacts/linux-thumbpad-confirmed-window.json'
        if not capture.exists():
            self.skipTest('Requires physical thumb-pad recording')
        recording = json.loads(capture.read_text())
        for cancelled in (False, True):
            with self.subTest(cancelled=cancelled):
                traffic = recording['trace']
                if cancelled:
                    event_hex = {event['report_hex'] for event in recording['events']}
                    traffic = [row for row in traffic if row['hex'] not in event_hex]
                transport = ReplayTransport(self, traffic)
                def notification(**_):
                    row = transport.traffic[transport.position]
                    self.assertEqual(row['direction'], 'in')
                    transport.position += 1
                    return bytes.fromhex(row['hex'])
                transport.read_notification = notification
                device = Device(transport, 2)
                self.assertEqual(device.name(), recording['name'])
                ready = []
                if cancelled:
                    with self.assertRaises(TimeoutError):
                        capture_control(device, 416, ready=lambda: ready.append(True), cancelled=lambda: True)
                else:
                    changes = capture_control(device, 416, ready=lambda: ready.append(True))
                    self.assertEqual(changes[-1].released, (416,))
                self.assertEqual(ready, [True])
                self.assertEqual(transport.position, len(transport.traffic))

    def test_physical_thumb_pad_capture(self):
        capture = Path(__file__).resolve().parents[1] / 'artifacts/linux-thumbpad-confirmed-window.json'
        if not capture.exists():
            self.skipTest('Requires physical thumb-pad recording')
        recording = json.loads(capture.read_text())
        self.assertTrue(recording['press_and_release_seen'])
        self.assertEqual(recording['before'], recording['restored'])
        report = bytes.fromhex(recording['events'][0]['report_hex'])
        tracker = ControlTracker(report[1], report[2])
        changes = [tracker.feed(bytes.fromhex(event['report_hex'])) for event in recording['events']]
        self.assertEqual(changes[0].pressed, (416,))
        self.assertEqual(changes[-1].released, (416,))
        self.assertEqual(tracker.held, ())

    def test_unrelated_reports_preserve_held_state(self):
        tracker = ControlTracker(2, 13)
        down = bytes.fromhex('11020d0001a00000000000000000000000000000')
        self.assertEqual(tracker.feed(down).pressed, (416,))
        self.assertEqual(tracker.feed(down).pressed, ())
        for header in ['11010d00', '11020e00', '11020d10', '11020d0e']:
            self.assertIsNone(tracker.feed(bytes.fromhex(header).ljust(20, b'\0')))
            self.assertEqual(tracker.held, (416,))
        with self.assertRaises(ValueError):
            tracker.feed(down[:7])
        self.assertEqual(tracker.held, (416,))
