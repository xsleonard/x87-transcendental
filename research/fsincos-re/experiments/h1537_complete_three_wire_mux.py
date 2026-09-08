#!/usr/bin/env python3
"""Exhaust every three-history 2:1 mux over the current R59 wall.

The missing bit is itself a selector, so a carry-select mux is the next
canonical circuit after h1535/h1536's 3:2-compressor outputs:

    mux(s,d0,d1) = (~s & d0) | (s & d1).

For a fixed selector history s, d0 must equal the target wherever s is zero
and d1 must equal it wherever s is one.  This yields an exact quadratic
membership census over all ordered selector/data roles.  Prefix tests use
the same equality constraints on a subset of rows and therefore cannot hide
a solution; every survivor is checked over the complete wall.

This is a representation/circuit-class audit.  It does not establish Intel
Skylake provenance and cannot by itself promote a selector.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np

import h1398_branch_two_wire_gate as h1398
import h1535_complete_three_wire_xor as h1535


MAX_RECORDED_MATCHES = 500
DEPENDENCIES = (
    "h1398_branch_two_wire_gate.py",
    "h1535_complete_three_wire_xor.py",
    *h1535.DEPENDENCIES[1:],
)
CATEGORIES = (
    "all_distinct",
    "selector_equals_data0",
    "selector_equals_data1",
    "data0_equals_data1",
    "all_equal",
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def word_matrix(patterns: list[int], row_count: int) -> np.ndarray:
    word_count = (row_count + 63) // 64
    byte_count = word_count * 8
    matrix = np.empty((len(patterns), word_count), dtype=np.uint64)
    for index, pattern in enumerate(patterns):
        matrix[index] = np.frombuffer(
            pattern.to_bytes(byte_count, "little"), dtype="<u8"
        )
    return matrix


def mux(selector: int, data0: int, data1: int, mask: int) -> int:
    return ((~selector & data0) | (selector & data1)) & mask


def role_category(selector: int, data0: int, data1: int) -> str:
    if selector == data0 == data1:
        return "all_equal"
    if selector == data0:
        return "selector_equals_data0"
    if selector == data1:
        return "selector_equals_data1"
    if data0 == data1:
        return "data0_equals_data1"
    return "all_distinct"


def search_target(
        patterns: list[int], truth: int, row_count: int,
        prefix_word_count: int,
) -> dict[str, object]:
    matrix = word_matrix(patterns, row_count)
    truth_words = word_matrix([truth], row_count)[0]
    delta = matrix ^ truth_words
    prefix_word_count = min(prefix_word_count, matrix.shape[1])
    if prefix_word_count < 1:
        raise RuntimeError("empty mux prefix")

    prefix_delta = delta[:, :prefix_word_count]
    counts = {category: 0 for category in CATEGORIES}
    recorded: list[tuple[int, int, int, str]] = []
    prefix_data0_memberships = 0
    prefix_data1_memberships = 0
    full_data0_memberships = 0
    full_data1_memberships = 0
    started = time.monotonic()

    for selector in range(len(patterns)):
        selector_words = matrix[selector]
        selector_prefix = selector_words[:prefix_word_count]
        data0_prefix = np.flatnonzero(
            ~np.any(prefix_delta & np.bitwise_not(selector_prefix), axis=1)
        )
        data1_prefix = np.flatnonzero(
            ~np.any(prefix_delta & selector_prefix, axis=1)
        )
        prefix_data0_memberships += len(data0_prefix)
        prefix_data1_memberships += len(data1_prefix)

        if prefix_word_count < matrix.shape[1]:
            data0_indices = data0_prefix[
                ~np.any(
                    delta[data0_prefix] & np.bitwise_not(selector_words),
                    axis=1,
                )
            ]
            data1_indices = data1_prefix[
                ~np.any(delta[data1_prefix] & selector_words, axis=1)
            ]
        else:
            data0_indices = data0_prefix
            data1_indices = data1_prefix
        full_data0_memberships += len(data0_indices)
        full_data1_memberships += len(data1_indices)

        data0_set = set(map(int, data0_indices))
        data1_set = set(map(int, data1_indices))
        selector_in_data0 = int(selector in data0_set)
        selector_in_data1 = int(selector in data1_set)
        intersection = data0_set & data1_set
        all_equal = selector_in_data0 & selector_in_data1
        data0_equals_data1 = len(intersection) - all_equal
        selector_equals_data0 = (
            selector_in_data0 * (len(data1_set) - selector_in_data1)
        )
        selector_equals_data1 = (
            selector_in_data1 * (len(data0_set) - selector_in_data0)
        )
        all_distinct = (
            (len(data0_set) - selector_in_data0)
            * (len(data1_set) - selector_in_data1)
            - data0_equals_data1
        )
        local_counts = {
            "all_distinct": all_distinct,
            "selector_equals_data0": selector_equals_data0,
            "selector_equals_data1": selector_equals_data1,
            "data0_equals_data1": data0_equals_data1,
            "all_equal": all_equal,
        }
        for category, value in local_counts.items():
            counts[category] += value

        if len(recorded) < MAX_RECORDED_MATCHES:
            for data0 in data0_indices:
                for data1 in data1_indices:
                    d0 = int(data0)
                    d1 = int(data1)
                    category = role_category(selector, d0, d1)
                    recorded.append((selector, d0, d1, category))
                    if len(recorded) >= MAX_RECORDED_MATCHES:
                        break
                if len(recorded) >= MAX_RECORDED_MATCHES:
                    break

        if selector and selector % 1000 == 0:
            print(
                "mux", selector, "of", len(patterns),
                "d0", full_data0_memberships,
                "d1", full_data1_memberships,
                "programs", sum(counts.values()),
                flush=True,
            )

    exact_programs = sum(counts.values())
    return {
        "selector_checks": len(patterns),
        "data_membership_checks": 2 * len(patterns) * len(patterns),
        "prefix_word_count": prefix_word_count,
        "prefix_data0_memberships": prefix_data0_memberships,
        "prefix_data1_memberships": prefix_data1_memberships,
        "full_data0_memberships": full_data0_memberships,
        "full_data1_memberships": full_data1_memberships,
        "category_counts": counts,
        "exact_pattern_role_programs": exact_programs,
        "recorded_indices": recorded,
        "recorded_matches_truncated": exact_programs > len(recorded),
        "elapsed_seconds": time.monotonic() - started,
    }


def selftest() -> None:
    patterns = [0b000001, 0b001110, 0b110000, 0b101011, 0b011101]
    row_count = 6
    mask = (1 << row_count) - 1
    truths = [
        mux(patterns[0], patterns[2], patterns[4], mask),
        0b010101,
    ]
    for truth in truths:
        result = search_target(patterns, truth, row_count, 1)
        expected = {category: 0 for category in CATEGORIES}
        expected_indices = []
        for selector in range(len(patterns)):
            for data0 in range(len(patterns)):
                for data1 in range(len(patterns)):
                    if mux(
                            patterns[selector], patterns[data0],
                            patterns[data1], mask
                    ) != truth:
                        continue
                    category = role_category(selector, data0, data1)
                    expected[category] += 1
                    expected_indices.append(
                        (selector, data0, data1, category)
                    )
        if result["category_counts"] != expected:
            raise RuntimeError("mux selftest category mismatch")
        if result["exact_pattern_role_programs"] != len(expected_indices):
            raise RuntimeError("mux selftest count mismatch")
        if result["recorded_indices"] != expected_indices:
            raise RuntimeError("mux selftest witness mismatch")


def named_matches(
        result: dict[str, object], patterns: list[int],
        literals: dict[int, list[str]],
) -> list[dict[str, object]]:
    matches = []
    for selector, data0, data1, category in result["recorded_indices"]:
        indices = (selector, data0, data1)
        equivalent_names = [literals[patterns[index]] for index in indices]
        matches.append({
            "category": category,
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("positive_allmode", type=Path)
    parser.add_argument("control_allmode", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--prefix-words", type=int, default=64)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit("refusing to overwrite " + str(args.report))
    if args.jobs < 1 or args.prefix_words < 1:
        raise SystemExit("--jobs and --prefix-words must be positive")

    selftest()
    (source_rows, patterns, literals, carry_truth, flip_truth,
     named_feature_count, constrained_rows, h1401_feature_count,
     h1401_pattern_count) = h1535.build_wall(
         args.features, args.positive_allmode, args.control_allmode, args.jobs)
    carry_result = search_target(
        patterns, carry_truth, constrained_rows, args.prefix_words
    )
    flip_result = search_target(
        patterns, flip_truth, constrained_rows, args.prefix_words
    )

    report = {
        "schema": "fsincos-h1537-complete-three-wire-mux-v1",
        "code": {
            "script_sha256": digest(Path(__file__)),
            "dependency_sha256": {
                name: digest(Path(__file__).with_name(name))
                for name in DEPENDENCIES
            },
        },
        "inputs": {
            "features": str(args.features),
            "features_sha256": digest(args.features),
            "positive_allmode": str(args.positive_allmode),
            "positive_allmode_sha256": digest(args.positive_allmode),
            "control_allmode": str(args.control_allmode),
            "control_allmode_sha256": digest(args.control_allmode),
        },
        "source_rows": len(source_rows),
        "constrained_rows": constrained_rows,
        "neutral_rows": len(source_rows) - constrained_rows,
        "carry_ones": carry_truth.bit_count(),
        "flip_ones": flip_truth.bit_count(),
        "h1401_reproduced_universe": {
            "named_features": h1401_feature_count,
            "literal_patterns": h1401_pattern_count,
            "components": "terminal_product_state",
            "historical_report_counts_match": True,
        },
        "expanded_current_universe": {
            "named_features": named_feature_count,
            "literal_patterns": len(patterns),
            "components": "terminal_product_p5cpa_state",
            "ordered_pattern_role_programs": len(patterns) ** 3,
            "strictly_contains_h1401_named_feature_universe": True,
        },
        "search": {
            "class": "three_history_two_to_one_mux",
            "identity": (
                "selector_zero_implies_data0=target;"
                "selector_one_implies_data1=target"
            ),
            "algorithm": "quadratic_exact_masked_membership",
            "prefix_filter": "exact_subset_of_rows_no_false_negatives",
            "prefix_word_count": args.prefix_words,
            "selftest": "pass",
            "feature_jobs": args.jobs,
            "universe": "expanded_current_universe",
        },
        "physical_carry": result_for_report(
            carry_result, patterns, literals
        ),
        "incumbent_flip": result_for_report(
            flip_result, patterns, literals
        ),
        "hardware_policy": "immutable_cached_labels_only_no_x87_execution",
        "promotion": "none_without_exact_match_and_causal_provenance",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        "wrote", args.report,
        "rows", constrained_rows,
        "patterns", len(patterns),
        "ordered_programs", len(patterns) ** 3,
        "carry_exact", carry_result["exact_pattern_role_programs"],
        "flip_exact", flip_result["exact_pattern_role_programs"],
        flush=True,
    )


if __name__ == "__main__":
    main()
