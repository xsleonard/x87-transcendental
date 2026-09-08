#!/usr/bin/env python3
"""Exhaust the irreducible three-input unate standard-cell basis.

With complemented input literals, every unate Boolean function of three
variables is represented by one of the 20 monotone functions.  Constants,
projections, two-input AND/OR, and majority are reducible or already covered.
The remaining irreducible shapes are:

    AND3(a,b,c)
    OR3(a,b,c)
    AO21(a,b,c) = a & (b | c)
    OA21(a,b,c) = a | (b & c)

This audit exhausts those shapes, including repeated input histories.  The
three-way AND/OR searches are exact three-set-cover problems.  Small sampled
row signatures only prefilter possible third sets; every survivor is checked
against the full constrained-row vector.  AO21/OA21 reduce exactly to
two-set covers after fixing the distinguished input.

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

import h1398_branch_two_wire_gate as h1398
import h1535_complete_three_wire_xor as h1535


MAX_RECORDED_MATCHES = 500
SAMPLE_BITS = 128
SAMPLE_BLOCK_BITS = 16
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


def set_positions(value: int) -> list[int]:
    positions = []
    while value:
        low = value & -value
        positions.append(low.bit_length() - 1)
        value ^= low
    return positions


def sampled_blocks(universe: int) -> list[tuple[int, ...]]:
    positions = set_positions(universe)
    if len(positions) > SAMPLE_BITS:
        positions = [
            positions[(index * len(positions)) // SAMPLE_BITS]
            for index in range(SAMPLE_BITS)
        ]
    return [
        tuple(positions[start:start + SAMPLE_BLOCK_BITS])
        for start in range(0, len(positions), SAMPLE_BLOCK_BITS)
    ]


def signature(value: int, positions: tuple[int, ...]) -> int:
    result = 0
    for output_bit, input_bit in enumerate(positions):
        result |= ((value >> input_bit) & 1) << output_bit
    return result


def superset_table(
        signatures: list[int], width: int,
) -> list[int]:
    size = 1 << width
    table = [0] * size
    for index, value in enumerate(signatures):
        table[value] |= 1 << index
    for bit in range(width):
        flag = 1 << bit
        for value in range(size):
            if not value & flag:
                table[value] |= table[value | flag]
    return table


def permutation_count(left: int, middle: int, right: int) -> int:
    if left == right:
        return 1
    if left == middle or middle == right:
        return 3
    return 6


def search_three_union_cover(
        candidate_indices: list[int], covers: list[int], universe: int,
) -> dict[str, object]:
    """Find i <= j <= k whose three covers union to universe."""
    blocks = sampled_blocks(universe)
    block_signatures = [
        [signature(cover, block) for cover in covers]
        for block in blocks
    ]
    tables = [
        superset_table(values, len(block))
        for values, block in zip(block_signatures, blocks)
    ]
    full_signatures = [(1 << len(block)) - 1 for block in blocks]
    all_candidates = (1 << len(covers)) - 1
    pair_checks = 0
    prefix_third_candidates = 0
    full_third_checks = 0
    unordered_matches = 0
    ordered_matches = 0
    recorded: list[tuple[int, int, int]] = []
    started = time.monotonic()

    for left in range(len(covers)):
        for middle in range(left, len(covers)):
            pair_checks += 1
            allowed = all_candidates & ~((1 << middle) - 1)
            for block_index, table in enumerate(tables):
                missing = full_signatures[block_index] ^ (
                    block_signatures[block_index][left]
                    | block_signatures[block_index][middle]
                )
                allowed &= table[missing]
                if not allowed:
                    break
            prefix_third_candidates += allowed.bit_count()
            pair_cover = covers[left] | covers[middle]
            while allowed:
                low = allowed & -allowed
                right = low.bit_length() - 1
                allowed ^= low
                full_third_checks += 1
                if pair_cover | covers[right] != universe:
                    continue
                unordered_matches += 1
                ordered_matches += permutation_count(left, middle, right)
                if len(recorded) < MAX_RECORDED_MATCHES:
                    recorded.append((
                        candidate_indices[left],
                        candidate_indices[middle],
                        candidate_indices[right],
                    ))

    return {
        "candidate_patterns": len(covers),
        "unordered_candidate_multisets": math.comb(len(covers) + 2, 3),
        "sampled_universe_bits": sum(map(len, blocks)),
        "sample_blocks": len(blocks),
        "pair_checks": pair_checks,
        "prefix_third_candidates": prefix_third_candidates,
        "full_third_checks": full_third_checks,
        "exact_unordered_pattern_multisets": unordered_matches,
        "exact_ordered_pattern_roles": ordered_matches,
        "recorded_indices": recorded,
        "recorded_matches_truncated": unordered_matches > len(recorded),
        "elapsed_seconds": time.monotonic() - started,
    }


def pair_order_count(left: int, right: int) -> int:
    return 1 if left == right else 2


def search_ao21(patterns: list[int], truth: int, all_mask: int) -> dict:
    distinguished = [
        index for index, pattern in enumerate(patterns)
        if pattern & truth == truth
    ]
    pair_checks = 0
    unordered_matches = 0
    ordered_matches = 0
    recorded = []
    candidate_min = None
    candidate_max = 0
    started = time.monotonic()
    for a_index in distinguished:
        a = patterns[a_index]
        forbidden = a & (all_mask ^ truth)
        candidates = [
            index for index, pattern in enumerate(patterns)
            if not pattern & forbidden
        ]
        candidate_min = (len(candidates) if candidate_min is None
                         else min(candidate_min, len(candidates)))
        candidate_max = max(candidate_max, len(candidates))
        for left_pos, b_index in enumerate(candidates):
            b = patterns[b_index]
            for c_index in candidates[left_pos:]:
                pair_checks += 1
                if a & (b | patterns[c_index]) != truth:
                    continue
                unordered_matches += 1
                ordered_matches += pair_order_count(b_index, c_index)
                if len(recorded) < MAX_RECORDED_MATCHES:
                    recorded.append((a_index, b_index, c_index))
    return {
        "distinguished_candidates": len(distinguished),
        "symmetric_candidate_min": candidate_min or 0,
        "symmetric_candidate_max": candidate_max,
        "pair_checks": pair_checks,
        "exact_unordered_symmetric_pairs": unordered_matches,
        "exact_ordered_pattern_roles": ordered_matches,
        "recorded_indices": recorded,
        "recorded_matches_truncated": unordered_matches > len(recorded),
        "elapsed_seconds": time.monotonic() - started,
    }


def search_oa21(patterns: list[int], truth: int, all_mask: int) -> dict:
    distinguished = [
        index for index, pattern in enumerate(patterns)
        if pattern & (all_mask ^ truth) == 0
    ]
    pair_checks = 0
    unordered_matches = 0
    ordered_matches = 0
    recorded = []
    candidate_min = None
    candidate_max = 0
    started = time.monotonic()
    for a_index in distinguished:
        a = patterns[a_index]
        required = truth & ~a
        candidates = [
            index for index, pattern in enumerate(patterns)
            if pattern & required == required
        ]
        candidate_min = (len(candidates) if candidate_min is None
                         else min(candidate_min, len(candidates)))
        candidate_max = max(candidate_max, len(candidates))
        for left_pos, b_index in enumerate(candidates):
            b = patterns[b_index]
            for c_index in candidates[left_pos:]:
                pair_checks += 1
                if a | (b & patterns[c_index]) != truth:
                    continue
                unordered_matches += 1
                ordered_matches += pair_order_count(b_index, c_index)
                if len(recorded) < MAX_RECORDED_MATCHES:
                    recorded.append((a_index, b_index, c_index))
    return {
        "distinguished_candidates": len(distinguished),
        "symmetric_candidate_min": candidate_min or 0,
        "symmetric_candidate_max": candidate_max,
        "pair_checks": pair_checks,
        "exact_unordered_symmetric_pairs": unordered_matches,
        "exact_ordered_pattern_roles": ordered_matches,
        "recorded_indices": recorded,
        "recorded_matches_truncated": unordered_matches > len(recorded),
        "elapsed_seconds": time.monotonic() - started,
    }


def search_target(
        patterns: list[int], truth: int, row_count: int,
) -> dict[str, dict]:
    all_mask = (1 << row_count) - 1
    zero_universe = all_mask ^ truth
    and_indices = [
        index for index, pattern in enumerate(patterns)
        if pattern & truth == truth
    ]
    and_covers = [zero_universe & ~patterns[index] for index in and_indices]
    or_indices = [
        index for index, pattern in enumerate(patterns)
        if pattern & zero_universe == 0
    ]
    or_covers = [patterns[index] for index in or_indices]
    return {
        "and3": search_three_union_cover(
            and_indices, and_covers, zero_universe
        ),
        "or3": search_three_union_cover(or_indices, or_covers, truth),
        "ao21": search_ao21(patterns, truth, all_mask),
        "oa21": search_oa21(patterns, truth, all_mask),
    }


def evaluate(shape: str, a: int, b: int, c: int) -> int:
    if shape == "and3":
        return a & b & c
    if shape == "or3":
        return a | b | c
    if shape == "ao21":
        return a & (b | c)
    if shape == "oa21":
        return a | (b & c)
    raise ValueError(shape)


def selftest() -> None:
    patterns = [0b000001, 0b001110, 0b110000, 0b101011, 0b011101]
    row_count = 6
    truths = [
        evaluate("and3", patterns[0], patterns[2], patterns[4]),
        evaluate("or3", patterns[0], patterns[2], patterns[4]),
        evaluate("ao21", patterns[0], patterns[2], patterns[4]),
        evaluate("oa21", patterns[0], patterns[2], patterns[4]),
        0b010101,
    ]
    for truth in truths:
        result = search_target(patterns, truth, row_count)
        for shape in ("and3", "or3", "ao21", "oa21"):
            unordered = 0
            ordered = 0
            if shape in ("and3", "or3"):
                for left in range(len(patterns)):
                    for middle in range(left, len(patterns)):
                        for right in range(middle, len(patterns)):
                            if evaluate(
                                    shape, patterns[left], patterns[middle],
                                    patterns[right]
                            ) != truth:
                                continue
                            unordered += 1
                            ordered += permutation_count(left, middle, right)
                got_unordered = result[shape][
                    "exact_unordered_pattern_multisets"
                ]
            else:
                for a_index in range(len(patterns)):
                    for b_index in range(len(patterns)):
                        for c_index in range(b_index, len(patterns)):
                            if evaluate(
                                    shape, patterns[a_index], patterns[b_index],
                                    patterns[c_index]
                            ) != truth:
                                continue
                            unordered += 1
                            ordered += pair_order_count(b_index, c_index)
                got_unordered = result[shape][
                    "exact_unordered_symmetric_pairs"
                ]
            if got_unordered != unordered:
                raise RuntimeError(f"{shape} selftest unordered mismatch")
            if result[shape]["exact_ordered_pattern_roles"] != ordered:
                raise RuntimeError(f"{shape} selftest ordered mismatch")


def named_matches(
        result: dict, patterns: list[int], literals: dict[int, list[str]],
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
        result: dict, patterns: list[int], literals: dict[int, list[str]],
) -> dict:
    return {
        **{key: value for key, value in result.items()
           if key != "recorded_indices"},
        "matches": named_matches(result, patterns, literals),
    }


def target_for_report(
        result: dict[str, dict], patterns: list[int],
        literals: dict[int, list[str]],
) -> dict[str, dict]:
    return {
        shape: result_for_report(values, patterns, literals)
        for shape, values in result.items()
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("positive_allmode", type=Path)
    parser.add_argument("control_allmode", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit("refusing to overwrite " + str(args.report))
    if args.jobs < 1:
        raise SystemExit("--jobs must be positive")

    selftest()
    (source_rows, patterns, literals, carry_truth, flip_truth,
     named_feature_count, constrained_rows, h1401_feature_count,
     h1401_pattern_count) = h1535.build_wall(
         args.features, args.positive_allmode, args.control_allmode, args.jobs)
    carry_result = search_target(patterns, carry_truth, constrained_rows)
    flip_result = search_target(patterns, flip_truth, constrained_rows)

    report = {
        "schema": "fsincos-h1538-complete-three-input-unate-v1",
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
            "strictly_contains_h1401_named_feature_universe": True,
        },
        "search": {
            "class": "irreducible_three_input_unate_standard_cell_basis",
            "shapes": ["and3", "or3", "ao21", "oa21"],
            "coverage": (
                "with_complemented_literals_plus_prior_majority_covers_all_"
                "twenty_three_variable_monotone_functions_and_therefore_"
                "all_three_variable_unate_functions"
            ),
            "algorithm": "exact_set_cover_and_distinguished_input_reduction",
            "sample_filter": "necessary_only_no_false_negatives",
            "sample_bits": SAMPLE_BITS,
            "selftest": "pass",
            "feature_jobs": args.jobs,
            "universe": "expanded_current_universe",
        },
        "physical_carry": target_for_report(
            carry_result, patterns, literals
        ),
        "incumbent_flip": target_for_report(
            flip_result, patterns, literals
        ),
        "hardware_policy": "immutable_cached_labels_only_no_x87_execution",
        "promotion": "none_without_exact_match_and_causal_provenance",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        "wrote", args.report,
        "carry", {shape: values["exact_ordered_pattern_roles"]
                  for shape, values in carry_result.items()},
        "flip", {shape: values["exact_ordered_pattern_roles"]
                 for shape, values in flip_result.items()},
        flush=True,
    )


if __name__ == "__main__":
    main()
