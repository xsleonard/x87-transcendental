#!/usr/bin/env python3
"""Discriminate the h70 75-bit q-Horner pre-round survivor.

h70 found that materializing the final negative q-Horner sum away from zero
at 75 bits, then applying RN64, fixes both h65 outliers without changing any
of the 80,000 complete-capture results.  This generator scans host-FP-free
raw polynomial inputs and retains only architectural disagreements between:

* direct fused RN64 (Round 18);
* away75 -> RN64 at only the final q-Horner edge;
* away75 -> RN64 at every q-Horner edge.

Generation does not consult hardware.  ``score`` compares a fresh RN/RD/RU
capture against all three schedules.
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
import h70_poly_outlier_forensics as h70


DIRECT = h70.HornerVariant(-1, 64, "rn")
FINAL75 = h70.HornerVariant(5, 75, "away")
ALL75 = h70.HornerVariant(0, 75, "away")
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
    final75 = direct
    all75 = direct
    for step, row in enumerate(h58.C6[1:], 1):
        constant = h58.coefficient(row, h65.CANDIDATE_PRODUCER)
        direct_exact = h58.add_exact(
            h58.mul_exact(direct, asq), constant
        )
        direct = h58.round_fp(direct_exact, 64, "rn")

        final_exact = h58.add_exact(
            h58.mul_exact(final75, asq), constant
        )
        if step == 5:
            final_exact = h58.round_fp(final_exact, 75, "away")
        final75 = h58.round_fp(final_exact, 64, "rn")

        all_exact = h58.add_exact(
            h58.mul_exact(all75, asq), constant
        )
        all_exact = h58.round_fp(all_exact, 75, "away")
        all75 = h58.round_fp(all_exact, 64, "rn")
    return asq, direct, final75, all75


def rounded_cos(
    q: h58.FP,
    asq: h58.FP,
) -> tuple[tuple[int, int], ...]:
    tail = h58.fmul(q, asq, 67, "chop")
    hidden = h58.add_exact(h58.ONE, tail)
    return tuple(h58.x87_round(hidden, rc) for rc in h58.RCS)


def three_predictions(
    sig: int,
) -> tuple[
    tuple[tuple[int, int], ...],
    tuple[tuple[int, int], ...],
    tuple[tuple[int, int], ...],
]:
    asq, direct, final75, all75 = three_q_values(sig)
    return (
        rounded_cos(direct, asq),
        rounded_cos(final75, asq),
        rounded_cos(all75, asq),
    )


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
        final75 = rounded_cos(final_q, asq)
        all75 = rounded_cos(all_q, asq)
        final_diff = direct != final75
        placement_diff = final75 != all75
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
        ("final75", FINAL75),
        ("all75", ALL75),
    )
    print(f"loaded {len(raw)} captured h71 inputs")
    for name, variant in schedules:
        mode_misses = 0
        output_misses = 0
        rn_misses = 0
        examples = []
        for point in raw:
            predicted = tuple(
                h58.x87_round(
                    h70.horner_hidden(point, variant), rc
                )
                for rc in h58.RCS
            )
            expected = tuple(row[1] for row in point.sincos)
            misses = sum(
                actual != wanted
                for actual, wanted in zip(predicted, expected)
            )
            mode_misses += misses
            output_misses += bool(misses)
            rn_misses += predicted[0] != expected[0]
            if misses and len(examples) < 8:
                examples.append((point, predicted, expected))
        print(
            f"{name:8s} {mode_misses}/{3 * len(raw)} mode, "
            f"{output_misses}/{len(raw)} output, "
            f"{rn_misses}/{len(raw)} RN"
        )
        for point, predicted, expected in examples:
            print(
                f"  index={point.index} "
                f"{(point.sign << 15) | 0x3ffc:04x} "
                f"{point.sig:016x}"
            )
            print(
                "    predicted "
                + " ".join(
                    f"{rc}={value[0]:04x}:{value[1]:016x}"
                    for rc, value in zip(h58.RCS, predicted)
                )
            )
            print(
                "    hardware  "
                + " ".join(
                    f"{rc}={value[0]:04x}:{value[1]:016x}"
                    for rc, value in zip(h58.RCS, expected)
                )
            )


def emit(inputs: pathlib.Path, rc: str, which: str) -> None:
    rc_index = h58.RCS.index(rc)
    schedule = {
        "direct": DIRECT,
        "final75": FINAL75,
        "all75": ALL75,
    }[which]
    for index, line in enumerate(inputs.read_text().splitlines()):
        se_text, sig_text = line.split()
        se, sig = int(se_text, 16), int(sig_text, 16)
        raw = make_raw(index, se >> 15, sig)
        cosine = h58.x87_round(
            h70.horner_hidden(raw, schedule), rc
        )
        print(f"OK {cosine[0]:04x} {cosine[1]:016x}")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    scanning = sub.add_parser("scan")
    scanning.add_argument("--count", type=int, default=128)
    scanning.add_argument(
        "--seed", type=lambda value: int(value, 0), default=0xF710
    )
    scanning.add_argument("--scan-limit", type=int, default=10_000_000)
    scanning.add_argument("--emit", action="store_true")
    scoring = sub.add_parser("score")
    scoring.add_argument("inputs", type=pathlib.Path)
    scoring.add_argument("capture", type=pathlib.Path)
    scoring.add_argument("--prefix", default="constraint_poly_round75")
    emitting = sub.add_parser("emit")
    emitting.add_argument("inputs", type=pathlib.Path)
    emitting.add_argument("--rc", choices=h58.RCS, default="rn")
    emitting.add_argument(
        "--which",
        choices=("direct", "final75", "all75"),
        default="final75",
    )
    args = parser.parse_args()
    if args.command == "scan":
        scan(args.count, args.seed, args.scan_limit, args.emit)
    elif args.command == "score":
        score(args.inputs, args.capture, args.prefix)
    else:
        emit(args.inputs, args.rc, args.which)


if __name__ == "__main__":
    main()
