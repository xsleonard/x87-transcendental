#!/usr/bin/env python3
"""Discriminate the shared six-term producer in the wide table cells.

h64 identified chop67(a^2) plus fused RN64 Horner steps in the direct
polynomial region.  The wide table cells use the same six coefficients.
This host-FP-free generator selects raw [1/2, pi/4) inputs where applying
that producer with the unchanged table tail changes RN/RD/RU output bits.
"""

from __future__ import annotations

import argparse
import pathlib
import random
import sys

import h58_constraint_search as h58
import h59_discriminator as h59
import h65_poly_discriminator as h65


DUMMY_HW = (((0, 0), (0, 0)),) * 3
START = 0x8000000000000000
END = 0xC90FDAA22168C234


def values(
    raw: h58.RawPoint,
    profile: str,
) -> tuple[h58.FP, h58.FP]:
    magnitude = (0, raw.sig, raw.exponent - 63)
    return values_from_magnitude(magnitude, raw.sign, profile)


def prepare_magnitude(
    magnitude: h58.FP,
    sign: int,
    producer: h58.ProducerConfig,
    q_final_product_bits: int | None = None,
) -> h58.PreparedPoint:
    width = magnitude[1].bit_length()
    exponent = magnitude[2] + width - 1
    if width >= 64:
        normalized_sig = magnitude[1] >> (width - 64)
    else:
        normalized_sig = magnitude[1] << (64 - width)
    raw = h58.RawPoint(
        index=0,
        sign=sign,
        exponent=exponent,
        sig=normalized_sig,
        hw=DUMMY_HW,
    )
    cell = h58.cell_for(normalized_sig, exponent)
    a = h58.add_exact(magnitude, (1, cell, -6))
    asq = h58.fmul(
        a, a, producer.asq_bits, producer.asq_mode
    )
    p = h58.horner(h58.S6, asq, producer)
    if q_final_product_bits is None:
        q = h58.horner(h58.C6, asq, producer)
    else:
        q = h58.coefficient(h58.C6[0], producer)
        for step, row in enumerate(h58.C6[1:], 1):
            product = h58.mul_exact(q, asq)
            if step == len(h58.C6) - 1:
                product = h58.round_fp(
                    product, q_final_product_bits, "chop"
                )
            q = h58.round_fp(
                h58.add_exact(
                    product, h58.coefficient(row, producer)
                ),
                producer.horner_bits,
                producer.horner_mode,
            )
    return h58.PreparedPoint(
        raw=raw,
        cell=cell,
        wide=True,
        a=a,
        asq=asq,
        p=p,
        q=q,
        sin_t=h58.ROM[h58.SIN_ROW[cell]],
        cos_t=h58.ROM[h58.COS_ROW[cell]],
    )


def values_from_magnitude(
    magnitude: h58.FP,
    sign: int,
    profile: str,
) -> tuple[h58.FP, h58.FP]:
    baseline = prepare_magnitude(
        magnitude, sign, h58.BASE_PRODUCER
    )
    candidate = prepare_magnitude(
        magnitude, sign, h65.CANDIDATE_PRODUCER
    )
    candidate_product = prepare_magnitude(
        magnitude,
        sign,
        h65.CANDIDATE_PRODUCER,
        h65.CANDIDATE_Q_FINAL_PRODUCT_BITS,
    )
    p_point = candidate if profile in ("p-only", "both") else baseline
    if profile == "q-product":
        q_point = candidate_product
    else:
        q_point = (
            candidate if profile in ("q-only", "both") else baseline
        )
    m = h58.fmul(p_point.p, p_point.asq, 64, "rn")
    correction = h58.fmul(m, baseline.a, 64, "rn")
    sine_a = h58.fadd(baseline.a, correction, 64, "rn")
    tail = h58.fmul(q_point.q, q_point.asq, 64, "rn")
    one_plus_tail = h58.add_exact(h58.ONE, tail)
    sine = h58.add_exact(
        h58.mul_exact(baseline.sin_t, one_plus_tail),
        h58.mul_exact(baseline.cos_t, sine_a),
    )
    cosine = h58.add_exact(
        h58.mul_exact(baseline.cos_t, one_plus_tail),
        h58.neg(h58.mul_exact(baseline.sin_t, sine_a)),
    )
    if sign:
        sine = h58.neg(sine)
    return sine, cosine


