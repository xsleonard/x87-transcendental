#!/usr/bin/env python3
"""Transfer the solved ordinary-FMUL class into the shared P6 table state.

The earlier shared-state fit predates the independent F2XM1 constraint and
uses empirical RN64/away67/chop65 representatives at four ordinary multiply
sites.  F2XM1 proves that ordinary FMUL returns a magnitude-chopped 67-bit
carrier.  This pass changes only those opcode-class sites; FADD, the distinct
multiply-class cosine-tail operation, constants, graph, and the h260 FPTAN
input read remain frozen.
"""

from __future__ import annotations

import argparse

import h218_fadd_residual_programs as h218
import h226_p6_full_sine_graph as h226
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230
import h245_fptan_shared_state as h245
import h260_fptan_multiplier_input_format as h260
import h268_fptan_residual_neighborhood as h268
import h271_fptan_scan_residuals as h271


BASE = h260.LEGACY_STATE
SHARED_FMUL = h228.CANDIDATE
FPTAN_INPUTS = h260.Candidate("rn64", "exact", "exact")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--section",
        choices=("all", "shared", "dense", "sweep", "residuals"),
        default="all",
    )
    args = parser.parse_args()
    if args.section in ("all", "shared"):
        shared = h218.datasets()
        baseline_shared = h230.score(shared, BASE)
        transferred_shared = h230.score(shared, SHARED_FMUL)
        print(
            "shared table objective: "
            f"baseline={h226.objective(baseline_shared)} "
            f"transferred={h226.objective(transferred_shared)} "
            f"regressions={h226.regressions(transferred_shared, baseline_shared)}"
        )
        for (name, _), baseline, transferred in zip(
            shared, baseline_shared, transferred_shared
        ):
            if baseline != transferred:
                print(f"  {name}: {baseline} -> {transferred}")

    for name in ("dense", "sweep"):
        if args.section not in ("all", name):
            continue
        points = h228.points(name)
        hardware = h245.captures(name)
        baseline = h260.score(points, hardware, FPTAN_INPUTS, BASE)
        transferred = h260.score(
            points, hardware, FPTAN_INPUTS, SHARED_FMUL
        )
        print(f"FPTAN {name}: {baseline} -> {transferred}")

    if args.section in ("all", "residuals"):
        residual_points, _ = h268.points(h271.INPUTS)
        residual_hardware = h271.captures()
        baseline = h260.score(
            residual_points, residual_hardware, FPTAN_INPUTS, BASE
        )
        transferred = h260.score(
            residual_points,
            residual_hardware,
            FPTAN_INPUTS,
            SHARED_FMUL,
        )
        print(f"FPTAN h269 seven residuals: {baseline} -> {transferred}")


if __name__ == "__main__":
    main()
