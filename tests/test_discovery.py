import unittest
from unittest.mock import Mock

from logioptions.discovery import snapshot


class DiscoveryTests(unittest.TestCase):
    def test_optional_failure_keeps_device_and_other_settings(self):
        device = Mock(device_index=2)
        device.name.return_value = 'MX Master 4'
        device.kind_code.return_value = 3
        device.battery_status.return_value = dict(percentage=50)
        device.dpi.return_value = dict(current=1000)
        device.dpi_limits.side_effect = TimeoutError('range timed out')
        device.smartshift.side_effect = TimeoutError('wheel timed out')
        device.controls.return_value = []
        device.haptic_config.return_value = dict(enabled=True, level=60)
        actual = snapshot(device, '/dev/hidraw6')
        self.assertEqual(actual['name'], 'MX Master 4')
        self.assertEqual(actual['haptics']['level'], 60)
        self.assertEqual(len(actual['read_errors']), 2)
        self.assertNotIn('smartshift', actual)
        self.assertNotIn('dpi_limits', actual)
