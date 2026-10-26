import os
import tempfile
import unittest
from unittest.mock import Mock, patch

try:
    from logioptions.gui import OptionsApp, OptionsWindow, Gtk, Gdk
    from logioptions import button_actions
except ImportError:
    Gtk = None


@unittest.skipUnless(Gtk is not None and os.environ.get('LOGIOPTIONS_ISOLATED_GUI_TEST') == '1'
                    and os.environ.get('GDK_BACKEND') == 'x11', 'Requires isolated GTK display')
class ButtonUITests(unittest.TestCase):
    def test_record_save_reload_and_return_to_hardware(self):
        def children(widget):
            result = []
            child = widget.get_first_child()
            while child:
                result.append(child)
                result.extend(children(child))
                child = child.get_next_sibling()
            return result
        app = OptionsApp()
        app.set_application_id('local.logioptions.ButtonUITest')
        app.register(None)
        with tempfile.TemporaryDirectory() as config, patch.dict(os.environ, XDG_CONFIG_HOME=config), patch.object(OptionsWindow,'refresh'), patch('logioptions.button_actions.available',return_value=True):
            window = OptionsWindow(app)
            window.devices = [dict(key='fake',name='MX Master 4',identity='stable-mouse',kind_code=3,
                controls=[dict(index=0,control_id=83,flags=0x30,group=1,group_mask=1,reporting={'remapped_to':83}),
                          dict(index=1,control_id=86,flags=0x30,group=1,group_mask=1,reporting={'remapped_to':86})])]
            device = Mock()
            device.identity.return_value = 'stable-mouse'
            device.control_reporting.return_value = {'remapped_to':83}
            window.action = Mock(side_effect=lambda work,*args,**kwargs:work(device))
            try:
                window.render_device()
                card = window.cards['Button actions']
                widgets = children(card)
                dropdowns = [w for w in widgets if isinstance(w,Gtk.DropDown)]
                target = dropdowns[1]
                def select(name):
                    model = target.get_model()
                    target.set_selected(next(i for i in range(model.get_n_items()) if model.get_string(i)==name))
                select('Keyboard shortcut…')
                self.assertFalse(next(w for w in widgets if isinstance(w,Gtk.Button) and w.get_label()=='Apply button action').get_sensitive())
                record = next(w for w in widgets if isinstance(w,Gtk.Button) and w.get_label()=='Record shortcut')
                record.emit('clicked')
                controllers = record.observe_controllers()
                controller = next(controllers.get_item(i) for i in range(controllers.get_n_items())
                                  if isinstance(controllers.get_item(i), Gtk.EventControllerKey))
                self.assertTrue(controller.emit('key-pressed',Gdk.KEY_c,54,Gdk.ModifierType.CONTROL_MASK))
                apply = next(w for w in widgets if isinstance(w,Gtk.Button) and w.get_label()=='Apply button action')
                self.assertTrue(apply.get_sensitive())
                apply.emit('clicked')
                self.assertEqual(button_actions.for_device('stable-mouse')['83'], {'type':'shortcut','keys':['Control_L','c']})
                device.remap_control.assert_not_called()
                window.render_device()
                card = window.cards['Button actions']
                widgets = children(card)
                target = [w for w in widgets if isinstance(w,Gtk.DropDown)][1]
                self.assertEqual(target.get_model().get_string(target.get_selected()),'Copy')
                self.assertIn('Back button · Copy · Ctrl+C',[w.get_tooltip_text() for w in window.callouts])
                next(w for w in window.callouts if (w.get_tooltip_text() or '').startswith('Forward button ·')).emit('clicked')
                self.assertEqual(window.mapping_controls[window.mapping_source.get_selected()]['control_id'],86)
                next(w for w in window.callouts if (w.get_tooltip_text() or '').startswith('Back button ·')).emit('clicked')
                self.assertEqual(window.mapping_controls[window.mapping_source.get_selected()]['control_id'],83)
                self.assertEqual(target.get_model().get_string(target.get_selected()),'Copy')
                select('Default behavior')
                with patch('logioptions.preferences.save') as save:
                    next(w for w in widgets if isinstance(w,Gtk.Button) and w.get_label()=='Apply button action').emit('clicked')
                    device.remap_control.assert_called_once_with(83,83)
                    save.assert_called_once_with('stable-mouse',{'button:83':83})
                self.assertEqual(button_actions.for_device('stable-mouse'),{})
                with patch('logioptions.button_actions.available', return_value=False):
                    window.render_device()
                    widgets = children(window.cards['Button actions'])
                    target = [w for w in widgets if isinstance(w,Gtk.DropDown)][1]
                    apply = next(w for w in widgets if isinstance(w,Gtk.Button) and w.get_label()=='Apply button action')
                    select('Copy')
                    self.assertFalse(apply.get_sensitive())
                    select('Back (built-in)')
                    self.assertTrue(apply.get_sensitive())
            finally:
                window.on_close()
                window.destroy()
