import argparse
import json
import sys

from .device import Device
from .hidpp import LinuxHidppTransport
from . import haptics


def version():
    from pathlib import Path
    return (Path(__file__).resolve().parents[1] / 'VERSION').read_text().strip()


def show_status():
    import subprocess
    from .autostart import enabled
    from .tray_status import battery_labels
    print(f'Options for Linux {version()}')
    for unit, title in [('ring', 'Background service'), ('tray', 'Tray icon')]:
        try:
            result = subprocess.run(['systemctl', '--user', 'show', '--property=ActiveState',
                                     '--value', f'logioptions-{unit}.service'],
                                    capture_output=True, text=True, timeout=5)
            state = result.stdout.strip() if result.returncode == 0 else 'unavailable'
        except (OSError, subprocess.TimeoutExpired):
            state = 'unavailable'
        print(f'{title}: {state or "unavailable"}')
    print('Start at login: ' + ('enabled' if enabled() else 'disabled'))
    print('Latest device readings:')
    rows = battery_labels()
    for row in rows:
        print('  ' + ''.join(char for char in row if char.isprintable()))
    if not rows:
        print('  No readings available. Open the app to discover devices.')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog='logioptions',
        description='Options for Linux — Logitech device settings, battery tray, and Actions Ring.',
        epilog='Run logioptions without a command to open the app.\n'
               'Use logioptions COMMAND --help for command details.\n'
               'Commands marked Advanced access devices directly; prefer the app for everyday settings.',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--version', action='version', version=f'Options for Linux {version()}')
    commands = parser.add_subparsers(dest='command', title='commands', metavar='COMMAND')
    commands.add_parser('gui', help='Open the app (default)')
    commands.add_parser('status', help='Show background services and latest device readings')
    for name, help_text in [('inspect', 'Read a connected device name, features and battery'),
                            ('settings-read', 'Read current mouse DPI and SmartShift settings'),
                            ('dpi-set', 'Set a device-advertised DPI value'),
                            ('controls-read', 'Read the device control table'),
                            ('remap', 'Remap a programmable control to another hardware control'),
                            ('haptic-read', 'Read haptic configuration bytes'),
                            ('haptic-play', 'Play one waveform on a haptic device')]:
        command = commands.add_parser(name, help='Advanced: ' + help_text, description=help_text)
        command.add_argument('--path', required=True, help='Logitech HID++ hidraw node')
        command.add_argument('--device-index', type=lambda v: int(v, 0), required=True)
        command.add_argument('--trace', action='store_true', help='Write raw traffic to stderr')
        if name == 'haptic-play':
            command.add_argument('--waveform', type=lambda v: int(v, 0), required=True)
        elif name == 'dpi-set':
            command.add_argument('--dpi', type=int, required=True)
        elif name == 'remap':
            command.add_argument('--control', type=lambda v: int(v, 0), required=True)
            command.add_argument('--target', type=lambda v: int(v, 0), required=True)
    args = parser.parse_args(argv)
    if args.command in (None, 'gui'):
        from .gui import main as gui_main
        return gui_main()
    if args.command == 'status':
        return show_status()

    def trace(direction, packet):
        print(json.dumps(dict(direction=direction, hex=packet.hex())), file=sys.stderr)

    with LinuxHidppTransport(args.path, trace=trace if args.trace else None) as transport:
        device = Device(transport, args.device_index)
        if args.command == 'inspect':
            result = device.inspect()
        elif args.command == 'settings-read':
            result = dict(name=device.name(), dpi=device.dpi(), dpi_limits=device.dpi_limits(), smartshift=device.smartshift())
        elif args.command == 'dpi-set':
            name = device.name()
            device.set_dpi(args.dpi)
            result = dict(name=name, dpi=device.dpi())
        elif args.command == 'controls-read':
            result = dict(name=device.name(), controls=device.controls())
        elif args.command == 'remap':
            name = device.name()
            device.remap_control(args.control, args.target)
            result = dict(name=name, reporting=device.control_reporting(args.control))
        elif args.command == 'haptic-read':
            result = dict(name=device.name(), haptic_config_hex=device.haptic_config_bytes().hex())
        else:
            command = haptics.play_waveform(args.waveform)
            name = device.name()
            result = dict(name=name, waveform=args.waveform,
                          response_hex=device.execute_haptic(command).hex())
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    raise SystemExit(main())
