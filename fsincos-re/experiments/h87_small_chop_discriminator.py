#!/usr/bin/env python3
"""Generate an independent discriminator for the h86 69-bit-chop result.

The candidate profiles were selected after scoring h85, but this input set is
chosen without consulting any h87 hardware output.  It separates global
67/68/69/70-bit chopped evaluation, 69-bit RN/away evaluation, and the best
one-site h86 alternatives.
"""

from __future__ import annotations

import collections
import random
import sys

import h84_small_operation_search as h84
import h85_small_width_discriminator as h85


SEED = 0xF871C05
MAX_PER_SIGNATURE = 32
MAX_INPUTS = 1024

PROFILES = (
    ("base64", h84.Variant()),
    ("g67-chop", h84.Variant("*", 67, "chop")),
    ("g68-chop", h84.Variant("*", 68, "chop")),
    ("g69-chop", h84.Variant("*", 69, "chop")),
    ("g70-chop", h84.Variant("*", 70, "chop")),
    ("g69-rn", h84.Variant("*", 69, "rn")),
    ("g69-away", h84.Variant("*", 69, "away")),
    (
        "g69c-phrsq66c",
        h84.Variant(
            "ph_times_rsq", 66, "chop", False, 69, "chop"
        ),
    ),
    (
        "g69c-rsq66c",
        h84.Variant("rsq", 66, "chop", False, 69, "chop"),
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


def main() -> None:
    rng = random.Random(SEED)
    points = list(h85.candidates()[: 10 * 1025])
    for _ in range(600_000):
        exponent = rng.choices((-4, -5, -6), weights=(8, 3, 1))[0]
        sign = rng.getrandbits(1)
        se = (sign << 15) | (exponent + 16383)
        sig = rng.getrandbits(64) | (1 << 63)
        points.append((se, sig))

    selected: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    counts: collections.Counter[
        tuple[tuple[int, ...], tuple[int, ...]]
    ] = collections.Counter()
    for se, sig in points:
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
        f"h87: selected {len(selected)} inputs across "
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
