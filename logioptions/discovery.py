"""Discover HID++ interfaces and read connected devices without changing settings."""
from pathlib import Path

from .device import Device, UnsupportedFeature
from .hidpp import LinuxHidppTransport, HidppError


def report_ids(descriptor):
    result = set()
    offset = 0
    while offset < len(descriptor):
        prefix = descriptor[offset]
        offset += 1
        if prefix == 0xFE:
            if offset + 2 > len(descriptor):
                break
            size = descriptor[offset]
            offset += 2 + size
            continue
        size = prefix & 3
        if size == 3:
            size = 4
        if offset + size > len(descriptor):
            break
        if prefix == 0x85 and size == 1:
            result.add(descriptor[offset])
        offset += size
    return result


def interfaces():
    rows = []
    for entry in sorted(Path('/sys/class/hidraw').glob('hidraw*')):
        try:
            properties = dict(line.split('=', 1) for line in (entry / 'device/uevent').read_text().splitlines() if '=' in line)
            bus, vendor, product = [int(v, 16) for v in properties['HID_ID'].split(':')]
            if vendor != 0x046D:
                continue
            ids = report_ids((entry / 'device/report_descriptor').read_bytes())
            if not {0x10, 0x11}.issubset(ids):
                continue
            receiver = 'receiver' in properties.get('HID_NAME', '').lower()
            rows.append(dict(path='/dev/' + entry.name, receiver=receiver, bus=bus, product=product,
                             indices=list(range(1, 7)) if receiver else [255]))
        except (OSError, ValueError, KeyError):
            continue
    return rows


def snapshot(device, path):
    result = dict(path=path, device_index=device.device_index, name=device.name(),
                  key=f'{path}:{device.device_index}', read_errors=[])
    for name, reader in [('identity', device.identity), ('kind_code', device.kind_code), ('battery', device.battery_status),
                         ('thumb_force', device.thumb_force), ('dpi', device.dpi), ('smartshift', device.smartshift), ('wheel_capabilities', device.wheel_capabilities),
                         ('controls', device.controls), ('haptics', device.haptic_config),
                         ('fn_mode', device.fn_mode), ('backlight', device.backlight),
                         ('vertical_scroll', device.scroll_direction),
                         ('thumb_scroll', lambda: device.scroll_direction(True))]:
        try:
            result[name] = reader()
        except UnsupportedFeature:
            pass
        except (TimeoutError, HidppError, ValueError) as error:
            result['read_errors'].append(f'{name}: {error}')
    if 'dpi' in result:
        try:
            result['dpi_limits'] = device.dpi_limits()
        except (UnsupportedFeature, TimeoutError, HidppError, ValueError) as error:
            result['read_errors'].append(f'DPI range: {error}')
    for control in result.get('controls', []):
        if control['flags'] & 0x10:
            try:
                control['reporting'] = device.control_reporting(control['control_id'])
            except (TimeoutError, HidppError, ValueError) as error:
                result['read_errors'].append(f"Button {control['control_id']}: {error}")
    return result


def discover():
    devices, errors = [], []
    for interface in interfaces():
        try:
            with LinuxHidppTransport(interface['path']) as transport:
                pending = list(interface['indices'])
                failures = {}
                # Wireless devices can take longer to answer while waking.
                # Retry only missing slots after the fast first pass; retain
                # already discovered devices without duplicating or rereading.
                for timeout in (0.25, 1.0):
                    retry = []
                    for index in pending:
                        identified = False
                        try:
                            feature = transport.lookup_feature(index, 0x0005, timeout=timeout)
                            if not feature['index']:
                                continue
                            identified = True
                            device = Device(transport, index)
                            device.features[0x0005] = feature
                            devices.append(snapshot(device, interface['path']))
                            failures.pop(index, None)
                        except (TimeoutError, HidppError) as error:
                            retry.append(index)
                            if identified:
                                failures[index] = f"{interface['path']} slot {index}: {error}"
                    pending = retry
                    if not pending:
                        break
                errors.extend(failures.values())
        except OSError as error:
            errors.append(str(error))
    return devices, errors
