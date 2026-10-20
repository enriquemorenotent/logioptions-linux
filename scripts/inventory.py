#!/usr/bin/env python3
"""Create a reproducible content inventory without executing inspected files."""
import argparse
import hashlib
import json
from pathlib import Path


def inventory(root):
    root = root.resolve()
    paths = sorted(root.rglob("*")) if root.is_dir() else [root]
    result = []
    for path in paths:
        if path.is_symlink() or not path.is_file():
            continue
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        result.append({
            "path": str(path.relative_to(root) if root.is_dir() else path.name),
            "size": path.stat().st_size,
            "sha256": digest.hexdigest(),
        })
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.path.exists():
        parser.error(f"Input does not exist: {args.path}")
    result = inventory(args.path)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Inventoried {len(result)} files into {args.output}")


if __name__ == "__main__":
    main()
