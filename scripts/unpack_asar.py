#!/usr/bin/env python3
"""Extract regular packed files from the observed Electron ASAR container."""
import argparse
import hashlib
import json
import struct
from pathlib import Path


def unpack(source, destination):
    root = destination.resolve()
    with source.open('rb') as stream:
        prefix = stream.read(16)
        if len(prefix) != 16:
            raise ValueError('Truncated ASAR header')
        marker, header_size, pickle_size, json_size = struct.unpack('<4I', prefix)
        if marker != 4 or header_size != pickle_size + 4 or json_size > pickle_size - 4:
            raise ValueError('Unsupported ASAR header')
        header = json.loads(stream.read(json_size))
        base = 8 + header_size
        records = []

        def walk(files, parent):
            for name, item in files.items():
                if name in ('.', '..') or '/' in name or '\\' in name or ':' in name:
                    raise ValueError(f'Unsafe filename: {name!r}')
                path = parent / name
                if not path.resolve().is_relative_to(root):
                    raise ValueError('Escaping ASAR path')
                if 'files' in item:
                    walk(item['files'], path)
                    continue
                if 'link' in item or item.get('unpacked'):
                    raise ValueError(f'Unsupported link or external file: {path}')
                offset, size = int(item['offset']), int(item['size'])
                if offset < 0 or size < 0 or base + offset + size > source.stat().st_size:
                    raise ValueError('Truncated ASAR payload')
                stream.seek(base + offset)
                payload = stream.read(size)
                digest = hashlib.sha256(payload).hexdigest()
                integrity = item.get('integrity', {})
                if integrity:
                    if integrity.get('algorithm') != 'SHA256' or integrity.get('hash') != digest:
                        raise ValueError(f'ASAR integrity mismatch: {path}')
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(payload)
                records.append(dict(path=str(path.relative_to(root)), offset=base + offset,
                                    size=size, sha256=digest))
        walk(header['files'], root)
        return records


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    records = unpack(args.source, args.destination)
    args.destination.with_suffix('.inventory.json').write_text(json.dumps(records, indent=2) + '\n')
    print(f'Extracted and hashed {len(records)} files')
