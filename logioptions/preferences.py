"""Saved device settings, matched by hardware identity and restored without pulses."""
import json
import os
from pathlib import Path
import tempfile
from .device import Device
from .hidpp import LinuxHidppTransport, HidppError


def path():
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'logioptions/devices.json'


def load():
    if not path().exists(): return {'version': 1, 'devices': {}}
    data = json.loads(path().read_text())
    if data.get('version') != 1 or not isinstance(data.get('devices'), dict):
        raise ValueError('Invalid saved device settings')
    return data


def save(identity, settings):
    data = load()
    saved = data['devices'].setdefault(identity, {})
    if 'fn_mode' in settings:
        settings = dict(settings, fn_mode={**saved.get('fn_mode', {}), **settings['fn_mode']})
    saved.update(settings)
    path().parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.devices-', dir=path().parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(data, stream, indent=2)
            stream.write('\n')
        os.replace(temporary, path())
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def selected_settings(descriptor, setting):
    if setting in ('vertical_scroll', 'thumb_scroll'):
        return {setting: descriptor[setting]['reversed']}
    if setting == 'thumb_force': return {'thumb_force': descriptor['thumb_force']['current']}
    if setting == 'dpi': return {'dpi': descriptor['dpi']['current']}
    if setting == 'fn_mode':
        state = descriptor['fn_mode']
        return {'fn_mode': {str(state['host']): state['media_keys']}}
    if setting == 'haptics': return {'haptics': {k: descriptor['haptics'][k] for k in ('enabled','level')}}
    if setting == 'smartshift': return {'smartshift': {k: descriptor['smartshift'][k] for k in ('mode_code','threshold','torque')}}
    if setting == 'backlight':
        state = descriptor['backlight']
        return {'backlight': dict(mode=state['mode'] if state['enabled'] else 255,
                                 **{k: state[k] for k in ('level','hands_out','hands_in','powered')})}
    if setting.startswith('button:'):
        cid = int(setting.split(':')[1])
        row = next(c for c in descriptor['controls'] if c['control_id'] == cid)
        return {setting: row['reporting']['remapped_to']}
    raise ValueError('Unknown device setting')


def restore(device, settings):
    changed = []
    for key, value in settings.items():
        if key == 'dpi':
            if device.dpi()['current'] == value: continue
            limits = device.dpi_limits()
            values, step = limits['values'], limits['step']
            if type(value) is not int or (value not in range(values[0],values[-1]+1,step) if step else value not in values):
                raise ValueError('Saved DPI is outside the device range')
            device.set_dpi(value)
            if device.dpi()['current'] != value: raise ValueError('DPI restore failed')
        elif key in ('vertical_scroll', 'thumb_scroll'):
            thumb = key == 'thumb_scroll'
            if type(value) is not bool: raise ValueError('Invalid saved scroll direction')
            if device.scroll_direction(thumb)['reversed'] == value: continue
            device.set_scroll_direction(value, thumb)
        elif key == 'thumb_force':
            if device.thumb_force()['current'] == value: continue
            device.set_thumb_force(value)
        elif key == 'fn_mode':
            state = device.fn_mode()
            desired = value.get(str(state['host']))
            if desired is None or state['media_keys'] == desired: continue
            if type(desired) is not bool: raise ValueError('Invalid Fn mode')
            device.set_fn_mode(desired)
        elif key == 'backlight':
            state = device.backlight()
            # Off is the enable bit, independent of inactive firmware values.
            if value['mode'] == 255 and not state['enabled']:
                continue
            current = dict(mode=state['mode'] if state['enabled'] else 255,
                           **{k:state[k] for k in ('level','hands_out','hands_in','powered')})
            # The sensor controls brightness in automatic mode.
            if value['mode'] != 3: current['level'] = value['level']
            if current == value: continue
            device.set_backlight(**value)
        elif key == 'haptics':
            state = device.haptic_config()
            if all(state[k] == value[k] for k in ('enabled','level')): continue
            device.set_haptic_feedback(**value)
        elif key == 'smartshift':
            state = device.smartshift()
            if all(state[k] == value[k] for k in ('mode_code','threshold','torque')): continue
            device.set_smartshift_bytes(value['mode_code'],value['threshold'],value['torque'])
            state = device.smartshift()
            if any(state[k] != value[k] for k in value): raise ValueError('Wheel restore failed')
        elif key.startswith('button:'):
            cid = int(key.split(':')[1])
            if device.control_reporting(cid)['remapped_to'] == value: continue
            device.remap_control(cid,value)
            if device.control_reporting(cid)['remapped_to'] != value: raise ValueError('Button restore failed')
        else: raise ValueError('Unknown saved setting')
        changed.append(key)
    return changed


def reconcile(transport, indices, report=print):
    # Caller owns the receiver and the service lease. Read the file anew so a
    # foreground Apply always wins over an earlier background snapshot.
    data = load()['devices']
    if not data: return
    for index in indices:
        device = Device(transport,index)
        try:
            try:
                identity = device.identity(timeout=.35)
            except (TimeoutError, HidppError):
                continue
            if identity not in data: continue
            changed = restore(device,data[identity])
            if changed: report('Restored device settings: ' + ', '.join(changed))
        except (TimeoutError, OSError):
            continue  # asleep/absent: next maintenance pass retries
        except Exception as error:
            report(f'Device settings retry (slot {index}): {error}')


def restore_available(exclude=None):
    from .discovery import interfaces
    if not load()['devices']: return
    for interface in interfaces():
        if interface['path'] == exclude: continue
        try:
            with LinuxHidppTransport(interface['path']) as transport:
                reconcile(transport, interface['indices'])
        except OSError as error:
            print(f'Device restoration waiting: {error}', flush=True)


def apply_and_remember(device, descriptor, setting, work):
    identity = device.identity()
    if descriptor.get('identity') != identity:
        raise RuntimeError('Device changed or identity unavailable; refresh before applying')
    result = work(device)
    try:
        save(identity, selected_settings(descriptor, setting))
    except (OSError, ValueError) as error:
        raise RuntimeError(f'Setting applied, but could not save it: {error}') from error
    return result
