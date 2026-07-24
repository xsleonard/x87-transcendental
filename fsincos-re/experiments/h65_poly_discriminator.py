#!/usr/bin/env python3
"""Generate and score an independent discriminator for h64's exact schedule.

Generation is host-FP-free and does not consult a hardware capture.  Random
raw x87 inputs in [2^-3, 1/4) are retained only when the historical model and
the h64 candidate predict different RN/RD/RU FSINCOS bits.  A fresh silicon
replay therefore tests the candidate on data that was not used to discover
or cross-validate it.
"""

from __future__ import annotations

import argparse
import dataclasses
import pathlib
import random
import sys
from collections import Counter

import h58_constraint_search as h58
import h64_poly_constraints as h64


CANDIDATE_PRODUCER = dataclasses.replace(
    h58.BASE_PRODUCER,
    asq_bits=67,
    asq_mode="chop",
    horner_form="fused",
    horner_bits=64,
    horner_mode="rn",
)
CANDIDATE_SIN = h64.PolyTail(
    "sin-correction-rounded",
    product_bits=64,
    product_mode="rn",
    mid_bits=67,
    mid_mode="chop",
)
CANDIDATE_COS = h64.PolyTail(
    "cos-tail",
    product_bits=67,
    product_mode="chop",
)
# h65 was selected before h70-h74 identified the final q-product
# materialization.  Keep that historical selection schedule explicit so the
# versioned input remains byte-reproducible; scoring and emission use the
# current candidate below.
SELECTION_Q_FINAL_PRODUCT_BITS: int | None = None
CANDIDATE_Q_FINAL_PRODUCT_BITS = 67
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


def rounded(
    raw: h64.PolyRaw,
    producer: h58.ProducerConfig,
    sine_tail: h64.PolyTail,
    cosine_tail: h64.PolyTail,
    q_final_product_bits: int | None = None,
) -> tuple[tuple[tuple[int, int], tuple[int, int]], ...]:
    point = h64.prepare(
        raw, producer, q_final_product_bits
    )
    sine = h64.poly_value(point, 0, sine_tail)
    cosine = h64.poly_value(point, 1, cosine_tail)
    return tuple(
        (h58.x87_round(sine, rc), h58.x87_round(cosine, rc))
        for rc in h58.RCS
    )


def predictions(
    raw: h64.PolyRaw,
    q_final_product_bits: int | None = CANDIDATE_Q_FINAL_PRODUCT_BITS,
) -> tuple[
    tuple[tuple[tuple[int, int], tuple[int, int]], ...],
    tuple[tuple[tuple[int, int], tuple[int, int]], ...],
]:
    baseline = rounded(
        raw,
        h58.BASE_PRODUCER,
        h64.SIN_BASE,
        h64.COS_BASE,
    )
    candidate = rounded(
        raw,
        CANDIDATE_PRODUCER,
        CANDIDATE_SIN,
        CANDIDATE_COS,
        q_final_product_bits,
    )
    return baseline, candidate


def generate(count: int, seed: int, scan_limit: int) -> None:
    rng = random.Random(seed)
    found = 0
    categories: Counter[tuple[bool, bool]] = Counter()
    for scan_index in range(scan_limit):
        raw = make_raw(
            found,
            rng.randrange(2),
            rng.getrandbits(64) | (1 << 63),
        )
        baseline, candidate = predictions(
            raw, SELECTION_Q_FINAL_PRODUCT_BITS
        )
        if baseline == candidate:
            continue
        sine_diff = any(
            base[0] != cand[0] for base, cand in zip(baseline, candidate)
        )
        cosine_diff = any(
            base[1] != cand[1] for base, cand in zip(baseline, candidate)
        )
        categories[(sine_diff, cosine_diff)] += 1
        se = (raw.sign << 15) | 0x3FFC
        print(f"{se:04x} {raw.sig:016x}")
        found += 1
        if found == count:
            print(
                f"selected {found} disagreements from {scan_index + 1} "
                f"raw inputs; categories={dict(categories)}; seed={seed:#x}",
                file=sys.stderr,
            )
            return
    raise SystemExit(
        f"found only {found}/{count} disagreements in {scan_limit} inputs; "
        f"categories={dict(categories)}"
    )


