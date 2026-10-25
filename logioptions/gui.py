"""Native GTK desktop controls backed by the verified Linux device implementation."""
from concurrent.futures import ThreadPoolExecutor
import sys
import signal
from pathlib import Path

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gdk, GLib, Gtk

from .device import Device
from .events import capture_control
from .ring import available as ring_available, shell_call
from .background import foreground_access
from .discovery import discover
from .hidpp import LinuxHidppTransport

CONTROL_NAMES = {80: 'Left click', 81: 'Right click', 82: 'Wheel click', 83: 'Back',
                 86: 'Forward', 195: 'Gesture button', 196: 'Wheel mode', 416: 'Haptic thumb pad', 215: 'Virtual gesture'}
PURE_TARGETS = {80, 81, 82, 83, 86, 196}
from .appearance import Presentation, CSS, load_fonts



def label(text, css=None):
    widget = Gtk.Label(label=text, xalign=0)
    if css:
        widget.add_css_class(css)
    return widget


def box(vertical=True, spacing=12):
    return Gtk.Box(orientation=Gtk.Orientation.VERTICAL if vertical else Gtk.Orientation.HORIZONTAL, spacing=spacing)


class OptionsWindow(Presentation, Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title='Options for Linux', default_width=1280, default_height=820)
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.closed = False
        self.ring_ready = ring_available()
        self.busy = False
        self.devices = []
        self.selected = 0
        self.connect('close-request', self.on_close)
        self.build_shell()
        self.refresh()

    def on_close(self, *_):
        self.closed = True
        self.pool.shutdown(wait=False, cancel_futures=True)
        return False

    def run(self, work, done, status):
        if self.busy or self.closed:
            return
        self.busy = True
        self.status.set_text(status)
        self.spinner.start()
        self.page.set_sensitive(False)
        self.refresh_button.set_sensitive(False)
        self.device_list.set_sensitive(False)
        def exclusive_work():
            with foreground_access():
                return work()
        future = self.pool.submit(exclusive_work)
        def finish():
            if self.closed:
                return False
            self.spinner.stop()
            self.busy = False
            self.page.set_sensitive(True)
            self.refresh_button.set_sensitive(True)
            self.device_list.set_sensitive(True)
            try:
                done(future.result())
            except Exception as error:
                self.status.set_text(str(error))
            return False
        future.add_done_callback(lambda _: GLib.idle_add(finish))

    def show_ring_profiles(self):
        from .profile_ui import ProfileWindow
        try:
            window = getattr(self, 'profile_window', None)
            if window is None:
                window = ProfileWindow(self)
                self.profile_window = window
                window.connect('destroy', lambda *_: setattr(self, 'profile_window', None))
            window.present()
        except (ValueError, OSError) as error:
            self.status.set_text(f'Cannot open ring profiles: {error}')

    def refresh(self):
        self.run(discover, self.got_devices, 'Reading connected devices…')

    def got_devices(self, result):
        was_home = self.home
        devices, errors = result
        old_key = self.devices[self.selected]['key'] if self.devices and self.selected < len(self.devices) else None
        self.devices = devices
        self.device_list.remove_all()
        for device in devices:
            row = box(spacing=4)
            row.append(label(device['name']))
            battery = device.get('battery', {}).get('percentage')
            row.append(label(f'{battery}% battery' if battery is not None else 'Connected', 'muted'))
            self.device_list.append(row)
        if devices:
            self.selected = next((i for i, d in enumerate(devices) if d['key'] == old_key),
                                 next((i for i, d in enumerate(devices) if 'dpi' in d), 0))
            self.device_list.select_row(self.device_list.get_row_at_index(self.selected))
            self.status.set_text(f"{len(devices)} device{'s' if len(devices) != 1 else ''} connected")
            if errors:
                self.status.set_text('; '.join(errors))
            if was_home:
                self.show_home()
        else:
            self.clear_page()
            self.page.append(label('Connect your Logitech device', 'device-title'))
            self.page.append(label(errors[0] if errors else 'Connect a receiver or a Bluetooth device, then refresh.', 'muted'))
            self.status.set_text('No connected devices found')

    def choose_device(self, _, row):
        if row is not None:
            self.selected = row.get_index()
            self.render_device()

    def clear_page(self):
        while self.page.get_first_child():
            self.page.remove(self.page.get_first_child())

    def card(self, title):
        card = box(spacing=12)
        card.add_css_class('card')
        card.append(label(title, 'section-title'))
        self.controls_box.append(card)
        self.cards[title] = card
        return card

    def button(self, text, callback, primary=False):
        button = Gtk.Button(label=text)
        button.add_css_class('control-button')
        if primary:
            button.add_css_class('suggested-action')
        button.connect('clicked', lambda *_: callback())
        return button

    def action(self, work, success, remember=None):
        selected = self.devices[self.selected]
        def execute():
            with LinuxHidppTransport(selected['path']) as transport:
                from .preferences import apply_and_remember
                device = Device(transport, selected['device_index'])
                if remember:
                    return apply_and_remember(device, selected, remember, work)
                return work(device)
        def complete(result):
            title = self.panel_title if self.drawer.get_visible() else None
            self.render_device()
            if title:
                self.show_panel(title)
            self.status.set_text(success)
        self.run(execute, complete, 'Applying your change…')

    def _build_controls(self):
        device = self.devices[self.selected]
        is_mouse = device.get('kind_code') == 3 or 'dpi' in device
        if device.get('read_errors'):
            warning = label('Some settings could not be read. Refresh to retry. ' + '; '.join(device['read_errors']), 'muted')
            warning.set_wrap(True)
            self.page.append(warning)
        if 'dpi' in device and 'dpi_limits' in device:
            card = self.card('Pointer speed')
            limits = device['dpi_limits']
            values, step = limits['values'], limits['step']
            current = device['dpi']['current']
            value = label(f'{current:,} DPI', 'accent-value')
            card.append(value)
            choices = list(range(values[0], values[-1] + 1, step)) if step else values
            dpi_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, max(1, len(choices) - 1), 1)
            dpi_scale.set_draw_value(False)
            dpi_scale.set_round_digits(0)
            dpi_scale.set_value(min(range(len(choices)), key=lambda i: abs(choices[i] - current)))
            def selected_dpi():
                return choices[min(len(choices) - 1, round(dpi_scale.get_value()))]
            dpi_scale.connect('value-changed', lambda s: value.set_text(f'{selected_dpi():,} DPI'))
            card.append(dpi_scale)
            def apply_dpi():
                chosen = selected_dpi()
                def apply(d):
                    d.set_dpi(chosen)
                    actual = d.dpi()
                    if actual['current'] != chosen:
                        raise ValueError('The device did not accept that DPI value')
                    device['dpi'] = actual
                self.action(apply, f'Pointer speed set to {chosen:,} DPI', remember='dpi')
            card.append(self.button('Apply pointer speed', apply_dpi, True))
        if 'haptics' in device:
            current = device['haptics']
            card = self.card('Haptic feedback')
            row = box(False)
            enabled = Gtk.Switch(active=current['enabled'], valign=Gtk.Align.CENTER)
            row.append(label('Enable feedback'))
            row.append(enabled)
            card.append(row)
            strength = label(f"Strength · {current['level']}%", 'accent-value')
            card.append(strength)
            scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 100, 1)
            scale.set_value(current['level'])
            scale.set_draw_value(False)
            scale.set_round_digits(0)
            scale.connect('value-changed', lambda s: strength.set_text(f'Strength · {int(s.get_value())}%'))
            card.append(scale)
            buttons = box()
            card.append(label('Choose a strength, then apply it or apply and test.', 'muted'))
            def apply_feedback(test=False):
                level, on = int(scale.get_value()), enabled.get_active()
                def apply(d):
                    device['haptics'] = (d.test_haptic_feedback(on, level) if test
                                         else d.set_haptic_feedback(on, level))
                self.action(apply, f'Feedback set to {level}%' + (' · test vibration sent' if test else ''), remember='haptics')
            buttons.append(self.button('Apply feedback', apply_feedback, True))
            buttons.append(self.button('Apply and test vibration', lambda: apply_feedback(True)))
            card.append(buttons)
        if 'smartshift' in device:
            card = self.card('Scroll wheel')
            state = device['smartshift']
            mode = Gtk.DropDown.new_from_strings(['Free-spin', 'Ratchet', 'SmartShift'])
            mode.set_selected(0 if state['mode_code'] == 1 else 1 if state['threshold'] >= 50 else 2)
            card.append(label('Wheel mode'))
            card.append(mode)
            sensitivity_title = label('Switching speed', 'muted')
            card.append(sensitivity_title)
            threshold = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 49, 1)
            threshold.set_digits(0)
            threshold.set_value(max(1,min(49,state['threshold'])))
            card.append(threshold)
            hint = label('Lower: switches to free-spin more easily. Higher: requires a faster spin.', 'muted')
            hint.set_wrap(True)
            card.append(hint)
            torque_title = label('Wheel resistance', 'muted')
            card.append(torque_title)
            torque = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 100, 1)
            torque.set_digits(0)
            torque.set_value(max(1,state['torque']))
            card.append(torque)
            torque_hint = label('Lower: lighter clicks. Higher: firmer clicks.', 'muted')
            torque_hint.set_wrap(True)
            card.append(torque_hint)
            adjustable = device.get('wheel_capabilities', {}).get('tunable_torque', False)
            def show_wheel_controls(*_):
                for widget in (sensitivity_title,threshold,hint):
                    widget.set_visible(mode.get_selected() == 2)
                for widget in (torque_title,torque,torque_hint):
                    widget.set_visible(adjustable and mode.get_selected() != 0)
            mode.connect('notify::selected',show_wheel_controls)
            show_wheel_controls()
            def apply_mode():
                chosen = ('free','ratchet','smart')[mode.get_selected()]
                speed = int(threshold.get_value())
                resistance = int(torque.get_value()) if adjustable else state['torque']
                def apply(d):
                    device['smartshift'] = d.set_wheel_settings(chosen, speed, resistance)
                self.action(apply, 'Wheel settings updated', remember='smartshift')
            card.append(self.button('Apply wheel settings', apply_mode, True))
        for setting, title, thumb in [('vertical_scroll', 'Scroll wheel', False),
                                       ('thumb_scroll', 'Horizontal scroll', True)]:
            if setting not in device:
                continue
            card = self.cards.get(title)
            if card is None:
                card = self.card(title)
            card.append(label('Scroll direction'))
            direction = Gtk.DropDown.new_from_strings(['Standard', 'Reversed'])
            direction.set_selected(int(device[setting]['reversed']))
            card.append(direction)
            note = label('Reverses this wheel relative to its standard direction. Your desktop’s natural scrolling setting also affects the result.', 'muted')
            note.set_wrap(True)
            card.append(note)
            def apply_direction(key=setting, is_thumb=thumb, choice=direction):
                reverse = choice.get_selected() == 1
                def apply(d):
                    device[key] = d.set_scroll_direction(reverse, is_thumb)
                self.action(apply, 'Scroll direction updated', remember=key)
            card.append(self.button('Apply scroll direction', apply_direction, True))
        if device.get('thumb_force', {}).get('changeable'):
            card = self.card('Button press sensitivity')
            state = device['thumb_force']
            note = label('Choose how firmly you press the thumb pad to open Actions Ring.', 'muted')
            note.set_wrap(True)
            card.append(note)
            force = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, state['minimum'], state['maximum'], 1)
            force.set_draw_value(False)
            force.set_round_digits(0)
            force.set_value(state['current'])
            card.append(force)
            card.append(label('Lighter press ← → Firmer press', 'muted'))
            def apply_force():
                value = int(force.get_value())
                def apply(d):
                    device['thumb_force'] = d.set_thumb_force(value)
                self.action(apply, 'Thumb-pad pressure updated', remember='thumb_force')
            card.append(self.button('Apply thumb-pad pressure', apply_force, True))
            card.append(self.button('Use default pressure', lambda: force.set_value(state['default'])))
        controls = device.get('controls', [])
        if any(c['control_id'] == 416 and c['flags'] & 0x20 for c in controls):
            card = self.card('Thumb pad')
            if 'Button press sensitivity' in self.cards:
                card.append(self.button('Adjust thumb-pad pressure', lambda: self.show_panel('Button press sensitivity')))
            card.append(self.button('Configure per-app ring', self.show_ring_profiles, True))
            if self.ring_ready:
                card.append(label('Press the thumb pad to open Actions Ring.', 'muted'))
                card.append(label('Runs in the background. Choose an action, or press Escape to cancel.', 'muted'))
                card.append(self.button('Preview Actions Ring', lambda: shell_call('Show')))
            else:
                installed = any((base / 'gnome-shell/extensions/logioptions-ring@local/metadata.json').exists() for base in (Path.home() / '.local/share', Path('/usr/share')))
                message = ('Actions Ring needs activation. Log out and back in, then reopen this app.'
                           if installed else 'Install the GNOME 50 extension with scripts/install_ring.py, then log out and back in.')
                note = label(message, 'muted')
                note.set_wrap(True)
                card.append(note)
            def test_thumb_pad():
                def ready():
                    def prompt():
                        if not self.closed:
                            self.status.set_text('Press and release the thumb pad now · listening for 30 seconds')
                        return False
                    GLib.idle_add(prompt)
                self.action(lambda d: capture_control(d, 416, ready=ready, cancelled=lambda: self.closed),
                            'Thumb pad press and release received · normal settings restored')
            card.append(self.button('Test thumb pad', test_thumb_pad))
        sources = [c for c in controls if c['flags'] & 0x10]
        targets = [c for c in controls if c['control_id'] in PURE_TARGETS]
        if is_mouse and sources and targets:
            card = self.card('Button actions')
            source = Gtk.DropDown.new_from_strings([CONTROL_NAMES.get(c['control_id'], 'Button ' + str(c['index'] + 1)) for c in sources])
            target = Gtk.DropDown.new_from_strings([CONTROL_NAMES[c['control_id']] for c in targets])
            self.mapping_source = source
            self.mapping_controls = sources
            card.append(label('Button', 'muted'))
            card.append(source)
            card.append(label('Action', 'muted'))
            card.append(target)
            available_targets = []
            def show_mapping(*_):
                selected_control = sources[source.get_selected()]
                available_targets[:] = [c for c in controls
                    if c['group'] > 0 and selected_control['group_mask'] & (1 << (c['group'] - 1))]
                target.set_model(Gtk.StringList.new([CONTROL_NAMES.get(c['control_id'], str(c['control_id']))
                                                    for c in available_targets]))
                current = selected_control.get('reporting', {}).get('remapped_to')
                target.set_selected(next((i for i, c in enumerate(available_targets)
                                          if c['control_id'] == current), Gtk.INVALID_LIST_POSITION))
            source.connect('notify::selected', show_mapping)
            show_mapping()
            def apply_mapping():
                cid = sources[source.get_selected()]['control_id']
                if target.get_selected() == Gtk.INVALID_LIST_POSITION:
                    self.status.set_text('Choose an action first')
                    return
                destination = available_targets[target.get_selected()]['control_id']
                def apply(d):
                    d.remap_control(cid, destination)
                    actual = d.control_reporting(cid)
                    if actual['remapped_to'] != destination:
                        raise ValueError('The device did not accept the button action')
                    next(c for c in sources if c['control_id'] == cid)['reporting'] = actual
                self.action(apply, 'Button action updated', remember=f'button:{cid}')
            card.append(self.button('Apply button action', apply_mapping))
        if 'fn_mode' in device:
            card = self.card('Function keys')
            choice = Gtk.DropDown.new_from_strings(['F1–F12 keys', 'Media and brightness keys'])
            choice.set_selected(int(device['fn_mode']['media_keys']))
            card.append(label('Choose what the top row does without holding Fn.', 'muted'))
            card.append(choice)
            def apply_fn():
                media = choice.get_selected() == 1
                def apply(d):
                    device['fn_mode'] = d.set_fn_mode(media)
                self.action(apply, 'Function-key mode updated', remember='fn_mode')
            card.append(self.button('Apply function-key mode', apply_fn, True))
        if 'backlight' in device:
            current = device['backlight']
            card = self.card('Keyboard backlight')
            names = {255: 'Off', 0: 'On', 1: 'Automatic', 3: 'Manual'}
            modes = current['modes']
            mode = Gtk.DropDown.new_from_strings([names[m] for m in modes])
            selected = current['mode'] if current['enabled'] else 255
            mode.set_selected(modes.index(selected) if selected in modes else 0)
            card.append(label('Backlight mode'))
            card.append(mode)
            level = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, current['max_level'], 1)
            level.set_digits(0)
            level.set_value(current['level'])
            brightness_label = label('Brightness', 'muted')
            card.append(brightness_label)
            card.append(level)
            def show_brightness(*_):
                manual = modes[mode.get_selected()] == 3
                brightness_label.set_visible(manual)
                level.set_visible(manual)
            mode.connect('notify::selected', show_brightness)
            show_brightness()
            timers = {}
            for key, title in [('hands_out', 'Hands away'), ('hands_in', 'Hands nearby'), ('powered', 'While charging')]:
                row = box(False)
                row.append(label(title + ' · seconds'))
                spin = Gtk.SpinButton.new_with_range(5, 600, 5)
                spin.set_value(current[key])
                spin.set_snap_to_ticks(True)
                row.append(spin)
                card.append(row)
                timers[key] = spin
            def apply_backlight():
                values = [int(timers[k].get_value()) for k in ('hands_out', 'hands_in', 'powered')]
                chosen, strength = modes[mode.get_selected()], int(level.get_value())
                def apply(d):
                    device['backlight'] = d.set_backlight(chosen, strength, *values)
                self.action(apply, 'Keyboard backlight updated', remember='backlight')
            card.append(self.button('Apply backlight', apply_backlight, True))



class OptionsApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id='local.logioptions.Rebuild')
        self.window = None

    def do_activate(self):
        if not self.window:
            load_fonts()
            provider = Gtk.CssProvider()
            provider.load_from_bytes(GLib.Bytes.new(CSS))
            Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
            self.window = OptionsWindow(self)
        self.window.present()


def main():
    app = OptionsApp()
    def stop():
        if app.window:
            app.window.on_close()
        app.quit()
        return GLib.SOURCE_REMOVE
    for signum in (signal.SIGINT, signal.SIGTERM):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signum, stop)
    return app.run([sys.argv[0]])


if __name__ == '__main__':
    main()
