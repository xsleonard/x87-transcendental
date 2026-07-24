#!/usr/bin/env python3
"""Test the narrow row-169 correction's wide-family analogue.

ROM rows 157 and 169 are the final sine-polynomial coefficients for the
six- and four-term table families and have nearly identical values.  Since
the narrow row-169 equivalent correction survives h107, this pass tests the
previously uncrossed possibility that the wide row 157 needs a similar
correction after the RN67 final accumulator is introduced.

Candidate row-157 deltas are crossed with the wide shared-S proxy and ranked
on h59/h67/h78/h95/h107.  The complete direct capture, h108's exact 65-bit
reduced operands, and the untouched master validate only the finalists.
"""

from __future__ import annotations

import dataclasses

import h58_constraint_search as h58
import h59_discriminator as h59
import h60_round16_parity as h60
import h79_table_state_bias as h79
import h80_round21_parity as h80
import h99_narrow_candidate_crossvalidate as h99
import h104_table_final_partial_search as h104
import h107_round24_parameter_discriminator as h107
import h108_reduced_table_parameter_discriminator as h108


VARIANT = h104.Variant("delta-correction", 67, "rn")
DELTAS = tuple(range(-16384, 16385, 1024))
BIASES = tuple(range(0, 11))
H108_CAPTURE = (
    h108.ROOT
    / "capture-kit-captures"
    / "skylake-h108-reduced-table-parameters"
)


def alter_p(
    point: h58.PreparedPoint,
    delta: int,
) -> h58.PreparedPoint:
    rows = h58.S6
    value = h58.coefficient(rows[0], h58.BASE_PRODUCER)
    for row in rows[1:-1]:
        value = h58.fadd(
            h58.fmul(value, point.asq, 64, "rn"),
            h58.coefficient(row, h58.BASE_PRODUCER),
            64,
            "rn",
        )
    constant = h58.ROM[rows[-1]]
    constant = (
        constant[0],
        constant[1] + delta,
        constant[2],
    )
    value = h58.fadd(
        h58.fmul(value, point.asq, 64, "rn"),
        constant,
        64,
        "rn",
    )
    return dataclasses.replace(point, p=value)


def values(
    point: h58.PreparedPoint,
    delta: int,
    bias: int,
) -> tuple[h58.FP, h58.FP]:
    return h104.values(
        alter_p(point, delta),
        VARIANT,
        narrow_delta=0,
        narrow_bias=0,
        wide_bias=bias,
    )


def score(
    points: list[h58.PreparedPoint],
    delta: int,
    bias: int,
) -> tuple[int, int, int]:
    mode_misses = 0
    output_misses = 0
    rn_misses = 0
    for point in points:
        predicted = values(point, delta, bias)
        for side, value in enumerate(predicted):
            missed_output = False
            for rc_index, rc in enumerate(h58.RCS):
                mismatch = (
                    h58.x87_round(value, rc)
                    != point.raw.hw[rc_index][side]
                )
                mode_misses += mismatch
                rn_misses += mismatch if rc_index == 0 else 0
                missed_output |= mismatch
            output_misses += missed_output
    return mode_misses, output_misses, rn_misses


def load_direct(
    inputs,
    capture,
    prefix: str,
) -> list[h58.PreparedPoint]:
    return [
        h58.prepare(point)
        for point in h59.load_score_points(inputs, capture, prefix)
        if point.exponent == -1
    ]


def load_h108() -> list[
    tuple[
        int,
        h58.PreparedPoint,
        tuple[tuple[tuple[int, int], tuple[int, int]], ...],
    ]
]:
    input_lines = h108.DEFAULT_OUTPUT.read_text().splitlines()
    metadata = h108.DEFAULT_METADATA.read_text().splitlines()
    outputs = [
        (
            H108_CAPTURE
            / f"constraint_reduced_table_parameters_{rc}.txt"
        )
        .read_text()
        .splitlines()
        for rc in h58.RCS
    ]
    result = []
    for index, (line, meta) in enumerate(
        zip(input_lines, metadata)
    ):
        if meta.split()[0] != "wide":
            continue
        se, sig = (int(field, 16) for field in line.split())
        active = h80.active_table_input(se, sig)
        if active is None or not active[2] or not active[1].wide:
            raise AssertionError("h108 wide metadata mismatch")
        result.append(
            (
                active[0],
                active[1],
                tuple(
                    h58.parse_sincos(lines[index])
                    for lines in outputs
                ),
            )
        )
    return result


