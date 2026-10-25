#!/usr/bin/env python3
"""Install and start the ring listener for this user's graphical sessions."""
from pathlib import Path
import subprocess

project = Path(__file__).resolve().parents[1]
if '\n' in str(project) or '\r' in str(project):
    raise ValueError('The checkout path cannot contain newlines')
working_directory = str(project).replace('%', '%%')

units = Path.home() / '.config/systemd/user'
units.mkdir(parents=True, exist_ok=True)
(units / 'logioptions-ring.service').write_text(
    '[Unit]\nDescription=Options for Linux background Actions Ring\n'
    'PartOf=graphical-session.target\nAfter=graphical-session.target\n\n'
    '[Service]\nType=simple\n'
    f'WorkingDirectory={working_directory}\n'
    'ExecStart=/usr/bin/python3 -m logioptions.background\n'
    'Restart=on-failure\nRestartSec=3\nTimeoutStopSec=45\n\n'
    '[Install]\nWantedBy=graphical-session.target\n')
(units / 'logioptions-tray.service').write_text(
    '[Unit]\nDescription=Options for Linux tray icon\n'
    'PartOf=graphical-session.target\nAfter=graphical-session.target\n\n'
    '[Service]\nType=simple\n'
    f'WorkingDirectory={working_directory}\n'
    'ExecStart=/usr/bin/python3 -m logioptions.tray\n'
    'Restart=on-failure\nRestartSec=3\n\n'
    '[Install]\nWantedBy=graphical-session.target\n')
subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
import sys
sys.path.insert(0, str(project))
from logioptions.autostart import enabled, UNITS
subprocess.run(['systemctl', '--user', 'enable' if enabled() else 'disable', *UNITS], check=True)
subprocess.run(['systemctl', '--user', 'start', *UNITS], check=True)
print('Background Actions Ring and tray icon started. Login startup preference preserved.')
