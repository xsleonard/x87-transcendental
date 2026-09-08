#!/usr/bin/env python3
"""Partition Round-36 residual lanes by exact-producing FADD programs.

Round 36 validates one conditional leaf from h212's literal-program oracle.
This pass removes that leaf from the baseline, then asks which of h212's
eleven jam-sub greedy-cover programs can exactly reproduce every remaining
standalone-sine or paired-cosine hardware interval.  Sweep, dense, old
focused captures, and the fresh h216 capture are reported independently.

This is an oracle inventory, not a selector: a program is credited per lane
without claiming that hardware can recognize that lane.  The resulting
program masks and physical strata bound the next causal decision-tree pass.
"""

from __future__ import annotations

import collections
import dataclasses

import h207_tang_literal_fadd as h207
import h211_fadd_complete_tree_grammar as h211
import h213_fadd_causal_selector as h213
import h214_fadd_node0_selector as h214
import h216_fadd_microcontrol_discriminator as h216


RULE = h216.RULES["b_bit3"]
PROGRAMS = h213.PROGRAMS
ZERO = (0, 0, 0)


@dataclasses.dataclass(frozen=True)
class Residual:
    dataset: str
    point: h207.Point
    cosine: bool
    baseline: tuple[int, int, int]
    exact_mask: int
    improving_mask: int


def lane_metrics(point: h207.Point, values):
    return h213.metric_for_values(point, *values)


def no_worse(value, baseline) -> bool:
    return all(new <= old for new, old in zip(value, baseline))


def current_values(point: h207.Point):
    return h216.hidden_values(point, RULE)


def datasets():
    result = [
        *h207.joint_partitions("sweep"),
        *h207.joint_partitions("dense"),
        *h207.focused_datasets(),
    ]
    fresh = h216.load_capture(
        h216.DEFAULT_OUTPUT,
        h216.ROOT / "capture-kit-captures" / "skylake-fsin-h216",
    )
    result.append(("h216", fresh))
    return result


def inventory(name: str, points: list[h207.Point]):
    residuals = []
    baseline_total = h213.ZERO_JOINT
    active = collections.Counter()
    strata = collections.Counter()
    exact_programs = collections.Counter()
    improving_programs = collections.Counter()
    for point in points:
        baseline_values = current_values(point)
        baseline_metrics = lane_metrics(point, baseline_values)
        baseline_total = h213.add(baseline_total, baseline_metrics)
        candidate_metrics = None
        for cosine in (False, True):
            if cosine and not point.cosine_hardware:
                continue
            baseline = baseline_metrics[cosine]
            if baseline == ZERO:
                continue
            if candidate_metrics is None:
                candidate_metrics = [
                    lane_metrics(
                        point,
                        h211.hidden_values(point.prepared, program),
                    )
                    for program in PROGRAMS
                ]
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
            features = h214.lane_features(point, RULE.candidate, cosine)
            selected = all(
                features.get(feature) == value
                for feature, value in RULE.terms
            )
            active["active" if selected else "inactive"] += 1
            observed = point.prepared.joint.observed
            strata[
                "cosine" if cosine else "sine",
                observed.source,
                observed.point.cell,
                observed.signed_n & 3,
                bool(exact_mask),
            ] += 1
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
    return (
        residuals,
        baseline_total,
        active,
        strata,
        exact_programs,
        improving_programs,
    )


def greedy_cover(residuals: list[Residual], exact: bool):
    uncovered = {
        index
        for index, residual in enumerate(residuals)
        if (residual.exact_mask if exact else residual.improving_mask)
    }
    selected = []
    while uncovered:
        best = None
        for program in range(len(PROGRAMS)):
            covered = {
                index
                for index in uncovered
                if (
                    residuals[index].exact_mask
                    if exact
                    else residuals[index].improving_mask
                )
                & (1 << program)
            }
            item = (len(covered), -program, program, covered)
            if best is None or item[:2] > best[:2]:
                best = item
        if best is None or best[0] == 0:
            break
        selected.append((best[2], best[0]))
        uncovered -= best[3]
    return selected, uncovered


def short(index: int) -> str:
    return PROGRAMS[index].short()


def main() -> None:
    all_residuals = []
    for name, points in datasets():
        (
            residuals,
            baseline,
            active,
            strata,
            exact_programs,
            improving_programs,
        ) = inventory(name, points)
        all_residuals.extend(residuals)
        exact_union = sum(bool(item.exact_mask) for item in residuals)
        improving_union = sum(bool(item.improving_mask) for item in residuals)
        print(
            f"{name}: points={len(points)} residual-lanes={len(residuals)} "
            f"baseline={baseline} exact-union={exact_union} "
            f"improving-union={improving_union} active={dict(active)}"
        )
        missing = collections.Counter(
            (
                "cosine" if item.cosine else "sine",
                item.point.prepared.joint.observed.source,
                item.point.prepared.joint.observed.point.cell,
            )
            for item in residuals
            if not item.exact_mask
        )
        if missing:
            print(f"  exact-unreachable strata={dict(sorted(missing.items()))}")
        ranked = sorted(
            range(len(PROGRAMS)),
            key=lambda index: (
                -exact_programs[index],
                -improving_programs[index],
                index,
            ),
        )
        for index in ranked[:5]:
            if not (exact_programs[index] or improving_programs[index]):
                continue
            print(
                f"  p{index + 1:02d} exact={exact_programs[index]:4d} "
                f"improves={improving_programs[index]:4d} {short(index)}"
            )

    for exact in (True, False):
        selected, uncovered = greedy_cover(all_residuals, exact)
        reachable = sum(
            bool(item.exact_mask if exact else item.improving_mask)
            for item in all_residuals
        )
        label = "exact" if exact else "improving"
        print(
            f"joint {label} greedy-cover programs={len(selected)} "
            f"reachable={reachable}/{len(all_residuals)} "
            f"uncovered-within-union={len(uncovered)}"
        )
        for index, count in selected:
            print(f"  covers={count:4d} p{index + 1:02d} {short(index)}")


if __name__ == "__main__":
    main()
