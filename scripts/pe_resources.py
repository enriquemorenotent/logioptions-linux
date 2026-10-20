#!/usr/bin/env python3
"""Extract PE resources statically; record each resource's exact source offset."""
import argparse
import hashlib
import json
import mmap
import struct
from pathlib import Path


def extract(source, destination):
    destination.mkdir(parents=True, exist_ok=True)
    with source.open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
        def unpack(fmt, offset):
            return struct.unpack_from('<' + fmt, data, offset)

        if data[:2] != b'MZ':
            raise ValueError('Not a PE file')
        pe, = unpack('I', 0x3C)
        if data[pe:pe + 4] != b'PE\0\0':
            raise ValueError('Missing PE signature')
        count, = unpack('H', pe + 6)
        optional_size, = unpack('H', pe + 20)
        optional = pe + 24
        magic, = unpack('H', optional)
        if magic not in (0x10B, 0x20B):
            raise ValueError('Unknown optional header format')
        directories = optional + (112 if magic == 0x20B else 96)
        resource_rva, resource_size = unpack('II', directories + 16)
        sections = []
        for i in range(count):
            section = optional + optional_size + 40 * i
            virtual_size, rva, raw_size, raw_offset = unpack('IIII', section + 8)
            sections.append((rva, virtual_size, raw_size, raw_offset))

        def file_offset(address, size=1):
            for rva, virtual_size, raw_size, raw_offset in sections:
                if rva <= address and address + size <= rva + raw_size:
                    offset = raw_offset + address - rva
                    if offset + size > len(data):
                        raise ValueError('Truncated PE resource data')
                    return offset
            raise ValueError(f'RVA {address:#x} is not backed by file data')

        if not resource_rva:
            return []
        base = file_offset(resource_rva)
        records = []

        def visit(relative, labels, ancestors):
            if relative in ancestors or len(labels) > 8:
                raise ValueError('Cyclic or excessively deep resource tree')
            if relative + 16 > resource_size:
                raise ValueError('Resource directory outside resource section')
            named, numeric = unpack('HH', base + relative + 12)
            if relative + 16 + 8 * (named + numeric) > resource_size:
                raise ValueError('Resource entries outside resource section')
            for i in range(named + numeric):
                name, target = unpack('II', base + relative + 16 + i * 8)
                if name & 0x80000000:
                    location = base + (name & 0x7FFFFFFF)
                    length, = unpack('H', location)
                    label = data[location + 2:location + 2 + length * 2].decode('utf-16-le')
                else:
                    label = str(name)
                path = labels + [label]
                if target & 0x80000000:
                    visit(target & 0x7FFFFFFF, path, ancestors | {relative})
                else:
                    rva, size, codepage, reserved = unpack('IIII', base + target)
                    offset = file_offset(rva, size)
                    # Numbered names avoid trusting arbitrary embedded path strings.
                    filename = f'{len(records):05d}.bin'
                    payload = memoryview(data)[offset:offset + size]
                    try:
                        digest = hashlib.sha256(payload).hexdigest()
                        (destination / filename).write_bytes(payload)
                    finally:
                        payload.release()
                    records.append(dict(resource=path, file=filename, offset=offset,
                                        size=size, codepage=codepage, sha256=digest))

        visit(0, [], set())
        (destination / 'resources.json').write_text(json.dumps(records, indent=2) + '\n')
        return records


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    print(f'Extracted {len(extract(args.source, args.destination))} resources')
