import tempfile
from pathlib import Path
import unittest
from logioptions.session import migrate

class SessionTests(unittest.TestCase):
    def test_migrates_only_recognized_source_overrides_and_keeps_settings(self):
        with tempfile.TemporaryDirectory() as temporary:
            home=Path(temporary)
            service=home/'.config/systemd/user/logioptions-ring.service'
            service.parent.mkdir(parents=True)
            service.write_text('[Service]\nExecStart=/usr/bin/python3 -m logioptions.background\n')
            custom=service.with_name('logioptions-tray.service');custom.write_text('custom user unit')
            preferences=home/'.config/logioptions/devices.json';preferences.parent.mkdir();preferences.write_text('{}')
            self.assertTrue(migrate(home))
            self.assertFalse(service.exists())
            self.assertEqual(custom.read_text(),'custom user unit')
            self.assertEqual(preferences.read_text(),'{}')
            self.assertEqual(len(list((home/'.config/logioptions/source-install-backup').rglob('logioptions-ring.service'))),1)
            self.assertFalse(migrate(home))
