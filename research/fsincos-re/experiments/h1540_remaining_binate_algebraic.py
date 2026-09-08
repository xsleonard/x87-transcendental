#!/usr/bin/env python3
"""Exhaust NPN classes 0x06 (gated XOR) and 0x1e (XOR-of-OR).

H1539 identifies five three-input NPN classes not covered by the structural
audits.  Two have direct algebraic reductions:

    gated_xor(a,b,c) = a & (b ^ c)
    xor_or(a,b,c)    = a ^ (b | c)

For gated XOR, a must contain the target and c's projection under a is fixed
by b.  For XOR-of-OR, a is uniquely the target XOR (b OR c); a fixed 128-row
signature is only a necessary lookup filter and every candidate is checked
against the full vector.  Both target polarities are searched so the entire
NPN orbit, including output inversion, is covered.

This is a circuit-complexity exclusion audit, not physical provenance for a
selector and not an emulator promotion criterion.
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


def pair_order_count(left: int, right: int) -> int:
    return 1 if left == right else 2


def search_gated_xor(patterns: list[int], truth: int) -> dict[str, object]:
    distinguished = [
        index for index, pattern in enumerate(patterns)
        if pattern & truth == truth
    ]
    projection_builds = 0
    symmetric_input_checks = 0
    exact_unordered = 0
    exact_ordered = 0
    recorded = []
    started = time.monotonic()
    for a_index in distinguished:
        a = patterns[a_index]
        projected: dict[int, list[int]] = defaultdict(list)
        for index, pattern in enumerate(patterns):
            projected[pattern & a].append(index)
            projection_builds += 1
        for b_index, b in enumerate(patterns):
            required = (b ^ truth) & a
            candidates = projected.get(required, ())
            symmetric_input_checks += len(candidates)
            for c_index in candidates:
                if c_index < b_index:
                    continue
                if a & (b ^ patterns[c_index]) != truth:
                    raise RuntimeError("gated-XOR projection admitted false match")
                exact_unordered += 1
                exact_ordered += pair_order_count(b_index, c_index)
                if len(recorded) < MAX_RECORDED_MATCHES:
                    recorded.append((a_index, b_index, c_index))
    return {
        "distinguished_candidates": len(distinguished),
        "projection_builds": projection_builds,
        "projection_candidate_checks": symmetric_input_checks,
        "exact_unordered_symmetric_pairs": exact_unordered,
        "exact_ordered_pattern_roles": exact_ordered,
        "recorded_indices": recorded,
        "recorded_matches_truncated": exact_unordered > len(recorded),
        "elapsed_seconds": time.monotonic() - started,
    }


def search_xor_or(
        patterns: list[int], truth: int, row_count: int,
) -> dict[str, object]:
    sample_width = min(SAMPLE_BITS, row_count)
    sample_mask = (1 << sample_width) - 1
    samples = [pattern & sample_mask for pattern in patterns]
    truth_sample = truth & sample_mask
    by_sample: dict[int, list[int]] = defaultdict(list)
    for index, value in enumerate(samples):
        by_sample[value].append(index)

    symmetric_pair_checks = 0
    sample_candidates = 0
    full_candidate_checks = 0
    exact_unordered = 0
    exact_ordered = 0
    recorded = []
    started = time.monotonic()
    for b_index, b_sample in enumerate(samples):
        b = patterns[b_index]
        for c_index in range(b_index, len(patterns)):
            symmetric_pair_checks += 1
            required_sample = truth_sample ^ (b_sample | samples[c_index])
            candidates = by_sample.get(required_sample, ())
            sample_candidates += len(candidates)
            if not candidates:
                continue
            required = truth ^ (b | patterns[c_index])
            for a_index in candidates:
                full_candidate_checks += 1
                if patterns[a_index] != required:
                    continue
                exact_unordered += 1
                exact_ordered += pair_order_count(b_index, c_index)
                if len(recorded) < MAX_RECORDED_MATCHES:
                    recorded.append((a_index, b_index, c_index))
    return {
        "sample_bits": sample_width,
        "symmetric_pair_checks": symmetric_pair_checks,
        "sample_candidates": sample_candidates,
        "full_candidate_checks": full_candidate_checks,
        "exact_unordered_symmetric_pairs": exact_unordered,
        "exact_ordered_pattern_roles": exact_ordered,
        "recorded_indices": recorded,
        "recorded_matches_truncated": exact_unordered > len(recorded),
        "elapsed_seconds": time.monotonic() - started,
    }


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
        gated = search_gated_xor(patterns, target)
        xor_or = search_xor_or(patterns, target, row_count)
        report[polarity] = {
            "target_ones": target.bit_count(),
            "gated_xor": result_for_report(gated, patterns, literals),
            "xor_or": result_for_report(xor_or, patterns, literals),
        }
    return report


def selftest() -> None:
    patterns = [0b000001, 0b001110, 0b110000, 0b101011, 0b011101]
    row_count = 6
    truths = [
        patterns[0] & (patterns[2] ^ patterns[4]),
        patterns[0] ^ (patterns[2] | patterns[4]),
        0b010101,
    ]
    for truth in truths:
        gated = search_gated_xor(patterns, truth)
        xor_or = search_xor_or(patterns, truth, row_count)
        for shape, result in (("gated", gated), ("xor_or", xor_or)):
            unordered = 0
            ordered = 0
            for a_index, a in enumerate(patterns):
                for b_index, b in enumerate(patterns):
                    for c_index in range(b_index, len(patterns)):
                        c = patterns[c_index]
                        value = (a & (b ^ c) if shape == "gated"
                                 else a ^ (b | c))
                        if value != truth:
                            continue
                        unordered += 1
                        ordered += pair_order_count(b_index, c_index)
            if result["exact_unordered_symmetric_pairs"] != unordered:
                raise RuntimeError(f"{shape} selftest unordered mismatch")
            if result["exact_ordered_pattern_roles"] != ordered:
                raise RuntimeError(f"{shape} selftest ordered mismatch")


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
        "schema": "fsincos-h1540-remaining-binate-algebraic-v1",
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
            "npn_classes": ["06_gated_xor", "1e_xor_or"],
            "both_output_polarities": True,
            "input_polarities": "literal_universe_contains_both",
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
    summary = {}
    for target_name in ("physical_carry", "incumbent_flip"):
        summary[target_name] = {
            polarity: {
                shape: report[target_name][polarity][shape][
                    "exact_ordered_pattern_roles"
                ]
                for shape in ("gated_xor", "xor_or")
            }
            for polarity in ("direct", "output_inverted")
        }
    print("wrote", args.report, summary, flush=True)


if __name__ == "__main__":
    main()
