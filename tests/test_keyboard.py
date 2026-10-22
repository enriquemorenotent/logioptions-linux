import struct
import unittest
from unittest.mock import Mock
from logioptions.device import Device


class KeyboardTests(unittest.TestCase):
    def test_fn_uses_active_host_and_verifies(self):
        d = Device(Mock(), 1)
        d.feature = Mock()
        d.request = Mock(side_effect=[b'\x00\x00\x00\x02', b'\x02\x00', b'', b'\x00\x00\x00\x02', b'\x02\x01'])
        self.assertTrue(d.set_fn_mode(True)['media_keys'])
        self.assertEqual(d.request.call_args_list[2].args, (0x40a3, 1, b'\x02\x01'))

    def test_backlight_decodes_range_and_five_second_units(self):
        d = Device(Mock(), 1)
        d.feature = Mock(return_value={'version': 3})
        d.request = Mock(side_effect=[bytes.fromhex('000d3d030000010002000c0000'), b'\x08'])
        value = d.backlight()
        self.assertEqual([value[k] for k in ('hands_out','hands_in','powered','max_level')], [5,10,60,7])
        self.assertEqual(value['modes'], [255,1,3])

    def test_setter_preserves_low_options_and_encodes_delays(self):
        d = Device(Mock(), 1)
        before = dict(enabled=False, mode=1, modes=[255,1,3], options=13, level=0, max_level=7, hands_out=5, hands_in=10, powered=60)
        after = dict(before, enabled=True, mode=3, level=2, hands_out=10, hands_in=15, powered=65)
        d.backlight = Mock(side_effect=[before,after])
        d.request = Mock()
        d.set_backlight(3,2,10,15,65)
        self.assertEqual(d.request.call_args.args, (0x1982,1,struct.pack('<BBBBHHH',1,29,255,2,2,3,13)))

    def test_invalid_values_and_failed_readback(self):
        d = Device(Mock(),1)
        state = dict(enabled=False,mode=1,modes=[255,1,3],options=13,level=0,max_level=7,hands_out=5,hands_in=10,powered=60)
        d.backlight = Mock(return_value=state)
        d.request = Mock()
        for args in [(2,0,5,10,60),(3,8,5,10,60),(3,2,6,10,60),(3,2,0,10,60)]:
            with self.assertRaises(ValueError): d.set_backlight(*args)
        d.request.assert_not_called()
        with self.assertRaises(ValueError): d.set_backlight(3,2,5,10,60)
