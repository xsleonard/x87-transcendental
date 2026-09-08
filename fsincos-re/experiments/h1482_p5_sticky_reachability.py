#!/usr/bin/env python3
"""Audit documented P5 sticky state and R1475 causal reachability.

US 5,195,051 places Booth generation in X1, the four-level CSA tree and
sticky generation in X2, and final carry propagation/rounding in WF.  Its
incorporated sticky patent, US 5,260,889, derives two precision-dependent
sticky candidates from the sum of the operands' trailing-zero counts and
selects between them with product overflow.

This audit tests that entire documented two-threshold/overflow grammar against
the cached H1472 labels.  It also establishes whether the varying R1475
function can be a direct bit of the exact right product.  H1476 rows carry only
software function values and are used for the latter function comparison.
No x87 instruction or unopened hardware label is used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from h1479_r1475_topology_isomorphism import (
    replay_anchors,
    replay_disjoint,
    replay_h1472,
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def trailing_zeros(value: int) -> int:
    if value <= 0:
        raise ValueError("trailing-zero encoder requires a positive operand")
    return (value & -value).bit_length() - 1


def product_state(record: dict[str, object]) -> dict[str, object]:
    row = record["row"]
    multiplicand = int(row["tc_f4_sig"], 16)
    multiplier = int(row["tc_rf_sig"], 16)
    product = multiplicand * multiplier
    cut = product.bit_length() - 67
    left_zeros = trailing_zeros(multiplicand)
    right_zeros = trailing_zeros(multiplier)
    zero_sum = left_zeros + right_zeros
    if trailing_zeros(product) != zero_sum:
        raise RuntimeError("binary trailing-zero identity failed")
    return {
        "multiplicand": multiplicand,
        "multiplier": multiplier,
        "product": product,
        "cut": cut,
        "overflow": int(cut == 64),
        "multiplicand_trailing_zeros": left_zeros,
        "multiplier_trailing_zeros": right_zeros,
        "trailing_zero_sum": zero_sum,
        "value": int(record["value"]),
        "name": record["name"],
        "provenance": record["provenance"],
    }


def fixed_relative_runs(states: list[dict[str, object]]):
    fixed = []
    for offset in range(-64, 67):
        values = set()
        for state in states:
            position = int(state["cut"]) + offset
            value = ((int(state["product"]) >> position) & 1
                     if position >= 0 else 0)
            values.add(value)
        if len(values) == 1:
            fixed.append((offset, next(iter(values))))
    runs = []
    for offset, value in fixed:
        if not runs or offset != runs[-1][-1][0] + 1:
            runs.append([])
        runs[-1].append((offset, value))
    return [
        {
            "first_offset": run[0][0],
            "last_offset": run[-1][0],
            "bits_low_to_high": "".join(str(value) for _, value in run),
            "length": len(run),
        }
        for run in runs
    ]


def exact_product_bit_aliases(states: list[dict[str, object]]):
    truth = "".join(str(state["value"]) for state in states)
    aliases = []
    for coordinate, positions in (
            ("absolute", range(0, 131)),
            ("cut_relative", range(-80, 67))):
        for position in positions:
            pattern = ""
            for state in states:
                actual = (position if coordinate == "absolute"
                          else int(state["cut"]) + position)
                value = ((int(state["product"]) >> actual) & 1
                         if actual >= 0 else 0)
                pattern += str(value)
            if pattern == truth:
                aliases.append({
                    "coordinate": coordinate,
                    "position": position,
                    "complemented": False,
                })
            complement = "".join("1" if bit == "0" else "0" for bit in pattern)
            if complement == truth:
                aliases.append({
                    "coordinate": coordinate,
                    "position": position,
                    "complemented": True,
                })
    return aliases


def sticky_threshold_audit(states: list[dict[str, object]]):
    # 0..132 covers every possible trailing-zero count of a nonzero 131-bit
    # product plus both constant endpoint predicates.  Each pre-sticky may
    # independently use either comparison orientation, and either overflow
    # mux polarity is admitted as an OCR/documentation control.
    best_error = len(states) + 1
    best_count = 0
    best_examples = []
    exact = []
    candidates = 0
    for invert_a in (0, 1):
        for invert_v in (0, 1):
            for swap_mux in (0, 1):
                for threshold_a in range(133):
                    pre_a = [
                        int(int(state["trailing_zero_sum"]) < threshold_a)
                        ^ invert_a
                        for state in states
                    ]
                    for threshold_v in range(133):
                        candidates += 1
                        prediction = []
                        for index, state in enumerate(states):
                            pre_v = (
                                int(int(state["trailing_zero_sum"]) < threshold_v)
                                ^ invert_v
                            )
                            overflow = int(state["overflow"])
                            selected = (pre_v if overflow else pre_a[index])
                            if swap_mux:
                                selected = pre_a[index] if overflow else pre_v
                            prediction.append(selected)
                        errors = sum(
                            predicted != int(state["value"])
                            for predicted, state in zip(prediction, states)
                        )
                        item = {
                            "errors": errors,
                            "invert_a": invert_a,
                            "invert_v": invert_v,
                            "swap_overflow_mux": swap_mux,
                            "threshold_a": threshold_a,
                            "threshold_v": threshold_v,
                        }
                        if errors == 0:
                            exact.append(item)
                        if errors < best_error:
                            best_error = errors
                            best_count = 1
                            best_examples = [item]
                        elif errors == best_error:
                            best_count += 1
                            if len(best_examples) < 16:
                                best_examples.append(item)
    return {
        "candidate_laws": candidates,
        "exact_laws": exact,
        "best_errors": best_error,
        "best_law_count": best_count,
        "best_examples": best_examples,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("h1472_score", type=Path)
    parser.add_argument("h1476_bank", type=Path)
    parser.add_argument("p5_multiplier_patent", type=Path)
    parser.add_argument("p5_sticky_patent", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    labeled_records = replay_h1472(args.model, args.h1472_score)
    labeled_records.extend(replay_anchors(args.model))
    disjoint_records = replay_disjoint(args.model, args.h1476_bank)
    labeled = [product_state(record) for record in labeled_records]
    disjoint = [product_state(record) for record in disjoint_records]
    combined = labeled + disjoint
    if len(labeled) != 18 or len(disjoint) != 22:
        raise RuntimeError("H1472/H1476 row census changed")

    label_truth = "".join(str(state["value"]) for state in labeled)
    if label_truth != "000101010001111101":
        raise RuntimeError("cached label order or values changed")
    combined_truth = "".join(str(state["value"]) for state in combined)
    fixed_runs = fixed_relative_runs(combined)
    longest = max(fixed_runs, key=lambda run: run["length"])
    if longest != {
        "first_offset": -17,
        "last_offset": 7,
        "bits_low_to_high": "1010101010101010111000000",
        "length": 25,
    }:
        raise RuntimeError(f"exact boundary plateau changed: {longest}")

    product_aliases = exact_product_bit_aliases(combined)
    if product_aliases:
        raise RuntimeError("R1475 acquired an exact-product-bit alias")
    threshold = sticky_threshold_audit(labeled)
    if threshold["exact_laws"] or threshold["best_errors"] != 5:
        raise RuntimeError("documented sticky threshold result changed")

    # US5260889 lists extended-precision constants H46 and H45 for its two
    # candidate stickies.  Every row is far below both thresholds, so the two
    # pre-stickies are equal.  Either possible interpretation of the scanned
    # comparator polarity is constant and misses half the 9/9 labels.
    literal_constants = (0x46, 0x45)
    if max(int(state["trailing_zero_sum"]) for state in labeled) >= min(literal_constants):
        raise RuntimeError("literal PC64 sticky stopped being constant")

    report = {
        "experiment": "h1482_p5_sticky_reachability",
        "status": "DOCUMENTED_STICKY_AND_EXACT_VALUE_ROUTES_FALSIFIED",
        "hardware_policy": (
            "cached_h1472_and_prior_anchor_labels_only; h1476 supplies "
            "software function values; no_x87_execution"
        ),
        "labeled_rows": len(labeled),
        "labeled_merge_ones": label_truth.count("1"),
        "labeled_merge_zeros": label_truth.count("0"),
        "disjoint_function_rows": len(disjoint),
        "combined_rows": len(combined),
        "combined_function_ones": combined_truth.count("1"),
        "right_product_cut_counts": dict(sorted(Counter(
            int(state["cut"]) for state in combined).items()
        )),
        "trailing_zero_sum": {
            "labeled_min": min(int(state["trailing_zero_sum"]) for state in labeled),
            "labeled_max": max(int(state["trailing_zero_sum"]) for state in labeled),
            "combined_min": min(int(state["trailing_zero_sum"]) for state in combined),
            "combined_max": max(int(state["trailing_zero_sum"]) for state in combined),
            "labeled_counts": dict(sorted(Counter(
                int(state["trailing_zero_sum"]) for state in labeled).items()
            )),
            "binary_product_identity_verified_rows": len(combined),
        },
        "literal_pc64_sticky": {
            "patent_constants_hex": ["0x46", "0x45"],
            "candidate_stickies_equal_on_all_labeled_rows": True,
            "selected_sticky_is_constant": True,
            "errors_for_either_constant_polarity": 9,
        },
        "generalized_documented_sticky_grammar": threshold,
        "exact_product_boundary": {
            "fixed_relative_runs": fixed_runs,
            "longest_fixed_run": longest,
            "exact_single_bit_aliases_with_complements": product_aliases,
            "interpretation": (
                "The selector varies while a 25-bit exact-product window from "
                "cut-17 through cut+7 is identical on all forty rows. It is "
                "therefore not a direct boundary-value bit."
            ),
        },
        "pipeline_reachability": {
            "source_summary": (
                "US5195051 places partial-product generation in X1, four-level "
                "CSA reduction and sticky generation in X2, and final carry "
                "propagation/rounding in WF. US5260889 exposes trailing-zero "
                "sum, two sticky comparisons, overflow selection, and the "
                "selected sticky."
            ),
            "r1475_wires_stage": "X2_CSA_internal",
            "r1475_wires_documented_as_wf_latched": False,
            "r1475_same_cycle_x2_gate_possible": True,
            "r1475_late_selector_requires_undocumented_state": True,
            "interpretation": (
                "R1475 is causally possible only as combinational X2 control "
                "or through an undocumented latch/sideband. The documented "
                "sticky carrier cannot encode the observed split."
            ),
        },
        "claim_boundary": (
            "This closes the documented P5 sticky/overflow carrier and direct "
            "exact-product-bit interpretations. It neither proves nor "
            "falsifies a Skylake-specific X2 control gate or hidden latch. "
            "R1475 remains label-selected and H1477 remains unopened."
        ),
        "emulator_change": "none",
        "paper_change": "none",
        "sha256": {
            "model": digest(args.model),
            "h1472_score": digest(args.h1472_score),
            "h1476_bank": digest(args.h1476_bank),
            "p5_multiplier_patent": digest(args.p5_multiplier_patent),
            "p5_sticky_patent": digest(args.p5_sticky_patent),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps({
        "output": str(args.output),
        "labeled_rows": len(labeled),
        "sticky_exact_laws": len(threshold["exact_laws"]),
        "sticky_best_errors": threshold["best_errors"],
        "exact_product_bit_aliases": len(product_aliases),
        "fixed_boundary_window": [
            longest["first_offset"], longest["last_offset"]
        ],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
