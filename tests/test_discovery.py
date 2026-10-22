import unittest
from unittest.mock import Mock, patch

from logioptions.discovery import snapshot, discover


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

    def test_slow_keyboard_retried_without_duplicate_mouse(self):
        transport = Mock()
        def lookup(index, feature, timeout):
            if index == 1 and timeout == .25:
                raise TimeoutError('keyboard waking')
            if index == 3:
                raise TimeoutError('empty slot')
            return {'index': 5}
        transport.lookup_feature.side_effect = lookup
        def descriptor(device, path):
            return {'name': 'keyboard' if device.device_index == 1 else 'mouse'}
        with patch('logioptions.discovery.interfaces', return_value=[{'path':'fake','indices':[1,2,3]}]), \
             patch('logioptions.discovery.LinuxHidppTransport') as factory, \
             patch('logioptions.discovery.snapshot', side_effect=descriptor):
            factory.return_value.__enter__.return_value = transport
            devices, errors = discover()
        self.assertEqual(devices, [{'name':'mouse'}, {'name':'keyboard'}])
        self.assertEqual(errors, [])
        self.assertEqual([(c.args[0], c.kwargs['timeout']) for c in transport.lookup_feature.call_args_list],
                         [(1,.25),(2,.25),(3,.25),(1,1.0),(3,1.0)])
