#!/usr/bin/env python3
"""Generate held-out discriminators for the h84 small-kernel schedules.

No hardware result is consulted while selecting points.  The generator scans
deterministic direct-small inputs and retains only arguments where the
architectural RN result differs among:

* 68, 69, and 80-bit RN evaluation;
* 61, 62, 63, and 64-bit materialization of the sine r*ph product;
* the original 64-bit Itanium schedule.

Neighborhoods around the h83 boundaries are included because they reveal
which side of each output midpoint a candidate crosses.
"""

from __future__ import annotations

import collections
import pathlib
import random
import sys

import h84_small_operation_search as h84


ROOT = pathlib.Path(__file__).resolve().parents[1]
H83_INPUTS = ROOT / "capture-kit" / "inputs" / "constraint_small_h83.txt"
SEED = 0xF851C05
MAX_PER_SIGNATURE = 24
MAX_INPUTS = 4096

PROFILES = (
    ("base64", h84.Variant()),
    (
        "g68-p61",
        h84.Variant("ph_times_r", 61, "rn", False, 68, "rn"),
    ),
    (
        "g68-p62",
        h84.Variant("ph_times_r", 62, "rn", False, 68, "rn"),
    ),
    (
        "g68-p63",
        h84.Variant("ph_times_r", 63, "rn", False, 68, "rn"),
    ),
    (
        "g68-p64",
        h84.Variant("ph_times_r", 64, "rn", False, 68, "rn"),
    ),
    (
        "g69-p62",
        h84.Variant("ph_times_r", 62, "rn", False, 69, "rn"),
    ),
    (
        "g80-p62",
        h84.Variant("ph_times_r", 62, "rn", False, 80, "rn"),
    ),
)


def predictions(
    se: int,
    sig: int,
) -> tuple[tuple[tuple[int, int], tuple[int, int]], ...]:
    return tuple(
        h84.outputs(se, sig, "rn", variant)
        for _, variant in PROFILES
    )


def signature(
    predicted: tuple[tuple[tuple[int, int], tuple[int, int]], ...],
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Profile equivalence classes for sine and cosine results."""
    lanes = []
    for lane in (0, 1):
        classes: dict[tuple[int, int], int] = {}
        lanes.append(
            tuple(
                classes.setdefault(result[lane], len(classes))
                for result in predicted
            )
        )
    return tuple(lanes)  # type: ignore[return-value]


def candidates() -> list[tuple[int, int]]:
    h83 = [
        tuple(int(field, 16) for field in line.split())
        for line in H83_INPUTS.read_text().splitlines()
    ]
    points: list[tuple[int, int]] = []
    for se, sig in h83:
        for delta in range(-512, 513):
            neighbor = sig + delta
            if 1 << 63 <= neighbor < 1 << 64:
                points.append((se, neighbor))

    rng = random.Random(SEED)
    for _ in range(400_000):
        exponent = rng.choices((-4, -5, -6), weights=(8, 3, 1))[0]
        sign = rng.getrandbits(1)
        se = (sign << 15) | (exponent + 16383)
        sig = rng.getrandbits(64) | (1 << 63)
        points.append((se, sig))
    return points


def main() -> None:
    selected: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    counts: collections.Counter[
        tuple[tuple[int, ...], tuple[int, ...]]
    ] = collections.Counter()
    for se, sig in candidates():
        if (se, sig) in seen:
            continue
        predicted = predictions(se, sig)
        if len(set(predicted)) == 1:
            continue
        key = signature(predicted)
        if counts[key] >= MAX_PER_SIGNATURE:
            continue
        counts[key] += 1
        seen.add((se, sig))
        selected.append((se, sig))
        if len(selected) >= MAX_INPUTS:
            break

    print(
        f"h85: selected {len(selected)} inputs across "
        f"{len(counts)} prediction signatures",
        file=sys.stderr,
    )
    print(
        "profiles: " + ", ".join(name for name, _ in PROFILES),
        file=sys.stderr,
    )
    for key, count in counts.most_common():
        print(
            f"  count={count:2d} sine={key[0]} cosine={key[1]}",
            file=sys.stderr,
        )
    for se, sig in selected:
        print(f"{se:04x} {sig:016x}")


if __name__ == "__main__":
    main()
