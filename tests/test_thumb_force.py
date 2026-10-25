import unittest
from unittest.mock import Mock
from logioptions.device import Device, UnsupportedFeature
from logioptions.preferences import restore, selected_settings

class ThumbForceTests(unittest.TestCase):
    def device(self, current=5935):
        d=Device(Mock(),2)
        d.request=Mock(side_effect=lambda feature,function,payload=b'': {
            0:b'\x01',1:bytes.fromhex('0001172f1ed6128c'),2:current.to_bytes(2,'big'),3:b''}[function])
        return d

    def test_advertised_range_and_encoding(self):
        d=self.device(6035)
        state=d.set_thumb_force(6035)
        self.assertEqual((state['minimum'],state['maximum'],state['default']),(4748,7894,5935))
        d.request.assert_any_call(0x19c0,3,b'\0\x17\x93')

    def test_invalid_values_and_readback(self):
        for value in [True,4747,7895,3.5]:
            d=self.device()
            with self.assertRaises(ValueError): d.set_thumb_force(value)
            self.assertFalse(any(c.args[1]==3 for c in d.request.call_args_list))
        with self.assertRaises(ValueError): self.device().set_thumb_force(6035)

    def test_unsupported_and_truncated(self):
        d=self.device();d.request=Mock(return_value=b'\x02')
        with self.assertRaises(UnsupportedFeature): d.thumb_force()
        d.request=Mock(side_effect=[b'\x01',b'',b''])
        with self.assertRaises(ValueError): d.thumb_force()

    def test_persistence_only_writes_changed_value(self):
        d=Mock();d.thumb_force.return_value={'current':5935}
        self.assertEqual(restore(d,{'thumb_force':5935}),[])
        d.set_thumb_force.assert_not_called()
        self.assertEqual(restore(d,{'thumb_force':6035}),['thumb_force'])
        d.set_thumb_force.assert_called_once_with(6035)
        self.assertEqual(selected_settings({'thumb_force':{'current':6035}},'thumb_force'),{'thumb_force':6035})
