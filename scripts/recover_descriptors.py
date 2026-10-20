#!/usr/bin/env python3
"""Recover embedded proto3 FileDescriptorProto records from an official binary.

Requires protobuf. Walks top-level wire fields to the syntax field rather than
guessing descriptor boundaries from strings. Records original offsets and hashes.
"""
import argparse
import hashlib
import json
import mmap
import re
from pathlib import Path

from google.protobuf import descriptor_pb2, json_format
from google.protobuf.message import DecodeError


def varint(data, offset, limit):
    value = 0
    for shift in range(0, 70, 7):
        if offset >= limit:
            raise ValueError('Truncated varint')
        byte = data[offset]
        offset += 1
        value |= (byte & 127) << shift
        if byte < 128:
            return value, offset
    raise ValueError('Oversized varint')


def descriptor_end(data, start):
    offset = start
    limit = min(len(data), start + 2 * 1024 * 1024)
    while offset < limit:
        tag, offset = varint(data, offset, limit)
        number, wire = tag >> 3, tag & 7
        if not 1 <= number <= 14:
            raise ValueError('Not a descriptor field')
        if wire == 0:
            _, offset = varint(data, offset, limit)
        elif wire == 1:
            offset += 8
        elif wire == 5:
            offset += 4
        elif wire == 2:
            size, offset = varint(data, offset, limit)
            end = offset + size
            if end > limit:
                raise ValueError('Truncated field')
            if number == 12:
                if data[offset:end] != b'proto3':
                    raise ValueError('Unsupported syntax')
                return end
            offset = end
        else:
            raise ValueError('Unsupported wire type')
    raise ValueError('Missing syntax field')


def recover(source, destination):
    destination.mkdir(parents=True, exist_ok=True)
    found = {}
    bundle = descriptor_pb2.FileDescriptorSet()
    with source.open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
        pattern = rb'\x0a([\x01-\x7f])([A-Za-z0-9_./-]+\.proto)'
        for match in re.finditer(pattern, data):
            name = match[2]
            if match[1][0] != len(name):
                continue
            try:
                end = descriptor_end(data, match.start())
                payload = data[match.start():end]
                descriptor = descriptor_pb2.FileDescriptorProto.FromString(payload)
                if descriptor.name != name.decode() or not descriptor.package:
                    continue
            except (ValueError, UnicodeDecodeError, DecodeError):
                # Binary matches need not actually be descriptors; reject parse failures.
                continue
            digest = hashlib.sha256(payload).hexdigest()
            key = (descriptor.name, digest)
            if key in found:
                found[key]['offsets'].append(match.start())
                continue
            file_id = f'{len(found):04d}'
            (destination / (file_id + '.pb')).write_bytes(payload)
            (destination / (file_id + '.json')).write_text(
                json_format.MessageToJson(descriptor, preserving_proto_field_name=True) + '\n')
            record = dict(name=descriptor.name, package=descriptor.package,
                          file=file_id + '.pb', json=file_id + '.json',
                          size=len(payload), sha256=digest, offsets=[match.start()])
            found[key] = record
            bundle.file.add().CopyFrom(descriptor)
    (destination / 'index.json').write_text(json.dumps(list(found.values()), indent=2) + '\n')
    (destination / 'descriptors.pb').write_bytes(bundle.SerializeToString())
    return list(found.values())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    print(f'Recovered {len(recover(args.source, args.destination))} unique embedded descriptors')
