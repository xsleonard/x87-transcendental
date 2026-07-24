#!/usr/bin/env python3
"""Refine h214's two closest rules with one raw-node counterexample bit.

h214 exhaustively tests first-FADD one- and two-signal rules.  Its closest
profile has aggregate validation violation two; the best rule already using
node state has violation four.  This bounded CEGIS pass adds exactly one
first-node atom to each near miss, treating both dense halves as explicit
counterexamples while preserving both sweep halves.  The h171/h175 and
h183/h185/h189 focused captures remain an independent final gate.

No arbitrary structural or input-identity predicate is admitted at the new
term: it must be operation, alignment, exponent, J/GRS, overflow, sign, or a
retained first-node carrier bit from h214's literal trace.
"""

from __future__ import annotations

import collections

import h207_tang_literal_fadd as h207
import h213_fadd_causal_selector as h213
import h214_fadd_node0_selector as h214


BASE_RULES = (
    h213.Rule(
        h213.PROGRAMS[3],
        (
            ("pair.lead-p.difference", 27),
            ("pair.q-p.difference", 10),
        ),
    ),
    h213.Rule(
        h213.PROGRAMS[6],
        (
            ("node0.exponent-difference", 14),
            ("node0.raw.exponent-mod4", 0),
        ),
    ),
)


def base_matches(atoms, rule: h213.Rule) -> bool:
    values = set(atoms)
    return all(term in values for term in rule.terms)


def node_atoms(atoms):
    return tuple(atom for atom in atoms if atom[0].startswith("node0."))


def deltas_for_rule(datasets, rule: h213.Rule):
    records = h214.lane_records(datasets, rule.candidate)
    result = collections.defaultdict(
        lambda: [h213.ZERO_JOINT for _ in datasets]
    )
    for partition_index, atoms, delta in records:
        if not base_matches(atoms, rule):
            continue
        for atom in node_atoms(atoms):
            if atom in rule.terms:
                continue
            result[atom][partition_index] = h213.add(
                result[atom][partition_index], delta
            )
    return result


def score_delta(delta, baselines):
    values = [
        h213.add(baseline, item)
        for baseline, item in zip(baselines, delta)
    ]
    passed = all(
        h207.no_worse(value, baseline)
        for value, baseline in zip(values, baselines)
    ) and any(value != baseline for value, baseline in zip(values, baselines))
    return values, passed


def main() -> None:
    fitting = [
        *h207.joint_partitions("sweep"),
        *h207.joint_partitions("dense"),
    ]
    baselines = h213.partition_baselines(fitting)
    print(
        "h215 first-node CEGIS: "
        f"base-rules={len(BASE_RULES)} points="
        f"{sum(len(points) for _, points in fitting)}"
    )
    for (name, points), baseline in zip(fitting, baselines):
        print(f"  baseline {name} n={len(points)} {baseline}")

    survivors = []
    for base_index, base in enumerate(BASE_RULES, 1):
        deltas = deltas_for_rule(fitting, base)
        closest = []
        for atom, delta in deltas.items():
            values, passed = score_delta(delta, baselines)
            rule = h213.Rule(base.candidate, (*base.terms, atom))
            item = (
                h213.violation(values, baselines),
                h207.objective(values),
                rule,
                values,
            )
            closest.append(item)
            if passed:
                survivors.append(item)
        closest.sort(key=lambda item: (item[0], item[1], item[2].short()))
        print(
            f"  base {base_index}: atoms={len(deltas)} "
            f"best-violation={closest[0][0]} {base.short()}"
        )
        for violation, _, rule, values in closest[:5]:
            print(f"    violation={violation} {rule.terms[-1]}")
            print(f"      fitting={values}")

    survivors.sort(key=lambda item: (item[1], item[2].short()))
    print(f"h215 fitting survivors: {len(survivors)}")
    for _, _, rule, values in survivors[:30]:
        print(f"  {rule.short()}")
        print(f"    fitting={values}")
    if not survivors:
        return

    validation = h207.focused_datasets()
    validation_baselines = h213.partition_baselines(validation)
    rules = [item[2] for item in survivors]
    groups = collections.defaultdict(list)
    for rule in rules:
        groups[rule.candidate].append(rule)
    final = []
    rejected = []
    for candidate_rules in groups.values():
        results = h214.validate_group(
            candidate_rules, validation, validation_baselines
        )
        for rule, (values, passed) in results.items():
            item = (
                h213.violation(values, validation_baselines),
                h207.objective(values),
                rule,
                values,
            )
            (final if passed else rejected).append(item)
    final.sort(key=lambda item: (item[1], item[2].short()))
    rejected.sort(key=lambda item: (item[0], item[1], item[2].short()))
    print(f"h215 focused survivors: {len(final)}")
    for _, _, rule, values in final[:30]:
        print(f"  {rule.short()}")
        print(f"    focused={values}")
    print("  leading focused rejections:")
    for violation, _, rule, values in rejected[:10]:
        print(f"    violation={violation} {rule.short()}")
        for name, baseline, value in h214.changed_report(
            validation, values, validation_baselines
        ):
            print(f"      {name}: {baseline}->{value}")


if __name__ == "__main__":
    main()