def rounded(
    raw: h58.RawPoint,
    profile: str,
) -> tuple[tuple[tuple[int, int], tuple[int, int]], ...]:
    result = values(raw, profile)
    return tuple(
        tuple(h58.x87_round(value, rc) for value in result)
        for rc in h58.RCS
    )


def predictions(
    raw: h58.RawPoint,
) -> tuple[
    tuple[tuple[tuple[int, int], tuple[int, int]], ...],
    tuple[tuple[tuple[int, int], tuple[int, int]], ...],
]:
    return (
        rounded(raw, "baseline"),
        rounded(raw, "both"),
    )


def generate(count: int, seed: int, scan_limit: int) -> None:
    rng = random.Random(seed)
    found = 0
    for scan_index in range(scan_limit):
        raw = h58.RawPoint(
            index=found,
            sign=rng.randrange(2),
            exponent=-1,
            sig=rng.randrange(START, END),
            hw=DUMMY_HW,
        )
        baseline, candidate = predictions(raw)
        if baseline == candidate:
            continue
        se = (raw.sign << 15) | 0x3FFE
        print(f"{se:04x} {raw.sig:016x}")
        found += 1
        if found == count:
            print(
                f"selected {found} disagreements from {scan_index + 1} "
                f"raw inputs; seed={seed:#x}",
                file=sys.stderr,
            )
            return
    raise SystemExit(
        f"found only {found}/{count} disagreements in {scan_limit} inputs"
    )


def score(inputs: pathlib.Path, capture: pathlib.Path, prefix: str) -> None:
    raw = h59.load_score_points(inputs, capture, prefix)
    print(f"loaded {len(raw)} captured wide-producer inputs")
    for name in ("baseline", "p-only", "q-only", "q-product", "both"):
        result = score_points(raw, name)
        print(f"{name:9s} {result.describe()}")
        for key in sorted(result.by_region):
            if result.by_region[key]:
                print(f"          {key[1]}: {result.by_region[key]:.0f}")


def score_points(
    raw: list[h58.RawPoint],
    profile: str,
) -> h58.Score:
    result = h58.Score()
    for point in raw:
        result.total_outputs += 2
        predictions_by_rc = rounded(point, profile)
        for side in range(2):
            output_missed = False
            for rc_index, rc in enumerate(h58.RCS):
                mismatch = (
                    predictions_by_rc[rc_index][side]
                    != point.hw[rc_index][side]
                )
                result.mode_misses += mismatch
                result.rn_misses += mismatch if rc == "rn" else 0
                result.by_region[("wide", f"{'sc'[side]}-{rc}")] += mismatch
                output_missed |= mismatch
            result.constrained_output_misses += output_missed
    return result


def emit(inputs: pathlib.Path, rc: str, which: str) -> None:
    rc_index = h58.RCS.index(rc)
    for raw in h59.load_input_points(inputs):
        sine, cosine = rounded(raw, which)[rc_index]
        print(
            f"OK {sine[0]:04x} {sine[1]:016x} "
            f"{cosine[0]:04x} {cosine[1]:016x}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    generating = sub.add_parser("generate")
    generating.add_argument("--count", type=int, default=2000)
    generating.add_argument(
        "--seed", type=lambda value: int(value, 0), default=0xF670
    )
    generating.add_argument("--scan-limit", type=int, default=5_000_000)
    scoring = sub.add_parser("score")
    scoring.add_argument("inputs", type=pathlib.Path)
    scoring.add_argument("capture", type=pathlib.Path)
    scoring.add_argument("--prefix", default="constraint_wide_producer")
    emitting = sub.add_parser("emit")
    emitting.add_argument("inputs", type=pathlib.Path)
    emitting.add_argument("--rc", choices=h58.RCS, default="rn")
    emitting.add_argument(
        "--which",
        choices=(
            "baseline",
            "p-only",
            "q-only",
            "q-product",
            "both",
        ),
        default="q-only",
    )
    args = parser.parse_args()
    if args.command == "generate":
        generate(args.count, args.seed, args.scan_limit)
    elif args.command == "score":
        score(args.inputs, args.capture, args.prefix)
    else:
        emit(args.inputs, args.rc, args.which)


if __name__ == "__main__":
    main()
