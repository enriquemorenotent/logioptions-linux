#!/usr/bin/env python3
"""Unpack the plaintext depot format observed in Options+ 2.8.981479.

Layout verified against full main application, keyboard and action depots:
4-byte magic, uint32 LE JSON length, JSON file list, then one uint32 LE length
and file payload per list entry. Encrypted capsules are deliberately rejected.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path, PurePosixPath

MAGIC = bytes.fromhex('10011720')


def unpack(source, destination):
    data = source.read_bytes()
    if data[:4] != MAGIC:
        raise ValueError('Unsupported depot format (possibly an encrypted capsule)')

    def length(at):
        if at + 4 > len(data):
            raise ValueError('Truncated length field')
        return struct.unpack_from('<I', data, at)[0]

    header_size = length(4)
    offset = 8 + header_size
    if offset > len(data):
        raise ValueError('Truncated header')
    header = json.loads(data[8:offset])
    entries = []
    seen = set()
    root = destination.resolve()
    # Validate every entry and complete layout before writing any output.
    for record in header['files']:
        name = record['name']
        path = PurePosixPath(name.replace('\\', '/'))
        if path.is_absolute() or '..' in path.parts or ':' in name or not path.parts:
            raise ValueError(f'Unsafe embedded filename: {name!r}')
        target = root.joinpath(*path.parts)
        if not target.resolve().is_relative_to(root):
            raise ValueError(f'Escaping path: {name!r}')
        if target in seen:
            # Preserve repeated entries without assuming the installer's overwrite policy.
            target = root / '__duplicate_entries__' / str(len(entries)) / Path(*path.parts)
            if not target.resolve().is_relative_to(root) or target in seen:
                raise ValueError(f'Unsafe duplicate path: {name!r}')
        seen.add(target)
        size = length(offset)
        offset += 4
        if offset + size > len(data):
            raise ValueError(f'Truncated payload: {name!r}')
        entries.append((target, name, offset, size))
        offset += size
    if offset != len(data):
        raise ValueError(f'Unexpected trailing data: {len(data) - offset} bytes')
    index = []
    for target, name, offset, size in entries:
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = memoryview(data)[offset:offset + size]
        target.write_bytes(payload)
        index.append(dict(path=name, extracted_path=str(target.relative_to(root)), offset=offset, size=size,
                          sha256=hashlib.sha256(payload).hexdigest()))
    return index


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    index = unpack(args.source, args.destination)
    args.destination.with_suffix('.inventory.json').write_text(json.dumps(index, indent=2) + '\n')
    print(f'Extracted and hashed {len(index)} files')
