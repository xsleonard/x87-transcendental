#!/usr/bin/env python3
"""Classify the H1487 functions against the published P5 tree topology.

The four surviving spellings use the same unlabeled six-to-three-to-two-to-one
4:2-CSA graph as US 5,195,051 Figure 7, but different assignments of the six
first-level PP quartets to that graph.  This audit makes the distinction exact:
graph isomorphism is free; a row-label-preserving or order-preserving
isomorphism is not.  It also scores the literal patent pairing on all 28
hardware labels.  No x87 instruction is executed.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path

from h1400_p5_representation_audit import tree_variants
from h1479_r1475_topology_isomorphism import replay_anchors, replay_h1472, tree_features
from h1486_surviving_propagate_class import EXPECTED_SIGNALS, replay_score


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def inversions(order):
    return sum(
        order[left] > order[right]
        for left in range(len(order)) for right in range(left + 1, len(order)))


def pairing_crossings(pairing):
    normalized = [tuple(sorted(pair)) for pair in pairing]
    result = 0
    for left, right in itertools.combinations(normalized, 2):
        a, b = left
        c, d = right
        result += int((a < c < b < d) or (c < a < d < b))
    return result


def topology_record(name, config):
    order = tuple(value for pair in config.pairing for value in pair)
    spans = [abs(left - right) for left, right in config.pairing]
    return {
        "layout": name,
        "pairing": [list(pair) for pair in config.pairing],
        "held_level2_branch": config.hold,
        "held_level1_groups": list(config.pairing[config.hold]),
        "first_level_group_order_ltr": list(order),
        "first_level_pp_quartets_ltr": [
            f"PP{4 * group}..PP{4 * group + 3}" for group in order],
        "permutation_inversions": inversions(order),
        "total_group_displacement": sum(
            abs(position - group) for position, group in enumerate(order)),
        "maximum_group_displacement": max(
            abs(position - group) for position, group in enumerate(order)),
        "level2_group_spans": spans,
        "crossing_pair_count_in_natural_order": pairing_crossings(config.pairing),
        "row_label_preserving": order == tuple(range(6)),
        "order_preserving": all(
            order[index] < order[index + 1] for index in range(5)),
        "order_reversing": all(
            order[index] > order[index + 1] for index in range(5)),
        "unlabeled_graph_isomorphic_to_patent": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("h1472_score", type=Path)
    parser.add_argument("h1478_score", type=Path)
    parser.add_argument("patent_pdf", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    labels = replay_h1472(args.model, args.h1472_score)
    labels.extend(replay_anchors(args.model))
    labels.extend(replay_score(
        args.model, args.h1478_score, "h1477_fresh_hardware_label"))
    if len(labels) != 28:
        raise RuntimeError("hardware label census changed")
    truth = "".join(str(row["value"]) for row in labels)

    configs = {name: config for name, _, config in tree_variants()}
    candidate_names = sorted(
        signal.split(".final.")[0] for signal in EXPECTED_SIGNALS)
    patent = configs["patent"]
    if patent.pairing != ((0, 1), (2, 3), (4, 5)) or patent.hold != 2:
        raise RuntimeError("patent topology transcription changed")

    patterns = {}
    for name in ["patent", *candidate_names]:
        pattern = "".join(str(
            tree_features(row["row"], configs[name])["final.propagate.-18"])
            for row in labels)
        patterns[name] = {
            "pattern": pattern,
            "errors": sum(left != right for left, right in zip(pattern, truth)),
            "mismatches": [
                {
                    "name": row["name"],
                    "mode": row["mode"],
                    "operand": row["operand"].replace(" ", ":"),
                    "provenance": row["provenance"],
                    "hardware_merge": int(wanted),
                    "candidate_merge": int(actual),
                }
                for row, actual, wanted in zip(labels, pattern, truth)
                if actual != wanted
            ],
            "topology": topology_record(name, configs[name]),
        }
    if patterns["patent"]["errors"] == 0:
        raise RuntimeError("literal patent topology unexpectedly became exact")
    if any(patterns[name]["errors"] != 0 for name in candidate_names):
        raise RuntimeError("H1487 candidate stopped fitting 28 labels")

    abstract_pair_hold_topologies = 0
    row_preserving_topologies = []
    candidate_pairing_set = {
        (config.pairing, config.hold) for name, config in configs.items()
        if name in candidate_names
    }
    for permutation in itertools.permutations(range(6)):
        pairing = tuple(
            (permutation[2 * index], permutation[2 * index + 1])
            for index in range(3))
        abstract_pair_hold_topologies += 1
        if permutation == tuple(range(6)):
            row_preserving_topologies.append({
                "pairing": [list(pair) for pair in pairing], "hold": 2})
    if abstract_pair_hold_topologies != 720 or len(row_preserving_topologies) != 1:
        raise AssertionError("six-leaf topology census changed")

    report = {
        "experiment": "h1491_propagate_topology_isomorphism",
        "status": "UNLABELED_GRAPH_ISOMORPHISM_REQUIRES_NONLOCAL_ROW_RELABELING",
        "hardware_execution": "none",
        "hardware_labels": {"cached_prior": 18, "fresh_h1477": 10, "total": 28},
        "published_topology": {
            "source": "US 5,195,051 Figure 7",
            "figure_description": (
                "Six first-level 4:2 CSAs feed three second-level CSAs; the "
                "first two second-level outputs feed a third-level CSA and "
                "the rightmost second-level output is held for the final CSA."
            ),
            "transcribed_pairing": [[0, 1], [2, 3], [4, 5]],
            "held_branch": 2,
            "scope_warning": (
                "The drawing orders 22 partial-product arrows left-to-right "
                "but does not textually number each arrow-to-CSA connection."
            ),
        },
        "hardware_truth": truth,
        "layout_scores": patterns,
        "isomorphism": {
            "six_leaf_permutations": abstract_pair_hold_topologies,
            "all_candidates_share_unlabeled_graph": True,
            "row_label_preserving_candidate_count": sum(
                patterns[name]["topology"]["row_label_preserving"]
                for name in candidate_names),
            "order_or_reverse_preserving_candidate_count": sum(
                patterns[name]["topology"]["order_preserving"]
                or patterns[name]["topology"]["order_reversing"]
                for name in candidate_names),
            "candidate_pairing_hold_forms": [
                {"pairing": [list(pair) for pair in pairing], "hold": hold}
                for pairing, hold in sorted(candidate_pairing_set)
            ],
            "interpretation": (
                "As unlabeled compressor graphs, the candidates and Figure 7 "
                "are isomorphic. Preserving the PP-quartet labels or their "
                "linear order leaves only the literal patent assignment, "
                "which is not exact on the 28 labels. Every survivor requires "
                "crossed, nonlocal reassignment of first-level PP quartets."
            ),
        },
        "claim_boundary": (
            "The public drawing disfavors but cannot formally exclude a later "
            "Skylake row permutation. This audit establishes the exact kind of "
            "isomorphism required; it does not identify physical wiring."
        ),
        "emulator_change": "none",
        "paper_change": "none",
        "sha256": {
            "model": digest(args.model),
            "h1472_score": digest(args.h1472_score),
            "h1478_score": digest(args.h1478_score),
            "patent_pdf": digest(args.patent_pdf),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps({
        "output": str(args.output),
        "patent_errors": patterns["patent"]["errors"],
        "candidate_errors": [patterns[name]["errors"] for name in candidate_names],
        "row_preserving_candidates": report["isomorphism"][
            "row_label_preserving_candidate_count"],
        "order_preserving_candidates": report["isomorphism"][
            "order_or_reverse_preserving_candidate_count"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
