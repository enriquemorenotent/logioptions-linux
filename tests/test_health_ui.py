import os
import time
import unittest
from unittest.mock import patch
try:
    from logioptions.gui import OptionsApp,OptionsWindow,Gtk,GLib
except ImportError:
    Gtk=None


@unittest.skipUnless(Gtk is not None and os.environ.get('LOGIOPTIONS_ISOLATED_GUI_TEST')=='1'
                    and os.environ.get('GDK_BACKEND')=='x11','Requires isolated GTK display')
class HealthUITests(unittest.TestCase):
    def test_checks_and_restart_refresh_status_without_touching_autostart(self):
        app=OptionsApp();app.set_application_id('local.logioptions.HealthUITest');app.register(None)
        initial={key:dict(status='Ready',detail='Initial status') for key in ('background','tray','extension','devices')}
        refreshed={**initial,'background':dict(status='Running',detail='Restart succeeded')}
        def all_widgets(widget):
            yield widget
            child=widget.get_first_child()
            while child:
                yield from all_widgets(child)
                child=child.get_next_sibling()
        def wait_for(predicate):
            deadline=time.monotonic()+3
            while time.monotonic()<deadline:
                while GLib.MainContext.default().pending():GLib.MainContext.default().iteration(False)
                if predicate():return
                time.sleep(.005)
            self.fail('UI did not update in time')
        with patch.object(OptionsWindow,'refresh'),patch('logioptions.health.collect',side_effect=[initial,refreshed]) as collect,patch('logioptions.health.restart_background') as restart,patch('logioptions.autostart.enabled',return_value=False),patch('logioptions.autostart.set_enabled') as autostart:
            window=OptionsWindow(app)
            dialog=window.show_app_settings()
            try:
                widgets=list(all_widgets(dialog))
                button=next(w for w in widgets if isinstance(w,Gtk.Button) and w.get_label()=='Restart background service')
                rows=[w for w in widgets if hasattr(w,'get_subtitle')]
                wait_for(lambda: any('Initial status' in (w.get_subtitle() or '') for w in rows))
                button.emit('clicked')
                wait_for(lambda: any('Restart succeeded' in (w.get_subtitle() or '') for w in rows))
                restart.assert_called_once_with()
                self.assertEqual(collect.call_count,2)
                autostart.assert_not_called()
                self.assertTrue(button.get_sensitive())
                restart.side_effect=RuntimeError('restart denied')
                button.emit('clicked')
                wait_for(lambda:any('Could not restart' in (w.get_subtitle() or '') for w in rows))
                self.assertTrue(button.get_sensitive())
                autostart.assert_not_called()
            finally:
                dialog.close();window.on_close();window.destroy()
