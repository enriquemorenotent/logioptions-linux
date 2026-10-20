#!/usr/bin/env python3
"""Read one feature lookup through the native Linux HID++ implementation."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from logioptions.hidpp import LinuxHidppTransport

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--path', required=True)
parser.add_argument('--device-index', type=lambda v: int(v, 0), required=True)
parser.add_argument('--feature', type=lambda v: int(v, 0), required=True)
parser.add_argument('--timeout', type=float, default=2)
args = parser.parse_args()
trace = []
with LinuxHidppTransport(args.path, trace=lambda direction, data: trace.append(dict(direction=direction, hex=data.hex()))) as transport:
    reply = transport.lookup_feature(args.device_index, args.feature, timeout=args.timeout)
print(json.dumps(dict(reply=reply, trace=trace), indent=2))
