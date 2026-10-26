import os
import time
import unittest
from unittest.mock import patch
try:
    from logioptions.gui import OptionsWindow,OptionsApp,Gtk
except ImportError:
    Gtk=None


@unittest.skipUnless(Gtk is not None and os.environ.get('LOGIOPTIONS_ISOLATED_GUI_TEST')=='1'
                    and os.environ.get('GDK_BACKEND')=='x11','Requires isolated GTK display')
class StatusUITests(unittest.TestCase):
    def test_disconnect_stays_visible_readonly_and_refresh_recovers_controls(self):
        app=OptionsApp();app.set_application_id('local.logioptions.StatusUITest');app.register(None)
        with patch.object(OptionsWindow,'refresh'),patch('logioptions.device_status.read_rows',return_value=[]):
            window=OptionsWindow(app)
            device=dict(key='fake',identity='mouse',path='/dev/fake-mouse',device_index=2,name='MX Master 4',kind_code=3,battery={'percentage':70})
            try:
                window.got_devices(([device],[]))
                self.assertTrue(window.home)
                self.assertEqual(len(window.device_status_labels),1)
                self.assertIn('Connected',window.device_status_labels[0][1].get_text())
                window.got_devices(([],[]))
                self.assertEqual(len(window.devices),1)
                self.assertTrue(window.devices[0]['_missing'])
                self.assertIn('Disconnected',window.device_status_labels[0][1].get_text())
                window.open_device(0)
                self.assertEqual(list(window.cards),['Device status'])
                self.assertFalse(window.navigation.get_visible())
                self.assertIn('Disconnected',window.connection_label.get_text())
                window.devices[0]['_checked_at']=time.time()-10
                row=dict(identity='mouse',name='MX Master 4',state='connected',checked=time.time(),last_seen=time.time(),updated=time.time(),percentage=70)
                with patch('logioptions.device_status.read_rows',return_value=[row]):
                    window.refresh_device_status()
                    self.assertIn('responding',window.device_notice.get_text())
                    self.assertIn('Connected',window.connection_label.get_text())
                window.got_devices(([device],[]))
                self.assertNotIn('_missing',window.devices[0])
                self.assertIn('Connected',window.connection_label.get_text())
                self.assertTrue(window.navigation.get_visible())
            finally:
                window.on_close();window.destroy()
