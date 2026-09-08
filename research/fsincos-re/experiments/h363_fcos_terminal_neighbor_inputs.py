#!/usr/bin/env python3
"""Generate sign-mirrored FCOS neighborhoods around terminal-boundary seeds."""

from __future__ import annotations

import argparse
import hashlib
import pathlib


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", type=pathlib.Path)
    parser.add_argument("output", type=pathlib.Path)
    parser.add_argument("metadata", type=pathlib.Path)
    parser.add_argument("--index", action="append", type=int, required=True)
    parser.add_argument("--radius", type=int, default=4096)
    args = parser.parse_args()

    source = [
        tuple(int(field, 16) for field in line.split())
        for line in args.inputs.read_text().splitlines()
        if line.strip()
    ]
    seen: set[tuple[int, int]] = set()
    output_lines = []
    metadata_lines = ["row seed_index offset sign partition"]
    for seed_index in args.index:
        sign_exponent, significand = source[seed_index]
        exponent = sign_exponent & 0x7FFF
        for offset in range(-args.radius, args.radius + 1):
            neighbor = significand + offset
            if not 1 << 63 <= neighbor < 1 << 64:
                continue
            for sign in (0, 1):
                item = (exponent | (sign << 15), neighbor)
                if item in seen:
                    continue
                seen.add(item)
                row = len(output_lines)
                output_lines.append(f"{item[0]:04x} {item[1]:016x}")
                partition = "train" if (abs(offset) & 1) == 0 else "heldout"
                metadata_lines.append(
                    f"{row} {seed_index} {offset} {sign} {partition}"
                )

    output_text = "\n".join(output_lines) + "\n"
    metadata_lines.extend(
        (
            f"rows {len(output_lines)}",
            f"radius {args.radius}",
            "seed_indexes " + ",".join(str(index) for index in args.index),
            "input_sha256 " + hashlib.sha256(output_text.encode()).hexdigest(),
        )
    )
    args.output.write_text(output_text)
    args.metadata.write_text("\n".join(metadata_lines) + "\n")
    print(f"wrote {len(output_lines)} inputs to {args.output}")
    print(metadata_lines[-1])


if __name__ == "__main__":
    main()
