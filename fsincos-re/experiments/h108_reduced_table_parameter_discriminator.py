#!/usr/bin/env python3
"""Generate and score fresh reduced-table state-bias separators.

h107 validates the current Round-24 parameters on direct table operands.
The master sweep carries the exact 65-bit M66 residual into the same kernel,
and its held-out reduced cases prefer a different equivalent shared-S bias.
That observation may be selection noise or evidence that the extra residual
bit changes a still-unmodeled producer phase.

This generator does not consult hardware.  It scans original operands with
exponents 0..62, retains only inputs whose M66 residual enters a table cell,
and selects RN/RD/RU separators for fine-grained shared-S candidates:

* narrow reduced residual: 16..40 / 256 local S ulp;
* wide reduced residual: 32..72 / 256 local S ulp.

All candidates use the h107-supported +7168 narrow row-169 correction and
the Round-24 RN67 delta accumulator.  The scorer ranks each family against
a returned capture.
"""

from __future__ import annotations

import argparse
import collections
import pathlib
import random
import sys

import h58_constraint_search as h58
import h60_round16_parity as h60
import h79_table_state_bias as h79
import h80_round21_parity as h80
import h104_table_final_partial_search as h104


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_reduced_table_parameters_h108.txt"
)
DEFAULT_METADATA = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_reduced_table_parameters_h108.meta.txt"
)
VARIANT = h104.Variant("delta-correction", 67, "rn")
SEED = 0xF10824
NARROW_BIASES = (16, 20, 24, 28, 32, 36, 40)
WIDE_BIASES = (32, 40, 48, 56, 64, 72)


def values(
    point: h58.PreparedPoint,
    bias: int,
) -> tuple[h58.FP, h58.FP]:
    altered, one_plus_tail, sine_a = h104.state(
        point,
        narrow_delta=7168,
        narrow_bias=0,
        wide_bias=0,
    )
    sine_a = h79.bias_toward_zero(
        sine_a,
        bias,
        denominator_bits=8,
    )
    sine = h104.lane_value(
        altered.sin_t,
        altered.cos_t,
        one_plus_tail,
        sine_a,
        False,
        VARIANT,
    )
    cosine = h104.lane_value(
        altered.cos_t,
        altered.sin_t,
        one_plus_tail,
        sine_a,
        True,
        VARIANT,
    )
    if point.raw.sign:
        sine = h58.neg(sine)
    return sine, cosine


def prediction(
    se: int,
    sig: int,
    bias: int,
) -> tuple[tuple[tuple[int, int], tuple[int, int]], ...]:
    active = h80.active_table_input(se, sig)
    if active is None or not active[2]:
        raise ValueError("h108 input is not a reduced table operand")
    signed_n, point, _ = active
    return active_prediction(signed_n, point, bias)


def active_prediction(
    signed_n: int,
    point: h58.PreparedPoint,
    bias: int,
) -> tuple[tuple[tuple[int, int], tuple[int, int]], ...]:
    rotated = h60.rotate(values(point, bias), signed_n)
    return tuple(
        tuple(h58.x87_round(value, rc) for value in rotated)
        for rc in h58.RCS
    )


