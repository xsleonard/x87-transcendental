#!/usr/bin/env python3
"""Re-cross-validate table parameters under the RN67 final correction.

Round 24 changes the boundary transfer function, so the row-169 correction
and Round-21 state biases must be rechecked rather than inherited blindly.
This pass searches:

* narrow row-169 deltas 0..12288 in steps of 256 crossed with 0..8/32 ulp;
* wide shared-S biases 0..10/32 ulp.

Selected h59/h67/h78/h95/h97 captures rank candidates.  The complete direct
capture and independent master sweep validate only the finalists.
"""

from __future__ import annotations

import h58_constraint_search as h58
import h59_discriminator as h59
import h60_round16_parity as h60
import h79_table_state_bias as h79
import h99_narrow_candidate_crossvalidate as h99
import h104_table_final_partial_search as h104


VARIANT = h104.Variant("delta-correction", 67, "rn")


def score(
    points: list[h58.PreparedPoint],
    delta: int,
    narrow_bias: int,
    wide_bias: int,
) -> tuple[int, int, int]:
    mode_misses = 0
    output_misses = 0
    rn_misses = 0
    for point in points:
        predicted = h104.values(
            point,
            VARIANT,
            delta,
            narrow_bias,
            wide_bias,
        )
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


def master_score(
    points: list[
        tuple[
            tuple[int, h58.PreparedPoint, bool] | None,
            tuple[tuple[int, int], tuple[int, int]] | None,
        ]
    ],
    delta: int,
    narrow_bias: int,
    wide_bias: int,
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
        predicted = h104.values(
            point,
            VARIANT,
            delta,
            narrow_bias,
            wide_bias,
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


def load_points(
    inputs,
    capture,
    prefix: str,
    exponent: int,
) -> list[h58.PreparedPoint]:
    return [
        h58.prepare(point)
        for point in h59.load_score_points(inputs, capture, prefix)
        if point.exponent == exponent
    ]


def main() -> None:
    narrow_sets = (
        (
            "h59",
            load_points(
                h99.H59_INPUTS,
                h99.H59_CAPTURE,
                "narrow",
                -2,
            ),
        ),
        (
            "h78",
            load_points(
                h99.H78_INPUTS,
                h99.H78_CAPTURE,
                "constraint_paired_table",
                -2,
            ),
        ),
        (
            "h95",
            load_points(
                h99.H95_INPUTS,
                h99.H95_CAPTURE,
                "constraint_table_local",
                -2,
            ),
        ),
        (
            "h97",
            load_points(
                h99.H97_INPUTS,
                h99.H97_CAPTURE,
                "constraint_narrow_coefficient",
                -2,
            ),
        ),
    )
    wide_sets = (
        (
            "h59",
            load_points(
                h99.H59_CAPTURE / "wide_inputs.txt",
                h99.H59_CAPTURE,
                "wide",
                -1,
            ),
        ),
        (
            "h67",
            load_points(
                h79.H67_INPUTS,
                h79.H67_CAPTURE,
                "constraint_wide_producer",
                -1,
            ),
        ),
        (
            "h78",
            load_points(
                h99.H78_INPUTS,
                h99.H78_CAPTURE,
                "constraint_paired_table",
                -1,
            ),
        ),
        (
            "h95",
            load_points(
                h99.H95_INPUTS,
                h99.H95_CAPTURE,
                "constraint_table_local",
                -1,
            ),
        ),
    )
    print(
        "h106: narrow "
        + " ".join(f"{name}={len(points)}" for name, points in narrow_sets)
        + "; wide "
        + " ".join(f"{name}={len(points)}" for name, points in wide_sets)
    )

    narrow_ranked = []
    for delta in range(0, 12289, 256):
        for bias in range(0, 9):
            scores = tuple(
                score(points, delta, bias, 5)
                for _, points in narrow_sets
            )
            narrow_ranked.append(
                (
                    sum(result[0] for result in scores),
                    sum(result[1] for result in scores),
                    sum(result[2] for result in scores),
                    delta,
                    bias,
                    scores,
                )
            )
    narrow_ranked.sort()

    wide_ranked = []
    for bias in range(0, 11):
        scores = tuple(
            score(points, 7168, 4, bias)
            for _, points in wide_sets
        )
        wide_ranked.append(
            (
                sum(result[0] for result in scores),
                sum(result[1] for result in scores),
                sum(result[2] for result in scores),
                bias,
                scores,
            )
        )
    wide_ranked.sort()

    dense_raw = h58.load_points(
        h99.ROOT / "capture-kit-captures" / "pentiumII"
    )
    dense_narrow = [
        h58.prepare(point)
        for point in dense_raw
        if point.exponent == -2
    ]
    dense_wide = [
        h58.prepare(point)
        for point in dense_raw
        if point.exponent == -1
    ]
    master = h99.master_points()

    print("narrow finalists:")
    for _, _, _, delta, bias, scores in narrow_ranked[:20]:
        dense = score(dense_narrow, delta, bias, 5)
        result = master_score(master, delta, bias, 5)
        print(
            f"  delta={delta:+5d} bias={bias}/32: "
            f"dense={dense[0]:4d} master={result[0]:3d}"
            f"(N={result[1]:2d},W={result[2]:3d}); "
            + " ".join(
                f"{name}={item[0]}"
                for (name, _), item in zip(narrow_sets, scores)
            )
        )
    print("wide finalists:")
    for _, _, _, bias, scores in wide_ranked:
        dense = score(dense_wide, 7168, 4, bias)
        result = master_score(master, 7168, 4, bias)
        print(
            f"  bias={bias}/32: dense={dense[0]:4d} "
            f"master={result[0]:3d}"
            f"(N={result[1]:2d},W={result[2]:3d}); "
            + " ".join(
                f"{name}={item[0]}"
                for (name, _), item in zip(wide_sets, scores)
            )
        )


if __name__ == "__main__":
    main()
