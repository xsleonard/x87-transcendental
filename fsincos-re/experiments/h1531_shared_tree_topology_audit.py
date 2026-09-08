#!/usr/bin/env python3
"""Reconcile H1486's four aliases with the validated shared P5-tree users.

The four candidate binaries select the H1486 pairings globally through
G_R1531TREEPAIR=1..4.  Their cached-wall scores are produced separately by
h1207_candidate_cache_audit.py.  This audit verifies and combines those
scores, then evaluates the R1272 held-level-2 carry on its unique d800/RU
hardware discriminator.  It executes software models only.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from h1210_stagea_residual_reframe import parse_dump, run
from h1400_p5_representation_audit import tree_variants
from h1479_r1475_topology_isomorphism import trace_tree


LAYOUTS = (
    "pair_02_14_35_hold2",
    "pair_02_15_34_hold2",
    "pair_03_14_25_hold2",
    "pair_03_15_24_hold2",
)
D800 = "3ffc d80000000b15da62"
D800_MODE = "ru"
D800_HARDWARE = "3ffe:fa5365e8f13f3e9e"
EXPECTED = (
    (3, 12),
    (4, 13),
    (4, 13),
    (3, 12),
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def parse_text_report(path: Path) -> dict[str, object]:
    fields: dict[str, str] = {}
    counts: dict[str, int] = {}
    section = "fields"
    for raw in path.read_text().splitlines():
        if not raw:
            continue
        if raw == "[counts]":
            section = "counts"
            continue
        key, value = raw.split("\t", 1)
        if section == "fields":
            fields[key] = value
        else:
            counts[key] = int(value)
    return {"fields": fields, "counts": counts}


def read_changes(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        return list(csv.DictReader(source, delimiter="\t"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline_model", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("cache_reports", nargs=4, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    configs = {
        name: config for name, _, config in tree_variants()
        if config.stage_width >= 131
    }
    _, stderr = run(args.baseline_model, D800_MODE, [D800], dump=True)
    row = parse_dump(stderr, [D800])[0]
    position = int(row["rsh"]) + 4

    results = []
    for ordinal, (layout, report_path, expected) in enumerate(zip(
            LAYOUTS, args.cache_reports, EXPECTED), 1):
        parsed = parse_text_report(report_path)
        fields = parsed["fields"]
        counts = parsed["counts"]
        changes_path = report_path.with_name(report_path.stem + "_changes.tsv")
        misses_path = report_path.with_name(report_path.stem + "_misses.tsv")
        changes = read_changes(changes_path)
        config = configs[layout]
        nodes, _, _ = trace_tree(row, config)
        held_carry = (
            nodes[f"l2_{config.hold}"][1] >> position
        ) & 1

        change_count, miss_count = expected
        if counts.get("unique_legs") != 204_788:
            raise RuntimeError(f"{layout}: cached-wall census changed")
        if counts.get("baseline_match.0") != 9:
            raise RuntimeError(f"{layout}: baseline miss count changed")
        if counts.get("changed.1") != change_count \
                or counts.get("candidate_match.0") != miss_count:
            raise RuntimeError(f"{layout}: score changed")
        if counts.get("classification.regression") != change_count \
                or any(item["classification"] != "regression"
                       for item in changes):
            raise RuntimeError(f"{layout}: non-regression change appeared")
        if fields.get("changes_sha256") != digest(changes_path) \
                or fields.get("misses_sha256") != digest(misses_path):
            raise RuntimeError(f"{layout}: child artifact digest mismatch")

        d800_changes = [
            item for item in changes
            if item["mode"] == D800_MODE and item["op"] == D800
        ]
        d800_output = (
            d800_changes[0]["candidate"] if d800_changes
            else D800_HARDWARE
        )
        if (held_carry == 0) != (d800_output == D800_HARDWARE):
            raise RuntimeError(f"{layout}: R1272 carry/output relation changed")

        results.append({
            "ordinal": ordinal,
            "layout": layout,
            "pairing": [list(pair) for pair in config.pairing],
            "held_branch": config.hold,
            "d800_r1272_position": position,
            "d800_held_level2_carry": held_carry,
            "d800_output": d800_output,
            "d800_hardware": D800_HARDWARE,
            "d800_exact": d800_output == D800_HARDWARE,
            "cached_unique_legs": counts["unique_legs"],
            "cached_baseline_misses": counts["baseline_match.0"],
            "cached_candidate_misses": counts["candidate_match.0"],
            "cached_changes": counts["changed.1"],
            "cached_fixes": counts.get("classification.fix", 0),
            "cached_regressions": counts["classification.regression"],
            "changed_rows": changes,
            "model_sha256": fields["candidate_sha256"],
            "cache_report": str(report_path.resolve()),
            "cache_report_sha256": digest(report_path),
            "changes_sha256": digest(changes_path),
            "misses_sha256": digest(misses_path),
        })

    d800_survivors = [
        item["layout"] for item in results if item["d800_exact"]
    ]
    global_survivors = [
        item["layout"] for item in results
        if item["cached_regressions"] == 0
    ]
    if d800_survivors != [LAYOUTS[3]] or global_survivors:
        raise RuntimeError("shared-topology conclusion changed")

    report = {
        "experiment": "h1531_shared_tree_topology_audit",
        "status": "R1272_ORIENTS_D800_BUT_NO_H1486_LAYOUT_SURVIVES_GLOBAL_REPLAY",
        "hardware_execution": "none",
        "hardware_policy": "cached_files_only_no_x87_execution",
        "source_change": (
            "G_R1531TREEPAIR is analysis-only/default-off; zero preserves "
            "the documented P5 pairing"
        ),
        "baseline_model_sha256": digest(args.baseline_model),
        "r1272_discriminator": {
            "mode": D800_MODE,
            "operand": D800.replace(" ", ":"),
            "hardware": D800_HARDWARE,
            "required_held_level2_carry": 0,
            "unique_h1486_layout": d800_survivors[0],
        },
        "cached_wall": {
            "unique_legs": 204_788,
            "duplicate_rows_checked": 2_798_209,
            "baseline_misses": 9,
            "globally_exact_h1486_layouts": global_survivors,
        },
        "layouts": results,
        "conclusion": (
            "The single R1272-positive row chooses one H1486 spelling when "
            "the held level-2 node name is transferred literally.  Applying "
            "any H1486 pairing to every existing consumer of the shared tree, "
            "however, causes three or four cached regressions and no fixes.  "
            "Therefore R1272 does not establish a globally consistent physical "
            "orientation for the H1530 quotient.  The constructive quotient "
            "decoder remains exact, but its pair-A/pair-B physical choice is "
            "still unresolved."
        ),
        "claim_boundary": (
            "A topology-relative remapping of each older consumer might retain "
            "its validated Boolean function, but then those consumers no longer "
            "supply an independent orientation constraint.  No selector is "
            "promoted and the ledger-free frontier is unchanged."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        f"d800_survivor={d800_survivors[0]} global_survivors=0 "
        f"output={args.output}"
    )


if __name__ == "__main__":
    main()
