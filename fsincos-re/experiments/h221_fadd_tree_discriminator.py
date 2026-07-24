#!/usr/bin/env python3
"""Generate and score fresh separators for h220's causal-tree branches.

h220 leaves two physical predicate families after complete sweep/dense and
focused validation.  Family A is visible on old sweep/dense data and chooses
between two distinct ``linear+q`` schedules.  Family B is visible only in the
fresh h216 capture and chooses between a ``linear+p`` and ``linear+q``
schedule.  This hardware-blind pass requires both baseline separators and
pairwise separators so a fresh Skylake capture can select or reject the
specific branch program rather than merely confirming that the region is
sensitive.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import itertools
import pathlib
import random
import sys

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h135_fsin_table_terminal_discriminator as h135
import h171_fsin_table_correction_discriminator as h171
import h175_fsin_table_path_discriminator as h175
import h182_table_joint_terminal_edges as h182
import h188_table_stage_local_pairs as h188
import h207_tang_literal_fadd as h207
import h211_fadd_complete_tree_grammar as h211
import h213_fadd_causal_selector as h213
import h214_fadd_node0_selector as h214
import h216_fadd_microcontrol_discriminator as h216
import h220_fadd_causal_tree as h220


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_table_fadd_tree_h221.txt"
)
DEFAULT_METADATA = DEFAULT_OUTPUT.with_suffix(".meta.txt")
CAPTURE_STEM = "constraint_table_fadd_tree_h221"
SEED = 0xF221C5


def rule(candidate, *terms):
    return h213.Rule(candidate, tuple(terms))


A_TERMS = (
    ("pair.lead-q.difference", 16),
    ("pair.lead-p.difference", 26),
)
B_TERMS = (
    ("node0.exponent-difference", 18),
    ("pair.lead-linear.difference", 9),
)
RULES = {
    "a_norm_chop": rule(h220.PROGRAMS[11], *A_TERMS),
    "a_raw_odd": rule(h220.PROGRAMS[7], *A_TERMS),
    "b_linear_p": rule(h220.PROGRAMS[2], *B_TERMS),
    "b_linear_q": rule(
        h220.PROGRAMS[11],
        ("pair.linear-p.difference", 18),
        ("pair.lead-linear.difference", 9),
    ),
}
PAIRS = tuple(itertools.combinations(RULES, 2))


def blank(observed) -> h182.Point:
    return h182.Point(
        observed,
        ((0, 0),) * len(h58.RCS),
        (False,) * len(h58.RCS),
    )


def selected(point: h207.Point, rule: h213.Rule, cosine: bool) -> bool:
    if all(
        h214.lane_features(
            point, h220.CURRENT_RULE.candidate, cosine
        ).get(name) == value
        for name, value in h220.CURRENT_RULE.terms
    ):
        return False
    features = h214.lane_features(
        point, h220.CURRENT_RULE.candidate, cosine
    )
    return all(features.get(name) == value for name, value in rule.terms)


def any_branch_selected(point: h207.Point) -> bool:
    for cosine in (False, True):
        features = h214.lane_features(
            point, h220.CURRENT_RULE.candidate, cosine
        )
        if all(
            features.get(name) == value
            for name, value in h220.CURRENT_RULE.terms
        ):
            continue
        if any(
            all(features.get(name) == value for name, value in branch.terms)
            for branch in RULES.values()
        ):
            return True
    return False


def hidden_values(point: h207.Point, branch: h213.Rule | None):
    baseline = h216.hidden_values(point, h220.CURRENT_RULE)
    if branch is None:
        return baseline
    candidate = h211.hidden_values(point.prepared, branch.candidate)
    return tuple(
        candidate[cosine] if selected(point, branch, cosine) else baseline[cosine]
        for cosine in (False, True)
    )


def profile_values(values):
    return tuple(
        tuple(
            (
                output := h58.x87_round(value, rc),
                h110.compare_magnitude(output, value) > 0,
            )
            for rc in h58.RCS
        )
        for value in values
    )


def profiles(point: h207.Point):
    """Profile all rules while replaying only predicates that can fire."""
    features = {
        cosine: h214.lane_features(
            point, h220.CURRENT_RULE.candidate, cosine
        )
        for cosine in (False, True)
    }
    current_active = {
        cosine: all(
            features[cosine].get(name) == value
            for name, value in h220.CURRENT_RULE.terms
        )
        for cosine in (False, True)
    }
    active = {
        name: tuple(
            not current_active[cosine]
            and all(
                features[cosine].get(feature) == value
                for feature, value in branch.terms
            )
            for cosine in (False, True)
        )
        for name, branch in RULES.items()
    }
    if not any(any(lanes) for lanes in active.values()):
        return None
    baseline_values = h216.hidden_values(point, h220.CURRENT_RULE)
    baseline = profile_values(baseline_values)
    candidate_values = {}
    result = {"baseline": baseline}
    for name, branch in RULES.items():
        lanes = active[name]
        if not any(lanes):
            result[name] = baseline
            continue
        values = candidate_values.get(branch.candidate)
        if values is None:
            values = h211.hidden_values(point.prepared, branch.candidate)
            candidate_values[branch.candidate] = values
        result[name] = profile_values(
            tuple(
                values[cosine] if lanes[cosine] else baseline_values[cosine]
                for cosine in (False, True)
            )
        )
    return result


def difference_mask(left, right) -> int:
    mask = 0
    for lane, (old_lane, new_lane) in enumerate(zip(left, right)):
        for index, (old, new) in enumerate(zip(old_lane, new_lane)):
            bit = lane * 6 + index
            if old[0] != new[0]:
                mask |= 1 << bit
            if old[1] != new[1]:
                mask |= 1 << (bit + 3)
    return mask


def seed_operands():
    """Collect old states that activate either new predicate family."""
    result = set()
    sources = (
        (
            "sweep",
            h207.joint_partitions("sweep"),
            h216.ROOT / "capture-kit" / "inputs" / "sweep_inputs.txt",
        ),
        (
            "dense",
            h207.joint_partitions("dense"),
            h216.ROOT / "capture-kit" / "inputs" / "dense_qn.txt",
        ),
    )
    for _, partitions, path in sources:
        lines = path.read_text().splitlines()
        for _, points in partitions:
            for point in points:
                if any_branch_selected(point):
                    result.add(
                        tuple(
                            int(field, 16)
                            for field in lines[
                                point.prepared.joint.observed.index
                            ].split()
                        )
                    )
    h216_lines = h216.DEFAULT_OUTPUT.read_text().splitlines()
    for index, line in enumerate(h216_lines):
        se, sig = (int(field, 16) for field in line.split())
        observed = h171.observed_from_input(index, se, sig)
        if observed is None:
            continue
        point = h207.Point(h188.prepare(blank(observed)), True)
        if any_branch_selected(point):
            result.add((se, sig))
    return tuple(sorted(result))


def mutate_seed(rng: random.Random, seed):
    se, sig = seed
    if rng.getrandbits(1):
        bit = rng.randrange(0, 52)
        candidate = sig ^ (1 << bit)
    else:
        width = rng.randrange(2, 53)
        delta = rng.randrange(1, 1 << width)
        candidate = sig + (delta if rng.getrandbits(1) else -delta)
    if not (1 << 63) <= candidate < (1 << 64):
        candidate = sig ^ 1
    return se, candidate


def generate(output, metadata, per_rule: int, per_pair: int, scan_limit: int):
    rng = random.Random(SEED)
    rule_counts = collections.Counter()
    pair_counts = collections.Counter()
    rows = []
    meta = []
    seeds = seed_operands()
    states = set()
    for index, (se, sig) in enumerate(seeds):
        observed = h171.observed_from_input(index, se, sig)
        if observed is not None:
            states.add(
                (
                    observed.source,
                    observed.signed_n & 3,
                    observed.point.cell,
                    observed.point.a,
                )
            )
    strata = collections.Counter()
    print(f"h221 mutation seeds={len(seeds)}", file=sys.stderr)
    for scan_index in range(scan_limit):
        if scan_index and scan_index % 100_000 == 0:
            print(
                f"h221 scan={scan_index} rules={dict(rule_counts)} "
                f"pairs={dict(pair_counts)}",
                file=sys.stderr,
            )
        constructed = None
        if seeds and rng.randrange(5):
            se, sig = mutate_seed(rng, seeds[rng.randrange(len(seeds))])
        elif rng.getrandbits(1):
            se, sig = h135.direct_operand(rng, "wide")
        else:
            constructed = h175.construct_table_input(rng)
            if constructed is None:
                continue
            se, sig = constructed[:2]
        observed = h171.observed_from_input(scan_index, se, sig)
        if observed is None or observed.family != "wide":
            continue
        if constructed is not None and abs(observed.signed_n) != constructed[2]:
            continue
        key = (
            observed.source,
            observed.signed_n & 3,
            observed.point.cell,
            observed.point.a,
        )
        if key in states:
            continue
        point = h207.Point(h188.prepare(blank(observed)), True)
        values = profiles(point)
        if values is None:
            continue
        rule_hits = []
        for name in RULES:
            if rule_counts[name] >= per_rule:
                continue
            mask = difference_mask(values["baseline"], values[name])
            if mask:
                rule_hits.append((name, mask))
        pair_hits = []
        for left, right in PAIRS:
            pair = f"{left}-{right}"
            if pair_counts[pair] >= per_pair:
                continue
            mask = difference_mask(values[left], values[right])
            if mask:
                pair_hits.append((pair, mask))
        if not rule_hits and not pair_hits:
            continue
        states.add(key)
        rows.append(f"{se:04x} {sig:016x}")
        meta.append(
            f"{scan_index} {observed.source} {observed.signed_n} "
            f"{observed.point.cell} rules="
            + ",".join(f"{name}:{mask:03x}" for name, mask in rule_hits)
            + " pairs="
            + ",".join(f"{name}:{mask:03x}" for name, mask in pair_hits)
        )
        strata[observed.source, observed.signed_n & 3, observed.point.cell] += 1
        for name, _ in rule_hits:
            rule_counts[name] += 1
        for name, _ in pair_hits:
            pair_counts[name] += 1
        if (
            all(rule_counts[name] >= per_rule for name in RULES)
            and all(
                pair_counts[f"{left}-{right}"] >= per_pair
                for left, right in PAIRS
            )
        ):
            break
    missing_rules = {
        name: rule_counts[name]
        for name in RULES
        if rule_counts[name] < per_rule
    }
    missing_pairs = {
        f"{left}-{right}": pair_counts[f"{left}-{right}"]
        for left, right in PAIRS
        if pair_counts[f"{left}-{right}"] < per_pair
    }
    if missing_rules or missing_pairs:
        raise SystemExit(
            f"h221 incomplete after {scan_limit}: "
            f"rules={missing_rules} pairs={missing_pairs}"
        )
    output.write_text("\n".join(rows) + "\n")
    metadata.write_text("\n".join(meta) + "\n")
    print(
        f"h221 generated inputs={len(rows)} scans={scan_index + 1} "
        f"rules={dict(sorted(rule_counts.items()))} "
        f"pairs={dict(sorted(pair_counts.items()))} "
        f"strata={dict(sorted(strata.items()))} seed={SEED:#x}",
        file=sys.stderr,
    )


def load_capture(inputs: pathlib.Path, capture: pathlib.Path):
    operands = [
        tuple(int(field, 16) for field in line.split())
        for line in inputs.read_text().splitlines()
    ]
    sine_modes = [
        (capture / f"{CAPTURE_STEM}_fsin_{rc}_status.txt")
        .read_text().splitlines()
        for rc in h58.RCS
    ]
    pair_modes = [
        (capture / f"{CAPTURE_STEM}_fsincos_{rc}_status.txt")
        .read_text().splitlines()
        for rc in h58.RCS
    ]
    if any(len(lines) != len(operands) for lines in (*sine_modes, *pair_modes)):
        raise SystemExit("h221 input/capture line counts differ")
    result = []
    for index, (se, sig) in enumerate(operands):
        observed = h171.observed_from_input(index, se, sig)
        if observed is None or observed.family != "wide":
            raise SystemExit(f"h221 input {index + 1} is not wide table")
        sine_outputs = []
        sine_c1 = []
        cosine_outputs = []
        cosine_c1 = []
        for sine_lines, pair_lines in zip(sine_modes, pair_modes):
            sine_fields = sine_lines[index].split()
            pair_fields = pair_lines[index].split()
            if (
                len(sine_fields) != 5
                or sine_fields[0] != "OK"
                or sine_fields[3] != "SW"
                or len(pair_fields) != 7
                or pair_fields[0] != "OK"
                or pair_fields[5] != "SW"
            ):
                raise ValueError((sine_lines[index], pair_lines[index]))
            sine_outputs.append((int(sine_fields[1], 16), int(sine_fields[2], 16)))
            sine_c1.append(bool(int(sine_fields[4], 16) & 0x0200))
            cosine_outputs.append((int(pair_fields[3], 16), int(pair_fields[4], 16)))
            cosine_c1.append(bool(int(pair_fields[6], 16) & 0x0200))
        joint = h182.Point(
            dataclasses.replace(
                observed,
                outputs=tuple(sine_outputs),
                c1=tuple(sine_c1),
            ),
            tuple(cosine_outputs),
            tuple(cosine_c1),
        )
        result.append(h207.Point(h188.prepare(joint), True))
    return result


def score(points, branch):
    total = h213.ZERO_JOINT
    for point in points:
        values = hidden_values(point, branch)
        total = h213.add(total, h213.metric_for_values(point, *values))
    return total


def targeted(metadata, token: str, field: str):
    result = []
    prefix = f"{field}="
    for index, line in enumerate(metadata):
        values = next(
            value[len(prefix):]
            for value in line.split()
            if value.startswith(prefix)
        )
        names = [item.split(":", 1)[0] for item in values.split(",") if item]
        if token in names:
            result.append(index)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--score", type=pathlib.Path)
    parser.add_argument("--per-rule", type=int, default=16)
    parser.add_argument("--per-pair", type=int, default=12)
    parser.add_argument("--scan-limit", type=int, default=30_000_000)
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--metadata", type=pathlib.Path, default=DEFAULT_METADATA)
    args = parser.parse_args()
    if args.generate:
        generate(
            args.output,
            args.metadata,
            args.per_rule,
            args.per_pair,
            args.scan_limit,
        )
    if args.score is not None:
        points = load_capture(args.output, args.score)
        metadata = args.metadata.read_text().splitlines()
        print(f"loaded {len(points)} fresh h221 separators")
        baseline_all = score(points, None)
        print(f"  all baseline={baseline_all}")
        for name, branch in RULES.items():
            indices = targeted(metadata, name, "rules")
            selected_points = [points[index] for index in indices]
            baseline = score(selected_points, None)
            value = score(selected_points, branch)
            status = "PASS" if h207.no_worse(value, baseline) else "FAIL"
            print(
                f"{status} {name:11s} n={len(indices):3d} "
                f"sine {baseline[0]}->{value[0]} "
                f"cosine {baseline[1]}->{value[1]}"
            )
        for left, right in PAIRS:
            name = f"{left}-{right}"
            indices = targeted(metadata, name, "pairs")
            selected_points = [points[index] for index in indices]
            left_value = score(selected_points, RULES[left])
            right_value = score(selected_points, RULES[right])
            print(
                f"PAIR {name:25s} n={len(indices):3d} "
                f"{left_value}->{right_value}"
            )
    if not args.generate and args.score is None:
        parser.error("select --generate and/or --score CAPTURE_DIRECTORY")


if __name__ == "__main__":
    main()
