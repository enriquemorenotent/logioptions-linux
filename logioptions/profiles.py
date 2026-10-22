"""Validated, atomic storage for the ring's default and per-application layouts."""
import json
import os
from pathlib import Path
import tempfile

ACTIONS = {
    'cut': ('Cut', 'edit-cut-symbolic', ['Control_L', 'x']),
    'copy': ('Copy', 'edit-copy-symbolic', ['Control_L', 'c']),
    'paste': ('Paste', 'edit-paste-symbolic', ['Control_L', 'v']),
    'forward': ('Forward', 'go-next-symbolic', ['Alt_L', 'Right']),
    'back': ('Back', 'go-previous-symbolic', ['Alt_L', 'Left']),
    'undo': ('Undo', 'edit-undo-symbolic', ['Control_L', 'z']),
    'redo': ('Redo', 'edit-redo-symbolic', ['Control_L', 'Shift_L', 'z']),
    'none': ('Unassigned', 'list-remove-symbolic', None),
    'save': ('Save', 'document-save-symbolic', ['Control_L', 's']),
    'save_as': ('Save as', 'document-save-as-symbolic', ['Control_L', 'Shift_L', 's']),
    'find': ('Find', 'edit-find-symbolic', ['Control_L', 'f']),
    'select_all': ('Select all', 'edit-select-all-symbolic', ['Control_L', 'a']),
    'new_tab': ('New tab', 'tab-new-symbolic', ['Control_L', 't']),
    'close_tab': ('Close tab', 'window-close-symbolic', ['Control_L', 'w']),
    'reopen_tab': ('Reopen tab', 'tab-new-symbolic', ['Control_L', 'Shift_L', 't']),
    'next_tab': ('Next tab', 'go-next-symbolic', ['Control_L', 'Tab']),
    'previous_tab': ('Previous tab', 'go-previous-symbolic', ['Control_L', 'Shift_L', 'Tab']),
    'reload': ('Reload', 'view-refresh-symbolic', ['Control_L', 'r']),
    'zoom_in': ('Zoom in', 'zoom-in-symbolic', ['Control_L', 'plus']),
    'zoom_out': ('Zoom out', 'zoom-out-symbolic', ['Control_L', 'minus']),
    'zoom_reset': ('Reset zoom', 'zoom-original-symbolic', ['Control_L', '0']),
    'command_palette': ('Command palette', 'system-run-symbolic', ['Control_L', 'Shift_L', 'p']),
    'terminal_copy': ('Terminal copy', 'edit-copy-symbolic', ['Control_L', 'Shift_L', 'c']),
    'terminal_paste': ('Terminal paste', 'edit-paste-symbolic', ['Control_L', 'Shift_L', 'v']),
}
DEFAULT = ['cut', 'copy', 'paste', 'forward', 'back', 'undo', 'redo', 'none']


def config_path():
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'logioptions/ring-profiles.json'


def validate(config):
    if not isinstance(config, dict) or config.get('version') != 1:
        raise ValueError('Unsupported ring profile format')
    applications = config.get('applications')
    if not isinstance(applications, dict):
        raise ValueError('Application profiles must be an object')
    for app_id, profile in applications.items():
        if not isinstance(app_id, str) or not app_id or len(app_id) > 256:
            raise ValueError('Invalid application ID')
        if not isinstance(profile, dict) or not isinstance(profile.get('name'), str):
            raise ValueError('Application profile needs a name')
    for slots in [config.get('default')] + [p.get('slots') for p in applications.values()]:
        if not isinstance(slots, list) or len(slots) != 8 or any(not isinstance(s, str) or s not in ACTIONS for s in slots):
            raise ValueError('Each ring needs eight supported actions')
    return config


def load():
    path = config_path()
    if not path.exists():
        return dict(version=1, default=list(DEFAULT), applications={})
    return validate(json.loads(path.read_text()))


def save(config):
    validate(config)
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.ring-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as file:
            json.dump(config, file, indent=2)
            file.write('\n')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)
