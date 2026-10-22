#!/usr/bin/env python3
"""Install the local GNOME extension without restarting the user's session."""
from pathlib import Path
import shutil
from gi.repository import Gio

source = Path(__file__).resolve().parents[1] / 'extensions/logioptions-ring@local'
target = Path.home() / '.local/share/gnome-shell/extensions' / source.name
target.mkdir(parents=True, exist_ok=True)
for name in ('metadata.json', 'extension.js', 'stylesheet.css', 'profiles.js', 'actions.json'):
    shutil.copy2(source / name, target / name)
settings = Gio.Settings.new('org.gnome.shell')
enabled = list(settings.get_strv('enabled-extensions'))
if source.name not in enabled:
    settings.set_strv('enabled-extensions', enabled + [source.name])
disabled = list(settings.get_strv('disabled-extensions'))
if source.name in disabled:
    settings.set_strv('disabled-extensions', [name for name in disabled if name != source.name])
Gio.Settings.sync()
print(f'Installed {target}. Log out and back in to load it.')
applications = Path.home() / '.local/share/applications'
applications.mkdir(parents=True, exist_ok=True)
project = str(source.parents[1])
(applications / 'local.logioptions.Rebuild.desktop').write_text(
    '[Desktop Entry]\nType=Application\nName=Options for Linux\n'
    'Comment=Logitech device controls and Actions Ring\n'
    f'Path={project}\nExec=/usr/bin/python3 -m logioptions gui\n'
    'Icon=input-mouse\nTerminal=false\nCategories=Settings;HardwareSettings;\n')

# The listener runs independently of the settings window.
import subprocess
subprocess.run(['/usr/bin/python3', str(source.parents[1] / 'scripts/install_background.py')], check=True)
