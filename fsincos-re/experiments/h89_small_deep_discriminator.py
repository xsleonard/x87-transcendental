#!/usr/bin/env python3
"""Generate deep-small discriminators for P5 versus Itanium evaluation.

h83/h85/h87 prove that the Round-18 Pentium six-term path continues through
exponents -4, -5, and -6.  This generator searches exponents -7 through -32
for architectural outputs where that path and Itanium small_r differ.  It
does not consult hardware while selecting inputs.
"""

from __future__ import annotations

import collections
import random
import sys

import h58_constraint_search as h58
import h64_poly_constraints as h64
import h65_poly_discriminator as h65
import h84_small_operation_search as h84


SEED = 0xF891C05
COUNT = 384
SCAN_LIMIT = 3_000_000


def p5_predictions(
    se: int,
    sig: int,
) -> tuple[tuple[tuple[int, int], tuple[int, int]], ...]:
    raw = h64.PolyRaw(
        index=0,
        sign=se >> 15,
        exponent=(se & 0x7FFF) - 16383,
        sig=sig,
        sincos=h65.DUMMY_SINCOS,
        standalone=h65.DUMMY_OUTPUT,
    )
    point = h64.prepare(
        raw,
        h65.CANDIDATE_PRODUCER,
        h65.CANDIDATE_Q_FINAL_PRODUCT_BITS,
    )
    values = (
        h64.poly_value(point, 0, h65.CANDIDATE_SIN),
        h64.poly_value(point, 1, h65.CANDIDATE_COS),
    )
    return tuple(
        tuple(h58.x87_round(value, rc) for value in values)
        for rc in h58.RCS
    )


def main() -> None:
    rng = random.Random(SEED)
    selected: list[tuple[int, int]] = []
    by_exponent: collections.Counter[int] = collections.Counter()
    by_lane: collections.Counter[str] = collections.Counter()
    for scan_index in range(SCAN_LIMIT):
        # Most observable differences are expected at the upper end, but
        # retain a deterministic tail over the complete nontrivial range.
        exponent = rng.choices(
            tuple(range(-7, -33, -1)),
            weights=tuple(32 if e == -7 else 8 if e == -8 else 1
                          for e in range(-7, -33, -1)),
        )[0]
        sign = rng.getrandbits(1)
        se = (sign << 15) | (exponent + 16383)
        sig = rng.getrandbits(64) | (1 << 63)
        itanium = tuple(
            h84.outputs(se, sig, rc, h84.Variant())
            for rc in h58.RCS
        )
        pentium = p5_predictions(se, sig)
        if itanium == pentium:
            continue
        selected.append((se, sig))
        by_exponent[exponent] += 1
        if any(left[0] != right[0]
               for left, right in zip(itanium, pentium)):
            by_lane["sine"] += 1
        if any(left[1] != right[1]
               for left, right in zip(itanium, pentium)):
            by_lane["cosine"] += 1
        if len(selected) == COUNT:
            print(
                f"h89: selected {COUNT} disagreements from "
                f"{scan_index + 1} scans; exponents={dict(by_exponent)}; "
                f"lanes={dict(by_lane)}; seed={SEED:#x}",
                file=sys.stderr,
            )
            break
    else:
        print(
            f"h89: selected only {len(selected)}/{COUNT} disagreements "
            f"from {SCAN_LIMIT} scans; exponents={dict(by_exponent)}; "
            f"lanes={dict(by_lane)}; seed={SEED:#x}",
            file=sys.stderr,
        )

    for se, sig in selected:
        print(f"{se:04x} {sig:016x}")


if __name__ == "__main__":
    main()