def signature(
    profiles: tuple[
        tuple[tuple[tuple[int, int], tuple[int, int]], ...],
        ...,
    ],
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    lanes = []
    for lane in (0, 1):
        classes: dict[tuple[tuple[int, int], ...], int] = {}
        lanes.append(
            tuple(
                classes.setdefault(
                    tuple(result[lane] for result in profile),
                    len(classes),
                )
                for profile in profiles
            )
        )
    return tuple(lanes)  # type: ignore[return-value]


def generate(
    output: pathlib.Path,
    metadata: pathlib.Path,
    count: int,
    scan_limit: int,
) -> None:
    rng = random.Random(SEED)
    selected = collections.Counter()
    signatures: dict[str, collections.Counter[object]] = {
        "narrow": collections.Counter(),
        "wide": collections.Counter(),
    }
    rows = []
    meta = []
    for scan_index in range(scan_limit):
        exponent = rng.randrange(0, 63)
        sig = rng.randrange(1 << 63, 1 << 64)
        sign = rng.getrandbits(1)
        se = (sign << 15) | (exponent + 16383)
        active = h80.active_table_input(se, sig)
        if active is None or not active[2]:
            continue
        _, point, _ = active
        family = "wide" if point.wide else "narrow"
        if selected[family] >= count:
            if all(
                selected[name] >= count
                for name in ("narrow", "wide")
            ):
                break
            continue
        biases = (
            WIDE_BIASES if point.wide else NARROW_BIASES
        )
        profiles = tuple(
            active_prediction(active[0], point, bias)
            for bias in biases
        )
        if len(set(profiles)) == 1:
            continue
        key = signature(profiles)
        if signatures[family][key] >= 64:
            continue
        signatures[family][key] += 1
        group = selected[family]
        selected[family] += 1
        rows.append(f"{se:04x} {sig:016x}")
        meta.append(
            f"{family} {group} {active[0]} {point.cell}"
        )
        if all(selected[name] >= count for name in ("narrow", "wide")):
            break
    if any(selected[family] < count for family in ("narrow", "wide")):
        raise SystemExit(
            f"h108 selected {dict(selected)} after "
            f"{scan_index + 1} scans; wanted {count} per family"
        )
    output.write_text("\n".join(rows) + "\n")
    metadata.write_text("\n".join(meta) + "\n")
    print(
        f"h108: selected {dict(selected)} inputs from "
        f"{scan_index + 1} scans; signatures="
        f"{ {name: len(items) for name, items in signatures.items()} }; "
        f"seed={SEED:#x}",
        file=sys.stderr,
    )


def load_capture(
    inputs: pathlib.Path,
    metadata: pathlib.Path,
    capture: pathlib.Path,
) -> list[
    tuple[
        str,
        int,
        int,
        tuple[tuple[tuple[int, int], tuple[int, int]], ...],
    ]
]:
    input_lines = inputs.read_text().splitlines()
    meta = metadata.read_text().splitlines()
    outputs = [
        (
            capture
            / f"constraint_reduced_table_parameters_{rc}.txt"
        )
        .read_text()
        .splitlines()
        for rc in h58.RCS
    ]
    if (
        len(meta) != len(input_lines)
        or any(len(lines) != len(input_lines) for lines in outputs)
    ):
        raise SystemExit("h108 input/metadata/capture line counts differ")
    result = []
    for index, (line, metadata_line) in enumerate(
        zip(input_lines, meta)
    ):
        se_text, sig_text = line.split()
        family = metadata_line.split()[0]
        result.append(
            (
                family,
                int(se_text, 16),
                int(sig_text, 16),
                tuple(
                    h58.parse_sincos(lines[index])
                    for lines in outputs
                ),
            )
        )
    return result


def score(
    inputs: pathlib.Path,
    metadata: pathlib.Path,
    capture: pathlib.Path,
) -> None:
    raw = load_capture(inputs, metadata, capture)
    for family, biases in (
        ("narrow", NARROW_BIASES),
        ("wide", WIDE_BIASES),
    ):
        selected = [item for item in raw if item[0] == family]
        ranked = []
        for bias in biases:
            mode_misses = 0
            input_misses = 0
            rn_misses = 0
            for _, se, sig, hardware in selected:
                predicted = prediction(se, sig, bias)
                missed_input = False
                for rc_index, (expected_lanes, actual_lanes) in enumerate(
                    zip(predicted, hardware)
                ):
                    for expected, actual in zip(
                        expected_lanes,
                        actual_lanes,
                    ):
                        mismatch = expected != actual
                        mode_misses += mismatch
                        rn_misses += mismatch if rc_index == 0 else 0
                        missed_input |= mismatch
                input_misses += missed_input
            ranked.append(
                (
                    mode_misses,
                    input_misses,
                    rn_misses,
                    bias,
                )
            )
        print(
            f"{family}: {len(selected)} inputs / "
            f"{6 * len(selected)} output-mode checks"
        )
        for mode, inputs_missed, rn, bias in sorted(ranked):
            print(
                f"  bias={bias:+3d}/256: mode={mode:4d} "
                f"inputs={inputs_missed:4d} rn={rn:4d}"
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--metadata",
        type=pathlib.Path,
        default=DEFAULT_METADATA,
    )
    parser.add_argument("--count", type=int, default=1024)
    parser.add_argument("--scan-limit", type=int, default=4_000_000)
    parser.add_argument("--score", type=pathlib.Path, metavar="CAPTURE")
    args = parser.parse_args()
    if args.score is not None:
        score(args.output, args.metadata, args.score)
    else:
        generate(
            args.output,
            args.metadata,
            args.count,
            args.scan_limit,
        )


if __name__ == "__main__":
    main()
