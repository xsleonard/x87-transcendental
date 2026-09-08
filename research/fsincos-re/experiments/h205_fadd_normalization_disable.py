#!/usr/bin/env python3
"""Test P5 FADD carriers retained with FRND normalization disabled.

US 5,257,215 states that FRND normalization and rounding can be disabled
independently.  h200--h204 retain an unrounded carrier but normalize a far
subtraction whose leading J position cancels.  This pass tests the remaining
literal control: both normalization and rounding are off at selected stages,
so the compressed FAMUBUS carrier has J=0 before the next FMUL.

All four bounded alignment/sticky interpretations are tested in the table
P/Q path (including direct/reduced gates), the Round-31--33 internal-cosine
proxy schedules, and h203's coherent physical route grid.  Candidates must
be componentwise non-regressing before they advance from deterministic
samples to the complete existing captures.
"""

from __future__ import annotations

import collections
import dataclasses
import hashlib

import h188_table_stage_local_pairs as h188
import h200_p5_fadd_bitvector as h200
import h201_p5_fadd_path_gate as h201
import h202_fsin_cosine_fadd_bitvector as h202
import h203_fsin_cosine_physical_datapath as h203
import h204_fadd_borrow_sticky as h204


MODES = (*h200.FADD_MODES, *h204.MODES)


@dataclasses.dataclass(frozen=True)
class TableCandidate:
    mode: str
    p_mask: int | None
    p_gate: str | None
    q_mask: int | None
    q_gate: str | None

    def short(self) -> str:
        def show(name: str, mask: int | None, gate: str | None) -> str:
            if mask is None:
                return f"{name}=scalar"
            stages = "".join(
                str(index + 1)
                for index in range(h200.STAGES)
                if mask & (1 << index)
            )
            return f"{name}={gate}-raw[{stages or '-'}]"

        return (
            f"{self.mode} {show('P', self.p_mask, self.p_gate)} "
            f"{show('Q', self.q_mask, self.q_gate)}"
        )


def table_hidden(point: h188.Point, candidate: TableCandidate):
    p_mask = (
        candidate.p_mask
        if h201.selected(candidate.p_gate, point)
        else None
    )
    q_mask = (
        candidate.q_mask
        if h201.selected(candidate.q_gate, point)
        else None
    )
    return h200.hidden_values(
        point,
        h200.Candidate(
            candidate.mode,
            p_mask,
            q_mask,
            normalize_retained=False,
        ),
    )


def table_metric(point: h188.Point, candidate: TableCandidate):
    sine, cosine = table_hidden(point, candidate)
    return (
        h200.h170.point_metric(point.joint.observed, sine),
        h200.h182.point_metric(
            point.joint.cosine_outputs,
            point.joint.cosine_c1,
            cosine,
        ),
    )


def table_score(datasets, candidate: TableCandidate | None):
    digest = hashlib.sha256()
    values = []
    for name, points in datasets:
        digest.update(name.encode("ascii"))
        result: h200.JointMetric = ((0, 0, 0), (0, 0, 0))
        for point in points:
            metric = (
                h200.point_metric(point, h200.CURRENT)
                if candidate is None
                else table_metric(point, candidate)
            )
            digest.update(bytes((*metric[0], *metric[1])))
            result = h200.add(result, metric)
        values.append(result)
    return values, digest.digest()


def table_mask_profiles(mode: str, chain: str, datasets):
    classes: dict[bytes, list[int]] = collections.defaultdict(list)
    for mask in range(1, 32):
        digest = hashlib.sha256()
        for name, points in datasets:
            digest.update(name.encode("ascii"))
            for point in points:
                if chain == "p":
                    value = h200.p_value(point, mask, mode, False)
                    h201.value_digest(value, digest)
                else:
                    h201.value_digest(
                        h200.q_value(point, mask, mode, False, False),
                        digest,
                    )
                    h201.value_digest(
                        h200.q_value(point, mask, mode, True, False),
                        digest,
                    )
        classes[digest.digest()].append(mask)
    return {min(masks): tuple(masks) for masks in classes.values()}


def table_candidates(mode: str, p_masks, q_masks):
    p_options = [(None, None)] + [
        (mask, gate) for mask in p_masks for gate in h201.GATES
    ]
    q_options = [(None, None)] + [
        (mask, gate) for mask in q_masks for gate in h201.GATES
    ]
    return tuple(
        TableCandidate(mode, p_mask, p_gate, q_mask, q_gate)
        for p_mask, p_gate in p_options
        for q_mask, q_gate in q_options
        if p_mask is not None or q_mask is not None
    )


