"""Independent GTK3 indicator; settings use GTK4 in a separate process."""
from pathlib import Path
import signal
import subprocess
import threading
import gi

gi.require_version('Gtk', '3.0')
gi.require_version('AyatanaAppIndicator3', '0.1')
from gi.repository import Gtk, GLib, AyatanaAppIndicator3
from .background import lockfile, acquire
from .tray_status import battery_labels, warning_reason

PROJECT = Path(__file__).resolve().parents[1]


def open_settings(*_):
    # GApplication forwards activation to an existing settings window.
    subprocess.Popen(['/usr/bin/python3', '-m', 'logioptions', 'gui'], cwd=PROJECT)


class Tray:
    def __init__(self):
        self.indicator = AyatanaAppIndicator3.Indicator.new('logioptions-linux',
            'logioptions-symbolic', AyatanaAppIndicator3.IndicatorCategory.HARDWARE)
        self.indicator.set_icon_theme_path(str(PROJECT / 'assets'))
        self.indicator.set_title('Options for Linux')
        self.icon_state = None
        self.indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.ACTIVE)
        self.busy = False
        self.menu = Gtk.Menu()
        opener = Gtk.MenuItem(label='Open settings')
        opener.connect('activate', open_settings)
        self.menu.append(opener)
        self.menu.append(Gtk.SeparatorMenuItem())
        self.battery_items = []
        self.status_item = Gtk.MenuItem(label='Background service: Checking…')
        self.status_item.set_sensitive(False)
        self.menu.append(self.status_item)
        self.menu.show_all()
        self.indicator.set_menu(self.menu)
        self.indicator.set_secondary_activate_target(opener)
        self.refresh()
        GLib.timeout_add_seconds(5, self.refresh)

    def update(self, state):
        reason = warning_reason(state)
        icon_state = ('logioptions-warning-symbolic' if reason else 'logioptions-symbolic',
                      reason or 'Options for Linux')
        if self.icon_state != icon_state:
            self.indicator.set_icon_full(*icon_state)
            self.icon_state = icon_state
        labels = battery_labels() or ['Waiting for device battery readings…']
        while len(self.battery_items) > len(labels):
            self.battery_items.pop().destroy()
        while len(self.battery_items) < len(labels):
            item = Gtk.MenuItem()
            item.set_sensitive(False)
            self.menu.insert(item, 2 + len(self.battery_items))
            self.battery_items.append(item)
        for item, text in zip(self.battery_items, labels):
            item.set_label(text)
        self.status_item.set_label('Background service: ' + state)
        self.menu.show_all()
        self.busy = False
        return False

    def refresh(self):
        if self.busy: return True
        self.busy = True
        def read():
            try:
                result = subprocess.run(['systemctl', '--user', 'is-active', 'logioptions-ring.service'],
                                        capture_output=True, text=True, timeout=3)
                state = 'Running' if result.stdout.strip() == 'active' else 'Stopped'
            except (OSError, subprocess.TimeoutExpired):
                state = 'Unavailable'
            GLib.idle_add(self.update, state)
        threading.Thread(target=read, daemon=True).start()
        return True


def main():
    with lockfile('tray') as singleton:
        if not acquire(singleton, blocking=False): return
        tray = Tray()
        for sig in (signal.SIGINT, signal.SIGTERM):
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, lambda: (Gtk.main_quit(), False)[1])
        Gtk.main()


if __name__ == '__main__':
    main()
