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
    'Restart=on-failure\nRestartSec=3\nTimeoutStopSec=30\n\n'
    '[Install]\nWantedBy=graphical-session.target\n')
subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
subprocess.run(['systemctl', '--user', 'enable', '--now', 'logioptions-ring.service'], check=True)
print('Background Actions Ring enabled for this and future graphical sessions.')
