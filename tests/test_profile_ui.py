import os
import tempfile
import unittest
from unittest.mock import Mock, patch

try:
    import gi
    gi.require_version('Gtk', '4.0')
    gi.require_version('Adw', '1')
    from gi.repository import Gtk, Adw, GLib
    from logioptions.profile_ui import ProfileWindow
    from logioptions import profiles
except ImportError:
    Gtk = None


@unittest.skipUnless(Gtk is not None and os.environ.get('LOGIOPTIONS_ISOLATED_GUI_TEST') == '1'
                    and os.environ.get('GDK_BACKEND') == 'x11', 'Requires isolated GTK display')
class ProfileUITests(unittest.TestCase):
    def test_edit_switch_persist_and_remove_profile(self):
        Adw.init()
        parent = Gtk.Window()
        app = Mock()
        app.get_id.return_value = 'test.editor.desktop'
        app.get_display_name.return_value = 'Test editor'
        app.should_show.return_value = True
        def call(method):
            return GLib.Variant('(u)', (1,)) if method == 'ProfileVersion' else GLib.Variant('(s)', ('[]',))
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, XDG_CONFIG_HOME=directory), \
             patch('logioptions.profile_ui.Gio.AppInfo.get_all', return_value=[app]), \
             patch('logioptions.profile_ui.shell_call', side_effect=call):
            window = ProfileWindow(parent)
            try:
                window.picker.set_selected(1)
                window.slots[0].set_selected(window.action_ids.index('save'))
                window.save_button.emit('clicked')
                saved = profiles.load()
                self.assertEqual(saved['applications']['test.editor.desktop']['slots'][0], 'save')
                self.assertEqual(saved['default'], profiles.DEFAULT)
                window.slots[1].set_selected(window.action_ids.index('find'))
                window.picker.set_selected(0)  # switching saves pending edits
                self.assertEqual(profiles.load()['applications']['test.editor.desktop']['slots'][1], 'find')
                window.picker.set_selected(1)
                window.reset.emit('clicked')
                self.assertEqual(profiles.load()['applications'], {})
                self.assertEqual(window.slots[0].get_selected(), window.action_ids.index('cut'))
                # Optional screenshot from the isolated test only.
                if os.environ.get('LOGIOPTIONS_PROFILE_SHOT'):
                    import subprocess, time
                    window.present()
                    deadline = time.monotonic() + .8
                    while time.monotonic() < deadline:
                        while GLib.MainContext.default().pending(): GLib.MainContext.default().iteration(False)
                        time.sleep(.01)
                    subprocess.run(['import', '-window', 'root', os.environ['LOGIOPTIONS_PROFILE_SHOT']], check=True)
            finally:
                window.destroy()
                parent.destroy()
