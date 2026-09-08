#!/usr/bin/env python3
"""Generate and score fresh separators for h215 microcontrol rules.

h215 leaves 25 three-signal rules that are componentwise non-regressing on
all 91,379 sweep/dense points.  Existing focused captures never activate
them.  This hardware-blind generator freezes nine physically distinct
representatives spanning both surviving program families and selects inputs
where each differs architecturally from the current Round-35 model.

The representatives distinguish operation/sign, guard/round, and retained
carrier-bit readings that are equivalent on fitting data.  Standalone FSIN
and paired FSINCOS cosine are captured under RN/RD/RU with status so the same
shared-kernel lane-local rule is tested independently in both orientations.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
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


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_table_fadd_microcontrol_h216.txt"
)
DEFAULT_METADATA = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_table_fadd_microcontrol_h216.meta.txt"
)
SEED = 0xF216C5


def extended(base: h213.Rule, term) -> h213.Rule:
    return h213.Rule(base.candidate, (*base.terms, term))


BASE_A = h213.Rule(
    h213.PROGRAMS[3],
    (
        ("pair.lead-p.difference", 27),
        ("pair.q-p.difference", 10),
    ),
)
BASE_B = h213.Rule(
    h213.PROGRAMS[6],
    (
        ("node0.exponent-difference", 14),
        ("node0.raw.exponent-mod4", 0),
    ),
)
RULES = {
    "a_far": extended(BASE_A, ("node0.operation-far-sub", 1)),
    "a_guard0": extended(BASE_A, ("node0.raw.guard", 0)),
    "a_retbit5": extended(BASE_A, ("node0.retained.bit5", 1)),
    "a_bit4z": extended(BASE_A, ("node0.raw.bit4", 0)),
    "a_round0": extended(BASE_A, ("node0.raw.round", 0)),
    "b_bit3": extended(BASE_B, ("node0.raw.bit3", 1)),
    "b_round": extended(BASE_B, ("node0.raw.round", 1)),
    "b_sign": extended(BASE_B, ("node0.raw.sign", 0)),
    "b_bit7": extended(BASE_B, ("node0.raw.bit7", 1)),
}


def blank(observed) -> h182.Point:
    return h182.Point(
        observed,
        ((0, 0),) * len(h58.RCS),
        (False,) * len(h58.RCS),
    )


def hidden_values(point: h207.Point, rule: h213.Rule | None):
    baseline = h207.current_values(point.prepared)
    if rule is None:
        return baseline
    candidate = h211.hidden_values(point.prepared, rule.candidate)
    outputs = []
    for cosine in (False, True):
        features = h214.lane_features(point, rule.candidate, cosine)
        selected = all(
            features.get(name) == value for name, value in rule.terms
        )
        outputs.append(candidate[cosine] if selected else baseline[cosine])
    return tuple(outputs)


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


def profile(point: h207.Point, rule: h213.Rule | None):
    return profile_values(hidden_values(point, rule))


def rule_profiles(point: h207.Point, active_names=None):
    """Compute all rule profiles with each shared program replayed once."""
    baseline_values = h207.current_values(point.prepared)
    result = {}
    groups = collections.defaultdict(list)
    active_names = set(RULES) if active_names is None else set(active_names)
    for name, rule in RULES.items():
        if name not in active_names:
            continue
        groups[rule.candidate].append((name, rule))
    for candidate, candidate_rules in groups.items():
        candidate_values = h211.hidden_values(point.prepared, candidate)
        features = {
            cosine: h214.lane_features(point, candidate, cosine)
            for cosine in (False, True)
        }
        for name, rule in candidate_rules:
            values = tuple(
                candidate_values[cosine]
                if all(
                    features[cosine].get(feature) == value
                    for feature, value in rule.terms
                )
                else baseline_values[cosine]
                for cosine in (False, True)
            )
            result[name] = profile_values(values)
    return profile_values(baseline_values), result


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


def generate(output, metadata, per_rule: int, scan_limit: int) -> None:
    rng = random.Random(SEED)
    counts = collections.Counter()
    rows = []
    meta = []
    states = set()
    strata = collections.Counter()
    for scan_index in range(scan_limit):
        if scan_index and scan_index % 50_000 == 0:
            print(
                f"h216 scan={scan_index} counts={dict(sorted(counts.items()))}",
                file=sys.stderr,
            )
        constructed = None
        if rng.getrandbits(1):
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
        active_names = [
            name for name in RULES if counts[name] < per_rule
        ]
        baseline, profiles = rule_profiles(point, active_names)
        separated = []
        for name in RULES:
            if counts[name] >= per_rule:
                continue
            mask = difference_mask(baseline, profiles[name])
            if mask:
                separated.append((name, mask))
        if not separated:
            continue
        states.add(key)
        rows.append(f"{se:04x} {sig:016x}")
        meta.append(
            f"{scan_index} {observed.source} {observed.signed_n} "
            f"{observed.point.cell} "
            + ",".join(f"{name}:{mask:03x}" for name, mask in separated)
        )
        strata[observed.source, observed.signed_n & 3, observed.point.cell] += 1
        for name, _ in separated:
            counts[name] += 1
        if all(counts[name] >= per_rule for name in RULES):
            break
    missing = {
        name: counts[name] for name in RULES if counts[name] < per_rule
    }
    if missing:
        raise SystemExit(
            f"h216 stopped after {scan_limit} scans; incomplete={missing}"
        )
    output.write_text("\n".join(rows) + "\n")
    metadata.write_text("\n".join(meta) + "\n")
    print(
        f"h216: selected {len(rows)} inputs from {scan_index + 1} scans; "
        f"per-rule={dict(sorted(counts.items()))}; "
        f"strata={dict(sorted(strata.items()))}; seed={SEED:#x}",
        file=sys.stderr,
    )


def load_capture(inputs: pathlib.Path, capture: pathlib.Path):
    operands = [
        tuple(int(field, 16) for field in line.split())
        for line in inputs.read_text().splitlines()
    ]
    sine_modes = [
        (
            capture
            / f"constraint_table_fadd_microcontrol_h216_fsin_{rc}_status.txt"
        ).read_text().splitlines()
        for rc in h58.RCS
    ]
    pair_modes = [
        (
            capture
            / f"constraint_table_fadd_microcontrol_h216_fsincos_{rc}_status.txt"
        ).read_text().splitlines()
        for rc in h58.RCS
    ]
    if any(
        len(lines) != len(operands)
        for lines in (*sine_modes, *pair_modes)
    ):
        raise SystemExit("h216 input/capture line counts differ")
    result = []
    for index, (se, sig) in enumerate(operands):
        observed = h171.observed_from_input(index, se, sig)
        if observed is None or observed.family != "wide":
            raise SystemExit(f"h216 input {index + 1} is not wide table")
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
            sine_outputs.append(
                (int(sine_fields[1], 16), int(sine_fields[2], 16))
            )
            sine_c1.append(bool(int(sine_fields[4], 16) & 0x0200))
            cosine_outputs.append(
                (int(pair_fields[3], 16), int(pair_fields[4], 16))
            )
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


def score(points, rule: h213.Rule | None):
    value = h213.ZERO_JOINT
    for point in points:
        metric = (
            h211.point_metric(point, None)
            if rule is None
            else h214.conditional_metric(point, rule)
        )
        value = h213.add(value, metric)
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--score", type=pathlib.Path)
    parser.add_argument("--per-rule", type=int, default=8)
    parser.add_argument("--scan-limit", type=int, default=30_000_000)
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--metadata", type=pathlib.Path, default=DEFAULT_METADATA
    )
    args = parser.parse_args()
    if args.generate:
        generate(args.output, args.metadata, args.per_rule, args.scan_limit)
    if args.score is not None:
        points = load_capture(args.output, args.score)
        metadata = args.metadata.read_text().splitlines()
        print(f"loaded {len(points)} fresh h216 separators")
        for name, rule in RULES.items():
            targeted = [
                point
                for point, line in zip(points, metadata)
                if any(
                    item.split(":", 1)[0] == name
                    for item in line.split()[-1].split(",")
                )
            ]
            baseline = score(targeted, None)
            value = score(targeted, rule)
            status = "PASS" if h207.no_worse(value, baseline) else "FAIL"
            print(
                f"{status} {name:10s} n={len(targeted):3d} "
                f"sine {baseline[0]}->{value[0]} "
                f"cosine {baseline[1]}->{value[1]}"
            )
    if not args.generate and args.score is None:
        parser.error("select --generate and/or --score CAPTURE_DIRECTORY")


if __name__ == "__main__":
    main()
