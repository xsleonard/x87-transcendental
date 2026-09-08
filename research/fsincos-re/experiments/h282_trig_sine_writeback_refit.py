#!/usr/bin/env python3
"""Refit only the shared-sine writeback after the h275 FMUL correction.

h230 fitted RN64 plus a 4/32- or 5/32-ulp proxy while several upstream
ordinary FMUL sites still used superseded scalar representatives.  h275
changed those products to the independently solved chop67 class.  This pass
therefore rechecks every 64--72-bit scalar writeback and the wide-family bias
coordinate, while freezing the graph, coefficients, all multiply classes,
FADD sites, cosine-tail state, and final reconstruction.
"""

from __future__ import annotations

import dataclasses

import h218_fadd_residual_programs as h218
import h226_p6_full_sine_graph as h226
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230
import h278_trig_final_literal_fadd as h278


CANDIDATES = tuple(
    dataclasses.replace(
        h228.CANDIDATE, sine_add=action, sine_bias=bias
    )
    for action in h230.ACTIONS
    for bias in h230.BIAS_ACTIONS
)


def main() -> None:
    complete = h218.datasets()
    selected = [
        h278.sample_dataset(name, points) for name, points in complete
    ]
    baseline = h230.score(selected, h228.CANDIDATE)
    print(
        "h282 sine-writeback refit: "
        f"candidates={len(CANDIDATES)} "
        f"selected={sum(len(points) for _, points in selected)} "
        f"complete={sum(len(points) for _, points in complete)}"
    )
    print(f"baseline selected objective={h226.objective(baseline)}")
    ranked = []
    for candidate in CANDIDATES:
        values = h230.score(selected, candidate)
        ranked.append(
            (
                h226.regressions(values, baseline),
                h226.objective(values),
                candidate.short(),
                candidate,
                values,
            )
        )
    ranked.sort()
    print("regression leaders:")
    for item in ranked[:24]:
        print(f"  regressions={item[0]} objective={item[1]} {item[2]}")
    print("objective leaders:")
    for item in sorted(ranked, key=lambda value: (value[1], value[0], value[2]))[:24]:
        print(f"  objective={item[1]} regressions={item[0]} {item[2]}")

    complete_baseline = h230.score(complete, h228.CANDIDATE)
    finalists = []
    for _, _, _, candidate, selected_values in ranked[:24]:
        if not h226.no_worse(selected_values, baseline):
            continue
        values = h230.score(complete, candidate)
        finalists.append(
            (
                h226.regressions(values, complete_baseline),
                h226.objective(values),
                candidate.short(),
                values,
            )
        )
    print(f"complete checked={len(finalists)}")
    for item in sorted(finalists):
        print(f"  regressions={item[0]} objective={item[1]} {item[2]}")


if __name__ == "__main__":
    main()
