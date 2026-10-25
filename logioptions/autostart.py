"""Per-user login startup, shared by the UI and packaged session launcher."""
import configparser
import os
from pathlib import Path
import subprocess
import shutil

UNITS = ('logioptions-ring.service', 'logioptions-tray.service')


def entry_path():
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'autostart/logioptions-session.desktop'


def enabled():
    path = entry_path()
    if not path.exists():
        return True
    entry = configparser.ConfigParser(interpolation=None)
    entry.read(path)
    return not entry.getboolean('Desktop Entry', 'Hidden', fallback=False)


def set_enabled(value):
    """Change future logins without stopping the user's current session."""
    path = entry_path()
    previous = path.read_bytes() if path.exists() else None
    path.parent.mkdir(parents=True, exist_ok=True)
    command = 'logioptions session' if shutil.which('logioptions') else 'systemctl --user start ' + ' '.join(UNITS)
    content = ('[Desktop Entry]\nType=Application\nName=LogiOptions background services\n'
               f'Exec={command}\nOnlyShowIn=GNOME;\nNoDisplay=true\n'
               f'Hidden={str(not value).lower()}\n')
    temporary = path.with_suffix('.desktop.tmp')
    temporary.write_text(content)
    temporary.replace(path)
    try:
        subprocess.run(['systemctl', '--user', 'enable' if value else 'disable', *UNITS],
                       check=True, capture_output=True, text=True, timeout=15)
    except Exception:
        if previous is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(previous)
        raise


def start_services():
    subprocess.run(['systemctl', '--user', 'start', *UNITS], check=True,
                   capture_output=True, text=True, timeout=15)
