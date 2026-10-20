#!/usr/bin/env python3
"""Temporarily capture one diverted control press/release and restore reporting."""
import argparse
import json
from pathlib import Path
import sys
import signal
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from logioptions.device import Device
from logioptions.hidpp import LinuxHidppTransport

def interrupted(signum, frame):
    raise KeyboardInterrupt('Capture interrupted; restoring button reporting')

signal.signal(signal.SIGTERM, interrupted)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--path', required=True)
parser.add_argument('--device-index', type=lambda v: int(v, 0), required=True)
parser.add_argument('--control', type=lambda v: int(v, 0), required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--seconds', type=int, default=120)
args = parser.parse_args()
if not 1 <= args.seconds <= 300:
    parser.error('--seconds must be between 1 and 300')
trace, events = [], []
result = dict(control_id=args.control)
try:
    with LinuxHidppTransport(args.path, trace=lambda direction, data: trace.append(dict(direction=direction, hex=data.hex()))) as transport:
        device = Device(transport, args.device_index)
        result['name'] = device.name()
        controls = {row['control_id']: row for row in device.controls()}
        if args.control not in controls or not controls[args.control]['flags'] & 0x20:
            raise ValueError('Control does not advertise diversion')
        before = device.control_reporting(args.control)
        result['before'] = before
        feature_index = device.feature(0x1B04)['index']
        try:
            device.set_control_reporting_bytes(args.control, 3, before['remapped_to'])
            result['during'] = device.control_reporting(args.control)
            if not result['during']['flags'] & 1:
                raise ValueError('Control did not enter diverted reporting')
            print('Capture ready: waiting for control press and release', flush=True)
            deadline = time.monotonic() + args.seconds
            pressed = False
            while time.monotonic() < deadline:
                report = transport.read_notification(timeout=0.5)
                if report is None or report[1] != args.device_index or report[2] != feature_index:
                    continue
                entry = dict(function=report[3] >> 4, report_hex=report.hex())
                if report[3] == 0 and len(report) >= 12:
                    entry['pressed_controls'] = [value for at in range(4, 12, 2)
                                                if (value := int.from_bytes(report[at:at + 2], 'big'))]
                    pressed |= args.control in entry['pressed_controls']
                    events.append(entry)
                    if pressed and args.control not in entry['pressed_controls']:
                        break
                else:
                    events.append(entry)
            result['press_and_release_seen'] = pressed and bool(events) and args.control not in events[-1].get('pressed_controls', [args.control])
        finally:
            restore_flags = 2 | (before['flags'] & 1)
            device.set_control_reporting_bytes(args.control, restore_flags, before['remapped_to'])
            result['restored'] = device.control_reporting(args.control)
            if result['restored'] != before:
                raise ValueError('Original control reporting did not restore')
finally:
    result['events'] = events
    result['trace'] = trace
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({key: value for key, value in result.items() if key not in ('trace',)}, indent=2))
