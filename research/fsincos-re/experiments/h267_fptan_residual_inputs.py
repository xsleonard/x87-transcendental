#!/usr/bin/env python3
"""Generate dense x87 neighborhoods around the two h260 residual inputs.

The seeds are the original dense-corpus operands, not their reduced residuals.
Each seed receives every adjacent representable significand within ``radius``
plus power-of-two offsets through bit 31.  Output is capture-kit input format
on stdout so the existing compiler-free binary can consume it directly.
"""

from __future__ import annotations

import argparse


SEEDS = (
    (0x3FFE, 0xF2C6A55E688A4408),
    (0xBFFE, 0x9B55474B1424FFF5),
)


def inputs(radius: int):
    result = set()
    for se, significand in SEEDS:
        for delta in range(-radius, radius + 1):
            candidate = significand + delta
            if 1 << 63 <= candidate < 1 << 64:
                result.add((se, candidate))
        for bit in range(0, 32):
            for direction in (-1, 1):
                candidate = significand + direction * (1 << bit)
                if 1 << 63 <= candidate < 1 << 64:
                    result.add((se, candidate))
    return sorted(result)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--radius", type=int, default=4096)
    args = parser.parse_args()
    if args.radius < 0:
        raise SystemExit("radius must be nonnegative")
    for se, significand in inputs(args.radius):
        print(f"{se:04x} {significand:016x}")


if __name__ == "__main__":
    main()
