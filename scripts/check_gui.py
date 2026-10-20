#!/usr/bin/env python3
"""Render the real native app against connected hardware on an isolated display.

Only reads devices; never activates settings or vibration buttons. Owns and
cleans up its Xvfb and D-Bus session. Uses system Python for the GTK bindings.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def inside(output, snapshot=None):
    from logioptions.gui import OptionsApp
    from gi.repository import GLib
    if snapshot:
        import logioptions.gui as gui
        captured = json.loads(snapshot.read_text())
        gui.discover = lambda: captured
    app = OptionsApp()
    started = time.monotonic()
    errors = []
    stage = [0]
    shot_names = ['home', 'buttons', 'point', 'haptics', 'haptic-panel']

    def check():
        window = app.window
        if window and window.devices and window.page.get_sensitive():
            try:
                names = [d['name'] for d in window.devices]
                if 'MX Master 4' not in names:
                    raise AssertionError('Physical MX Master 4 was not discovered')
                selected = window.devices[window.selected]
                if 'haptics' not in selected or 'dpi' not in selected:
                    raise AssertionError('Mouse controls were not populated')
                if stage[0] == 0:
                    stage[0] = 1
                    return True
                if not window.home:
                    window.layout_canvas(window.canvas, None)
                shot = output.with_name(output.stem + '-' + shot_names[stage[0] - 1] + output.suffix)
                subprocess.run(['import', '-display', os.environ['DISPLAY'], '-window', 'root', str(shot)], check=True, timeout=5)
                if stage[0] < len(shot_names):
                    next_page = shot_names[stage[0]]
                    if next_page == 'buttons': window.open_device(window.selected)
                    elif next_page == 'haptic-panel': window.show_panel('Haptic feedback')
                    else: window.show_section(next_page)
                    stage[0] += 1
                    return True
                output.with_suffix('.json').write_text(json.dumps(dict(devices=names, selected=selected['name'],
                    dpi=selected['dpi']['current'], haptic_level=selected['haptics']['level']), indent=2) + '\n')
                print('Native GUI verified with captured devices:' if snapshot else 'Native GUI verified with live devices:', ', '.join(names), flush=True)
            except Exception as error:
                errors.append(str(error))
            app.quit()
            return False
        if time.monotonic() - started > 20:
            errors.append('Timed out waiting for real hardware UI: ' + (window.status.get_text() if window else 'no window'))
            app.quit()
            return False
        return True

    GLib.timeout_add(900, check)
    app.run(['native-ui-check'])
    if errors:
        raise RuntimeError('; '.join(errors))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inside', action='store_true')
    parser.add_argument('--snapshot', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'artifacts/native-ui.png')
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.inside:
        return inside(args.output, args.snapshot)
    read_fd, write_fd = os.pipe()
    log = args.output.with_suffix('.xvfb.log').open('w')
    server = subprocess.Popen(['Xvfb', '-displayfd', str(write_fd), '-screen', '0', '1440x900x24', '-nolisten', 'tcp'],
                              pass_fds=(write_fd,), stdout=log, stderr=log)
    os.close(write_fd)
    try:
        display = os.read(read_fd, 32).decode().strip()
        if not display.isdigit():
            raise RuntimeError('Xvfb did not provide an isolated display')
        with tempfile.TemporaryDirectory(prefix='logioptions-gui-') as private:
            for name in ('runtime', 'config', 'cache', 'data'):
                (Path(private) / name).mkdir(mode=0o700)
            env = dict(os.environ, DISPLAY=':' + display, GDK_BACKEND='x11',
                       GTK_USE_PORTAL='0', GIO_USE_VFS='local',
                       XDG_RUNTIME_DIR=private + '/runtime', XDG_CONFIG_HOME=private + '/config',
                       XDG_CACHE_HOME=private + '/cache', XDG_DATA_HOME=private + '/data')
            for name in ('WAYLAND_DISPLAY', 'GNOME_KEYRING_CONTROL', 'SSH_AUTH_SOCK'):
                env.pop(name, None)
            subprocess.run(['dbus-run-session', '--', '/usr/bin/python3', str(Path(__file__).resolve()),
                            '--inside', '--output', str(args.output)] + (['--snapshot', str(args.snapshot.resolve())] if args.snapshot else []), env=env, check=True, timeout=30)
    finally:
        os.close(read_fd)
        server.terminate()
        server.wait(timeout=5)
        log.close()


if __name__ == '__main__':
    main()
