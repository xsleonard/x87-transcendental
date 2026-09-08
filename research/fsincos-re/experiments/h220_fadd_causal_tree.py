#!/usr/bin/env python3
"""Synthesize the next causal Round-36 microcontrol branch.

h218-h219 prove that conditional jam-sub programs can reach every remaining
measured lane.  This pass asks the harder question: can one additional small
physical predicate select such a program without regressing any old or fresh
partition?

The existing h216 leaf has priority.  New top-level rules are evaluated only
where it is inactive.  Predicates may use range/term/pair state available
before the first reconstruction FADD.  A candidate whose first node is the
same ``linear+p`` operation as Round 36 may additionally use that node's raw
J/GRS/carrier state.  Raw input-identity bits are excluded.  One-, two-, and
bounded three-atom conjunctions are fit on every residual plus deterministic
controls, then replayed on the complete sweep/dense and focused captures.
"""

from __future__ import annotations

import collections
import dataclasses

import h207_tang_literal_fadd as h207
import h211_fadd_complete_tree_grammar as h211
import h213_fadd_causal_selector as h213
import h214_fadd_node0_selector as h214
import h216_fadd_microcontrol_discriminator as h216


Metric = tuple[int, int, int]
Vector = tuple[int, int, int, int, int, int]
ZERO_VECTOR: Vector = (0, 0, 0, 0, 0, 0)
CURRENT_RULE = h216.RULES["b_bit3"]
PAIR_ATOMS = 36
PAIR_BEAM = 96
FULL_RULE_LIMIT = 240


def extra_program(tree_text: str, first: str, second: str):
    return h211.Candidate(
        h213.tree(tree_text),
        "jam-sub",
        first,
        second,
        True,
        h207.ProductRoute("odd67", "odd67", "odd67"),
    )


EXTRA_PROGRAMS = (
    extra_program("(((linear+q)+p)+lead)", "away64", "chop64"),
    extra_program("(((lead+linear)+p)+q)", "away64", "chop64"),
    extra_program("(((lead+linear)+p)+q)", "away64", "retain-raw"),
    extra_program("(((linear+q)+p)+lead)", "chop64", "rn64"),
)
PROGRAMS = tuple(dict.fromkeys((*h213.PROGRAMS, *EXTRA_PROGRAMS)))


@dataclasses.dataclass(frozen=True)
class Lane:
    partition: int
    point: h207.Point
    cosine: bool
    baseline: Metric
    current_active: bool


@dataclasses.dataclass(frozen=True)
class Result:
    violation: int
    objective: int
    rule: h213.Rule
    values: tuple[Vector, ...]


def vector(metric, cosine: bool) -> Vector:
    return (
        (0, 0, 0, *metric)
        if cosine
        else (*metric, 0, 0, 0)
    )


def add(left: Vector, right: Vector) -> Vector:
    return tuple(a + b for a, b in zip(left, right))  # type: ignore[return-value]


def subtract(left: Vector, right: Vector) -> Vector:
    return tuple(a - b for a, b in zip(left, right))  # type: ignore[return-value]


def baseline_values(point: h207.Point):
    return h216.hidden_values(point, CURRENT_RULE)


def point_metrics(point: h207.Point, values):
    return h213.metric_for_values(point, *values)


def base_selected(point: h207.Point, cosine: bool) -> bool:
    features = h214.lane_features(point, CURRENT_RULE.candidate, cosine)
    return all(
        features.get(name) == value for name, value in CURRENT_RULE.terms
    )


def partitions():
    focused = h207.focused_datasets()[:5]
    fresh = h216.load_capture(
        h216.DEFAULT_OUTPUT,
        h216.ROOT / "capture-kit-captures" / "skylake-fsin-h216",
    )
    return [
        *h207.joint_partitions("sweep"),
        *h207.joint_partitions("dense"),
        *focused,
        ("h216", fresh),
    ]


def build_lanes():
    named = partitions()
    lanes = []
    baselines = [ZERO_VECTOR for _ in named]
    for partition, (_, points) in enumerate(named):
        for point in points:
            metrics = point_metrics(point, baseline_values(point))
            for cosine in (False, True):
                if cosine and not point.cosine_hardware:
                    continue
                metric = metrics[cosine]
                lanes.append(
                    Lane(
                        partition,
                        point,
                        cosine,
                        metric,
                        base_selected(point, cosine),
                    )
                )
                baselines[partition] = add(
                    baselines[partition], vector(metric, cosine)
                )
    return named, lanes, tuple(baselines)


