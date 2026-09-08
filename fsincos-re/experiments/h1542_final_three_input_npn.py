#!/usr/bin/env python3
"""Exhaust the final NPN classes 0x16 and 0x19.

Class 0x16 is represented by exactly_one(a,b,c).  For a fixed symmetric pair
b,c, rows with b=c=1 must have target zero.  Everywhere else a is fixed to
target XOR (b XOR c).

Class 0x19 is represented by

    xor_or_mux(a,b,c) = a ? (b | c) : (b ^ c)
                         = (b ^ c) | (a & b & c).

For fixed b, c equals b on target-zero rows, equals one on target-one rows
where b is zero, and is unconstrained on target-one rows where b is one.
After c is chosen, a must equal the target wherever b=c=1.

Both reductions are necessary and sufficient.  Sampled partial-assignment
indices only reject candidates; every survivor is verified over the complete
constraint vector and by direct function evaluation.  Both output polarities
are searched, completing each NPN orbit because the literal universe already
contains both input polarities.
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path

import h1398_branch_two_wire_gate as h1398
import h1535_complete_three_wire_xor as h1535
import h1541_all_equal_npn as h1541


MAX_RECORDED_MATCHES = 500
DEPENDENCIES = (
    "h1398_branch_two_wire_gate.py",
    "h1535_complete_three_wire_xor.py",
    "h1539_three_input_npn_coverage.py",
    "h1540_remaining_binate_algebraic.py",
    "h1541_all_equal_npn.py",
    *h1535.DEPENDENCIES[1:],
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def pair_order_count(left: int, right: int) -> int:
    return 1 if left == right else 2


def exactly_one(left: int, middle: int, right: int, mask: int) -> int:
    return (
        (left & (mask ^ middle) & (mask ^ right))
        | ((mask ^ left) & middle & (mask ^ right))
        | ((mask ^ left) & (mask ^ middle) & right)
    )


def xor_or_mux(
        distinguished: int, left: int, right: int, mask: int,
) -> int:
    return ((left ^ right) | (distinguished & left & right)) & mask


def compatible_upper(
        index: h1541.PartialPatternIndex, block_constraints: list[tuple[int, int]],
        constraint_mask: int, required_value: int, maximum_index: int,
) -> tuple[int, list[int]]:
    allowed = index.all_patterns & ((1 << (maximum_index + 1)) - 1)
    for block_index, (block_mask, block_value) in enumerate(block_constraints):
        if not block_mask:
            continue
        allowed &= index.compatible_mask(
            block_index, block_mask, block_value
        )
        if not allowed:
            return 0, []
    prefix_count = allowed.bit_count()
    exact = []
    while allowed:
        low = allowed & -allowed
        candidate = low.bit_length() - 1
        allowed ^= low
        if ((index.patterns[candidate] ^ required_value)
                & constraint_mask == 0):
            exact.append(candidate)
    return prefix_count, exact


def small_target_pair_candidates(
        patterns: list[int], truth: int,
) -> tuple[int, list[tuple[int, int]]]:
    groups: dict[int, list[int]] = defaultdict(list)
    for index, pattern in enumerate(patterns):
        groups[pattern & truth].append(index)
    group_items = list(groups.items())
    pairs = []
    group_pair_checks = 0
    for left_group, (left_projection, left_indices) in enumerate(group_items):
        for right_projection, right_indices in group_items[left_group:]:
            group_pair_checks += 1
            if left_projection & right_projection:
                continue
            for left in left_indices:
                start = bisect.bisect_left(right_indices, left)
                for right in right_indices[start:]:
                    pairs.append((left, right))
            if left_projection != right_projection:
                for left in right_indices:
                    start = bisect.bisect_left(left_indices, left)
                    for right in left_indices[start:]:
                        pairs.append((left, right))
    pairs = sorted(set(pairs))
    return group_pair_checks, pairs


def search_exactly_one(
        patterns: list[int], truth: int, row_count: int,
) -> dict[str, object]:
    all_mask = (1 << row_count) - 1
    index = h1541.PartialPatternIndex(patterns, row_count)
    target_signatures = [
        h1541.signature(truth, block) for block in index.blocks
    ]
    pair_source = "small_target_projection_groups"
    pair_generation_checks = 0
    pair_generation_prefix_candidates = 0
    if truth.bit_count() <= 64:
        pair_generation_checks, pairs = small_target_pair_candidates(
            patterns, truth
        )
    else:
        pair_source = "sampled_disjoint_partial_index"
        pairs = []
        for middle, pattern in enumerate(patterns):
            constraint = pattern & truth
            prefix_count, right_indices = index.candidates(
                constraint, 0, middle
            )
            pair_generation_checks += 1
            pair_generation_prefix_candidates += prefix_count
            pairs.extend((middle, right) for right in right_indices)

    valid_pair_checks = 0
    prefix_distinguished_candidates = 0
    full_distinguished_checks = 0
    exact_unordered = 0
    exact_ordered = 0
    recorded = []
    started = time.monotonic()
    for middle, right in pairs:
        b = patterns[middle]
        c = patterns[right]
        both_one = b & c
        if both_one & truth:
            raise RuntimeError("exactly-one pair generator admitted target overlap")
        valid_pair_checks += 1
        constraint_mask = all_mask ^ both_one
        required_value = (truth ^ (b ^ c)) & constraint_mask
        block_constraints = []
        for block_index, block in enumerate(index.blocks):
            b_signature = index.signatures[block_index][middle]
            c_signature = index.signatures[block_index][right]
            width_mask = (1 << len(block)) - 1
            block_both = b_signature & c_signature
            block_mask = width_mask ^ block_both
            block_value = (
                target_signatures[block_index]
                ^ (b_signature ^ c_signature)
            ) & block_mask
            block_constraints.append((block_mask, block_value))
        prefix_count, left_indices = compatible_upper(
            index, block_constraints, constraint_mask, required_value, middle
        )
        prefix_distinguished_candidates += prefix_count
        full_distinguished_checks += prefix_count
        for left in left_indices:
            value = exactly_one(patterns[left], b, c, all_mask)
            if value != truth:
                raise RuntimeError("exactly-one partial query false match")
            exact_unordered += 1
            exact_ordered += h1541.permutation_count(left, middle, right)
            if len(recorded) < MAX_RECORDED_MATCHES:
                recorded.append((left, middle, right))

    return {
        "pair_source": pair_source,
        "pair_generation_checks": pair_generation_checks,
        "pair_generation_prefix_candidates": (
            pair_generation_prefix_candidates
        ),
        "valid_symmetric_pairs": valid_pair_checks,
        "sample_bits": sum(map(len, index.blocks)),
        "prefix_distinguished_candidates": prefix_distinguished_candidates,
        "full_distinguished_checks": full_distinguished_checks,
        "exact_unordered_pattern_multisets": exact_unordered,
        "exact_ordered_pattern_roles": exact_ordered,
        "recorded_indices": recorded,
        "recorded_matches_truncated": exact_unordered > len(recorded),
        "elapsed_seconds": time.monotonic() - started,
    }


def search_xor_or_mux(
        patterns: list[int], truth: int, row_count: int,
) -> dict[str, object]:
    all_mask = (1 << row_count) - 1
    index = h1541.PartialPatternIndex(patterns, row_count)
    pair_queries = 0
    pair_prefix_candidates = 0
    valid_symmetric_pairs = 0
    distinguished_queries = 0
    distinguished_prefix_candidates = 0
    full_distinguished_checks = 0
    exact_unordered = 0
    exact_ordered = 0
    recorded = []
    started = time.monotonic()

    for middle, b in enumerate(patterns):
        pair_constraint = all_mask ^ (truth & b)
        pair_required = (b ^ truth) & pair_constraint
        prefix_count, right_indices = index.candidates(
            pair_constraint, pair_required, middle
        )
        pair_queries += 1
        pair_prefix_candidates += prefix_count
        valid_symmetric_pairs += len(right_indices)
        for right in right_indices:
            c = patterns[right]
            both_one = b & c
            distinguished_queries += 1
            a_prefix_count, left_indices = index.candidates(
                both_one, truth, 0
            )
            distinguished_prefix_candidates += a_prefix_count
            full_distinguished_checks += a_prefix_count
            for left in left_indices:
                value = xor_or_mux(patterns[left], b, c, all_mask)
                if value != truth:
                    raise RuntimeError("XOR/OR-mux partial query false match")
                exact_unordered += 1
                exact_ordered += pair_order_count(middle, right)
                if len(recorded) < MAX_RECORDED_MATCHES:
                    recorded.append((left, middle, right))

    return {
        "pair_queries": pair_queries,
        "pair_prefix_candidates": pair_prefix_candidates,
        "valid_symmetric_pairs": valid_symmetric_pairs,
        "distinguished_queries": distinguished_queries,
        "sample_bits": sum(map(len, index.blocks)),
        "distinguished_prefix_candidates": distinguished_prefix_candidates,
        "full_distinguished_checks": full_distinguished_checks,
        "exact_unordered_symmetric_pairs": exact_unordered,
        "exact_ordered_pattern_roles": exact_ordered,
        "recorded_indices": recorded,
        "recorded_matches_truncated": exact_unordered > len(recorded),
        "elapsed_seconds": time.monotonic() - started,
    }


def selftest() -> None:
    patterns = [0b000001, 0b001110, 0b110000, 0b101011, 0b011101]
    row_count = 6
    all_mask = (1 << row_count) - 1
    truths = [
        exactly_one(patterns[0], patterns[2], patterns[4], all_mask),
        xor_or_mux(patterns[0], patterns[2], patterns[4], all_mask),
        0b010101,
    ]
    for truth in truths:
        one_result = search_exactly_one(patterns, truth, row_count)
        mux_result = search_xor_or_mux(patterns, truth, row_count)
        one_unordered = one_ordered = 0
        for left in range(len(patterns)):
            for middle in range(left, len(patterns)):
                for right in range(middle, len(patterns)):
                    if exactly_one(
                            patterns[left], patterns[middle], patterns[right],
                            all_mask
                    ) != truth:
                        continue
                    one_unordered += 1
                    one_ordered += h1541.permutation_count(
                        left, middle, right
                    )
        if one_result["exact_unordered_pattern_multisets"] != one_unordered:
            raise RuntimeError("exactly-one selftest unordered mismatch")
        if one_result["exact_ordered_pattern_roles"] != one_ordered:
            raise RuntimeError("exactly-one selftest ordered mismatch")

        mux_unordered = mux_ordered = 0
        for left in range(len(patterns)):
            for middle in range(len(patterns)):
                for right in range(middle, len(patterns)):
                    if xor_or_mux(
                            patterns[left], patterns[middle], patterns[right],
                            all_mask
                    ) != truth:
                        continue
                    mux_unordered += 1
                    mux_ordered += pair_order_count(middle, right)
        if mux_result["exact_unordered_symmetric_pairs"] != mux_unordered:
            raise RuntimeError("XOR/OR-mux selftest unordered mismatch")
        if mux_result["exact_ordered_pattern_roles"] != mux_ordered:
            raise RuntimeError("XOR/OR-mux selftest ordered mismatch")


def named_matches(
        result: dict[str, object], patterns: list[int],
        literals: dict[int, list[str]],
) -> list[dict[str, object]]:
    matches = []
    for indices in result["recorded_indices"]:
        equivalent_names = [literals[patterns[index]] for index in indices]
        matches.append({
            "representatives": [
                h1398.representative(names) for names in equivalent_names
            ],
            "equivalent_counts": [len(names) for names in equivalent_names],
        })
    return matches


def result_for_report(
        result: dict[str, object], patterns: list[int],
        literals: dict[int, list[str]],
) -> dict[str, object]:
    return {
        **{key: value for key, value in result.items()
           if key != "recorded_indices"},
        "matches": named_matches(result, patterns, literals),
    }


def search_polarities(
        patterns: list[int], literals: dict[int, list[str]], truth: int,
        row_count: int,
) -> dict[str, dict[str, object]]:
    all_mask = (1 << row_count) - 1
    report = {}
    for polarity, target in (
            ("direct", truth), ("output_inverted", all_mask ^ truth)):
        one_result = search_exactly_one(patterns, target, row_count)
        mux_result = search_xor_or_mux(patterns, target, row_count)
        report[polarity] = {
            "target_ones": target.bit_count(),
            "exactly_one": result_for_report(
                one_result, patterns, literals
            ),
            "xor_or_mux": result_for_report(mux_result, patterns, literals),
        }
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("positive_allmode", type=Path)
    parser.add_argument("control_allmode", type=Path)
    parser.add_argument("project_root", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit("refusing to overwrite " + str(args.report))

    selftest()
    (source_rows, patterns, literals, carry_truth, flip_truth,
     named_feature_count, constrained_rows, h1401_feature_count,
     h1401_pattern_count) = h1535.build_wall(
         args.features, args.positive_allmode, args.control_allmode, args.jobs)
    report = {
        "schema": "fsincos-h1542-final-three-input-npn-v1",
        "code": {
            "script_sha256": digest(Path(__file__)),
            "dependency_sha256": {
                name: digest(Path(__file__).with_name(name))
                for name in DEPENDENCIES
            },
        },
        "inputs": {
            "features_sha256": digest(args.features),
            "positive_allmode_sha256": digest(args.positive_allmode),
            "control_allmode_sha256": digest(args.control_allmode),
            "h1539_report_sha256": digest(
                args.project_root
                / "tmp/ledger33/current/h1539_three_input_npn_coverage.json"
            ),
            "h1540_report_sha256": digest(
                args.project_root
                / "tmp/ledger33/current/h1540_remaining_binate_algebraic.json"
            ),
            "h1541_report_sha256": digest(
                args.project_root
                / "tmp/ledger33/current/h1541_all_equal_npn.json"
            ),
        },
        "wall": {
            "source_rows": len(source_rows),
            "constrained_rows": constrained_rows,
            "neutral_rows": len(source_rows) - constrained_rows,
            "named_features": named_feature_count,
            "literal_patterns": len(patterns),
            "h1401_named_features": h1401_feature_count,
            "h1401_literal_patterns": h1401_pattern_count,
        },
        "search": {
            "npn_classes": ["16_exactly_one", "19_xor_or_mux"],
            "both_output_polarities": True,
            "input_polarities": "literal_universe_contains_both",
            "algorithms": (
                "exact_disjoint_projection_plus_partial_assignment;"
                "exact_two_stage_partial_assignment"
            ),
            "sample_filter": "necessary_only_no_false_negatives",
            "selftest": "pass",
            "hardware_policy": "immutable_cached_labels_no_x87_execution",
        },
        "physical_carry": search_polarities(
            patterns, literals, carry_truth, constrained_rows
        ),
        "incumbent_flip": search_polarities(
            patterns, literals, flip_truth, constrained_rows
        ),
        "promotion": "none_without_physical_provenance",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    summary = {
        target: {
            polarity: {
                shape: report[target][polarity][shape][
                    "exact_ordered_pattern_roles"
                ]
                for shape in ("exactly_one", "xor_or_mux")
            }
            for polarity in ("direct", "output_inverted")
        }
        for target in ("physical_carry", "incumbent_flip")
    }
    print("wrote", args.report, summary, flush=True)


if __name__ == "__main__":
    main()
