"""Activate packaged services in the logged-in user's session, never as root."""
from datetime import datetime
import os
from pathlib import Path
import shutil
import subprocess

UUID = 'logioptions-ring@local'


def migrate(home):
    """Retire only recognized source-install overrides, keeping a backup."""
    backup = home / '.config/logioptions/source-install-backup' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    candidates = []
    for unit, module in [('logioptions-ring.service','background'),('logioptions-tray.service','tray')]:
        path = home / '.config/systemd/user' / unit
        if path.is_file() and f'ExecStart=/usr/bin/python3 -m logioptions.{module}' in path.read_text():
            candidates.append(path)
    desktop = home / '.local/share/applications/local.logioptions.Rebuild.desktop'
    if desktop.is_file() and 'Exec=/usr/bin/python3 -m logioptions gui' in desktop.read_text():
        candidates.append(desktop)
    extension = home / '.local/share/gnome-shell/extensions' / UUID
    # Do not overwrite user modifications or unrelated extensions.
    system = Path('/usr/share/gnome-shell/extensions') / UUID
    if extension.is_dir() and system.is_dir():
        files = [p for p in system.iterdir() if p.is_file()]
        if files and all((extension / p.name).is_file() and (extension / p.name).read_bytes() == p.read_bytes() for p in files):
            candidates.append(extension)
    for path in candidates:
        target = backup / path.relative_to(home)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(target))
    return bool(candidates)


def main(login=True):
    if os.getuid() == 0:
        raise RuntimeError('Run logioptions session as your desktop user, not root')
    from .autostart import enabled as autostart_enabled, UNITS
    if login and not autostart_enabled():
        return
    from .background import lockfile, acquire
    with lockfile('session') as lock:
        if not acquire(lock, blocking=False): return
        migrated = migrate(Path.home())
        subprocess.run(['systemctl','--user','daemon-reload'],check=True)
        # Import the display environment for GTK services on first installation.
        names = [key for key in ('DISPLAY','WAYLAND_DISPLAY','XAUTHORITY','XDG_CURRENT_DESKTOP') if key in os.environ]
        if names:
            subprocess.run(['systemctl','--user','import-environment',*names],check=True)
        from gi.repository import Gio
        settings = Gio.Settings.new('org.gnome.shell')
        enabled = list(settings.get_strv('enabled-extensions'))
        if UUID not in enabled: settings.set_strv('enabled-extensions',enabled+[UUID])
        disabled = list(settings.get_strv('disabled-extensions'))
        if UUID in disabled: settings.set_strv('disabled-extensions',[v for v in disabled if v != UUID])
        Gio.Settings.sync()
        subprocess.run(['systemctl','--user','enable' if autostart_enabled() else 'disable',*UNITS],check=True)
        version = (Path(__file__).resolve().parents[1] / 'VERSION').read_text().strip()
        marker = Path.home() / '.config/logioptions/activated-package-version'
        upgrade = not marker.exists() or marker.read_text().strip() != version
        subprocess.run(['systemctl','--user','restart' if migrated or upgrade else 'start',
                        'logioptions-ring.service','logioptions-tray.service'],check=True)
        marker.parent.mkdir(parents=True,exist_ok=True)
        marker.write_text(version+'\n')
        print('LogiOptions background services activated. A new extension needs a new login session.')
