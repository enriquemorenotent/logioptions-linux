import json
import os
import tempfile
import unittest
from unittest.mock import patch, Mock
from logioptions.tray_status import BatteryCache, battery_labels, status_path

class TrayStatusTests(unittest.TestCase):
    def test_fresh_stale_and_invalid_cache(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,XDG_RUNTIME_DIR=directory):
            self.assertEqual(battery_labels(),[])
            cache=BatteryCache([dict(path='/test',identity='test',device_index=2,name='Mouse',battery={'percentage':70})])
            cache.rows[0].update(updated=100,battery_updated=100,last_seen=100,checked=100);cache.publish()
            self.assertEqual(battery_labels(now=110),['Mouse: Connected · 70%'])
            self.assertEqual(battery_labels(now=200),['Mouse: Status out of date · 70% · last read 1 min ago'])
            status_path().write_text('broken')
            self.assertEqual(battery_labels(),[])

    def test_refresh_reuses_owned_transport_and_rejects_replaced_device(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,XDG_RUNTIME_DIR=directory):
            cache=BatteryCache([dict(path='/test',identity='test',device_index=2,name='Mouse',battery={'percentage':70})])
            device=Mock();device.identity.return_value='other'
            transport=object()
            with patch('logioptions.tray_status.Device',return_value=device) as factory:
                cache.next_update=0;cache.refresh(transport,'/test')
                device.battery_status.assert_not_called()
                device.identity.return_value='test';device.battery_status.return_value={'percentage':65}
                cache.next_update=0;cache.refresh(transport,'/test')
                factory.assert_called_with(transport,2)
                self.assertEqual(json.loads(status_path().read_text())[0]['percentage'],65)

    def test_warning_only_for_fresh_low_battery_or_stopped_service(self):
        from logioptions.tray_status import warning_reason
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,XDG_RUNTIME_DIR=directory):
            self.assertIsNone(warning_reason('Running',now=100))
            self.assertEqual(warning_reason('Stopped'), 'Background service stopped')
            cache=BatteryCache([dict(path='/test',identity='test',device_index=2,name='Mouse',battery={'percentage':20})])
            cache.rows[0].update(updated=100,battery_updated=100,last_seen=100,checked=100);cache.publish()
            self.assertEqual(warning_reason('Running',now=110),'Low battery: Mouse')
            self.assertIsNone(warning_reason('Running',now=200))
            for value in (21,None,-1,True):
                cache.rows[0]['percentage']=value;cache.publish()
                self.assertIsNone(warning_reason('Running',now=110))
            cache.rows[0]['percentage']=0;cache.publish()
            self.assertEqual(warning_reason('Running',now=110),'Low battery: Mouse')
