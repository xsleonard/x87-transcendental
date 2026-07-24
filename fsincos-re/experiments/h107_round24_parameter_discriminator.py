#!/usr/bin/env python3
"""Generate and score fresh Round-24 parameter separators.

After introducing the RN67 delta correction, existing datasets disagree on
the exact narrow row-169 correction and wide shared-S bias.  This generator
does not consult hardware.  It selects direct table inputs where these
candidate sets predict different RN/RD/RU architectural results:

* narrow: row-169 deltas 0..10240, with the 4/32 S bias fixed;
* wide: S biases 3..9/32, with the six-term producer fixed.

The returned Skylake capture is scored independently per family.
"""

from __future__ import annotations

import argparse
import collections
import pathlib
import random
import sys

import h58_constraint_search as h58
import h59_discriminator as h59
import h104_table_final_partial_search as h104


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_round24_parameters_h107.txt"
)
DEFAULT_METADATA = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_round24_parameters_h107.meta.txt"
)
VARIANT = h104.Variant("delta-correction", 67, "rn")
SEED = 0xF10724
NARROW_DELTAS = (
    0,
    1024,
    2048,
    3072,
    4096,
    5120,
    6144,
    7168,
    8192,
    10240,
)
WIDE_BIASES = (3, 4, 5, 6, 7, 8, 9)
DUMMY_HW = (((0, 0), (0, 0)),) * 3


def prediction(
    se: int,
    sig: int,
    family: str,
    parameter: int,
) -> tuple[tuple[tuple[int, int], tuple[int, int]], ...]:
    raw = h58.RawPoint(
        index=0,
        sign=se >> 15,
        exponent=(se & 0x7FFF) - 16383,
        sig=sig,
        hw=DUMMY_HW,
    )
    point = h58.prepare(raw)
    if family == "narrow":
        values = h104.values(
            point,
            VARIANT,
            narrow_delta=parameter,
            narrow_bias=4,
            wide_bias=5,
        )
    else:
        values = h104.values(
            point,
            VARIANT,
            narrow_delta=7168,
            narrow_bias=4,
            wide_bias=parameter,
        )
    return tuple(
        tuple(h58.x87_round(value, rc) for value in values)
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
    families = ("narrow", "wide")
    for scan_index in range(scan_limit):
        family = families[scan_index & 1]
        if selected[family] >= count:
            if all(selected[name] >= count for name in families):
                break
            continue
        cells = h59.CELLS[:4] if family == "narrow" else h59.CELLS[4:]
        _, exponent, start, end = cells[
            rng.randrange(len(cells))
        ]
        sig = rng.randrange(start, end)
        sign = rng.getrandbits(1)
        se = (sign << 15) | (exponent + 16383)
        parameters = (
            NARROW_DELTAS
            if family == "narrow"
            else WIDE_BIASES
        )
        profiles = tuple(
            prediction(se, sig, family, parameter)
            for parameter in parameters
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
        meta.append(f"{family} {group}")
    if any(selected[family] < count for family in families):
        raise SystemExit(
            f"h107 selected {dict(selected)} after {scan_limit} scans; "
            f"wanted {count} per family"
        )
    output.write_text("\n".join(rows) + "\n")
    metadata.write_text("\n".join(meta) + "\n")
    print(
        f"h107: selected {dict(selected)} inputs from "
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
        (capture / f"constraint_round24_parameters_{rc}.txt")
        .read_text()
        .splitlines()
        for rc in h58.RCS
    ]
    if (
        len(meta) != len(input_lines)
        or any(len(lines) != len(input_lines) for lines in outputs)
    ):
        raise SystemExit("h107 input/metadata/capture line counts differ")
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
    for family, parameters in (
        ("narrow", NARROW_DELTAS),
        ("wide", WIDE_BIASES),
    ):
        selected = [item for item in raw if item[0] == family]
        ranked = []
        for parameter in parameters:
            mode_misses = 0
            input_misses = 0
            rn_misses = 0
            for _, se, sig, hardware in selected:
                predicted = prediction(
                    se,
                    sig,
                    family,
                    parameter,
                )
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
                    parameter,
                )
            )
        label = "delta" if family == "narrow" else "bias"
        print(
            f"{family}: {len(selected)} inputs / "
            f"{6 * len(selected)} output-mode checks"
        )
        for mode, inputs_missed, rn, parameter in sorted(ranked):
            suffix = "" if family == "narrow" else "/32"
            print(
                f"  {label}={parameter:+5d}{suffix}: "
                f"mode={mode:4d} inputs={inputs_missed:4d} rn={rn:4d}"
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
