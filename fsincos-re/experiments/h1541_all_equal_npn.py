#!/usr/bin/env python3
"""Exhaust NPN class 0x18, the all-equal/opposite-minterm function.

For all_equal(a,b,c)=target, a and b must agree on every target-one row.
Where the target is zero and a,b differ, c is irrelevant; where they agree,
c must be their complement.  On target-one rows c must equal a.  Grouping
patterns by their projection onto target-one rows and querying those exact
partial assignments yields a complete search over unordered triples.

Both target polarities are searched.  The sampled partial-assignment index is
only a necessary filter; every surviving history is checked against the full
34,473-row constraint vector.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path

import h1398_branch_two_wire_gate as h1398
import h1535_complete_three_wire_xor as h1535


MAX_RECORDED_MATCHES = 500
SAMPLE_BITS = 128
BLOCK_BITS = 8
DEPENDENCIES = (
    "h1398_branch_two_wire_gate.py",
    "h1535_complete_three_wire_xor.py",
    "h1539_three_input_npn_coverage.py",
    *h1535.DEPENDENCIES[1:],
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def set_positions(value: int) -> list[int]:
    positions = []
    while value:
        low = value & -value
        positions.append(low.bit_length() - 1)
        value ^= low
    return positions


def sample_blocks(row_count: int) -> list[tuple[int, ...]]:
    count = min(SAMPLE_BITS, row_count)
    positions = [
        (index * row_count) // count for index in range(count)
    ]
    return [
        tuple(positions[start:start + BLOCK_BITS])
        for start in range(0, len(positions), BLOCK_BITS)
    ]


def signature(value: int, positions: tuple[int, ...]) -> int:
    result = 0
    for output_bit, input_bit in enumerate(positions):
        result |= ((value >> input_bit) & 1) << output_bit
    return result


class PartialPatternIndex:
    def __init__(self, patterns: list[int], row_count: int):
        self.patterns = patterns
        self.blocks = sample_blocks(row_count)
        self.signatures = [
            [signature(pattern, block) for pattern in patterns]
            for block in self.blocks
        ]
        self.exact_masks = []
        self.compatibility_caches: list[dict[tuple[int, int], int]] = []
        for block_index, block in enumerate(self.blocks):
            exact = [0] * (1 << len(block))
            for pattern_index, value in enumerate(
                    self.signatures[block_index]):
                exact[value] |= 1 << pattern_index
            self.exact_masks.append(exact)
            self.compatibility_caches.append({})
        self.all_patterns = (1 << len(patterns)) - 1

    def compatible_mask(
            self, block_index: int, constraint_mask: int,
            required_value: int,
    ) -> int:
        key = (constraint_mask, required_value & constraint_mask)
        cache = self.compatibility_caches[block_index]
        if key in cache:
            return cache[key]
        result = 0
        for value, pattern_mask in enumerate(self.exact_masks[block_index]):
            if (value ^ required_value) & constraint_mask == 0:
                result |= pattern_mask
        cache[key] = result
        return result

    def candidates(
            self, constraint_mask: int, required_value: int,
            minimum_index: int,
    ) -> tuple[int, list[int]]:
        allowed = self.all_patterns & ~((1 << minimum_index) - 1)
        for block_index, block in enumerate(self.blocks):
            block_mask = signature(constraint_mask, block)
            if not block_mask:
                continue
            block_value = signature(required_value, block)
            allowed &= self.compatible_mask(
                block_index, block_mask, block_value
            )
            if not allowed:
                return 0, []
        prefix_count = allowed.bit_count()
        exact = []
        while allowed:
            low = allowed & -allowed
            index = low.bit_length() - 1
            allowed ^= low
            if (self.patterns[index] ^ required_value) & constraint_mask == 0:
                exact.append(index)
        return prefix_count, exact


def permutation_count(left: int, middle: int, right: int) -> int:
    if left == right:
        return 1
    if left == middle or middle == right:
        return 3
    return 6


def search_target(
        patterns: list[int], truth: int, row_count: int,
) -> dict[str, object]:
    all_mask = (1 << row_count) - 1
    zero_mask = all_mask ^ truth
    groups: dict[int, list[int]] = defaultdict(list)
    for index, pattern in enumerate(patterns):
        groups[pattern & truth].append(index)
    index = PartialPatternIndex(patterns, row_count)

    pair_checks = 0
    prefix_third_candidates = 0
    full_third_checks = 0
    exact_unordered = 0
    exact_ordered = 0
    recorded = []
    started = time.monotonic()
    for group in groups.values():
        for left_pos, left_index in enumerate(group):
            left = patterns[left_index]
            for middle_index in group[left_pos:]:
                pair_checks += 1
                middle = patterns[middle_index]
                agreement = all_mask ^ (left ^ middle)
                constraint_mask = truth | (zero_mask & agreement)
                required = (
                    (truth & left)
                    | (zero_mask & agreement & (all_mask ^ left))
                )
                prefix_count, right_indices = index.candidates(
                    constraint_mask, required, middle_index
                )
                prefix_third_candidates += prefix_count
                full_third_checks += prefix_count
                for right_index in right_indices:
                    right = patterns[right_index]
                    value = (
                        (left & middle & right)
                        | ((all_mask ^ left)
                           & (all_mask ^ middle)
                           & (all_mask ^ right))
                    )
                    if value != truth:
                        raise RuntimeError("partial all-equal query false match")
                    exact_unordered += 1
                    exact_ordered += permutation_count(
                        left_index, middle_index, right_index
                    )
                    if len(recorded) < MAX_RECORDED_MATCHES:
                        recorded.append(
                            (left_index, middle_index, right_index)
                        )
    return {
        "positive_projection_groups": len(groups),
        "pair_checks": pair_checks,
        "sample_bits": sum(map(len, index.blocks)),
        "prefix_third_candidates": prefix_third_candidates,
        "full_third_checks": full_third_checks,
        "exact_unordered_pattern_multisets": exact_unordered,
        "exact_ordered_pattern_roles": exact_ordered,
        "recorded_indices": recorded,
        "recorded_matches_truncated": exact_unordered > len(recorded),
        "elapsed_seconds": time.monotonic() - started,
    }


def all_equal(left: int, middle: int, right: int, mask: int) -> int:
    return ((left & middle & right)
            | ((mask ^ left) & (mask ^ middle) & (mask ^ right)))


def selftest() -> None:
    patterns = [0b000001, 0b001110, 0b110000, 0b101011, 0b011101]
    row_count = 6
    mask = (1 << row_count) - 1
    truths = [
        all_equal(patterns[0], patterns[2], patterns[4], mask),
        0b010101,
    ]
    for truth in truths:
        result = search_target(patterns, truth, row_count)
        unordered = 0
        ordered = 0
        for left in range(len(patterns)):
            for middle in range(left, len(patterns)):
                for right in range(middle, len(patterns)):
                    if all_equal(
                            patterns[left], patterns[middle], patterns[right],
                            mask
                    ) != truth:
                        continue
                    unordered += 1
                    ordered += permutation_count(left, middle, right)
        if result["exact_unordered_pattern_multisets"] != unordered:
            raise RuntimeError("all-equal selftest unordered mismatch")
        if result["exact_ordered_pattern_roles"] != ordered:
            raise RuntimeError("all-equal selftest ordered mismatch")


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
        result = search_target(patterns, target, row_count)
        report[polarity] = {
            "target_ones": target.bit_count(),
            "all_equal": result_for_report(result, patterns, literals),
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
        "schema": "fsincos-h1541-all-equal-npn-v1",
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
            "npn_class": "18_all_equal_opposite_minterms",
            "both_output_polarities": True,
            "input_polarities": "literal_universe_contains_both",
            "algorithm": "exact_positive_projection_and_partial_assignment",
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
    print(
        "wrote", args.report,
        {
            target: {
                polarity: report[target][polarity]["all_equal"][
                    "exact_ordered_pattern_roles"
                ]
                for polarity in ("direct", "output_inverted")
            }
            for target in ("physical_carry", "incumbent_flip")
        },
        flush=True,
    )


if __name__ == "__main__":
    main()
