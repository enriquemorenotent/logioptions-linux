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
            window.action = lambda work, success: work(device)
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
            window.action = lambda work, success: work(Device())
            for position in [0, .1, 1.4, 20.68, 30.9, 75.5, 155.7, 156]:
                slider.set_value(position)
                apply.emit('clicked')
            self.assertEqual(chosen, [200, 200, 250, 1250, 1750, 4000, 8000, 8000])
        finally:
            window.on_close()
            window.destroy()
