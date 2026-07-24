#!/usr/bin/env python3
"""Generate a large hardware-blind scan of the two residual path classes.

h267 showed that each old FPTAN failure is isolated from all adjacent x87
significands through distance 4096.  Both nevertheless reconstruct a
negative, wide cell-36 residual: one enters directly and one after reduction.
This generator samples those two complete operand intervals uniformly with a
fixed SplitMix64 permutation.  It includes the two old seeds as positive
controls but does not use processor outputs or model low-bit state.
"""

from __future__ import annotations

import argparse
import pathlib
import sys


MASK64 = (1 << 64) - 1
DIRECT_SE = 0xBFFE
DIRECT_LOW = 0x8000000000000000
DIRECT_HIGH = 0xA000000000000000
REDUCED_SE = 0x3FFE
REDUCED_LOW = 0xF21FB54442D1846A
REDUCED_HIGH = 1 << 64
SEEDS = (
    (REDUCED_SE, 0xF2C6A55E688A4408),
    (DIRECT_SE, 0x9B55474B1424FFF5),
)


def splitmix64(value: int) -> int:
    value = (value + 0x9E3779B97F4A7C15) & MASK64
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & MASK64
    return value ^ (value >> 31)


def map_interval(value: int, low: int, high: int) -> int:
    return low + ((value * (high - low)) >> 64)


def generated(count: int):
    yield from SEEDS
    remaining = count - len(SEEDS)
    for index in range(remaining):
        random = splitmix64(index)
        if index & 1:
            yield (
                REDUCED_SE,
                map_interval(random, REDUCED_LOW, REDUCED_HIGH),
            )
        else:
            yield (
                DIRECT_SE,
                map_interval(random, DIRECT_LOW, DIRECT_HIGH),
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=1_000_002)
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()
    if args.count < len(SEEDS):
        raise SystemExit(f"count must be at least {len(SEEDS)}")
    stream = args.output.open("w") if args.output else sys.stdout
    try:
        for se, significand in generated(args.count):
            print(f"{se:04x} {significand:016x}", file=stream)
    finally:
        if args.output:
            stream.close()


if __name__ == "__main__":
    main()
