#!/usr/bin/env python3
"""Test whether the H1475 XOR is a canonical P5-tree signal in disguise.

H1475 selected a two-wire XOR from eighteen cached hardware labels.  Both
inputs are real wires in the public P5 multiplier transcription, but that
alone does not make their XOR a signal produced by the physical tree.  This
audit therefore asks two narrower, reproducible questions:

* is the analogous XOR stable under arithmetic-isomorphic compressor input
  choices; and
* does any single node/CPA signal in the bounded H1400 P5 representation
  family equal the XOR on both the labeled rows and a disjoint exact-lattice
  bank?

The disjoint rows carry no hardware truth here.  Their H1475 values are used
only as function values: one disagreement is enough to disprove an alleged
isomorphism.  This script executes the software model with diagnostic dumps;
it never executes an x87 instruction or opens H1477.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from h1210_stagea_residual_reframe import parse_dump, run
from h1400_p5_representation_audit import (
    TREE_MASK,
    TreeConfig,
    csa3,
    input_permutation,
    physical_inputs,
    tree_variants,
)


MODES = ("rn", "rd", "ru")
ANCHORS = (
    ("d0d0", "rd", "3ffc d0d000000cc0b3f8", 0),
    ("d800", "ru", "3ffc d80000000b15da62", 1),
)
NODE_OFFSETS = range(-8, 5)
FINAL_OFFSETS = range(-32, 17)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def normalized_operand(text: str) -> str:
    return text.lower().replace(":", " ")


def replay_h1472(model: Path, score: Path) -> list[dict[str, object]]:
    with score.open(newline="") as source:
        source_rows = list(csv.DictReader(source, delimiter="\t"))
    if len(source_rows) != 16:
        raise RuntimeError(f"expected sixteen H1472 rows, got {len(source_rows)}")
    if Counter(row["endpoint"] for row in source_rows) != {
            "incumbent": 8, "r1382": 8}:
        raise RuntimeError("H1472 endpoint split changed")

    result = []
    for mode in MODES:
        selected = [row for row in source_rows if row["mode"] == mode]
        operands = [normalized_operand(row["operand"]) for row in selected]
        _, stderr = run(model, mode, operands, dump=True)
        for source_row, dump in zip(selected, parse_dump(stderr, operands)):
            result.append({
                "name": source_row["case_id"],
                "mode": mode,
                "operand": normalized_operand(source_row["operand"]),
                "value": int(source_row["endpoint"] == "incumbent"),
                "row": dump,
                "provenance": "h1472_cached_hardware_label",
            })
    return result


def replay_anchors(model: Path) -> list[dict[str, object]]:
    result = []
    for name, mode, operand, value in ANCHORS:
        _, stderr = run(model, mode, [operand], dump=True)
        result.append({
            "name": name,
            "mode": mode,
            "operand": operand,
            "value": value,
            "row": parse_dump(stderr, [operand])[0],
            "provenance": "previously_established_hardware_anchor",
        })
    return result


def replay_disjoint(model: Path, bank: Path) -> list[dict[str, object]]:
    report = json.loads(bank.read_text())
    source_rows = report["all_endpoint_visible"]
    if len(source_rows) != 22:
        raise RuntimeError(f"expected 22 H1476 rows, got {len(source_rows)}")
    result = []
    for mode in MODES:
        selected = [row for row in source_rows if row["mode"] == mode]
        operands = [normalized_operand(row["operand"]) for row in selected]
        _, stderr = run(model, mode, operands, dump=True)
        for source_row, dump in zip(selected, parse_dump(stderr, operands)):
            result.append({
                "name": source_row["sig"],
                "mode": mode,
                "operand": normalized_operand(source_row["operand"]),
                "value": int(source_row["leading_merge"]),
                "row": dump,
                "provenance": "h1476_disjoint_software_function_value",
            })
    return result


def trace_tree(row: dict[str, str], config: TreeConfig):
    multiplicand = int(row["tc_f4_sig"], 16)
    multiplier = int(row["tc_rf_sig"], 16)
    product = multiplicand * multiplier
    cut = product.bit_length() - 67
    raw_inputs, _ = physical_inputs(
        multiplicand, multiplier, config.correction)
    mask = (1 << config.stage_width) - 1
    ordered = [
        raw_inputs[index] & TREE_MASK
        for index in input_permutation(config.input_order)
    ]
    nodes: dict[str, tuple[int, int, int, int]] = {}

    def compress(name: str, wires, d_slot: int):
        inputs = list(wires)
        distinguished = inputs.pop(d_slot)
        first_sum, first_carry = csa3(*inputs, mask=mask)
        out_sum, out_carry = csa3(
            distinguished, first_sum, first_carry, mask=mask)
        nodes[name] = out_sum, out_carry, first_sum, first_carry
        return out_sum, out_carry

    level1 = [
        compress(
            f"l1_{index}", ordered[4 * index:4 * index + 4],
            config.d_slots[0])
        for index in range(6)
    ]
    level2 = [
        compress(
            f"l2_{index}", level1[left] + level1[right],
            config.d_slots[1])
        for index, (left, right) in enumerate(config.pairing)
    ]
    remaining = [index for index in range(3) if index != config.hold]
    level3 = compress(
        "l3_0", level2[remaining[0]] + level2[remaining[1]],
        config.d_slots[2])
    final = compress(
        "l4_0", level3 + level2[config.hold], config.d_slots[3])
    if config.stage_width >= 131:
        arithmetic = (final[0] + final[1]) & ((1 << 131) - 1)
        if arithmetic != product & ((1 << 131) - 1):
            raise RuntimeError("arithmetic-exact tree stopped reconstructing product")
    return nodes, cut, final


def analogous_xor(row: dict[str, str], correction: str, d1: int, d2: int) -> int:
    config = TreeConfig(correction=correction, d_slots=(d1, d2, 0, 0))
    nodes, cut, _ = trace_tree(row, config)
    high_group_sum = (nodes["l1_4"][0] >> cut) & 1
    preceding_group_carry = (nodes["l2_1"][1] >> (cut - 3)) & 1
    return high_group_sum ^ preceding_group_carry


def tree_features(row: dict[str, str], config: TreeConfig) -> dict[str, int]:
    nodes, cut, (final_sum, final_carry) = trace_tree(row, config)
    values = {}
    vector_names = ("sum", "carry", "first_sum", "first_carry")
    for node_name, vectors in nodes.items():
        for vector_name, vector in zip(vector_names, vectors):
            for offset in NODE_OFFSETS:
                values[f"{node_name}.{vector_name}.{offset:+d}"] = (
                    vector >> (cut + offset)) & 1

    carry = 0
    carries = []
    for position in range(cut + max(FINAL_OFFSETS) + 1):
        carries.append(carry)
        left = (final_sum >> position) & 1
        right = (final_carry >> position) & 1
        carry = (left & right) | (left & carry) | (right & carry)
    for offset in FINAL_OFFSETS:
        position = cut + offset
        left = (final_sum >> position) & 1
        right = (final_carry >> position) & 1
        values[f"final.sum.{offset:+d}"] = left
        values[f"final.carry.{offset:+d}"] = right
        values[f"final.propagate.{offset:+d}"] = left ^ right
        values[f"final.generate.{offset:+d}"] = left & right
        values[f"final.kill.{offset:+d}"] = 1 ^ (left | right)
        values[f"final.cin.{offset:+d}"] = carries[position]
    return values


def invert(pattern: str) -> str:
    return "".join("1" if value == "0" else "0" for value in pattern)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("h1472_score", type=Path)
    parser.add_argument("h1475_audit", type=Path)
    parser.add_argument("h1476_bank", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    h1475 = json.loads(args.h1475_audit.read_text())
    lead = h1475["leading_hypothesis"]
    if (lead["gate"], lead["left"], lead["right"]) != (
            "xor", "product.R.l1_4.sum.+0",
            "product.R.l2_1.carry.-3"):
        raise RuntimeError("H1475 leading function changed")
    if h1475["exact_literals"]:
        raise RuntimeError("H1475 unexpectedly contains a default-tree literal")

    labeled = replay_h1472(args.model, args.h1472_score)
    labeled.extend(replay_anchors(args.model))
    disjoint = replay_disjoint(args.model, args.h1476_bank)
    if len(labeled) != 18 or len(disjoint) != 22:
        raise RuntimeError("row census changed")

    labeled_truth = "".join(str(row["value"]) for row in labeled)
    combined = labeled + disjoint
    combined_truth = "".join(str(row["value"]) for row in combined)

    analogs = []
    for correction in ("next_row", "source_row", "single_bus", "split_bus"):
        for d1 in range(4):
            for d2 in range(4):
                pattern = "".join(str(analogous_xor(
                    row["row"], correction, d1, d2)) for row in labeled)
                analogs.append({
                    "correction": correction,
                    "level1_d_slot": d1,
                    "level2_d_slot": d2,
                    "label_errors": sum(
                        left != right
                        for left, right in zip(pattern, labeled_truth)),
                    "label_pattern": pattern,
                })
    exact_analogs = [row for row in analogs if row["label_errors"] == 0]

    layouts = [
        (name, axis, config)
        for name, axis, config in tree_variants()
        if config.stage_width >= 131
    ]
    label_aliases = []
    combined_aliases = []
    features_per_layout = None
    for layout_name, axis, config in layouts:
        patterns: dict[str, str] = {}
        for row in combined:
            for feature, value in tree_features(row["row"], config).items():
                patterns[feature] = patterns.get(feature, "") + str(value)
        if features_per_layout is None:
            features_per_layout = len(patterns)
        elif len(patterns) != features_per_layout:
            raise RuntimeError("tree feature schema changed")
        for feature, pattern in patterns.items():
            for complemented, candidate in ((False, pattern), (True, invert(pattern))):
                name = ("!" if complemented else "") + layout_name + "." + feature
                if candidate[:len(labeled)] == labeled_truth:
                    errors = sum(
                        left != right
                        for left, right in zip(candidate, combined_truth))
                    label_aliases.append({
                        "signal": name,
                        "axis": axis,
                        "combined_errors": errors,
                        "disjoint_errors": errors,
                    })
                if candidate == combined_truth:
                    combined_aliases.append(name)

    label_aliases.sort(key=lambda row: (row["combined_errors"], row["signal"]))
    if len(label_aliases) != 11:
        raise RuntimeError(f"expected eleven label aliases, got {len(label_aliases)}")
    if combined_aliases:
        raise RuntimeError("an alternate single-signal isomorphism survived")
    if Counter(row["disjoint_errors"] for row in label_aliases) != {13: 9, 14: 2}:
        raise RuntimeError("alternate alias counterexample census changed")
    if Counter((row["level1_d_slot"], row["level2_d_slot"])
               for row in exact_analogs) != {(0, 0): 4}:
        raise RuntimeError("analogous-XOR representation specificity changed")

    report = {
        "experiment": "h1479_r1475_topology_isomorphism",
        "status": "NO_TESTED_SINGLE_SIGNAL_ISOMORPHISM",
        "hardware_policy": (
            "cached_h1472_and_prior_anchor_labels_only; "
            "h1476 supplies software function values; no_x87_execution"
        ),
        "labeled_rows": len(labeled),
        "disjoint_function_rows": len(disjoint),
        "combined_rows": len(combined),
        "default_tree_exact_literals_from_h1475": len(h1475["exact_literals"]),
        "analogous_xor": {
            "configurations": len(analogs),
            "correction_routes": 4,
            "distinguished_d_assignments": 16,
            "label_exact_configurations": len(exact_analogs),
            "label_exact_d_assignments_ignoring_correction_route": 1,
            "exact_configurations": exact_analogs,
            "interpretation": (
                "The fit requires the patent transcription's distinguished-D "
                "choice at levels one and two. The four low correction routes "
                "are indistinguishable at these high observed columns."
            ),
        },
        "alternate_single_signal_search": {
            "tree_layouts_total": len(tree_variants()),
            "arithmetic_exact_tree_layouts": len(layouts),
            "features_per_layout": features_per_layout,
            "single_signals_with_complements": (
                2 * len(layouts) * int(features_per_layout or 0)),
            "label_only_aliases": len(label_aliases),
            "label_only_alias_details": label_aliases,
            "combined_exact_aliases": combined_aliases,
            "counterexample_result": (
                "Every label-only alternate signal disagrees with the R1475 "
                "function on 13 or 14 of 22 disjoint exact-lattice rows."
            ),
        },
        "topology": {
            "left_input": "R.l1_4.sum[product_cut]",
            "left_physical_rows": "PP16..PP19",
            "left_route": "l1_4 -> l2_2 -> l4_0",
            "right_input": "R.l2_1.carry[product_cut-3]",
            "right_physical_rows": "PP8..PP15",
            "right_route": "l2_1 -> l3_0 -> l4_0",
            "first_common_consumer": "l4_0",
            "column_separation": 3,
            "same_compressor_cell": False,
            "interpretation": (
                "The operands come from disjoint Booth-row subtrees and reach "
                "their first common compressor at different bit columns. The "
                "XOR is not a direct gate already present in the reconstructed "
                "four-level tree."
            ),
        },
        "claim_boundary": (
            "This refutes an isomorphism to the tested single-node or final-CPA "
            "signals; it does not refute a separate silicon control gate that "
            "explicitly combines the two remote wires. R1475 remains "
            "label-selected, default-off, and subject to unopened H1477."
        ),
        "emulator_change": "none",
        "paper_change": "none",
        "sha256": {
            "model": digest(args.model),
            "h1472_score": digest(args.h1472_score),
            "h1475_audit": digest(args.h1475_audit),
            "h1476_bank": digest(args.h1476_bank),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps({
        "output": str(args.output),
        "labeled_rows": len(labeled),
        "disjoint_rows": len(disjoint),
        "label_exact_analog_configurations": len(exact_analogs),
        "label_only_alternate_aliases": len(label_aliases),
        "combined_exact_single_signal_aliases": len(combined_aliases),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
