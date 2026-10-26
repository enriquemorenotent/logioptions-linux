"""Global host actions keyed by stable device identity and control ID."""
import json
import os
from pathlib import Path
import re
import tempfile

DESKTOP = {'overview': 'Show overview', 'show_desktop': 'Show desktop',
           'workspace_left': 'Previous workspace', 'workspace_right': 'Next workspace'}
MODIFIERS = ('Control_L', 'Shift_L', 'Alt_L', 'Super_L')


def validate_action(action):
    if not isinstance(action, dict):
        raise ValueError('Invalid button action')
    kind = action.get('type')
    if kind == 'ring' and set(action) == {'type'}:
        return action
    if kind == 'desktop' and set(action) == {'type', 'action'} and isinstance(action['action'], str) and action['action'] in DESKTOP:
        return action
    if kind == 'shortcut' and set(action) == {'type', 'keys'}:
        keys = action['keys']
        if (isinstance(keys, list) and 1 <= len(keys) <= 5
                and all(isinstance(k, str) and re.fullmatch(r'[A-Za-z0-9_]{1,64}', k) for k in keys)
                and len(keys) == len(set(keys))
                and all(k in MODIFIERS for k in keys[:-1]) and keys[-1] not in MODIFIERS):
            return action
    raise ValueError('Choose a supported action or a keyboard shortcut')


def path():
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'logioptions/button-actions.json'


def load():
    if not path().exists():
        return {'version': 1, 'devices': {}}
    config = json.loads(path().read_text())
    if not isinstance(config, dict) or config.get('version') != 1 or not isinstance(config.get('devices'), dict):
        raise ValueError('Invalid saved button actions')
    for identity, actions in config['devices'].items():
        if not isinstance(identity, str) or not identity or not isinstance(actions, dict):
            raise ValueError('Invalid device button actions')
        for cid, action in actions.items():
            if not cid.isdecimal() or not 0 < int(cid) <= 65535 or int(cid) in (80, 81):
                raise ValueError('Invalid button control')
            validate_action(action)
    return config


def for_device(identity):
    return load()['devices'].get(identity, {})


def save(identity, cid, action):
    if not isinstance(identity, str) or not identity:
        raise ValueError('Refresh the device before assigning a button')
    if type(cid) is not int or not 0 < cid <= 65535 or (cid in (80, 81) and action is not None):
        raise ValueError('Primary clicks cannot be overridden')
    if action is not None:
        validate_action(action)
    config = load()
    actions = config['devices'].setdefault(identity, {})
    if action is None:
        actions.pop(str(cid), None)
    else:
        actions[str(cid)] = action
    path().parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.buttons-', dir=path().parent)
    try:
        with os.fdopen(fd, 'w') as file:
            json.dump(config, file, indent=2)
            file.write('\n')
        os.replace(temporary, path())
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def dispatch(action):
    from gi.repository import GLib
    from .ring import shell_call
    validate_action(action)
    shell_call('ExecuteButton', GLib.Variant('(s)', (json.dumps(action),)))


def available():
    from .ring import shell_call
    try:
        return shell_call('ButtonVersion').unpack() == (1,)
    except Exception:
        return False