def control_key(lane: Lane):
    observed = lane.point.prepared.joint.observed
    raw = observed.point.raw
    return (
        raw.sig ^ (raw.sig >> 23) ^ (observed.index << 9)
        ^ (observed.signed_n << 3) ^ int(lane.cosine),
        raw.sig,
    )


def sample_lanes(lanes: list[Lane], partition_count: int, controls: int):
    result = []
    for partition in range(partition_count):
        selected = [lane for lane in lanes if lane.partition == partition]
        residuals = [lane for lane in selected if lane.baseline != (0, 0, 0)]
        correct = [lane for lane in selected if lane.baseline == (0, 0, 0)]
        correct.sort(key=control_key)
        result.extend((*residuals, *correct[:controls]))
    return result


def same_first_node(candidate) -> bool:
    return h214.first_node(candidate.tree) == h214.first_node(
        CURRENT_RULE.candidate.tree
    )


def allowed_feature(name: str, node_allowed: bool) -> bool:
    if name.startswith("global.input-bit"):
        return False
    if name.startswith("global.residual-bit"):
        return False
    if name.startswith("node0.") and not node_allowed:
        return False
    return True


def atoms_for_lane(lane: Lane, node_allowed: bool):
    features = h214.lane_features(
        lane.point, CURRENT_RULE.candidate, lane.cosine
    )
    return tuple(
        sorted(
            (name, value)
            for name, value in features.items()
            if allowed_feature(name, node_allowed)
        )
    )


def candidate_records(lanes: list[Lane], candidate):
    cache = {}
    records = []
    for lane in lanes:
        candidate_metrics = cache.get(lane.point)
        if candidate_metrics is None:
            values = h211.hidden_values(lane.point.prepared, candidate)
            candidate_metrics = point_metrics(lane.point, values)
            cache[lane.point] = candidate_metrics
        old = vector(lane.baseline, lane.cosine)
        new = vector(candidate_metrics[lane.cosine], lane.cosine)
        delta = (
            ZERO_VECTOR
            if lane.current_active
            else subtract(new, old)
        )
        records.append((lane.partition, delta))
    return records


def atom_masks(lanes: list[Lane], node_allowed: bool):
    byte_count = (len(lanes) + 7) // 8
    buffers = {}
    for index, lane in enumerate(lanes):
        byte_index = index >> 3
        bit = 1 << (index & 7)
        atoms = atoms_for_lane(lane, node_allowed)
        for atom in atoms:
            buffer = buffers.get(atom)
            if buffer is None:
                buffer = bytearray(byte_count)
                buffers[atom] = buffer
            buffer[byte_index] |= bit
    return {
        atom: int.from_bytes(buffer, "little")
        for atom, buffer in buffers.items()
    }


class Scorer:
    def __init__(self, records, baselines):
        self.records = records
        self.baselines = baselines
        self.cache = {}

    def score(self, mask: int):
        result = [ZERO_VECTOR for _ in self.baselines]
        remaining = mask
        while remaining:
            bit = remaining & -remaining
            index = bit.bit_length() - 1
            partition, delta = self.records[index]
            result[partition] = add(result[partition], delta)
            remaining ^= bit
        values = tuple(
            add(baseline, delta)
            for baseline, delta in zip(self.baselines, result)
        )
        violation = sum(
            max(0, new - old)
            for value, baseline in zip(values, self.baselines)
            for new, old in zip(value, baseline)
        )
        changed = any(value != baseline for value, baseline in zip(values, self.baselines))
        passed = violation == 0 and changed
        objective = sum(sum(value) for value in values)
        return violation, objective, values, passed


def rule_mask(rule: h213.Rule, masks, count: int) -> int:
    result = (1 << count) - 1
    for atom in rule.terms:
        result &= masks.get(atom, 0)
    return result


def result_for(candidate, terms, mask, scorer):
    violation, objective, values, _ = scorer.score(mask)
    return Result(violation, objective, h213.Rule(candidate, terms), values)


