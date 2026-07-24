#!/usr/bin/env python3
"""Cross-validate joint narrow coefficient/shared-S candidates.

h98 shows that paired-state tomography and h97 architectural separators do
not select the same exact parameter pair.  This pass avoids promoting a
discriminator-conditioned optimum: it scores a small, explicit candidate
set on the complete dense direct capture, h59, h78, h95, h97, and the
independent 50,038-input master sweep.

The wide family remains at the Round-21 5/32-ulp state.  Reported master
counts therefore include its fixed residual and expose only net changes
caused by the narrow candidate.
"""

from __future__ import annotations

import pathlib

import h58_constraint_search as h58
import h59_discriminator as h59
import h60_round16_parity as h60
import h78_paired_table_tomography as h78
import h79_table_state_bias as h79
import h80_round21_parity as h80
import h96_table_state_regression as h96
import h97_narrow_coefficient_discriminator as h97


ROOT = pathlib.Path(__file__).resolve().parents[1]
MASTER_INPUTS = ROOT / "capture-kit" / "inputs" / "sweep_inputs.txt"
MASTER_CAPTURE = (
    ROOT / "capture-kit-captures" / "pentiumII" / "sweep_rn.txt"
)
H59_INPUTS = (
    ROOT / "capture-kit" / "inputs" / "constraint_narrow_h59.txt"
)
H59_CAPTURE = (
    ROOT / "capture-kit-captures" / "skylake-h59-constraints"
)
H78_INPUTS = (
    ROOT / "capture-kit" / "inputs" / "constraint_paired_table_h78.txt"
)
H78_CAPTURE = (
    ROOT / "capture-kit-captures" / "skylake-h78-paired-table"
)
H95_INPUTS = (
    ROOT / "capture-kit" / "inputs" / "constraint_table_local_h95.txt"
)
H95_CAPTURE = (
    ROOT / "capture-kit-captures" / "skylake-h95-table-local"
)
H97_INPUTS = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_narrow_coefficient_h97.txt"
)
H97_CAPTURE = (
    ROOT
    / "capture-kit-captures"
    / "skylake-h97-narrow-coefficient"
)

# Includes the historical state, exact-Taylor-adjacent delta, powers of two,
# the earlier cross-data optima, the paired-interval optimum, and h97's
# held-out optimum.  Bias is expressed in 1/256 ulp.
CANDIDATES = (
    (0, 32),
    (272, 32),
    (2048, 32),
    (3072, 28),
    (4096, 28),
    (4096, 32),
    (6144, 28),
    (6144, 32),
    (7168, 28),
    (7168, 32),
    (7680, 26),
    (7680, 28),
    (7680, 32),
    (8192, 26),
    (8192, 28),
    (8192, 32),
)


def candidate_values(
    point: h58.PreparedPoint,
    delta: int,
    bias: int,
) -> tuple[h58.FP, h58.FP]:
    altered = h97.alter_p(point, delta)
    return h79.values(
        altered,
        h79.BASE,
        bias,
        denominator_bits=8,
    )


def load_narrow(
    inputs: pathlib.Path,
    capture: pathlib.Path,
    prefix: str,
) -> list[h58.RawPoint]:
    return [
        point
        for point in h59.load_score_points(inputs, capture, prefix)
        if point.exponent == -2
    ]


def dataset_score(
    raw: list[h58.RawPoint],
    delta: int,
    bias: int,
) -> tuple[int, int, int]:
    mode_misses = 0
    output_misses = 0
    rn_misses = 0
    for item in raw:
        values = candidate_values(h58.prepare(item), delta, bias)
        for side, value in enumerate(values):
            missed_output = False
            for rc_index, rc in enumerate(h58.RCS):
                mismatch = (
                    h58.x87_round(value, rc)
                    != item.hw[rc_index][side]
                )
                mode_misses += mismatch
                rn_misses += mismatch if rc_index == 0 else 0
                missed_output |= mismatch
            output_misses += missed_output
    return mode_misses, output_misses, rn_misses


def master_points() -> list[
    tuple[
        tuple[int, h58.PreparedPoint, bool] | None,
        tuple[tuple[int, int], tuple[int, int]] | None,
    ]
]:
    inputs = [
        tuple(int(field, 16) for field in line.split())
        for line in MASTER_INPUTS.read_text().splitlines()
    ]
    hardware = [
        None if line == "C2" else h58.parse_sincos(line)
        for line in MASTER_CAPTURE.read_text().splitlines()
    ]
    return [
        (h80.active_table_input(se, sig), expected)
        for (se, sig), expected in zip(inputs, hardware)
    ]


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
    narrow_misses = 0
    wide_misses = 0
    for active, expected in points:
        if active is None:
            continue
        if expected is None:
            raise AssertionError("table-active master input returned C2")
        signed_n, point, _ = active
        if point.wide:
            values = h79.values(point, h79.BASE, 5)
        else:
            values = candidate_values(point, delta, bias)
        actual = tuple(
            h58.x87_round(value, "rn")
            for value in h60.rotate(values, signed_n)
        )
        mismatch = actual != expected
        misses += mismatch
        narrow_misses += mismatch if not point.wide else 0
        wide_misses += mismatch if point.wide else 0
    return misses, narrow_misses, wide_misses


def main() -> None:
    dense = [
        point
        for point in h58.load_points(
            ROOT / "capture-kit-captures" / "pentiumII"
        )
        if point.exponent == -2
    ]
    datasets = (
        ("dense", dense),
        (
            "h59",
            load_narrow(
                H59_INPUTS,
                H59_CAPTURE,
                "narrow",
            ),
        ),
        (
            "h78",
            load_narrow(
                H78_INPUTS,
                H78_CAPTURE,
                "constraint_paired_table",
            ),
        ),
        (
            "h95",
            load_narrow(
                H95_INPUTS,
                H95_CAPTURE,
                "constraint_table_local",
            ),
        ),
        (
            "h97",
            load_narrow(
                H97_INPUTS,
                H97_CAPTURE,
                "constraint_narrow_coefficient",
            ),
        ),
    )
    master = master_points()
    print(
        "h99 datasets: "
        + " ".join(f"{name}={len(raw)}" for name, raw in datasets)
        + f" master={len(master)}"
    )
    ranked = []
    for delta, bias in CANDIDATES:
        scores = [
            dataset_score(raw, delta, bias)
            for _, raw in datasets
        ]
        master_result = master_score(master, delta, bias)
        ranked.append(
            (
                master_result[0],
                sum(score[0] for score in scores),
                delta,
                bias,
                scores,
                master_result,
            )
        )
    for (
        _,
        total_mode,
        delta,
        bias,
        scores,
        master_result,
    ) in sorted(ranked):
        print(
            f"delta={delta:+5d} bias={bias:2d}/256: "
            f"master={master_result[0]:3d} "
            f"(N={master_result[1]:2d},W={master_result[2]:3d}); "
            f"cross-mode={total_mode:5d} "
            + " ".join(
                f"{name}={score[0]}"
                for (name, _), score in zip(datasets, scores)
            )
        )


if __name__ == "__main__":
    main()
