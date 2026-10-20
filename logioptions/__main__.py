import argparse
import json
import sys

from .device import Device
from .hidpp import LinuxHidppTransport
from . import haptics


def main():
    if len(sys.argv) == 2 and sys.argv[1] == 'gui':
        from .gui import main as gui_main
        return gui_main()
    parser = argparse.ArgumentParser(description='Native Linux Logitech device inspection')
    commands = parser.add_subparsers(dest='command', required=True)
    for name, help_text in [('inspect', 'Read a connected device name, features and battery'),
                            ('settings-read', 'Read current mouse DPI and SmartShift settings'),
                            ('dpi-set', 'Set a device-advertised DPI value'),
                            ('controls-read', 'Read the device control table'),
                            ('remap', 'Remap a programmable control to another hardware control'),
                            ('haptic-read', 'Read haptic configuration bytes'),
                            ('haptic-play', 'Play one waveform on a haptic device')]:
        command = commands.add_parser(name, help=help_text)
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
    args = parser.parse_args()

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
    main()
