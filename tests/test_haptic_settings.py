import unittest
from unittest.mock import Mock

from logioptions.device import Device


class HapticSettingsTests(unittest.TestCase):
    def device(self, before, after):
        device = Device(Mock(), 2)
        device.haptic_config_bytes = Mock(side_effect=[bytes.fromhex(before), bytes.fromhex(after)])
        device.execute_haptic = Mock()
        return device

    def test_preview_applies_selected_strength_and_preserves_other_flags(self):
        device = self.device('833c', '835a')
        self.assertEqual(device.test_haptic_feedback(True, 90)['level'], 90)
        commands = [call.args[0] for call in device.execute_haptic.call_args_list]
        self.assertEqual([(c.function, c.payload.hex()) for c in commands], [(2, '835a'), (4, '0700')])

    def test_failed_readback_does_not_play(self):
        device = self.device('013c', '013c')
        with self.assertRaises(ValueError):
            device.test_haptic_feedback(True, 90)
        self.assertEqual(device.execute_haptic.call_count, 1)

    def test_disabled_preview_does_not_write_or_play(self):
        device = self.device('013c', '003c')
        with self.assertRaises(ValueError):
            device.test_haptic_feedback(False, 60)
        device.execute_haptic.assert_not_called()

    def test_invalid_levels_do_not_write(self):
        for level in [0, 101, -1, True, 45.5]:
            device = self.device('013c', '013c')
            with self.subTest(level=level), self.assertRaises(ValueError):
                device.set_haptic_feedback(True, level)
            device.execute_haptic.assert_not_called()
