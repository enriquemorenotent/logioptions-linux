import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from logioptions.device_status import view,for_device,merge_devices,status_path
from logioptions.tray_status import BatteryCache,battery_labels,warning_reason


class DeviceStatusTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        env=patch.dict(os.environ,XDG_RUNTIME_DIR=self.temp.name)
        env.start();self.addCleanup(env.stop)

    def descriptor(self):
        return dict(identity='mouse-a',path='/dev/hidraw-test',device_index=2,key='mouse-a',name='MX Master 4',kind_code=3,battery={'percentage':70})

    def test_silent_device_is_not_guessed_to_be_disconnected(self):
        device=Mock();device.identity.side_effect=TimeoutError('asleep')
        with patch('logioptions.tray_status.time.time',return_value=100):
            cache=BatteryCache([self.descriptor()])
        with patch('logioptions.tray_status.Device',return_value=device),patch('logioptions.tray_status.time.time',return_value=150):
            cache.next_update=0;cache.refresh(object(),'/dev/hidraw-test')
        self.assertEqual(view(cache.rows[0],150)['state'],'unresponsive')
        self.assertIn('may be asleep',battery_labels(150)[0])
        self.assertIn('last read',battery_labels(150)[0])
        self.assertEqual(cache.rows[0]['battery_updated'],100)
        device.identity.side_effect=None;device.identity.return_value='mouse-a'
        device.battery_status.return_value={'percentage':65}
        with patch('logioptions.tray_status.Device',return_value=device),patch('logioptions.tray_status.time.time',return_value=160):
            cache.next_update=0;cache.refresh(object(),'/dev/hidraw-test')
        self.assertEqual(view(cache.rows[0],160)['state'],'connected')
        self.assertEqual(view(cache.rows[0],160)['battery'],'65%')

    def test_receiver_removed_and_slot_replaced_are_definite_disconnects(self):
        cache=BatteryCache([self.descriptor()])
        cache.next_update=0;cache.refresh(None,'different-path')
        self.assertEqual(cache.rows[0]['state'],'disconnected')
        other=Mock();other.identity.return_value='other-mouse'
        with patch('logioptions.tray_status.Device',return_value=other):
            cache.next_update=0;cache.refresh(object(),'/dev/hidraw-test')
        self.assertEqual(cache.rows[0]['state'],'disconnected')
        other.battery_status.assert_not_called()

    def test_discovery_keeps_missing_devices_and_battery_age(self):
        with patch('logioptions.device_status.read_rows',return_value=[]):
            old=merge_devices([self.descriptor()],[],now=100)
            with patch('logioptions.device_status.Path.exists',return_value=True):
                missing=merge_devices([],old,now=200)
            self.assertTrue(missing[0]['_missing'])
            status=for_device(missing[0],now=200,rows=[])
            self.assertEqual(status['state'],'unresponsive')
            self.assertIn('last read 1 min ago',status['battery'])
            fresh=self.descriptor();fresh.pop('battery')
            recovered=merge_devices([fresh],missing,now=210)
            self.assertNotIn('_missing',recovered[0])
            self.assertEqual(for_device(recovered[0],now=210,rows=[])['state'],'connected')
            self.assertEqual(recovered[0]['_battery_at'],100)

    def test_cache_survives_rediscovery_without_reviving_old_battery(self):
        with patch('logioptions.tray_status.time.time',return_value=100):
            cache=BatteryCache([self.descriptor()])
        with patch('logioptions.tray_status.time.time',return_value=300):
            missing=BatteryCache([])
        self.assertEqual(missing.rows[0]['identity'],'mouse-a')
        self.assertEqual(missing.rows[0]['battery_updated'],100)
        self.assertEqual(missing.rows[0]['state'],'disconnected')
        self.assertIn('last read 3 min ago',battery_labels(300)[0])

    def test_invalid_and_stopped_cache_never_looks_fresh_or_warns_low_battery(self):
        for row in [dict(name='Mouse',percentage=1,updated=500),
                    dict(name='Mouse',percentage=1,updated=0,state='unresponsive',checked=100,last_seen=0),
                    dict(name='Mouse',percentage=True,updated=100),
                    dict(name='Mouse',percentage=200,updated=100),
                    dict(name='Mouse',percentage=1,updated='bad',state=[])]:
            status_path().parent.mkdir(exist_ok=True)
            status_path().write_text(json.dumps([row]))
            self.assertIsNone(warning_reason('Running',now=110))
            battery_labels(now=110)
