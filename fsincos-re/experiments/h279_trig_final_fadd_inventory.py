#!/usr/bin/env python3
"""Inventory literal final-FADD programs over the h275 trig residuals.

h278 rejects every unconditional literal FADD program.  This pass asks the
next bounded question: can the same literal bus grammar reproduce each
remaining lane individually, and how many programs cover their union?  It is
an oracle inventory only; selecting a program by input identity is forbidden.
"""

from __future__ import annotations

import collections
import dataclasses

import h218_fadd_residual_programs as h218
import h226_p6_full_sine_graph as h226
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230
import h278_trig_final_literal_fadd as h278


ZERO = (0, 0, 0)


@dataclasses.dataclass(frozen=True)
class Residual:
    dataset: str
    point: object
    cosine: bool
    baseline: tuple[int, int, int]
    exact_mask: int
    improving_mask: int


def no_worse(value, baseline) -> bool:
    return all(new <= old for new, old in zip(value, baseline))


def inventory(name, points):
    residuals = []
    unreachable = collections.Counter()
    exact_programs = collections.Counter()
    improving_programs = collections.Counter()
    for point in points:
        baseline_values = h230.hidden_values(point, h228.CANDIDATE)
        baseline_metrics = h226.metric_for(point, baseline_values)
        if baseline_metrics == h226.ZERO_JOINT:
            continue
        candidate_metrics = [
            h226.metric_for(point, h278.hidden_values(point, candidate))
            for candidate in h278.CANDIDATES
        ]
        for cosine in (False, True):
            if cosine and not point.cosine_hardware:
                continue
            baseline = baseline_metrics[cosine]
            if baseline == ZERO:
                continue
            exact_mask = 0
            improving_mask = 0
            for index, metrics in enumerate(candidate_metrics):
                value = metrics[cosine]
                if value == ZERO:
                    exact_mask |= 1 << index
                    exact_programs[index] += 1
                if no_worse(value, baseline) and value != baseline:
                    improving_mask |= 1 << index
                    improving_programs[index] += 1
            observed = point.prepared.joint.observed
            stratum = (
                "cosine" if cosine else "sine",
                observed.source,
                observed.family,
                observed.point.cell,
            )
            if not exact_mask:
                unreachable[stratum] += 1
            residuals.append(
                Residual(
                    name,
                    point,
                    cosine,
                    baseline,
                    exact_mask,
                    improving_mask,
                )
            )
    return residuals, unreachable, exact_programs, improving_programs


def greedy_cover(residuals, exact: bool):
    field = "exact_mask" if exact else "improving_mask"
    uncovered = {
        index
        for index, residual in enumerate(residuals)
        if getattr(residual, field)
    }
    selected = []
    while uncovered:
        leader = None
        for program in range(len(h278.CANDIDATES)):
            covered = {
                index
                for index in uncovered
                if getattr(residuals[index], field) & (1 << program)
            }
            item = (len(covered), -program, program, covered)
            if leader is None or item[:2] > leader[:2]:
                leader = item
        if leader is None or not leader[0]:
            break
        selected.append((leader[2], leader[0]))
        uncovered -= leader[3]
    return selected, uncovered


def main() -> None:
    all_residuals = []
    masks = collections.Counter()
    for name, points in h218.datasets():
        residuals, unreachable, exact_counts, improving_counts = inventory(
            name, points
        )
        all_residuals.extend(residuals)
        masks.update(item.exact_mask for item in residuals)
        print(
            f"{name}: residual-lanes={len(residuals)} "
            f"exact-reachable={sum(bool(item.exact_mask) for item in residuals)} "
            f"improving-reachable="
            f"{sum(bool(item.improving_mask) for item in residuals)}"
        )
        if unreachable:
            print(f"  unreachable={dict(sorted(unreachable.items()))}")
        ranked = sorted(
            range(len(h278.CANDIDATES)),
            key=lambda index: (
                -exact_counts[index], -improving_counts[index], index
            ),
        )
        for index in ranked[:5]:
            if not (exact_counts[index] or improving_counts[index]):
                continue
            print(
                f"  p{index + 1:02d} exact={exact_counts[index]:4d} "
                f"improves={improving_counts[index]:4d} "
                f"{h278.CANDIDATES[index].short()}"
            )

    print(
        f"joint residual-lanes={len(all_residuals)} "
        f"unique-exact-masks={len(masks)}"
    )
    for exact in (True, False):
        selected, uncovered = greedy_cover(all_residuals, exact)
        field = "exact_mask" if exact else "improving_mask"
        reachable = sum(bool(getattr(item, field)) for item in all_residuals)
        label = "exact" if exact else "improving"
        print(
            f"joint {label}: reachable={reachable}/{len(all_residuals)} "
            f"greedy-programs={len(selected)} "
            f"uncovered-within-union={len(uncovered)}"
        )
        for index, count in selected:
            print(
                f"  covers={count:4d} p{index + 1:02d} "
                f"{h278.CANDIDATES[index].short()}"
            )


if __name__ == "__main__":
    main()
