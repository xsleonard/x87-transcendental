#!/usr/bin/env python3
"""Audit the single H1479 class that survived the opened H1477 bank.

H1481 found one precommitted prediction class exact on all ten fresh H1477
labels.  Its four spellings are the final-CPA propagate bit at cut-18 under
four arithmetic-exact compressor pairings.  This script replays all 28 known
hardware labels, redoes the complete 70-layout single-signal search, and asks
whether those four spellings are a genuine arithmetic invariant or merely a
finite-domain equivalence.  It also freezes their predictions on the unopened
H1485 software bank.  No x87 instruction is executed here.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from h1210_stagea_residual_reframe import parse_dump, run
from h1400_p5_representation_audit import (
    TREE_MASK,
    csa42,
    physical_inputs,
    tree_variants,
)
from h1479_r1475_topology_isomorphism import (
    MODES,
    normalized_operand,
    replay_anchors,
    replay_h1472,
    tree_features,
)


RANDOM_SEED = 0x9E3779B97F4A7C15
RANDOM_SAMPLES = 200_000
EXPECTED_SIGNALS = {
    "pair_02_14_35_hold2.final.propagate.-18",
    "pair_02_15_34_hold2.final.propagate.-18",
    "pair_03_14_25_hold2.final.propagate.-18",
    "pair_03_15_24_hold2.final.propagate.-18",
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def replay_score(model: Path, score: Path, provenance: str):
    with score.open(newline="") as source:
        source_rows = list(csv.DictReader(source, delimiter="\t"))
    by_mode: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in source_rows:
        if row["endpoint"] not in ("incumbent", "r1382"):
            raise RuntimeError(f"{row['case_id']}: non-binary hardware endpoint")
        by_mode[row["mode"]].append(row)
    result = []
    for mode in MODES:
        selected = by_mode[mode]
        if not selected:
            continue
        operands = [normalized_operand(row["operand"]) for row in selected]
        _, stderr = run(model, mode, operands, dump=True)
        dumps = parse_dump(stderr, operands)
        if len(dumps) != len(selected):
            raise RuntimeError(f"{mode}: diagnostic replay row count changed")
        for source_row, dump in zip(selected, dumps):
            result.append({
                "name": source_row["case_id"],
                "mode": mode,
                "operand": normalized_operand(source_row["operand"]),
                "value": int(source_row["endpoint"] == "incumbent"),
                "row": dump,
                "provenance": provenance,
            })
    return result


def replay_unopened_bank(model: Path, bank: Path):
    report = json.loads(bank.read_text())
    source_rows = report["all_endpoint_visible"]
    by_mode: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in source_rows:
        by_mode[str(row["mode"])].append(row)
    result = []
    for mode in MODES:
        selected = by_mode[mode]
        if not selected:
            continue
        operands = [normalized_operand(str(row["operand"])) for row in selected]
        _, stderr = run(model, mode, operands, dump=True)
        dumps = parse_dump(stderr, operands)
        if len(dumps) != len(selected):
            raise RuntimeError(f"{mode}: unopened-bank replay row count changed")
        for source_row, dump in zip(selected, dumps):
            result.append({
                "name": str(source_row["sig"]),
                "mode": mode,
                "operand": normalized_operand(str(source_row["operand"])),
                "row": dump,
                "incumbent": str(source_row["incumbent"]),
                "r1382": str(source_row["r1382"]),
            })
    return result


def splitmix64(state: int) -> tuple[int, int]:
    mask = (1 << 64) - 1
    state = (state + 0x9E3779B97F4A7C15) & mask
    value = state
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & mask
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & mask
    return state, value ^ (value >> 31)


def candidate_values(multiplicand: int, multiplier: int, configs) -> str:
    raw_inputs, _ = physical_inputs(multiplicand, multiplier, "next_row")
    mask = (1 << configs[0].stage_width) - 1
    ordered = [value & TREE_MASK for value in raw_inputs]
    level1 = [
        csa42(ordered[4 * index:4 * index + 4], 0, mask=mask)
        for index in range(6)
    ]
    product = multiplicand * multiplier
    cut = product.bit_length() - 67
    values = []
    for config in configs:
        level2 = [
            csa42(level1[left] + level1[right], 0, mask=mask)
            for left, right in config.pairing
        ]
        remaining = [index for index in range(3) if index != config.hold]
        level3 = csa42(
            level2[remaining[0]] + level2[remaining[1]], 0, mask=mask)
        final = csa42(level3 + level2[config.hold], 0, mask=mask)
        if ((final[0] + final[1]) & ((1 << 131) - 1)) \
                != (product & ((1 << 131) - 1)):
            raise RuntimeError("candidate layout stopped reconstructing product")
        values.append(((final[0] ^ final[1]) >> (cut - 18)) & 1)
    return "".join(map(str, values))


def candidate_patterns(records, configs):
    result = []
    for record in records:
        row = record["row"]
        pattern = candidate_values(
            int(row["tc_f4_sig"], 16), int(row["tc_rf_sig"], 16), configs)
        result.append({
            "name": record["name"],
            "mode": record["mode"],
            "operand": record["operand"].replace(" ", ":"),
            "candidate_pattern": pattern,
            "candidate_classes": len(set(pattern)),
            **({
                "candidate_endpoints": "".join(
                    "I" if bit == "1" else "N" for bit in pattern),
                "incumbent": record["incumbent"],
                "r1382": record["r1382"],
            } if "incumbent" in record else {}),
        })
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("h1472_score", type=Path)
    parser.add_argument("h1478_score", type=Path)
    parser.add_argument("h1481", type=Path)
    parser.add_argument("h1476_bank", type=Path)
    parser.add_argument("h1485_bank", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--random-samples", type=int, default=RANDOM_SAMPLES)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    h1481 = json.loads(args.h1481.read_text())
    if h1481["hardware_pattern"] != "0010100111" \
            or h1481["surviving_alternate_classes"] != 1:
        raise RuntimeError("H1481 survivor changed")
    precommitted = {
        signal
        for item in h1481["alternate_classes"] if item["exact"]
        for signal in item["signals"]
    }
    if precommitted != EXPECTED_SIGNALS:
        raise RuntimeError("H1481 exact signal class changed")

    labels = replay_h1472(args.model, args.h1472_score)
    labels.extend(replay_anchors(args.model))
    labels.extend(replay_score(
        args.model, args.h1478_score, "h1477_fresh_hardware_label"))
    if len(labels) != 28 or Counter(row["value"] for row in labels) != {0: 14, 1: 14}:
        raise RuntimeError("28-row hardware truth census changed")
    truth = "".join(str(row["value"]) for row in labels)

    layouts = [
        (name, axis, config)
        for name, axis, config in tree_variants()
        if config.stage_width >= 131
    ]
    exact_literals = []
    feature_count = None
    product_patterns: dict[int, str] = defaultdict(str)
    for record in labels:
        row = record["row"]
        product = int(row["tc_f4_sig"], 16) * int(row["tc_rf_sig"], 16)
        cut = product.bit_length() - 67
        for offset in range(-80, 67):
            position = cut + offset
            value = 0 if position < 0 else (product >> position) & 1
            product_patterns[offset] += str(value)
    exact_product_literals = []
    for offset, pattern in product_patterns.items():
        if pattern == truth:
            exact_product_literals.append(f"product.{offset:+d}")
        if "".join("1" if bit == "0" else "0" for bit in pattern) == truth:
            exact_product_literals.append(f"!product.{offset:+d}")

    for layout_name, axis, config in layouts:
        patterns: dict[str, str] = {}
        for record in labels:
            for feature, value in tree_features(record["row"], config).items():
                patterns[feature] = patterns.get(feature, "") + str(value)
        if feature_count is None:
            feature_count = len(patterns)
        elif len(patterns) != feature_count:
            raise RuntimeError("tree feature schema changed")
        for feature, pattern in patterns.items():
            if pattern == truth:
                exact_literals.append({
                    "signal": f"{layout_name}.{feature}",
                    "axis": axis,
                })
            inverse = "".join("1" if bit == "0" else "0" for bit in pattern)
            if inverse == truth:
                exact_literals.append({
                    "signal": f"!{layout_name}.{feature}",
                    "axis": axis,
                })
    found = {row["signal"] for row in exact_literals}
    if found != EXPECTED_SIGNALS:
        raise RuntimeError(f"unexpected 28-label exact literals: {sorted(found)}")
    if exact_product_literals:
        raise RuntimeError("hardware truth unexpectedly collapsed to product bit")

    configs_by_name = {name: config for name, _, config in layouts}
    signal_order = sorted(EXPECTED_SIGNALS)
    config_names = [signal.split(".final.")[0] for signal in signal_order]
    configs = [configs_by_name[name] for name in config_names]
    for config in configs:
        if config.input_order != "natural" or config.correction != "next_row" \
                or config.d_slots != (0, 0, 0, 0) or config.hold != 2:
            raise RuntimeError("survivor layout assumptions changed")

    labeled_candidate_rows = candidate_patterns(labels, configs)
    if any(row["candidate_pattern"] != "1111"
           if labels[index]["value"] else row["candidate_pattern"] != "0000"
           for index, row in enumerate(labeled_candidate_rows)):
        raise RuntimeError("candidate class stopped matching hardware labels")

    h1476_rows = replay_unopened_bank(args.model, args.h1476_bank)
    h1485_rows = replay_unopened_bank(args.model, args.h1485_bank)
    h1476_predictions = candidate_patterns(h1476_rows, configs)
    h1485_predictions = candidate_patterns(h1485_rows, configs)

    random_counts = Counter()
    first_disagreement = None
    state = RANDOM_SEED
    for sample in range(args.random_samples):
        state, low = splitmix64(state)
        state, high = splitmix64(state)
        state, multiplier_bits = splitmix64(state)
        multiplicand = (1 << 66) | ((high & 3) << 64) | low
        multiplier = (1 << 63) | (multiplier_bits & ((1 << 63) - 1))
        pattern = candidate_values(multiplicand, multiplier, configs)
        random_counts[pattern] += 1
        if len(set(pattern)) > 1 and first_disagreement is None:
            first_disagreement = {
                "sample": sample,
                "multiplicand": f"{multiplicand:017x}",
                "multiplier": f"{multiplier:016x}",
                "pattern": pattern,
            }

    report = {
        "experiment": "h1486_surviving_propagate_class",
        "status": (
            "SURVIVOR_IS_FINITE_DOMAIN_EQUIVALENCE"
            if first_disagreement is not None
            else "NO_RANDOM_LAYOUT_DISAGREEMENT_FOUND"
        ),
        "hardware_execution": "none",
        "hardware_labels": {
            "cached_prior": 18,
            "fresh_h1477": 10,
            "total": len(labels),
            "truth_zeros": truth.count("0"),
            "truth_ones": truth.count("1"),
        },
        "complete_single_signal_replay": {
            "arithmetic_exact_layouts": len(layouts),
            "features_per_layout": feature_count,
            "literals_with_complements": 2 * len(layouts) * int(feature_count or 0),
            "exact_literals": exact_literals,
            "exact_literal_count": len(exact_literals),
            "exact_product_literals": exact_product_literals,
        },
        "survivor_class": {
            "signal_order": signal_order,
            "interpretation": (
                "Each spelling is one redundant-pair propagate bit entering "
                "the final CPA at product_cut-18. The four spellings use "
                "different arithmetic-exact compressor pairings."
            ),
            "labeled_patterns": labeled_candidate_rows,
        },
        "unopened_predictions": {
            "h1476_all_rows": h1476_predictions,
            "h1476_pattern_counts": dict(sorted(Counter(
                row["candidate_pattern"] for row in h1476_predictions).items())),
            "h1485_rows": h1485_predictions,
            "h1485_pattern_counts": dict(sorted(Counter(
                row["candidate_pattern"] for row in h1485_predictions).items())),
        },
        "random_normalized_product_audit": {
            "seed": f"0x{RANDOM_SEED:016x}",
            "samples": args.random_samples,
            "pattern_counts": dict(sorted(random_counts.items())),
            "first_layout_disagreement": first_disagreement,
            "claim_boundary": (
                "A concrete disagreement disproves algebraic equivalence of "
                "the four layouts. Absence in a finite sample would not prove it."
            ),
        },
        "claim_boundary": (
            "Ten fresh labels validate this precommitted class on H1477, not "
            "globally. Alternative compressor layouts are not interchangeable "
            "unless independently identified with the physical datapath."
        ),
        "emulator_change": "none",
        "paper_change": "none",
        "sha256": {
            "model": digest(args.model),
            "h1472_score": digest(args.h1472_score),
            "h1478_score": digest(args.h1478_score),
            "h1481": digest(args.h1481),
            "h1476_bank": digest(args.h1476_bank),
            "h1485_bank": digest(args.h1485_bank),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps({
        "output": str(args.output),
        "hardware_labels": len(labels),
        "exact_literals": len(exact_literals),
        "random_patterns": len(random_counts),
        "first_random_disagreement": first_disagreement,
        "h1485_pattern_counts": report["unopened_predictions"]["h1485_pattern_counts"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
