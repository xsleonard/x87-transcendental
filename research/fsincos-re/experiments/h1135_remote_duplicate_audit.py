#!/usr/bin/env python3
"""Find exact h1135 operands in prior capture input inventories."""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("new", nargs="+", type=Path)
    parser.add_argument("--root", action="append", required=True, type=Path)
    args = parser.parse_args()

    operands = set()
    for path in args.new:
        with path.open() as source:
            operands.update(line.strip().lower() for line in source if line.strip())

    hits = []
    file_count = 0
    line_count = 0
    for root in args.root:
        for directory, _, names in os.walk(root):
            for name in names:
                if not name.endswith(".txt") or not (
                    "inputs" in name or "ops" in name
                ):
                    continue
                path = Path(directory) / name
                file_count += 1
                with path.open(errors="ignore") as source:
                    for number, line in enumerate(source, 1):
                        line_count += 1
                        value = line.strip().lower()
                        if value in operands:
                            hits.append((value, str(path), number))

    print(
        f"inventory_files={file_count} inventory_lines={line_count} "
        f"unique_new={len(operands)} hits={len(hits)}"
    )
    for value, path, number in hits:
        print(f"HIT\t{value}\t{path}\t{number}")


if __name__ == "__main__":
    main()
