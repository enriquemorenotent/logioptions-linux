import os
import tempfile
import unittest
from unittest.mock import Mock, patch
from logioptions import preferences as p


class PreferencesTests(unittest.TestCase):
    def test_merge_latest_setting_and_host_without_touching_other_devices(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, XDG_CONFIG_HOME=root):
            p.save('mouse:one', {'dpi': 1200})
            p.save('keyboard:two', {'fn_mode': {'0': True}})
            p.save('keyboard:two', {'fn_mode': {'1': False}})
            p.save('mouse:one', {'dpi': 1600})
            data=p.load()['devices']
            self.assertEqual(data['mouse:one'], {'dpi':1600})
            self.assertEqual(data['keyboard:two']['fn_mode'], {'0':True,'1':False})
            self.assertEqual(os.stat(p.path()).st_mode & 0o777, 0o600)

    def test_restore_only_drift_and_never_play_vibration(self):
        device=Mock()
        device.dpi.side_effect=[{'current':1000},{'current':1600}]
        device.dpi_limits.return_value={'values':[200,8000],'step':50}
        device.haptic_config.return_value={'enabled':True,'level':60}
        self.assertEqual(p.restore(device, {'dpi':1600,'haptics':{'enabled':True,'level':60}}), ['dpi'])
        device.set_dpi.assert_called_once_with(1600)
        device.set_haptic_feedback.assert_not_called()
        device.test_haptic_feedback.assert_not_called()
        device.execute_haptic.assert_not_called()

    def test_automatic_backlight_ignores_sensor_brightness_and_host_is_scoped(self):
        device=Mock()
        device.backlight.return_value=dict(enabled=True,mode=1,level=5,hands_out=5,hands_in=10,powered=60)
        device.fn_mode.return_value=dict(host=2,media_keys=False)
        self.assertEqual(p.restore(device, {'backlight':dict(mode=1,level=0,hands_out=5,hands_in=10,powered=60),
                                           'fn_mode':{'0':True}}), [])
        device.set_backlight.assert_not_called()
        device.set_fn_mode.assert_not_called()

    def test_wrong_identity_never_receives_saved_settings_and_late_device_recovers(self):
        with patch.object(p,'load', return_value={'devices':{'wanted':{'dpi':1600}}}), \
             patch.object(p,'Device') as factory, patch.object(p,'restore') as restore:
            factory.return_value.identity.side_effect=['different',TimeoutError(), 'wanted']
            p.reconcile(Mock(), [1,2])
            restore.assert_not_called()
            p.reconcile(Mock(), [2])
            restore.assert_called_once_with(factory.return_value, {'dpi':1600})

    def test_corrupt_file_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, XDG_CONFIG_HOME=root):
            p.path().parent.mkdir(parents=True)
            p.path().write_text('{invalid')
            with self.assertRaises(ValueError): p.save('device',{'dpi':1000})
            self.assertEqual(p.path().read_text(),'{invalid')

    def test_apply_commits_only_verified_new_values_and_checks_identity(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, XDG_CONFIG_HOME=root):
            device=Mock()
            device.identity.return_value='wanted'
            descriptor={'identity':'wanted','dpi':{'current':1000}}
            def success(d): descriptor['dpi']={'current':1600}
            p.apply_and_remember(device,descriptor,'dpi',success)
            self.assertEqual(p.load()['devices']['wanted']['dpi'],1600)
            def failed(d): raise ValueError('hardware refused')
            with self.assertRaises(ValueError): p.apply_and_remember(device,descriptor,'dpi',failed)
            self.assertEqual(p.load()['devices']['wanted']['dpi'],1600)
            device.identity.return_value='replacement'
            work=Mock()
            with self.assertRaises(RuntimeError): p.apply_and_remember(device,descriptor,'dpi',work)
            work.assert_not_called()

    def test_off_is_saved_after_disabled_readback_and_stays_off(self):
        from logioptions.device import Device
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,XDG_CONFIG_HOME=directory):
            before = dict(enabled=True,mode=3,modes=[255,1,3],options=29,level=1,
                          max_level=7,hands_out=5,hands_in=10,powered=60)
            after = dict(before,enabled=False,level=0)
            descriptor = dict(identity='keyboard',backlight=before)
            p.save('keyboard',{'backlight':dict(mode=3,level=1,hands_out=5,hands_in=10,powered=60)})
            device = Device(Mock(),1)
            device.identity = Mock(return_value='keyboard')
            device.backlight = Mock(side_effect=[before,after])
            device.request = Mock()
            def apply(d):
                descriptor['backlight']=d.set_backlight(255,1,5,10,60)
            p.apply_and_remember(device,descriptor,'backlight',apply)
            saved = p.load()['devices']['keyboard']
            self.assertEqual(saved['backlight']['mode'],255)
            # Inactive firmware fields may drift; avoid rewriting a disabled light.
            restored = Mock()
            restored.backlight.return_value=dict(after,mode=1,hands_in=25)
            self.assertEqual(p.restore(restored,saved),[])
            restored.set_backlight.assert_not_called()
            # If it actually enables itself, restore Off, never the old Manual setting.
            restored.backlight.return_value=before
            self.assertEqual(p.restore(restored,saved),['backlight'])
            self.assertEqual(restored.set_backlight.call_args.kwargs['mode'],255)
