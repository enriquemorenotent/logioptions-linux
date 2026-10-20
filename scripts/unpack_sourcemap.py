#!/usr/bin/env python3
"""Extract embedded source-map sources under numbered, non-executable filenames."""
import argparse
import hashlib
import json
from pathlib import Path


def unpack(source, destination):
    mapping = json.loads(source.read_text())
    sources = mapping['sources']
    bodies = mapping.get('sourcesContent', [])
    if len(sources) != len(bodies):
        raise ValueError('Missing embedded source bodies')
    destination.mkdir(parents=True, exist_ok=True)
    records = []
    for number, (name, body) in enumerate(zip(sources, bodies)):
        if body is None:
            continue
        filename = f'{number}.txt'
        payload = body.encode('utf-8')
        (destination / filename).write_bytes(payload)
        records.append(dict(source=name, file=filename, sha256=hashlib.sha256(payload).hexdigest()))
    (destination / 'index.json').write_text(json.dumps(records, indent=2) + '\n')
    return records


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    print(f'Extracted {len(unpack(args.source, args.destination))} embedded sources')
