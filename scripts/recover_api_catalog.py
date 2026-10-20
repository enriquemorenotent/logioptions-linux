#!/usr/bin/env python3
"""Index literal route declarations and direct route call sites in source maps.

This is a lexical evidence index, not an exhaustive JavaScript analysis or proof
that a route is supported by every agent version.
"""
import argparse
import json
import re
from pathlib import Path


def recover(source_map):
    mapping = json.loads(source_map.read_text())
    sources = list(zip(mapping['sources'], mapping['sourcesContent']))
    route_source, routes_body = next((name, body) for name, body in sources
                                    if name.endswith('/src/constants/routes.js'))
    routes = {}
    declaration = re.compile(r'export\s+const\s+(\w+)\s*=\s*("(?:[^"\\]|\\.)*")\s*;')
    for match in declaration.finditer(routes_body):
        value = json.loads(match[2])
        if value.startswith('/'):
            routes[match[1]] = dict(path=value, declaration_source=route_source,
                                   declaration_line=routes_body.count('\n', 0, match.start()) + 1,
                                   calls=[])
    call = re.compile(r'connection\.send\(\s*(GET|SET|POST|REMOVE|SUBSCRIBE|UNSUBSCRIBE|BROADCAST)\s*,\s*(?:sprintf\(\s*)?ROUTE\.(\w+)')
    for name, body in sources:
        if not body or '/src/' not in name:
            continue
        for match in call.finditer(body):
            if match[2] in routes:
                routes[match[2]]['calls'].append(dict(verb=match[1], source=name,
                                                    line=body.count('\n', 0, match.start()) + 1))
    return routes


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_map', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    routes = recover(args.source_map)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(routes, indent=2) + '\n')
    print(f'Indexed {len(routes)} literal routes and {sum(len(r["calls"]) for r in routes.values())} direct call sites')
