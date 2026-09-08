#!/usr/bin/env python3
"""Test direct/reduced gating of h200's literal P5 FADD producer profiles.

h200's global ``mark-after`` carrier is a near miss: it improves complete
sweep output counts in three of four lane/half partitions and is rejected
only by two train-cosine C1 observations.  Direct FSIN entry and M66-reduced
entry already have independently validated terminal schedules, so this pass
tests that existing microcode boundary without introducing cell or residual
predicates.

The 32 retain masks are first collapsed by their exact P or paired-Q producer
values on the residual-heavy sample.  Each distinct producer profile may be
used globally, on direct entry only, or on reduced entry only.  P and Q gates
remain independent because they are separate Horner flows.  Candidates must
pass the same joint sine/cosine componentwise sample, complete sweep, dense,
and fresh h183/h185/h189 gates as h200.
"""

from __future__ import annotations

import collections
import dataclasses
import hashlib

import h131_fsin_table_c1_search as h131
import h188_table_stage_local_pairs as h188
import h200_p5_fadd_bitvector as h200


JointMetric = h200.JointMetric
GATES = ("all", "direct", "reduced")


@dataclasses.dataclass(frozen=True)
class Candidate:
    mode: str = "scalar"
    p_mask: int | None = None
    p_gate: str | None = None
    q_mask: int | None = None
    q_gate: str | None = None

    def short(self) -> str:
        if self.mode == "scalar":
            return "current Round35 scalar"

        def show(name: str, mask: int | None, gate: str | None) -> str:
            if mask is None:
                return f"{name}=scalar"
            stages = "".join(
                str(index + 1)
                for index in range(h200.STAGES)
                if mask & (1 << index)
            )
            return f"{name}={gate}-retain[{stages or '-'}]"

        return (
            f"{self.mode} {show('P', self.p_mask, self.p_gate)} "
            f"{show('Q', self.q_mask, self.q_gate)}"
        )


CURRENT = Candidate()


def selected(gate: str | None, point: h188.Point) -> bool:
    if gate is None:
        return False
    source = point.joint.observed.source
    return gate == "all" or gate == source


def hidden_values(
    point: h188.Point, candidate: Candidate
):
    if candidate == CURRENT:
        return h200.hidden_values(point, h200.CURRENT)
    p_mask = (
        candidate.p_mask
        if selected(candidate.p_gate, point)
        else None
    )
    q_mask = (
        candidate.q_mask
        if selected(candidate.q_gate, point)
        else None
    )
    return h200.hidden_values(
        point,
        h200.Candidate(candidate.mode, p_mask, q_mask),
    )


def point_metric(point: h188.Point, candidate: Candidate) -> JointMetric:
    sine, cosine = hidden_values(point, candidate)
    return (
        h200.h170.point_metric(point.joint.observed, sine),
        h200.h182.point_metric(
            point.joint.cosine_outputs,
            point.joint.cosine_c1,
            cosine,
        ),
    )


def score_signature(datasets, candidate: Candidate):
    digest = hashlib.sha256()
    values = []
    for name, points in datasets:
        digest.update(name.encode("ascii"))
        result: JointMetric = ((0, 0, 0), (0, 0, 0))
        for point in points:
            metric = point_metric(point, candidate)
            digest.update(bytes((*metric[0], *metric[1])))
            result = h200.add(result, metric)
        values.append(result)
    return values, digest.digest()


def value_digest(value, digest: hashlib._Hash) -> None:
    digest.update(repr(value).encode("ascii"))


def mask_profiles(
    mode: str, chain: str, datasets
) -> dict[int, tuple[int, ...]]:
    classes: dict[bytes, list[int]] = collections.defaultdict(list)
    for mask in range(32):
        digest = hashlib.sha256()
        for name, points in datasets:
            digest.update(name.encode("ascii"))
            for point in points:
                if chain == "p":
                    value_digest(h200.p_value(point, mask, mode), digest)
                else:
                    value_digest(
                        h200.q_value(point, mask, mode, False), digest
                    )
                    value_digest(
                        h200.q_value(point, mask, mode, True), digest
                    )
        classes[digest.digest()].append(mask)
    return {min(masks): tuple(masks) for masks in classes.values()}


def sample(sweep, control_count: int = 400):
    result = []
    for name, points in sweep:
        constrained = []
        controls = []
        for point in points:
            target = (
                constrained
                if point_metric(point, CURRENT)
                != ((0, 0, 0), (0, 0, 0))
                else controls
            )
            target.append(point)
        controls.sort(
            key=lambda point: (
                point.joint.observed.point.raw.sig
                ^ (point.joint.observed.point.raw.sig >> 23)
                ^ point.joint.observed.index
                ^ point.joint.observed.signed_n
            )
        )
        result.append((name, constrained + controls[:control_count]))
    return result