def sample_search(lanes, baselines, candidate, masks):
    records = candidate_records(lanes, candidate)
    scorer = Scorer(records, baselines)
    singles = []
    passing = []
    for atom, mask in masks.items():
        result = result_for(candidate, (atom,), mask, scorer)
        singles.append(result)
        if result.violation == 0 and result.values != baselines:
            passing.append(result)
    singles.sort(key=lambda item: (item.violation, item.objective, item.rule.terms))
    top_atoms = [item.rule.terms[0] for item in singles[:PAIR_ATOMS]]

    pairs = []
    for left_index, left in enumerate(top_atoms):
        for right in top_atoms[left_index + 1:]:
            mask = masks[left] & masks[right]
            if not mask:
                continue
            result = result_for(candidate, (left, right), mask, scorer)
            pairs.append(result)
            if result.violation == 0 and result.values != baselines:
                passing.append(result)
    pairs.sort(key=lambda item: (item.violation, item.objective, item.rule.terms))

    triples = set()
    for pair in pairs[:PAIR_BEAM]:
        for atom in top_atoms:
            terms = tuple(sorted((*pair.rule.terms, atom)))
            if len(set(terms)) != 3 or terms in triples:
                continue
            triples.add(terms)
            mask = masks[terms[0]] & masks[terms[1]] & masks[terms[2]]
            if not mask:
                continue
            result = result_for(candidate, terms, mask, scorer)
            if result.violation == 0 and result.values != baselines:
                passing.append(result)

    passing = list({item.rule: item for item in passing}.values())
    passing.sort(key=lambda item: (item.objective, len(item.rule.terms), item.rule.short()))
    closest = [*singles[:3], *pairs[:3]]
    closest.sort(key=lambda item: (item.violation, item.objective, item.rule.short()))
    return passing[:FULL_RULE_LIMIT], closest[:5]


def full_validate(lanes, baselines, rules, pre_masks, node_masks):
    groups = collections.defaultdict(list)
    for rule in rules:
        groups[rule.candidate].append(rule)
    survivors = []
    rejected = []
    for candidate, candidate_rules in groups.items():
        records = candidate_records(lanes, candidate)
        masks = node_masks if same_first_node(candidate) else pre_masks
        scorer = Scorer(records, baselines)
        for rule in candidate_rules:
            mask = rule_mask(rule, masks, len(records))
            result = result_for(candidate, rule.terms, mask, scorer)
            target = survivors if result.violation == 0 and result.values != baselines else rejected
            target.append(result)
    survivors.sort(key=lambda item: (item.objective, len(item.rule.terms), item.rule.short()))
    rejected.sort(key=lambda item: (item.violation, item.objective, item.rule.short()))
    return survivors, rejected


def main() -> None:
    named, full, full_baselines = build_lanes()
    sample = sample_lanes(full, len(named), 500)
    sample_baselines = [ZERO_VECTOR for _ in named]
    for lane in sample:
        sample_baselines[lane.partition] = add(
            sample_baselines[lane.partition], vector(lane.baseline, lane.cosine)
        )
    sample_baselines = tuple(sample_baselines)
    sample_node_masks = atom_masks(sample, True)
    sample_pre_masks = {
        atom: mask
        for atom, mask in sample_node_masks.items()
        if not atom[0].startswith("node0.")
    }
    print(
        f"h220 causal tree programs={len(PROGRAMS)} "
        f"sample-lanes={len(sample)} full-lanes={len(full)}"
    )
    for (name, _), baseline in zip(named, full_baselines):
        print(f"  baseline {name:12s} {baseline}")

    sample_survivors = []
    for index, candidate in enumerate(PROGRAMS, 1):
        masks = sample_node_masks if same_first_node(candidate) else sample_pre_masks
        passing, closest = sample_search(
            sample, sample_baselines, candidate, masks
        )
        sample_survivors.extend(item.rule for item in passing)
        print(
            f"  p{index:02d} sample-survivors={len(passing):3d} "
            f"closest-violation={closest[0].violation:3d} "
            f"node={'yes' if same_first_node(candidate) else 'no'} "
            f"{candidate.short()}",
            flush=True,
        )
        for item in closest[:2]:
            print(
                f"    near violation={item.violation} terms={item.rule.terms}"
            )

    print(f"h220 sample rules advancing={len(sample_survivors)}")
    if not sample_survivors:
        return
    print("h220 building complete physical-predicate masks", flush=True)
    full_node_masks = atom_masks(full, True)
    full_pre_masks = {
        atom: mask
        for atom, mask in full_node_masks.items()
        if not atom[0].startswith("node0.")
    }
    survivors, rejected = full_validate(
        full,
        full_baselines,
        sample_survivors,
        full_pre_masks,
        full_node_masks,
    )
    print(f"h220 complete survivors={len(survivors)}")
    for item in survivors[:40]:
        print(f"  {item.rule.short()}")
        for (name, _), baseline, value in zip(named, full_baselines, item.values):
            if value != baseline:
                print(f"    {name}: {baseline}->{value}")
    print("  leading complete rejections:")
    for item in rejected[:10]:
        print(f"    violation={item.violation} {item.rule.short()}")


if __name__ == "__main__":
    main()
