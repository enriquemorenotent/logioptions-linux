"""Run with system Python on an isolated display; never writes to hardware."""
import os
import unittest
from unittest.mock import patch

try:
    from logioptions.gui import OptionsApp, OptionsWindow, Gtk
except ImportError:
    Gtk = None


@unittest.skipUnless(Gtk is not None and os.environ.get('LOGIOPTIONS_ISOLATED_GUI_TEST') == '1'
                     and os.environ.get('GDK_BACKEND') == 'x11',
                     'Requires system GTK Python and an explicitly isolated display')
class DpiSliderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = OptionsApp()
        cls.app.register(None)

    def test_tab_switches_keep_device_image_mapped(self):
        import time
        from gi.repository import GLib
        with patch.object(OptionsWindow, 'refresh'):
            window = OptionsWindow(self.app)
        try:
            window.devices = [dict(key='test:2', name='MX Master 4', kind_code=3)]
            window.render_device()
            window.present()
            def frames():
                deadline = time.monotonic() + .08
                context = GLib.MainContext.default()
                while time.monotonic() < deadline:
                    while context.pending(): context.iteration(False)
                    time.sleep(.002)
            frames()
            image, canvas = window.device_picture, window.canvas
            unmapped = []
            image.connect('unmap', lambda *_: unmapped.append(True))
            self.assertTrue(image.get_mapped())
            for section in ('point', 'haptics', 'easy', 'flow', 'settings', 'buttons') * 2:
                window.show_section(section)
                frames()
                self.assertIs(window.canvas, canvas)
                self.assertIs(window.device_picture, image)
                self.assertTrue(image.get_mapped())
                self.assertGreater(image.get_width(), 0)
            self.assertEqual(unmapped, [])
            # Returning from home still creates the correct device view.
            window.show_home()
            window.open_device(0)
            frames()
            self.assertTrue(window.device_picture.get_mapped())
        finally:
            window.on_close()
            window.destroy()

    def test_haptic_preview_uses_slider_and_disabled_state(self):
        app = self.app
        with patch.object(OptionsWindow, 'refresh'):
            window = OptionsWindow(app)
        try:
            window.devices = [dict(key='test:2', path='/dev/hidraw6', device_index=2,
                name='MX Master 4', kind_code=3,
                haptics=dict(enabled=True, level=60, flags=1, power_save=False))]
            window.render_device()
            window.show_panel('Haptic feedback')
            widgets = []
            def visit(widget):
                widgets.append(widget)
                child = widget.get_first_child()
                while child:
                    visit(child)
                    child = child.get_next_sibling()
            visit(window.panel)
            slider = next(w for w in widgets if isinstance(w, Gtk.Scale))
            toggle = next(w for w in widgets if isinstance(w, Gtk.Switch))
            preview = next(w for w in widgets if isinstance(w, Gtk.Button)
                           and w.get_label() == 'Apply and test vibration')
            from unittest.mock import Mock
            device = Mock()
            device.test_haptic_feedback.return_value = dict(enabled=True, level=90)
            window.action = lambda work, success, **kwargs: work(device)
            slider.set_value(90)
            preview.emit('clicked')
            device.test_haptic_feedback.assert_called_once_with(True, 90)
            toggle.set_active(False)
            preview.emit('clicked')
            device.test_haptic_feedback.assert_called_with(False, 90)
        finally:
            window.on_close()
            window.destroy()

    def test_failed_dpi_range_still_renders_other_controls(self):
        app = self.app
        with patch.object(OptionsWindow, 'refresh'):
            window = OptionsWindow(app)
        try:
            window.devices = [dict(key='test:2', name='MX Master 4', kind_code=3,
                dpi=dict(current=1000), read_errors=['DPI range: timed out'],
                haptics=dict(enabled=True, level=60, flags=1, power_save=False))]
            window.render_device()
            self.assertIsNotNone(window.page.get_first_child())
        finally:
            window.on_close()
            window.destroy()

    def test_drag_positions_only_apply_advertised_dpi(self):
        app = self.app
        with patch.object(OptionsWindow, 'refresh'):
            window = OptionsWindow(app)
        try:
            window.devices = [dict(key='test:2', path='/dev/hidraw6', device_index=2,
                name='MX Master 4', dpi=dict(current=1000),
                dpi_limits=dict(values=[200, 8000], step=50))]
            window.render_device()

            def descendants(widget):
                yield widget
                child = widget.get_first_child()
                while child:
                    yield from descendants(child)
                    child = child.get_next_sibling()

            window.show_panel('Pointer speed')
            widgets = list(descendants(window.panel))
            slider = next(w for w in widgets if isinstance(w, Gtk.Scale))
            apply = next(w for w in widgets if isinstance(w, Gtk.Button)
                         and w.get_label() == 'Apply pointer speed')
            chosen = []
            class Device:
                def set_dpi(self, value):
                    chosen.append(value)
                def dpi(self):
                    return dict(current=chosen[-1])
            window.action = lambda work, success, **kwargs: work(Device())
            for position in [0, .1, 1.4, 20.68, 30.9, 75.5, 155.7, 156]:
                slider.set_value(position)
                apply.emit('clicked')
            self.assertEqual(chosen, [200, 200, 250, 1250, 1750, 4000, 8000, 8000])
        finally:
            window.on_close()
            window.destroy()

    def test_keyboard_controls_apply_and_render(self):
        from unittest.mock import Mock
        with patch.object(OptionsWindow, 'refresh'):
            window = OptionsWindow(self.app)
        try:
            light = dict(enabled=False, mode=1, modes=[255,1,3], options=13,
                level=0, max_level=7, hands_out=5, hands_in=10, powered=60)
            window.devices = [dict(key='test:1', name='MX Keys for Business', kind_code=0,
                fn_mode=dict(host=0, media_keys=False), backlight=light)]
            window.render_device()
            self.assertIs(window.cards['Function keys'].get_parent(), window.panel)
            self.assertIs(window.cards['Keyboard backlight'].get_parent(), window.panel)
            def descendants(widget):
                yield widget
                child = widget.get_first_child()
                while child:
                    yield from descendants(child)
                    child = child.get_next_sibling()
            device = Mock()
            device.set_fn_mode.return_value = dict(host=0, media_keys=True)
            device.set_backlight.return_value = light
            window.action = lambda work, success, **kwargs: work(device)
            window.show_panel('Function keys')
            widgets = list(descendants(window.panel))
            next(w for w in widgets if isinstance(w,Gtk.DropDown)).set_selected(1)
            next(w for w in widgets if isinstance(w,Gtk.Button) and w.get_label() == 'Apply function-key mode').emit('clicked')
            device.set_fn_mode.assert_called_once_with(True)
            window.show_panel('Keyboard backlight')
            widgets = list(descendants(window.panel))
            mode = next(w for w in widgets if isinstance(w,Gtk.DropDown))
            scale = next(w for w in widgets if isinstance(w,Gtk.Scale))
            self.assertFalse(scale.get_visible())
            mode.set_selected(2)
            self.assertTrue(scale.get_visible())
            scale.set_value(3)
            next(w for w in widgets if isinstance(w,Gtk.Button) and w.get_label() == 'Apply backlight').emit('clicked')
            device.set_backlight.assert_called_once_with(3,3,5,10,60)
        finally:
            window.on_close()
            window.destroy()

    def test_navigation_follows_device_and_keyboard_section(self):
        with patch.object(OptionsWindow, 'refresh'):
            window = OptionsWindow(self.app)
        try:
            window.devices = [dict(key='keyboard', name='MX Keys', kind_code=0),
                              dict(key='mouse', name='MX Master 4', kind_code=3)]
            window.open_device(0)
            visible = lambda: {k for k,b in window.nav_buttons.items() if b.get_visible()}
            self.assertFalse(window.navigation.get_visible())
            self.assertEqual(window.section, 'keyboard')
            self.assertFalse(window.global_button.get_visible())
            image = window.device_picture
            self.assertEqual(len(window.callouts), 0)
            self.assertFalse(window.drawer_close.get_visible())
            self.assertTrue(window.drawer.get_visible())
            self.assertEqual(window.panel_title, 'Keyboard settings')
            for title in ('Function keys', 'Keyboard backlight'):
                window.show_panel(title)
                self.assertFalse(window.navigation.get_visible())
                window.close_panel()
                self.assertFalse(window.navigation.get_visible())
            self.assertIs(window.device_picture, image)
            window.open_device(1)
            self.assertEqual(visible(), {'buttons','point','haptics','easy','flow','settings'})
            self.assertEqual(window.section, 'buttons')
            window.open_device(0)
            self.assertFalse(window.navigation.get_visible())
        finally:
            window.on_close()
            window.destroy()

    def test_scroll_directions_use_the_correct_wheel(self):
        from unittest.mock import Mock
        with patch.object(OptionsWindow,'refresh'):
            window=OptionsWindow(self.app)
        try:
            window.devices=[dict(key='test',name='MX Master 4',kind_code=3,
                vertical_scroll=dict(reversed=False),thumb_scroll=dict(reversed=True))]
            window.render_device()
            device=Mock()
            device.set_scroll_direction.return_value={'reversed':True}
            window.action=lambda work,success,**kwargs: work(device)
            for title, expected in [('Scroll wheel',False),('Horizontal scroll',True)]:
                window.show_panel(title)
                card=window.cards[title]
                children=[]
                child=card.get_first_child()
                while child:
                    children.append(child)
                    child=child.get_next_sibling()
                choice=next(w for w in children if isinstance(w,Gtk.DropDown))
                choice.set_selected(1)
                next(w for w in children if isinstance(w,Gtk.Button) and w.get_label()=='Apply scroll direction').emit('clicked')
                device.set_scroll_direction.assert_called_with(True,expected)
        finally:
            window.on_close()
            window.destroy()

    def test_wheel_controls_follow_mode_and_apply_all_values(self):
        from unittest.mock import Mock
        with patch.object(OptionsWindow,'refresh'):
            window=OptionsWindow(self.app)
        try:
            state=dict(mode_code=2,threshold=12,torque=75)
            window.devices=[dict(key='test',name='MX Master 4',kind_code=3,
                smartshift=state,wheel_capabilities={'tunable_torque':True})]
            window.render_device()
            window.show_panel('Scroll wheel')
            children=[]
            child=window.cards['Scroll wheel'].get_first_child()
            while child:
                children.append(child);child=child.get_next_sibling()
            mode=next(w for w in children if isinstance(w,Gtk.DropDown))
            speed,torque=[w for w in children if isinstance(w,Gtk.Scale)]
            self.assertEqual(mode.get_selected(),2)
            self.assertTrue(speed.get_visible())
            mode.set_selected(0)
            self.assertFalse(speed.get_visible());self.assertFalse(torque.get_visible())
            mode.set_selected(1)
            self.assertFalse(speed.get_visible());self.assertTrue(torque.get_visible())
            mode.set_selected(2);speed.set_value(20);torque.set_value(60)
            device=Mock();device.set_wheel_settings.return_value=state
            window.action=lambda work,success,**kwargs: work(device)
            next(w for w in children if isinstance(w,Gtk.Button) and w.get_label()=='Apply wheel settings').emit('clicked')
            device.set_wheel_settings.assert_called_once_with('smart',20,60)
        finally:
            window.on_close();window.destroy()

    def test_thumb_pressure_uses_device_range_and_saves(self):
        from unittest.mock import Mock
        with patch.object(OptionsWindow,'refresh'):
            window=OptionsWindow(self.app)
        try:
            state=dict(changeable=True,minimum=4748,maximum=7894,default=5935,current=6035)
            window.devices=[dict(key='test',name='MX Master 4',kind_code=3,thumb_force=state)]
            window.render_device();window.show_panel('Button press sensitivity')
            children=[];child=window.cards['Button press sensitivity'].get_first_child()
            while child:
                children.append(child);child=child.get_next_sibling()
            slider=next(w for w in children if isinstance(w,Gtk.Scale))
            self.assertEqual(slider.get_adjustment().get_lower(),4748)
            self.assertEqual(slider.get_adjustment().get_upper(),7894)
            next(w for w in children if isinstance(w,Gtk.Button) and w.get_label()=='Use default pressure').emit('clicked')
            self.assertEqual(slider.get_value(),5935)
            slider.set_value(6200)
            device=Mock();device.set_thumb_force.return_value=state
            window.action=Mock(side_effect=lambda work,success,**kwargs: work(device))
            next(w for w in children if isinstance(w,Gtk.Button) and w.get_label()=='Apply thumb-pad pressure').emit('clicked')
            device.set_thumb_force.assert_called_once_with(6200)
            self.assertEqual(window.action.call_args.kwargs['remember'],'thumb_force')
        finally:
            window.on_close();window.destroy()