def table_pass() -> None:
    complete = h200.partitions("sweep")
    selected = h201.sample(complete)
    baselines, baseline_signature = table_score(selected, None)
    complete_baselines = table_score(complete, None)[0]
    profiles = collections.defaultdict(list)
    raw = []
    tested = 0
    for mode in MODES:
        p_profiles = table_mask_profiles(mode, "p", selected)
        q_profiles = table_mask_profiles(mode, "q", selected)
        print(
            f"  table {mode}: P profiles={p_profiles}; "
            f"Q profiles={q_profiles}"
        )
        for candidate in table_candidates(mode, p_profiles, q_profiles):
            tested += 1
            values, signature = table_score(selected, candidate)
            item = (*h200.objective(values), candidate.short(), candidate)
            raw.append(item)
            if (
                signature != baseline_signature
                and all(
                    h200.no_worse(value, baseline)
                    for value, baseline in zip(values, baselines)
                )
                and any(
                    value != baseline
                    for value, baseline in zip(values, baselines)
                )
            ):
                profiles[signature].append(item)
    raw.sort()
    representatives = sorted(min(items) for items in profiles.values())
    h204.report_ranked("raw-normalization table", raw)
    print(
        f"h205 table sample: tested={tested} "
        f"survivors={sum(len(items) for items in profiles.values())} "
        f"profiles={len(representatives)}"
    )
    final = []
    for item in representatives:
        candidate = item[4]
        values, _ = table_score(complete, candidate)
        if all(
            h200.no_worse(value, baseline)
            for value, baseline in zip(values, complete_baselines)
        ) and any(
            value != baseline
            for value, baseline in zip(values, complete_baselines)
        ):
            final.append((*h200.objective(values), candidate.short(), candidate))
    final.sort()
    print(f"h205 table complete: {len(final)} survivors")
    if final:
        dense_fresh = [*h200.partitions("dense"), *h200.fresh_datasets()]
        final_baselines = table_score(dense_fresh, None)[0]
        surviving = []
        for item in final:
            candidate = item[4]
            values, _ = table_score(dense_fresh, candidate)
            if all(
                h200.no_worse(value, baseline)
                for value, baseline in zip(values, final_baselines)
            ) and any(
                value != baseline
                for value, baseline in zip(values, final_baselines)
            ):
                surviving.append(candidate)
        print(f"h205 table dense/fresh: {len(surviving)} survivors")


def polynomial_pass() -> None:
    complete, selected = h203.selection_datasets()
    baselines, baseline_signature = h202.score_signature(
        selected, h202.CURRENT
    )
    complete_baselines = h202.score_signature(complete, h202.CURRENT)[0]
    candidates = tuple(
        h202.Candidate(mode, foundation, mask, False, False)
        for mode in MODES
        for foundation in h202.FOUNDATIONS
        for mask in range(1, 32)
    )
    profiles = collections.defaultdict(list)
    raw = []
    for candidate in candidates:
        values, signature = h202.score_signature(selected, candidate)
        item = (*h202.objective(values), candidate.short(), candidate)
        raw.append(item)
        if (
            signature != baseline_signature
            and all(
                h202.no_worse(value, baseline)
                for value, baseline in zip(values, baselines)
            )
            and any(
                value != baseline
                for value, baseline in zip(values, baselines)
            )
        ):
            profiles[signature].append(item)
    raw.sort()
    representatives = sorted(min(items) for items in profiles.values())
    h204.report_ranked("raw-normalization polynomial", raw)
    print(
        f"h205 polynomial sample: tested={len(candidates)} "
        f"survivors={sum(len(items) for items in profiles.values())} "
        f"profiles={len(representatives)}"
    )
    final = []
    for item in representatives:
        candidate = item[4]
        values, _ = h202.score_signature(complete, candidate)
        if all(
            h202.no_worse(value, baseline)
            for value, baseline in zip(values, complete_baselines)
        ) and any(
            value != baseline
            for value, baseline in zip(values, complete_baselines)
        ):
            final.append((*h202.objective(values), candidate.short(), candidate))
    final.sort()
    print(f"h205 polynomial complete: {len(final)} survivors")


def physical_pass() -> None:
    complete, selected = h203.selection_datasets()
    baselines, baseline_signature = h203.score_signature(selected, None)
    complete_baselines = h203.score_signature(complete, None)[0]
    candidates = tuple(
        dict.fromkeys(
            dataclasses.replace(
                candidate,
                mode=mode,
                normalize_retained=False,
            )
            for candidate in h203.candidates()
            if candidate.retain_mask
            for mode in MODES
        )
    )
    profiles = collections.defaultdict(list)
    raw = []
    for candidate in candidates:
        values, signature = h203.score_signature(selected, candidate)
        item = (*h203.objective(values), candidate.short(), candidate)
        raw.append(item)
        if (
            signature != baseline_signature
            and all(
                h203.no_worse(value, baseline)
                for value, baseline in zip(values, baselines)
            )
            and any(
                value != baseline
                for value, baseline in zip(values, baselines)
            )
        ):
            profiles[signature].append(item)
    raw.sort()
    representatives = sorted(min(items) for items in profiles.values())
    h204.report_ranked("raw-normalization physical", raw)
    print(
        f"h205 physical sample: tested={len(candidates)} "
        f"survivors={sum(len(items) for items in profiles.values())} "
        f"profiles={len(representatives)}"
    )
    final = []
    for item in representatives:
        candidate = item[4]
        values, _ = h203.score_signature(complete, candidate)
        if all(
            h203.no_worse(value, baseline)
            for value, baseline in zip(values, complete_baselines)
        ) and any(
            value != baseline
            for value, baseline in zip(values, complete_baselines)
        ):
            final.append((*h203.objective(values), candidate.short(), candidate))
    final.sort()
    print(f"h205 physical complete: {len(final)} survivors")


def main() -> None:
    print("h205 FRND normalization-disabled carrier")
    table_pass()
    polynomial_pass()
    physical_pass()


if __name__ == "__main__":
    main()