def load_captured(
    inputs: pathlib.Path,
    capture: pathlib.Path,
    prefix: str,
) -> list[h64.PolyRaw]:
    input_lines = inputs.read_text().splitlines()
    output_lines = [
        (capture / f"{prefix}_{rc}.txt").read_text().splitlines()
        for rc in h58.RCS
    ]
    if any(len(lines) != len(input_lines) for lines in output_lines):
        raise SystemExit("input/capture line counts differ")
    points = []
    for index, line in enumerate(input_lines):
        se_text, sig_text = line.split()
        se, sig = int(se_text, 16), int(sig_text, 16)
        points.append(
            h64.PolyRaw(
                index=index,
                sign=se >> 15,
                exponent=(se & 0x7FFF) - 16383,
                sig=sig,
                sincos=tuple(
                    h58.parse_sincos(lines[index]) for lines in output_lines
                ),
                standalone=DUMMY_OUTPUT,
            )
        )
    return points


def score_config(
    raw: list[h64.PolyRaw],
    producer: h58.ProducerConfig,
    sine_tail: h64.PolyTail,
    cosine_tail: h64.PolyTail,
    q_final_product_bits: int | None = None,
) -> tuple[int, int, int, Counter[tuple[str, str]]]:
    mode_misses = 0
    output_misses = 0
    rn_misses = 0
    by_side: Counter[tuple[str, str]] = Counter()
    for point in raw:
        predicted = rounded(
            point,
            producer,
            sine_tail,
            cosine_tail,
            q_final_product_bits,
        )
        for rc_index, rc in enumerate(h58.RCS):
            for side, name in enumerate(("sin", "cos")):
                mismatch = (
                    predicted[rc_index][side]
                    != point.sincos[rc_index][side]
                )
                mode_misses += mismatch
                by_side[(name, rc)] += mismatch
                if rc == "rn":
                    rn_misses += mismatch
        for side in range(2):
            if any(
                predicted[rc_index][side]
                != point.sincos[rc_index][side]
                for rc_index in range(3)
            ):
                output_misses += 1
    return mode_misses, output_misses, rn_misses, by_side


def score(inputs: pathlib.Path, capture: pathlib.Path, prefix: str) -> None:
    raw = load_captured(inputs, capture, prefix)
    print(f"loaded {len(raw)} captured discriminator inputs")
    configs = (
        (
            "baseline",
            h58.BASE_PRODUCER,
            h64.SIN_BASE,
            h64.COS_BASE,
            None,
        ),
        (
            "candidate",
            CANDIDATE_PRODUCER,
            CANDIDATE_SIN,
            CANDIDATE_COS,
            CANDIDATE_Q_FINAL_PRODUCT_BITS,
        ),
    )
    for (
        name,
        producer,
        sine_tail,
        cosine_tail,
        q_final_product_bits,
    ) in configs:
        mode, outputs, rn, by_side = score_config(
            raw,
            producer,
            sine_tail,
            cosine_tail,
            q_final_product_bits,
        )
        print(
            f"{name:9s} {mode}/{6 * len(raw)} mode, "
            f"{outputs}/{2 * len(raw)} output, "
            f"{rn}/{2 * len(raw)} RN"
        )
        print(
            f"          {producer.short()} | {sine_tail.short()} | "
            f"{cosine_tail.short()}"
        )
        for key in sorted(by_side):
            if by_side[key]:
                print(f"          {key[0]}-{key[1]}: {by_side[key]}")


def emit(inputs: pathlib.Path, rc: str, which: str) -> None:
    rc_index = h58.RCS.index(rc)
    for index, line in enumerate(inputs.read_text().splitlines()):
        se_text, sig_text = line.split()
        se, sig = int(se_text, 16), int(sig_text, 16)
        baseline, candidate = predictions(
            make_raw(index, se >> 15, sig)
        )
        outputs = baseline if which == "baseline" else candidate
        sine, cosine = outputs[rc_index]
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
        "--seed", type=lambda value: int(value, 0), default=0xF650
    )
    generating.add_argument("--scan-limit", type=int, default=2_000_000)
    scoring = sub.add_parser("score")
    scoring.add_argument("inputs", type=pathlib.Path)
    scoring.add_argument("capture", type=pathlib.Path)
    scoring.add_argument("--prefix", default="constraint_poly")
    emitting = sub.add_parser("emit")
    emitting.add_argument("inputs", type=pathlib.Path)
    emitting.add_argument("--rc", choices=h58.RCS, default="rn")
    emitting.add_argument(
        "--which", choices=("baseline", "candidate"), default="candidate"
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
