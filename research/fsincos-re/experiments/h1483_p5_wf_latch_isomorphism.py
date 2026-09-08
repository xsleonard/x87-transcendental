#!/usr/bin/env python3
"""Audit documented P5 X2-to-WF carry signals as R1475 isomorphisms.

H1479 searched individual CSA-node and final bit/carry signals.  US 5,195,051
also documents a group-generate/propagate block feeding the WF-stage adder and
a four-bit carry-select final stage.  This pass evaluates those group states,
conditional carries, conditional sum words, and P5-origin prefix states under
all seventy arithmetic-exact tree layouts already bounded by H1400.

Hardware labels are limited to the cached H1472 split and two prior anchors.
H1476 supplies disjoint software values only to disprove functional aliases.
H1477 remains unopened.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from h1400_p5_representation_audit import tree_variants
from h1479_r1475_topology_isomorphism import (
    normalized_operand,
    replay_anchors,
    replay_disjoint,
    replay_h1472,
    trace_tree,
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def bit(value: int, position: int) -> int:
    return (value >> position) & 1 if position >= 0 else 0


def group_state(sum_vector: int, carry_vector: int, start: int, end: int):
    generate = 0
    propagate = 1
    carry0, carry1 = 0, 1
    for position in range(start, end):
        left = bit(sum_vector, position)
        right = bit(carry_vector, position)
        local_generate = left & right
        local_propagate = left ^ right
        generate = local_generate | (local_propagate & generate)
        propagate &= local_propagate
        carry0 = local_generate | (local_propagate & carry0)
        carry1 = local_generate | (local_propagate & carry1)

    incoming = 0
    for position in range(start):
        left = bit(sum_vector, position)
        right = bit(carry_vector, position)
        incoming = (left & right) | ((left ^ right) & incoming)
    selected = carry1 if incoming else carry0
    return generate, propagate, carry0, carry1, incoming, selected


def latch_features(row: dict[str, str], config) -> dict[str, int]:
    _, cut, (sum_vector, carry_vector) = trace_tree(row, config)
    values = {}
    # US5195051's 129-bit adder begins at product column two.  Absolute-zero
    # and cut-relative origins remain bounded controls as in H1172.
    for width in (4, 8, 16):
        for alignment, origin in (("p5", 2), ("abs", 0), ("cut", cut)):
            base = origin + ((cut - origin) // width) * width
            for relative in range(-4, 5):
                start = base + relative * width
                end = start + width
                stem = f"{alignment}.w{width:02d}.rel{relative:+d}"
                if start < 0 or end > 131:
                    state = (0, 0, 0, 0, 0, 0)
                else:
                    state = group_state(sum_vector, carry_vector, start, end)
                for name, value in zip(
                        ("g", "p", "c0", "c1", "cin", "cout"), state):
                    values[f"{stem}.{name}"] = value

                if width == 4:
                    for assumed in (0, 1):
                        carry = assumed
                        for offset, position in enumerate(range(start, end)):
                            if start < 0 or end > 131:
                                result = 0
                            else:
                                left = bit(sum_vector, position)
                                right = bit(carry_vector, position)
                                result = left ^ right ^ carry
                                carry = (left & right) | ((left ^ right) & carry)
                            values[f"{stem}.sum{assumed}.b{offset}"] = result

    for offset in range(-24, 25):
        end = cut + offset + 1
        stem = f"p5prefix.rel{offset:+d}"
        if end <= 2 or end > 131:
            state = (0, 0, 0, 0)
        else:
            state = group_state(sum_vector, carry_vector, 2, end)[:4]
        for name, value in zip(("g", "p", "c0", "c1"), state):
            values[f"{stem}.{name}"] = value
    return values


def invert(pattern: str) -> str:
    return "".join("1" if value == "0" else "0" for value in pattern)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("h1472_score", type=Path)
    parser.add_argument("h1476_bank", type=Path)
    parser.add_argument("h1477_manifest", type=Path)
    parser.add_argument("h1480_predictions", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    labeled = replay_h1472(args.model, args.h1472_score)
    labeled.extend(replay_anchors(args.model))
    disjoint = replay_disjoint(args.model, args.h1476_bank)
    combined = labeled + disjoint
    if len(labeled) != 18 or len(disjoint) != 22:
        raise RuntimeError("H1472/H1476 row census changed")
    label_truth = "".join(str(record["value"]) for record in labeled)
    combined_truth = "".join(str(record["value"]) for record in combined)

    with args.h1477_manifest.open(newline="") as source:
        manifest = list(csv.DictReader(source, delimiter="\t"))
    if len(manifest) != 10:
        raise RuntimeError("H1477 manifest row count changed")
    disjoint_index = {
        normalized_operand(str(record["operand"])): index
        for index, record in enumerate(disjoint)
    }
    if any(row["operand"] not in disjoint_index for row in manifest):
        raise RuntimeError("H1477 is not a subset of H1476 disjoint rows")

    aliases = []
    combined_aliases = []
    features_per_layout = None
    for layout_name, axis, config in tree_variants():
        patterns: dict[str, str] = {}
        for record in combined:
            features = latch_features(record["row"], config)
            if features_per_layout is None:
                features_per_layout = len(features)
            elif len(features) != features_per_layout:
                raise RuntimeError("latch feature schema changed")
            for feature, value in features.items():
                patterns[feature] = patterns.get(feature, "") + str(value)
        for feature, pattern in patterns.items():
            for complemented, candidate in ((False, pattern), (True, invert(pattern))):
                signal = (
                    ("!" if complemented else "")
                    + layout_name + "." + feature
                )
                if candidate[:len(labeled)] == label_truth:
                    disjoint_pattern = candidate[len(labeled):]
                    aliases.append({
                        "signal": signal,
                        "axis": axis,
                        "disjoint_errors": sum(
                            left != right for left, right in zip(
                                disjoint_pattern,
                                combined_truth[len(labeled):],
                            )
                        ),
                        "disjoint_pattern": disjoint_pattern,
                        "h1477_pattern": "".join(
                            disjoint_pattern[disjoint_index[row["operand"]]]
                            for row in manifest
                        ),
                    })
                if candidate == combined_truth:
                    combined_aliases.append(signal)

    aliases.sort(key=lambda item: (item["disjoint_errors"], item["signal"]))
    if features_per_layout != 898:
        raise RuntimeError(f"expected 898 features per layout, got {features_per_layout}")
    if len(aliases) != 30 or combined_aliases:
        raise RuntimeError(
            f"latch alias result changed: labels={len(aliases)} combined={combined_aliases}"
        )
    if Counter(item["disjoint_errors"] for item in aliases) != {13: 24, 14: 6}:
        raise RuntimeError("latch alias counterexample counts changed")

    classes: dict[str, list[str]] = defaultdict(list)
    for item in aliases:
        classes[item["h1477_pattern"]].append(item["signal"])
    h1480 = json.loads(args.h1480_predictions.read_text())
    prior_patterns = {item["pattern"] for item in h1480["classes"]}
    r1475_pattern = h1480["r1475_pattern"]
    if r1475_pattern in classes:
        raise RuntimeError("H1477 does not separate R1475 from a latch alias")
    shared_patterns = set(classes) & prior_patterns
    new_patterns = set(classes) - prior_patterns
    prior_only_patterns = prior_patterns - set(classes)

    report = {
        "experiment": "h1483_p5_wf_latch_isomorphism",
        "status": "NO_DOCUMENTED_X2_WF_SINGLE_SIGNAL_ISOMORPHISM",
        "hardware_policy": (
            "cached_h1472_and_prior_anchor_labels_only; h1476 supplies "
            "software function values; no_x87_execution"
        ),
        "labeled_rows": len(labeled),
        "disjoint_function_rows": len(disjoint),
        "combined_rows": len(combined),
        "tree_layouts": len(tree_variants()),
        "features_per_layout": features_per_layout,
        "single_literals_with_complements": (
            2 * len(tree_variants()) * int(features_per_layout or 0)
        ),
        "label_only_aliases": len(aliases),
        "label_only_alias_error_counts": dict(sorted(Counter(
            item["disjoint_errors"] for item in aliases).items()
        )),
        "label_only_alias_details": aliases,
        "combined_exact_aliases": combined_aliases,
        "h1477_prediction_classes": [
            {"pattern": pattern, "signals": sorted(signals)}
            for pattern, signals in sorted(classes.items())
        ],
        "h1477_r1475_pattern": r1475_pattern,
        "h1477_r1475_separated_from_all_latch_classes": True,
        "h1477_prediction_classes_equal_h1480": not (
            new_patterns or prior_only_patterns
        ),
        "h1477_prediction_class_comparison": {
            "shared_with_h1480": sorted(shared_patterns),
            "new_in_h1483": sorted(new_patterns),
            "h1480_only": sorted(prior_only_patterns),
        },
        "interpretation": (
            "No group G/P, conditional-carry, carry-select word bit, or P5 "
            "prefix signal in the bounded exact-layout family is functionally "
            "identical to R1475. All label aliases have explicit disjoint "
            "counterexamples."
        ),
        "claim_boundary": (
            "This closes the tested documented X2-to-WF single-signal family, "
            "not arbitrary combinational logic or undocumented state. R1475 "
            "remains label-selected and H1477 remains unopened."
        ),
        "emulator_change": "none",
        "paper_change": "none",
        "sha256": {
            "model": digest(args.model),
            "h1472_score": digest(args.h1472_score),
            "h1476_bank": digest(args.h1476_bank),
            "h1477_manifest": digest(args.h1477_manifest),
            "h1480_predictions": digest(args.h1480_predictions),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps({
        "output": str(args.output),
        "layouts": len(tree_variants()),
        "features_per_layout": features_per_layout,
        "label_aliases": len(aliases),
        "combined_aliases": len(combined_aliases),
        "h1477_classes": len(classes),
        "h1477_new_classes": len(new_patterns),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
