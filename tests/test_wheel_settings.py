import unittest
from unittest.mock import Mock
from logioptions.device import Device


class WheelTests(unittest.TestCase):
    def test_modes_and_preservation(self):
        for mode, expected in [('free',(1,14,48)),('ratchet',(2,255,48)),('smart',(2,20,48))]:
            d=Device(Mock(),2)
            d.smartshift=Mock(side_effect=[dict(mode_code=2,threshold=14,torque=48),
                dict(zip(('mode_code','threshold','torque'),expected))])
            d.set_smartshift_bytes=Mock()
            d.set_wheel_settings(mode,20,48)
            d.set_smartshift_bytes.assert_called_once_with(*expected)

    def test_failed_readback_and_unsupported_resistance(self):
        d=Device(Mock(),2)
        d.smartshift=Mock(return_value=dict(mode_code=2,threshold=14,torque=48))
        d.wheel_capabilities=Mock(return_value={'tunable_torque':False})
        d.set_smartshift_bytes=Mock()
        with self.assertRaises(ValueError): d.set_wheel_settings('smart',20,60)
        d.set_smartshift_bytes.assert_not_called()
        with self.assertRaises(ValueError): d.set_wheel_settings('ratchet',20,48)

    def test_invalid_input_never_writes(self):
        d=Device(Mock(),2)
        d.set_smartshift_bytes=Mock()
        for args in [('smart',0,48),('smart',50,48),('smart',20,101),('bad',20,48)]:
            with self.assertRaises(ValueError): d.set_wheel_settings(*args)
        d.set_smartshift_bytes.assert_not_called()
