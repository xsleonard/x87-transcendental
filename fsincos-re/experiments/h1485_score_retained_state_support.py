#!/usr/bin/env python3
"""Challenge H1484's minimum six-signal retained-state fit on fresh rows.

The six-signal truth table was synthesized only from H1472 labels, two prior
anchors, and H1476 software function rows.  H1485 replays a disjoint-seed
exact-lattice bank and asks whether the pre-existing table predicts, leaves an
unassigned state, or conflicts at an already assigned state.  No hardware is
executed and H1477 remains unopened.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from h1210_stagea_residual_reframe import parse_dump, run
from h1400_p5_representation_audit import tree_variants
from h1479_r1475_topology_isomorphism import (
    analogous_xor,
    normalized_operand,
    replay_anchors,
    replay_disjoint,
    replay_h1472,
)
from h1484_x2_wf_state_determinism import (
    full_p5_features,
    minimum_arbitrary_support,
)


MODES = ("rn", "rd", "ru", "rz")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def operand_set_from_h1471(report: dict[str, object]) -> set[str]:
    result = set()
    for row in report["pre_candidate_bank"]["candidate_rows"]:
        if "operand" in row:
            result.add(normalized_operand(str(row["operand"])))
        else:
            result.add("3ffc " + str(row["sig"]).lower())
    return result


def signal_value(name: str, features: dict[str, int]) -> int:
    complemented = name.startswith("!")
    bare = name[1:] if complemented else name
    if bare not in features:
        raise RuntimeError(f"missing retained-state signal {bare}")
    return features[bare] ^ int(complemented)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("h1472_score", type=Path)
    parser.add_argument("h1471", type=Path)
    parser.add_argument("h1476", type=Path)
    parser.add_argument("h1484", type=Path)
    parser.add_argument("fresh_bank", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    h1471 = json.loads(args.h1471.read_text())
    h1476 = json.loads(args.h1476.read_text())
    h1484 = json.loads(args.h1484.read_text())
    fresh = json.loads(args.fresh_bank.read_text())
    rows = fresh["all_endpoint_visible"]
    if fresh["sampling"]["seed"] != "0x13198a2e03707344":
        raise RuntimeError("fresh-bank seed changed")
    if len(rows) != 6:
        raise RuntimeError(f"expected six fresh visible rows, got {len(rows)}")

    fresh_operands = {normalized_operand(str(row["operand"])) for row in rows}
    prior_operands = {
        normalized_operand(str(row["operand"]))
        for row in h1476["all_endpoint_visible"]
    }
    prior_operands.update(operand_set_from_h1471(h1471))
    prior_operands.update((
        "3ffc d0d000000cc0b3f8",
        "3ffc d80000000b15da62",
    ))
    overlap = sorted(fresh_operands & prior_operands)
    if overlap:
        raise RuntimeError(f"fresh software bank overlaps prior rows: {overlap}")

    patent_result = next(
        item for item in h1484["layout_results"] if item["layout"] == "patent"
    )
    support = patent_result["minimum_support_families"]["p5_w04_full_gp"]
    if support["minimum_support"] != 6:
        raise RuntimeError("H1484 retained-state minimum changed")
    witness = support["support_witness"]
    signals = []
    for aliases in witness["signals"]:
        if len(aliases) != 1:
            raise RuntimeError("H1484 witness signal unexpectedly ambiguous")
        signals.append(aliases[0])
    table = witness["truth_table_lsb_first"]
    if len(signals) != 6 or len(table) != 64:
        raise RuntimeError("H1484 six-input truth table changed")

    patent_config = next(
        config for name, _, config in tree_variants() if name == "patent"
    )
    dumps = {}
    for mode in MODES:
        selected = [row for row in rows if row["mode"] == mode]
        operands = [normalized_operand(str(row["operand"])) for row in selected]
        if not operands:
            continue
        _, stderr = run(args.model, mode, operands, dump=True)
        for source, dump in zip(selected, parse_dump(stderr, operands)):
            dumps[normalized_operand(str(source["operand"]))] = dump
    if len(dumps) != len(rows):
        raise RuntimeError("fresh diagnostic replay row count changed")

    scored = []
    fresh_records = []
    codes: dict[int, set[int]] = defaultdict(set)
    for row in rows:
        operand = normalized_operand(str(row["operand"]))
        dump = dumps[operand]
        actual = analogous_xor(dump, "next_row", 0, 0)
        if actual != int(row["leading_merge"]):
            raise RuntimeError("fresh bank disagrees with independent R1475 replay")
        features = full_p5_features(dump, patent_config)
        values = [signal_value(signal, features) for signal in signals]
        code = sum(value << index for index, value in enumerate(values))
        prediction = table[code]
        codes[code].add(actual)
        fresh_records.append({
            "name": row["sig"],
            "mode": row["mode"],
            "operand": operand,
            "value": actual,
            "row": dump,
            "provenance": "h1485_disjoint_software_function_value",
        })
        scored.append({
            "operand": operand.replace(" ", ":"),
            "mode": row["mode"],
            "r1475": actual,
            "support_bits_lsb_first": "".join(map(str, values)),
            "support_code": code,
            "precommitted_table_value": prediction,
            "outcome": (
                "UNSEEN_STATE" if prediction == "x"
                else "CORRECT" if int(prediction) == actual
                else "FALSIFIED"
            ),
        })

    defined = [row for row in scored if row["precommitted_table_value"] != "x"]
    conflicts = [row for row in scored if row["outcome"] == "FALSIFIED"]
    fresh_code_conflicts = sorted(
        code for code, values in codes.items() if len(values) > 1
    )
    training = replay_h1472(args.model, args.h1472_score)
    training.extend(replay_anchors(args.model))
    training.extend(replay_disjoint(args.model, args.h1476))
    if len(training) != 40:
        raise RuntimeError("H1484 training-row census changed")
    combined_records = training + fresh_records
    combined_features = [
        full_p5_features(record["row"], patent_config)
        for record in combined_records
    ]
    gp_names = sorted(
        name for name in combined_features[0]
        if name.startswith("fullp5.group")
        and name.endswith((".g", ".p"))
    )
    if len(gp_names) != 64:
        raise RuntimeError("full P5 group-G/P schema changed")
    training_support = minimum_arbitrary_support(
        training, combined_features[:len(training)], gp_names, maximum=6)
    if training_support["minimum_support"] != 6:
        raise RuntimeError("independent H1484 minimum-support replay changed")
    combined_support = minimum_arbitrary_support(
        combined_records, combined_features, gp_names, maximum=8)
    combined_minimum = combined_support["minimum_support"]
    all_six_falsified = (
        combined_minimum is None or int(combined_minimum) > 6
    )
    selected_falsified = bool(conflicts or fresh_code_conflicts)
    report = {
        "experiment": "h1485_score_retained_state_support",
        "status": (
            "ALL_SIX_SIGNAL_FITS_FALSIFIED" if all_six_falsified
            else "SELECTED_SIX_SIGNAL_FIT_FALSIFIED_ALTERNATE_SURVIVES"
            if selected_falsified
            else "SIX_SIGNAL_TABLE_EXTENDABLE_NOT_CLOSED"
        ),
        "hardware_execution": "none",
        "hardware_labels": "none",
        "h1477_state": "FROZEN_UNOPENED",
        "fresh_seed": fresh["sampling"]["seed"],
        "fresh_plateau_samples": fresh["sampling"]["samples"],
        "fresh_pre_candidates": fresh["sampling"]["disjoint_pre_candidates"],
        "fresh_endpoint_visible": len(rows),
        "fresh_prior_operand_overlaps": overlap,
        "support_signals": signals,
        "training_truth_table_lsb_first": table,
        "training_assigned_codes": sum(value != "x" for value in table),
        "training_unassigned_codes": sum(value == "x" for value in table),
        "fresh_defined_predictions": len(defined),
        "fresh_correct_defined_predictions": sum(
            row["outcome"] == "CORRECT" for row in defined),
        "fresh_falsified_defined_predictions": len(conflicts),
        "fresh_unseen_states": sum(
            row["outcome"] == "UNSEEN_STATE" for row in scored),
        "fresh_code_conflicts": fresh_code_conflicts,
        "selected_six_signal_fit_falsified": selected_falsified,
        "fresh_outcome_counts": dict(sorted(Counter(
            row["outcome"] for row in scored
        ).items())),
        "rows": scored,
        "training_support_replay": training_support,
        "combined_46_row_support_search": combined_support,
        "all_six_signal_supports_falsified": all_six_falsified,
        "interpretation": (
            "The fresh code-24 collision falsifies H1484's selected support. "
            "The exact combined-row minimum-support search decides whether "
            "any other support of six or fewer group-G/P signals survives. "
            "Any newly found wider truth table remains a finite fit, not a "
            "closed-form identity."
        ),
        "emulator_change": "none",
        "paper_change": "none",
        "sha256": {
            "model": digest(args.model),
            "h1472_score": digest(args.h1472_score),
            "h1471": digest(args.h1471),
            "h1476": digest(args.h1476),
            "h1484": digest(args.h1484),
            "fresh_bank": digest(args.fresh_bank),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps({
        "output": str(args.output),
        "status": report["status"],
        "fresh_outcomes": report["fresh_outcome_counts"],
        "fresh_code_conflicts": fresh_code_conflicts,
        "combined_minimum_support": combined_minimum,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
