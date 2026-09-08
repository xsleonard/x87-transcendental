#!/usr/bin/env python3
"""Exhaust three-literal XOR over the immutable h1401 R59 wall.

h1401 exhausts every one- and two-wire AND/OR/XOR expression over the
distinct truth histories of 6,864 named terminal, P5 tree, and P5 CPA
signals.  This audit tests the smallest physically recognizable extension:
the sum output of a three-input carry-save compressor.

Every unordered triple of distinct literal patterns is checked for equality
to both the required physical carry and the required incumbent-carry flip.
The quadratic search uses two deterministic GF(2)-linear 64-bit projections
as a necessary filter.  An exact full-width triple must have the matching
projection, so the filter cannot hide a solution; every projection candidate
is verified against the complete constrained-row bit vector.

This is a representation/circuit-class audit.  It does not establish Intel
Skylake provenance and cannot by itself promote a selector.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import multiprocessing
import os
import time
from collections import defaultdict
from pathlib import Path

import h1398_branch_two_wire_gate as h1398


MASK64 = (1 << 64) - 1
MAX_RECORDED_MATCHES = 5000
DEPENDENCIES = (
    "h1398_branch_two_wire_gate.py",
    "h1100_p5_multiplier_tree.py",
    "h1101_p5_tree_mine.py",
    "h1106_terminal_prefix_mine.py",
    "h1110_carry_gate_mine.py",
    "h1172_p5_cpa_predictor_mine.py",
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def rotl64(value: int, amount: int) -> int:
    amount &= 63
    if not amount:
        return value & MASK64
    return ((value << amount) | (value >> (64 - amount))) & MASK64


def linear_fingerprint(pattern: int) -> int:
    """Return a deterministic 128-bit map linear under bitwise XOR."""
    first = 0
    second = 0
    chunk = 0
    while pattern:
        word = pattern & MASK64
        first ^= rotl64(word, chunk)
        second ^= rotl64(word, 17 * chunk + 7)
        pattern >>= 64
        chunk += 1
    return (first << 64) | second


def selftest() -> None:
    values = [0x0, 0x1, 0x123456789abcdef0,
              (1 << 70) | 0x55, (1 << 191) | (1 << 129) | 7]
    for left in values:
        for right in values:
            if (linear_fingerprint(left ^ right) !=
                    (linear_fingerprint(left) ^ linear_fingerprint(right))):
                raise RuntimeError("fingerprint is not GF(2)-linear")

    patterns = [0b00001, 0b00110, 0b11000, 0b10101, 0b01111]
    truth = patterns[0] ^ patterns[2] ^ patterns[4]
    result = search_target(patterns, truth)
    expected = []
    for i in range(len(patterns)):
        for j in range(i + 1, len(patterns)):
            for k in range(j + 1, len(patterns)):
                if patterns[i] ^ patterns[j] ^ patterns[k] == truth:
                    expected.append((i, j, k))
    if result["exact_matches"] != len(expected):
        raise RuntimeError("three-XOR selftest count mismatch")
    if result["recorded_indices"] != expected:
        raise RuntimeError("three-XOR selftest witness mismatch")


def search_target(patterns: list[int], truth: int) -> dict[str, object]:
    """Exhaust i < j < k such that patterns[i] ^ patterns[j] ^ patterns[k]."""
    direct_pattern_indices = [
        index for index, pattern in enumerate(patterns) if pattern == truth
    ]
    fingerprints = [linear_fingerprint(pattern) for pattern in patterns]
    by_fingerprint: dict[int, list[int]] = defaultdict(list)
    for index, fingerprint in enumerate(fingerprints):
        by_fingerprint[fingerprint].append(index)

    truth_fingerprint = linear_fingerprint(truth)
    fingerprint_candidates = 0
    exact_matches = 0
    recorded_indices: list[tuple[int, int, int]] = []
    pair_checks = 0
    started = time.monotonic()
    for left in range(len(patterns) - 2):
        prefix = truth_fingerprint ^ fingerprints[left]
        for middle in range(left + 1, len(patterns) - 1):
            pair_checks += 1
            needed = prefix ^ fingerprints[middle]
            for right in by_fingerprint.get(needed, ()):
                if right <= middle:
                    continue
                fingerprint_candidates += 1
                if patterns[left] ^ patterns[middle] ^ patterns[right] != truth:
                    continue
                exact_matches += 1
                if len(recorded_indices) < MAX_RECORDED_MATCHES:
                    recorded_indices.append((left, middle, right))

    return {
        "pair_checks": pair_checks,
        "fingerprint_candidates": fingerprint_candidates,
        "exact_matches": exact_matches,
        "direct_pattern_indices": direct_pattern_indices,
        "recorded_indices": recorded_indices,
        "recorded_matches_truncated": exact_matches > len(recorded_indices),
        "elapsed_seconds": time.monotonic() - started,
    }


def accumulate_feature_chunk(
        task: tuple[int, list[dict[str, str]]],
) -> tuple[int, int, dict[str, int], tuple[str, ...]]:
    start, rows = task
    local_columns: dict[str, int] = defaultdict(int)
    schema = None
    for local_index, row in enumerate(rows):
        row_features = h1398.named_features(row)
        if schema is None:
            schema = tuple(sorted(row_features))
        elif set(row_features) != set(schema):
            raise RuntimeError("feature schema changed inside worker")
        for name, value in row_features.items():
            local_columns[name] |= value << local_index
    if schema is None:
        raise RuntimeError("empty feature worker chunk")
    return start, len(rows), dict(local_columns), schema


def build_wall(
        features_path: Path, positive_path: Path, control_path: Path, jobs: int,
) -> tuple[
        list[dict[str, str]], list[int], dict[int, list[str]], int, int, int,
        int, int, int,
]:
    positive = h1398.allmode_allowed(positive_path)
    controls = h1398.allmode_allowed(control_path)
    source_rows = h1398.read_rows(features_path)
    constrained = []
    for row in source_rows:
        allowed_delta = (positive if row["label"] == "POS" else controls)[
            row["op"]]
        state = h1398.extract_carry_state(row, allowed_delta)
        if len(state[3]) != 1:
            continue
        constrained.append((row, state))
    if not constrained:
        raise RuntimeError("no carry-constraining rows")

    columns: dict[str, int] = defaultdict(int)
    rows_only = [row for row, _ in constrained]
    chunk_size = math.ceil(len(rows_only) / jobs)
    tasks = [
        (start, rows_only[start:start + chunk_size])
        for start in range(0, len(rows_only), chunk_size)
    ]
    worker_results = []
    if jobs == 1:
        worker_results = [accumulate_feature_chunk(task) for task in tasks]
    else:
        context = multiprocessing.get_context("fork")
        with context.Pool(processes=jobs) as pool:
            for result in pool.imap_unordered(accumulate_feature_chunk, tasks):
                worker_results.append(result)
                print("feature_chunk", result[0], result[1], flush=True)
    schema = None
    for start, _, local_columns, local_schema in sorted(worker_results):
        if schema is None:
            schema = local_schema
        elif local_schema != schema:
            raise RuntimeError("feature schema changed between workers")
        for name, pattern in local_columns.items():
            columns[name] |= pattern << start

    carry_truth = 0
    flip_truth = 0
    for index, (_, state) in enumerate(constrained):
        physical = next(iter(state[3]))
        carry_truth |= physical << index
        flip_truth |= (physical ^ state[2]) << index

    columns["state.borrow"] = sum(
        state[0] << index
        for index, (_, state) in enumerate(constrained))
    columns["state.current_carry"] = sum(
        state[2] << index
        for index, (_, state) in enumerate(constrained))

    all_mask = (1 << len(constrained)) - 1
    literals: dict[int, list[str]] = defaultdict(list)
    for name, pattern in columns.items():
        literals[pattern].append(name)
        literals[pattern ^ all_mask].append("!" + name)
    h1401_columns = {
        name: pattern for name, pattern in columns.items()
        if not name.startswith("p5cpa.")
    }
    h1401_literals: dict[int, list[str]] = defaultdict(list)
    for name, pattern in h1401_columns.items():
        h1401_literals[pattern].append(name)
        h1401_literals[pattern ^ all_mask].append("!" + name)
    if len(h1401_columns) != 6864 or len(h1401_literals) != 7924:
        raise RuntimeError(
            "failed to reproduce h1401 feature/pattern counts: "
            f"{len(h1401_columns)}/{len(h1401_literals)}"
        )
    patterns = sorted(literals)
    return (source_rows, patterns, literals, carry_truth, flip_truth,
            len(columns), len(constrained), len(h1401_columns),
            len(h1401_literals))


def named_matches(
        result: dict[str, object], patterns: list[int],
        literals: dict[int, list[str]],
) -> list[dict[str, object]]:
    matches = []
    for left, middle, right in result["recorded_indices"]:
        pattern_indices = (left, middle, right)
        equivalent_names = [literals[patterns[index]]
                            for index in pattern_indices]
        representatives = [h1398.representative(names)
                           for names in equivalent_names]
        matches.append({
            "representatives": representatives,
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("positive_allmode", type=Path)
    parser.add_argument("control_allmode", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--jobs", type=int,
                        default=min(8, os.cpu_count() or 1))
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit("refusing to overwrite " + str(args.report))
    if args.jobs < 1:
        raise SystemExit("--jobs must be positive")

    selftest()
    (source_rows, patterns, literals, carry_truth, flip_truth,
     named_feature_count, constrained_rows, h1401_feature_count,
     h1401_pattern_count) = build_wall(
         args.features, args.positive_allmode, args.control_allmode, args.jobs)

    carry_result = search_target(patterns, carry_truth)
    flip_result = search_target(patterns, flip_truth)
    report = {
        "schema": "fsincos-h1535-complete-three-wire-xor-v2",
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
        "carry_ones": carry_truth.bit_count(),
        "flip_ones": flip_truth.bit_count(),
        "search": {
            "class": "xor_of_three_distinct_literal_patterns",
            "universe": "expanded_current_universe",
            "algorithm": "quadratic_exact_meet_in_the_middle",
            "filter": "two_deterministic_gf2_linear_64_bit_projections",
            "filter_completeness": (
                "necessary_only_no_false_negatives_full_vectors_verified"
            ),
            "selftest": "pass",
            "feature_jobs": args.jobs,
        },
        "physical_carry": {
            **{key: value for key, value in carry_result.items()
               if key not in ("recorded_indices", "direct_pattern_indices")},
            "direct_literal_matches": direct_names(
                carry_result, patterns, literals),
            "matches": named_matches(carry_result, patterns, literals),
        },
        "incumbent_flip": {
            **{key: value for key, value in flip_result.items()
               if key not in ("recorded_indices", "direct_pattern_indices")},
            "direct_literal_matches": direct_names(
                flip_result, patterns, literals),
            "matches": named_matches(flip_result, patterns, literals),
        },
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