def candidate_set(mode: str, p_masks, q_masks):
    p_options = [(None, None)] + [
        (mask, gate) for mask in p_masks for gate in GATES
    ]
    q_options = [(None, None)] + [
        (mask, gate) for mask in q_masks for gate in GATES
    ]
    return tuple(
        Candidate(mode, p_mask, p_gate, q_mask, q_gate)
        for p_mask, p_gate in p_options
        for q_mask, q_gate in q_options
        if p_mask is not None or q_mask is not None
    )


def objective(values):
    return h200.objective(values)


def main() -> None:
    sweep = h200.partitions("sweep")
    h200.assert_baseline(sweep)
    selected = sample(sweep)
    baseline_values, baseline_signature = score_signature(selected, CURRENT)
    complete_baselines = score_signature(sweep, CURRENT)[0]
    print(
        f"h201 FADD path gate: wide-sweep="
        f"{sum(len(points) for _, points in sweep)} "
        f"sample={sum(len(points) for _, points in selected)}"
    )

    all_profiles: dict[bytes, list[tuple]] = collections.defaultdict(list)
    tested = 0
    for mode in h200.FADD_MODES:
        p_profiles = mask_profiles(mode, "p", selected)
        q_profiles = mask_profiles(mode, "q", selected)
        print(
            f"  {mode}: P masks -> {len(p_profiles)} profiles "
            f"{p_profiles}; Q masks -> {len(q_profiles)} profiles "
            f"{q_profiles}"
        )
        for candidate in candidate_set(mode, p_profiles, q_profiles):
            tested += 1
            values, signature = score_signature(selected, candidate)
            if (
                signature == baseline_signature
                or not all(
                    h200.no_worse(value, baseline)
                    for value, baseline in zip(values, baseline_values)
                )
                or not any(
                    value != baseline
                    for value, baseline in zip(values, baseline_values)
                )
            ):
                continue
            all_profiles[signature].append(
                (*objective(values), candidate.short(), candidate, values)
            )
    representatives = sorted(min(items) for items in all_profiles.values())
    print(
        f"h201 sample gate: tested={tested} "
        f"survivors={sum(len(items) for items in all_profiles.values())} "
        f"profiles={len(representatives)}"
    )
    for item in representatives[:16]:
        print(
            f"  modes/c1/inputs={item[0]}/{item[1]}/{item[2]} "
            f"{item[4].short()}"
        )
    if not representatives:
        print("h201 complete sweep gate: 0 survivors")
        print("h201 dense/fresh gate: 0 survivors")
        return

    complete_ranked = []
    complete_survivors = []
    for item in representatives:
        candidate = item[4]
        values, _ = score_signature(sweep, candidate)
        completed = (*objective(values), candidate.short(), candidate, values)
        complete_ranked.append(completed)
        if all(
            h200.no_worse(value, baseline)
            for value, baseline in zip(values, complete_baselines)
        ) and any(
            value != baseline
            for value, baseline in zip(values, complete_baselines)
        ):
            complete_survivors.append(completed)
    complete_ranked.sort()
    complete_survivors.sort()
    print("  leading complete path-gated profiles:")
    for item in complete_ranked[:16]:
        print(
            f"    modes/c1/inputs={item[0]}/{item[1]}/{item[2]} "
            f"{item[4].short()} values={item[5]}"
        )
    print(
        f"h201 complete sweep gate: {len(complete_survivors)} survivors"
    )
    if not complete_survivors:
        print("h201 dense/fresh gate: 0 survivors")
        return

    final_datasets = [*h200.partitions("dense"), *h200.fresh_datasets()]
    h200.assert_baseline(final_datasets)
    final_baselines = score_signature(final_datasets, CURRENT)[0]
    final = []
    for item in complete_survivors:
        candidate = item[4]
        values, _ = score_signature(final_datasets, candidate)
        if all(
            h200.no_worse(value, baseline)
            for value, baseline in zip(values, final_baselines)
        ) and any(
            value != baseline
            for value, baseline in zip(values, final_baselines)
        ):
            final.append((candidate, values))
    print(f"h201 dense/fresh gate: {len(final)} survivors")
    for candidate, values in final:
        print(f"  {candidate.short()}")
        for (name, _), baseline, value in zip(
            final_datasets, final_baselines, values
        ):
            if value != baseline:
                print(f"    {name:11s} {baseline}->{value}")


if __name__ == "__main__":
    main()
