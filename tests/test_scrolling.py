import unittest
from unittest.mock import Mock
from logioptions.device import Device
from logioptions.preferences import restore, selected_settings


class ScrollTests(unittest.TestCase):
    def test_preserves_resolution_and_diversion_bits(self):
        for thumb, before, after in [(False,'03','07'), (True,'03a2','03a3')]:
            d=Device(Mock(),2)
            d.request=Mock(side_effect=[bytes.fromhex(before), b'', bytes.fromhex(after)])
            self.assertTrue(d.set_scroll_direction(True,thumb)['reversed'])
            self.assertEqual(d.request.call_args_list[1].args,
                             (0x2150 if thumb else 0x2121,2,bytes.fromhex(after)))

    def test_failed_readback_rejected_and_no_write_on_invalid_input(self):
        d=Device(Mock(),2)
        d.request=Mock(side_effect=[b'\x03', b'', b'\x03'])
        with self.assertRaises(ValueError): d.set_scroll_direction(True)
        d.request.reset_mock()
        with self.assertRaises(ValueError): d.set_scroll_direction('yes')
        d.request.assert_not_called()

    def test_saved_direction_restores_only_if_changed(self):
        d=Mock()
        d.scroll_direction.side_effect=[{'reversed':False},{'reversed':True}]
        self.assertEqual(restore(d,{'vertical_scroll':True,'thumb_scroll':True}), ['vertical_scroll'])
        d.set_scroll_direction.assert_called_once_with(True,False)
        self.assertEqual(selected_settings({'thumb_scroll':{'reversed':True}},'thumb_scroll'), {'thumb_scroll':True})