def score_h108(
    points: list[
        tuple[
            int,
            h58.PreparedPoint,
            tuple[tuple[tuple[int, int], tuple[int, int]], ...],
        ]
    ],
    delta: int,
    bias: int,
) -> tuple[int, int, int]:
    mode_misses = 0
    input_misses = 0
    rn_misses = 0
    for signed_n, point, hardware in points:
        rotated = h60.rotate(values(point, delta, bias), signed_n)
        missed_input = False
        for rc_index, rc in enumerate(h58.RCS):
            for side, value in enumerate(rotated):
                mismatch = (
                    h58.x87_round(value, rc)
                    != hardware[rc_index][side]
                )
                mode_misses += mismatch
                rn_misses += mismatch if rc_index == 0 else 0
                missed_input |= mismatch
        input_misses += missed_input
    return mode_misses, input_misses, rn_misses


def master_score(
    points: list[
        tuple[
            tuple[int, h58.PreparedPoint, bool] | None,
            tuple[tuple[int, int], tuple[int, int]] | None,
        ]
    ],
    delta: int,
    bias: int,
) -> tuple[int, int, int]:
    misses = 0
    narrow = 0
    wide = 0
    for active, expected in points:
        if active is None:
            continue
        if expected is None:
            raise AssertionError("table-active master input returned C2")
        signed_n, point, _ = active
        predicted = (
            values(point, delta, bias)
            if point.wide
            else h104.values(point, VARIANT)
        )
        actual = tuple(
            h58.x87_round(value, "rn")
            for value in h60.rotate(predicted, signed_n)
        )
        mismatch = actual != expected
        misses += mismatch
        narrow += mismatch if not point.wide else 0
        wide += mismatch if point.wide else 0
    return misses, narrow, wide


def main() -> None:
    datasets = (
        (
            "h59",
            load_direct(
                h99.H59_CAPTURE / "wide_inputs.txt",
                h99.H59_CAPTURE,
                "wide",
            ),
        ),
        (
            "h67",
            load_direct(
                h79.H67_INPUTS,
                h79.H67_CAPTURE,
                "constraint_wide_producer",
            ),
        ),
        (
            "h78",
            load_direct(
                h99.H78_INPUTS,
                h99.H78_CAPTURE,
                "constraint_paired_table",
            ),
        ),
        (
            "h95",
            load_direct(
                h99.H95_INPUTS,
                h99.H95_CAPTURE,
                "constraint_table_local",
            ),
        ),
        (
            "h107",
            load_direct(
                h107.DEFAULT_OUTPUT,
                h107.ROOT
                / "capture-kit-captures"
                / "skylake-h107-round24-parameters",
                "constraint_round24_parameters",
            ),
        ),
    )
    ranked = []
    for delta in DELTAS:
        for bias in BIASES:
            scores = tuple(
                score(points, delta, bias)
                for _, points in datasets
            )
            ranked.append(
                (
                    sum(result[0] for result in scores),
                    sum(result[1] for result in scores),
                    sum(result[2] for result in scores),
                    delta,
                    bias,
                    scores,
                )
            )
    ranked.sort()

    dense = [
        h58.prepare(point)
        for point in h58.load_points(
            h99.ROOT / "capture-kit-captures" / "pentiumII"
        )
        if point.exponent == -1
    ]
    reduced = load_h108()
    master = h99.master_points()
    print(
        "h109: "
        + " ".join(
            f"{name}={len(points)}" for name, points in datasets
        )
        + f"; deltas={len(DELTAS)} biases={len(BIASES)}"
    )
    for (
        total_mode,
        total_output,
        total_rn,
        delta,
        bias,
        scores,
    ) in ranked[:24]:
        dense_result = score(dense, delta, bias)
        reduced_result = score_h108(reduced, delta, bias)
        master_result = master_score(master, delta, bias)
        print(
            f"  delta={delta:+6d} bias={bias}/32: "
            f"search={total_mode:4d}/{total_output:4d}/{total_rn:4d} "
            f"dense={dense_result[0]:4d} h108={reduced_result[0]:3d} "
            f"master={master_result[0]:3d}"
            f"(N={master_result[1]:2d},W={master_result[2]:3d}); "
            + " ".join(
                f"{name}={result[0]}"
                for (name, _), result in zip(datasets, scores)
            )
        )


if __name__ == "__main__":
    main()
