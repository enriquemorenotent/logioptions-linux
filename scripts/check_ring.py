#!/usr/bin/env python3
"""Render and exercise the extension inside a private headless GNOME session.

No mouse device, real desktop extension, or system input injection is used.
Test-only D-Bus methods are added only to the temporary extension copy.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
UUID = 'logioptions-ring@local'


def scratch(path):
    import gi
    gi.require_version('Gtk', '4.0')
    from gi.repository import Gtk, GLib
    app = Gtk.Application(application_id='local.logioptions.RingTest')
    def activate(app):
        window = Gtk.ApplicationWindow(application=app, title='Ring test target')
        entry = Gtk.Entry(text='A safe test document')
        window.set_child(entry)
        controller = Gtk.EventControllerKey()
        controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        def pressed(_controller, key, code, state):
            with open(path, 'a') as output:
                output.write(f'{key} {int(state)}\n')
            return False
        controller.connect('key-pressed', pressed)
        window.add_controller(controller)
        window.present()
    app.connect('activate', activate)
    app.run([])


def inside(work, output):
    from gi.repository import Gio, GLib
    extension = work / 'data/gnome-shell/extensions' / UUID
    extension.mkdir(parents=True)
    for name in ('metadata.json', 'extension.js', 'stylesheet.css'):
        shutil.copy2(ROOT / 'extensions' / UUID / name, extension / name)
    source = (extension / 'extension.js').read_text()
    source = source.replace('<method name="Ping">', '<method name="TestFocus"><arg type="b" direction="out"/></method><method name="TestActivate"><arg type="u" direction="in"/></method><method name="Ping">')
    source = source.replace("    Ping() {", "    TestFocus() { const actor = global.get_window_actors().find(a => a.meta_window.title === 'Ring test target'); if (!actor) return false; actor.meta_window.activate(global.get_current_time()); return true; }\n    TestActivate(index) { this._activate(index); }\n    Ping() {")
    (extension / 'extension.js').write_text(source)
    os.environ.update(XDG_DATA_HOME=str(work / 'data'), XDG_CONFIG_HOME=str(work / 'config'),
                      WAYLAND_DISPLAY='logi-ring-test', GDK_BACKEND='wayland')
    shell_log = open(output / 'ring-shell.log', 'w')
    shell = subprocess.Popen(['gnome-shell', '--headless', '--wayland', '--no-x11',
                              '--wayland-display=logi-ring-test', '--virtual-monitor=1280x900'],
                             stdout=shell_log, stderr=subprocess.STDOUT)
    target = None
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    def call(method, params=None):
        return bus.call_sync('org.gnome.Shell', '/local/logioptions/Ring',
                             'local.logioptions.Ring', method, params, None, 0, 3000, None)
    try:
        for _ in range(100):
            try:
                result = bus.call_sync('org.gnome.Shell', '/org/gnome/Shell',
                    'org.gnome.Shell.Extensions', 'EnableExtension', GLib.Variant('(s)', (UUID,)), None, 0, 500, None)
                if result.unpack() == (True,):
                    call('Ping')
                    break
            except GLib.Error:
                pass
            time.sleep(.2)
        else: raise RuntimeError('Test shell failed to enable the ring')
        keys = output / 'ring-keys.log'
        keys.write_text('')
        target = subprocess.Popen(['/usr/bin/python3', __file__, '--scratch', str(keys)])
        for _ in range(50):
            try:
                if call('TestFocus').unpack() == (True,): break
                time.sleep(.1)
            except GLib.Error: time.sleep(.1)
        time.sleep(.4)
        call('Show')
        time.sleep(.5)
        # Own an approved screenshot caller name ONLY on this private test bus.
        bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus',
                      'RequestName', GLib.Variant('(su)', ('org.gnome.SettingsDaemon.MediaKeys', 4)), None, 0, 1000, None)
        result = bus.call_sync('org.gnome.Shell.Screenshot', '/org/gnome/Shell/Screenshot',
             'org.gnome.Shell.Screenshot', 'Screenshot',
             GLib.Variant('(bbs)', (False, False, str(output / 'actions-ring.png'))), None, 0, 5000, None)
        assert result.unpack()[0], result
        call('TestActivate', GLib.Variant('(u)', (1,)))  # Copy
        time.sleep(.5)
        events = [tuple(map(int, line.split())) for line in keys.read_text().splitlines()]
        assert any(key == ord('c') and state & 4 for key, state in events), events
        call('Show')
        call('Release')
        call('Hide')
        print('PASS: ring rendered; Copy delivered Ctrl+C to the original test window; release/hide succeeded.')
    finally:
        if target:
            target.terminate()
            target.wait(timeout=5)
        shell.terminate()
        shell.wait(timeout=10)
        shell_log.close()


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--scratch': scratch(sys.argv[2])
    elif len(sys.argv) > 1 and sys.argv[1] == '--inside': inside(Path(sys.argv[2]), Path(sys.argv[3]))
    else:
        output = ROOT / 'artifacts/ring-check'
        output.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='logi-ring-') as work:
            test_env = dict(os.environ, XDG_DATA_HOME=str(Path(work) / 'data'),
                            XDG_CONFIG_HOME=str(Path(work) / 'config'))
            # The bus daemon must inherit isolation too: D-Bus activated dconf
            # otherwise writes the real profile despite the shell's environment.
            subprocess.run(['dbus-run-session', '--', '/usr/bin/python3', __file__, '--inside', work, str(output)], check=True, env=test_env)
