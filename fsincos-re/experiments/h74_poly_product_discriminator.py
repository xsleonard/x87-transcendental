#!/usr/bin/env python3
"""Fresh discriminator for chop67 product materialization in q-Horner.

h73 inferred ``RN64(chop67(q*a^2) + coefficient)`` after observing h71.
This generator uses a new seed and retains only architectural disagreements
among direct fused RN64, final-edge-only product chop67, and product chop67
at every q-Horner edge.  It does not consult hardware.
"""

from __future__ import annotations

import argparse
import pathlib
import random
import sys
from collections import Counter

import h58_constraint_search as h58
import h64_poly_constraints as h64
import h65_poly_discriminator as h65
import h73_poly_product_crossvalidate as h73


DIRECT = h73.DIRECT
FINAL67 = h73.ProductVariant(5, 67, "chop")
ALL67 = h73.ProductVariant(0, 67, "chop")
DUMMY_OUTPUT = ((0, 0), (0, 0))
DUMMY_SINCOS = (DUMMY_OUTPUT,) * 3


def make_raw(index: int, sign: int, sig: int) -> h64.PolyRaw:
    return h64.PolyRaw(
        index=index,
        sign=sign,
        exponent=-3,
        sig=sig,
        sincos=DUMMY_SINCOS,
        standalone=DUMMY_OUTPUT,
    )


def three_q_values(
    sig: int,
) -> tuple[h58.FP, h58.FP, h58.FP, h58.FP]:
    r: h58.FP = (0, sig, -66)
    asq = h58.fmul(r, r, 67, "chop")
    direct = h58.coefficient(h58.C6[0], h65.CANDIDATE_PRODUCER)
    final67 = direct
    all67 = direct
    for step, row in enumerate(h58.C6[1:], 1):
        constant = h58.coefficient(row, h65.CANDIDATE_PRODUCER)
        direct = h58.round_fp(
            h58.add_exact(
                h58.mul_exact(direct, asq), constant
            ),
            64,
            "rn",
        )

        final_product = h58.mul_exact(final67, asq)
        if step == 5:
            final_product = h58.round_fp(
                final_product, 67, "chop"
            )
        final67 = h58.round_fp(
            h58.add_exact(final_product, constant), 64, "rn"
        )

        all_product = h58.round_fp(
            h58.mul_exact(all67, asq), 67, "chop"
        )
        all67 = h58.round_fp(
            h58.add_exact(all_product, constant), 64, "rn"
        )
    return asq, direct, final67, all67


def rounded_cos(
    q: h58.FP,
    asq: h58.FP,
) -> tuple[tuple[int, int], ...]:
    tail = h58.fmul(q, asq, 67, "chop")
    hidden = h58.add_exact(h58.ONE, tail)
    return tuple(h58.x87_round(hidden, rc) for rc in h58.RCS)


def scan(count: int, seed: int, scan_limit: int, emit: bool) -> None:
    rng = random.Random(seed)
    found = 0
    q_final_differences = 0
    q_placement_differences = 0
    categories: Counter[str] = Counter()
    for scan_index in range(scan_limit):
        sig = rng.getrandbits(64) | (1 << 63)
        asq, direct_q, final_q, all_q = three_q_values(sig)
        if direct_q != final_q:
            q_final_differences += 1
        if final_q != all_q:
            q_placement_differences += 1
        if direct_q == final_q and final_q == all_q:
            continue
        direct = rounded_cos(direct_q, asq)
        final67 = rounded_cos(final_q, asq)
        all67 = rounded_cos(all_q, asq)
        final_diff = direct != final67
        placement_diff = final67 != all67
        if not final_diff and not placement_diff:
            continue
        category = (
            "both" if final_diff and placement_diff
            else "final" if final_diff
            else "placement"
        )
        categories[category] += 1
        if emit:
            sign = rng.randrange(2)
            se = (sign << 15) | 0x3FFC
            print(f"{se:04x} {sig:016x}")
        found += 1
        if found == count:
            print(
                f"selected {found} architectural disagreements from "
                f"{scan_index + 1} raw inputs; q-final="
                f"{q_final_differences}, q-placement="
                f"{q_placement_differences}, "
                f"categories={dict(categories)}; seed={seed:#x}",
                file=sys.stderr,
            )
            return
    print(
        f"scan exhausted: architectural={found}/{count}, "
        f"q-final={q_final_differences}, "
        f"q-placement={q_placement_differences}, "
        f"categories={dict(categories)}, inputs={scan_limit}, "
        f"seed={seed:#x}",
        file=sys.stderr,
    )


def score(
    inputs: pathlib.Path,
    capture: pathlib.Path,
    prefix: str,
) -> None:
    raw = h65.load_captured(inputs, capture, prefix)
    schedules = (
        ("direct", DIRECT),
        ("final67", FINAL67),
        ("all67", ALL67),
    )
    print(f"loaded {len(raw)} captured h74 inputs")
    for name, variant in schedules:
        result = h73.score(raw, variant)
        print(
            f"{name:8s} {result[0]}/{3 * len(raw)} mode, "
            f"{result[1]}/{len(raw)} output, "
            f"{result[2]}/{len(raw)} RN"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    scanning = sub.add_parser("scan")
    scanning.add_argument("--count", type=int, default=64)
    scanning.add_argument(
        "--seed", type=lambda value: int(value, 0), default=0xF740
    )
    scanning.add_argument("--scan-limit", type=int, default=15_000_000)
    scanning.add_argument("--emit", action="store_true")
    scoring = sub.add_parser("score")
    scoring.add_argument("inputs", type=pathlib.Path)
    scoring.add_argument("capture", type=pathlib.Path)
    scoring.add_argument("--prefix", default="constraint_poly_product")
    args = parser.parse_args()
    if args.command == "scan":
        scan(args.count, args.seed, args.scan_limit, args.emit)
    else:
        score(args.inputs, args.capture, args.prefix)


if __name__ == "__main__":
    main()
