#!/usr/bin/env python3
"""Generate and score the standalone-FSIN tiny-input boundary probe."""

from __future__ import annotations

import argparse
import pathlib
import subprocess


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_INPUT = (
    ROOT / "capture-kit" / "inputs" / "constraint_fsin_tiny_h117.txt"
)
SIGNIFICANDS = (
    0x8000000000000000,
    0x8000000000000001,
    0xAAAAAAAAAAAAAAAA,
    0xFFFFFFFFFFFFFFFF,
)


def generate_lines() -> list[str]:
    result = []
    for exponent in range(-72, -27):
        for significand in SIGNIFICANDS:
            for sign in (0, 1):
                se = (
                    (sign << 15)
                    | (exponent + 16383)
                )
                result.append(f"{se:04x} {significand:016x}")
    return result


def value(line: str) -> tuple[str, ...]:
    fields = line.split()
    if fields[0] == "C2":
        return ("C2",)
    if fields[0] != "OK":
        raise ValueError(line)
    return "OK", fields[1], fields[2]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", type=pathlib.Path)
    parser.add_argument("--capture", type=pathlib.Path)
    parser.add_argument("--model", type=pathlib.Path)
    args = parser.parse_args()
    lines = generate_lines()

    if args.write:
        args.write.write_text("\n".join(lines) + "\n")
        print(f"wrote {len(lines)} inputs to {args.write}")

    if args.capture or args.model:
        if not (args.capture and args.model):
            raise SystemExit("--capture and --model must be used together")
        input_text = "\n".join(lines) + "\n"
        total = 0
        for rc in ("rn", "rd", "ru"):
            command = [
                str(args.model.resolve()),
                "--batch",
                "--fsin-standalone",
            ]
            if rc != "rn":
                command.append(f"--rc={rc}")
            actual = subprocess.run(
                command,
                input=input_text,
                text=True,
                stdout=subprocess.PIPE,
                check=True,
            ).stdout.splitlines()
            expected = (
                args.capture
                / f"constraint_fsin_tiny_{rc}_status.txt"
            ).read_text().splitlines()
            misses = sum(
                value(left) != value(right)
                for left, right in zip(actual, expected)
            )
            total += misses
            print(f"{rc}: {misses}/{len(lines)} mismatches")
        print(f"combined: {total}/{3 * len(lines)} mismatches")


if __name__ == "__main__":
    main()
