#!/usr/bin/env python3
"""Exhaust three-literal majority over the immutable h1401 R59 wall.

H1535 excludes the sum output of every possible three-wire compressor over
the current named histories.  This audit tests the complementary carry bit:

    majority(a,b,c) = (a & b) | (a & c) | (b & c).

For a fixed pair a,b, rows where they agree already fix the majority output;
rows where they differ require c to equal the target.  This identity yields
an exact quadratic search.  A NumPy prefix rejects impossible pairs quickly,
but every survivor is checked over the full constrained-row vector before
the required third histories are enumerated.

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


MAX_RECORDED_MATCHES = 5000
DEPENDENCIES = (
    "h1398_branch_two_wire_gate.py",
    "h1535_complete_three_wire_xor.py",
    *h1535.DEPENDENCIES[1:],
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


def search_target(
        patterns: list[int], truth: int, row_count: int,
        prefix_word_count: int,
) -> dict[str, object]:
    """Exhaust i < j < k whose bitwise majority equals truth."""
    matrix = word_matrix(patterns, row_count)
    truth_words = word_matrix([truth], row_count)[0]
    prefix_word_count = min(prefix_word_count, matrix.shape[1])
    if prefix_word_count < 1:
        raise RuntimeError("empty majority prefix")

    direct_pattern_indices = [
        index for index, pattern in enumerate(patterns) if pattern == truth
    ]
    pair_checks = 0
    prefix_pair_survivors = 0
    full_pair_survivors = 0
    third_pattern_checks = 0
    exact_matches = 0
    recorded_indices: list[tuple[int, int, int]] = []
    started = time.monotonic()

    for left in range(len(patterns) - 2):
        middle_start = left + 1
        middle_stop = len(patterns) - 1
        pair_checks += middle_stop - middle_start
        left_prefix = matrix[left, :prefix_word_count]
        target_delta_prefix = left_prefix ^ truth_words[:prefix_word_count]
        middle_prefix = matrix[
            middle_start:middle_stop, :prefix_word_count
        ]
        agreement_error = (
            np.bitwise_not(left_prefix ^ middle_prefix)
            & target_delta_prefix
        )
        middle_indices = (
            np.flatnonzero(~np.any(agreement_error, axis=1)) + middle_start
        )
        prefix_pair_survivors += len(middle_indices)
        if not len(middle_indices):
            continue

        if prefix_word_count < matrix.shape[1]:
            middle_full = matrix[middle_indices]
            full_error = (
                np.bitwise_not(matrix[left] ^ middle_full)
                & (matrix[left] ^ truth_words)
            )
            middle_indices = middle_indices[~np.any(full_error, axis=1)]
        full_pair_survivors += len(middle_indices)

        for middle_value in middle_indices:
            middle = int(middle_value)
            disagreement = matrix[left] ^ matrix[middle]
            third_start = middle + 1
            third_pattern_checks += len(patterns) - third_start
            if third_start >= len(patterns):
                continue
            third_rows = matrix[third_start:]
            third_error = (third_rows ^ truth_words) & disagreement
            right_indices = (
                np.flatnonzero(~np.any(third_error, axis=1)) + third_start
            )
            exact_matches += len(right_indices)
            if len(recorded_indices) < MAX_RECORDED_MATCHES:
                remaining = MAX_RECORDED_MATCHES - len(recorded_indices)
                recorded_indices.extend(
                    (left, middle, int(right))
                    for right in right_indices[:remaining]
                )

        if left and left % 1000 == 0:
            print(
                "majority", left, "of", len(patterns),
                "prefix_pairs", prefix_pair_survivors,
                "full_pairs", full_pair_survivors,
                "matches", exact_matches,
                flush=True,
            )

    return {
        "pair_checks": pair_checks,
        "prefix_word_count": prefix_word_count,
        "prefix_pair_survivors": prefix_pair_survivors,
        "full_pair_survivors": full_pair_survivors,
        "third_pattern_checks": third_pattern_checks,
        "exact_matches": exact_matches,
        "direct_pattern_indices": direct_pattern_indices,
        "recorded_indices": recorded_indices,
        "recorded_matches_truncated": exact_matches > len(recorded_indices),
        "elapsed_seconds": time.monotonic() - started,
    }


def brute_majority(left: int, middle: int, right: int) -> int:
    return (left & middle) | (left & right) | (middle & right)


def selftest() -> None:
    patterns = [0b000001, 0b001110, 0b110000, 0b101011, 0b011101]
    truth = brute_majority(patterns[0], patterns[2], patterns[4])
    result = search_target(patterns, truth, 6, 1)
    expected = []
    for left in range(len(patterns)):
        for middle in range(left + 1, len(patterns)):
            for right in range(middle + 1, len(patterns)):
                if brute_majority(
                        patterns[left], patterns[middle], patterns[right]
                ) == truth:
                    expected.append((left, middle, right))
    if result["exact_matches"] != len(expected):
        raise RuntimeError("majority selftest count mismatch")
    if result["recorded_indices"] != expected:
        raise RuntimeError("majority selftest witness mismatch")


def named_matches(
        result: dict[str, object], patterns: list[int],
        literals: dict[int, list[str]],
) -> list[dict[str, object]]:
    matches = []
    for left, middle, right in result["recorded_indices"]:
        indices = (left, middle, right)
        equivalent_names = [literals[patterns[index]] for index in indices]
        matches.append({
            "representatives": [
                h1398.representative(names) for names in equivalent_names
            ],
            "equivalent_counts": [len(names) for names in equivalent_names],
        })
    return matches


def direct_names(
        result: dict[str, object], patterns: list[int],
        literals: dict[int, list[str]],
) -> list[dict[str, object]]:
    return [
        {
            "representative": h1398.representative(literals[patterns[index]]),
            "equivalent_count": len(literals[patterns[index]]),
        }
        for index in result["direct_pattern_indices"]
    ]


def result_for_report(
        result: dict[str, object], patterns: list[int],
        literals: dict[int, list[str]],
) -> dict[str, object]:
    return {
        **{
            key: value for key, value in result.items()
            if key not in ("recorded_indices", "direct_pattern_indices")
        },
        "direct_literal_matches": direct_names(result, patterns, literals),
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
        "schema": "fsincos-h1536-complete-three-wire-majority-v1",
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
            "distinct_pattern_triples": math.comb(len(patterns), 3),
            "strictly_contains_h1401_named_feature_universe": True,
        },
        "search": {
            "class": "majority_of_three_distinct_literal_patterns",
            "identity": (
                "agreement(a,b)_implies_target=a;"
                "disagreement(a,b)_implies_c=target"
            ),
            "algorithm": "quadratic_exact_pair_elimination",
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
        "triples", report["expanded_current_universe"][
            "distinct_pattern_triples"],
        "carry_exact", carry_result["exact_matches"],
        "flip_exact", flip_result["exact_matches"],
        flush=True,
    )


if __name__ == "__main__":
    main()
