#!/usr/bin/env python3
"""Join H1600 square necessity to H1601 paired software observability.

Per-lane ordinary round-up indicators are not a claim about which operation
supplies physical FSINCOS C1. No labels, tuple ledgers or hardware are opened.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import h1601_paired_square_discriminator as paired


LOCKS = {
    "tmp/ledger33/current/h1600_joint_rc_c1_faithful_graph_v2/report.json":
        "e5d9c15ac734d6bc21d609890c3a31d581c3defe913ae8318354ab0cee8e2da6",
    "tmp/ledger33/current/h1601_paired_square_discriminator/report.json":
        "8dac3cb548ad3182817bd077f63cca5472cf3c244eb510e7a799aa4805cda53e",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    assert not args.output.exists(), "refusing existing output"
    reports = []
    for relative, expected in LOCKS.items():
        path = args.root/relative
        assert digest(path) == expected, relative
        reports.append(json.loads(path.read_text()))
    joint, software = reports
    assert digest(Path(paired.__file__)) == software["sha256"]["script"]
    assert digest(Path(paired.spec.__file__)) == software["sha256"]["spec"]
    joint_rows = {row["operand"]: row for row in joint["rows"]}
    rows = []
    for row in software["rows"]:
        if row["origin"] != "named_standalone":
            continue
        op, mode = row["operand"], row["mode"]
        indicators, prevalues = {}, {}
        for policy in ("chop", "away"):
            stages = paired.paired(op, mode, policy)
            assert {k: v.record() for k, v in stages.items()} == row["independent_stages"][policy]
            final_inputs = {"sin": paired.spec.decode_external(op), "cos": paired.V(1, 0)}
            before = {lane: paired.spec.exact_add(base, stages[lane+"_correction"])
                      for lane, base in final_inputs.items()}
            assert all(value.n > 0 for value in before.values())
            prevalues[policy] = {lane: str(value.fraction()) for lane, value in before.items()}
            indicators[policy] = {lane: int(stages[lane].fraction() > value.fraction())
                                  for lane, value in before.items()}
        square_required = {}
        alternative_available = {}
        for payload, detail in joint_rows[op]["variants"].items():
            family = detail["stages"]["joint_RC_and_C1"]["upstream_only_terminal_ordinary"]
            masks = family["successful_masks"]
            required = bool(masks) and all(mask & 1 for mask in masks)
            assert required == ("square" in family["must_depart_nodes"])
            square_required[payload] = required
            alternative_available[payload] = {
                "ordinary_square": any(not mask & 1 for mask in masks),
                "alternate_square": any(mask & 1 for mask in masks),
            }
        changed_up = [lane for lane in ("sin", "cos")
                      if indicators["chop"][lane] != indicators["away"][lane]]
        rows.append({"operand": op, "mode": mode,
                     "changed_output_lanes": row["changed_lanes"],
                     "paired_baseline": row["paired_baseline"],
                     "paired_alternate_square": row["paired_alternate_square"],
                     "ordinary_lane_round_up": indicators,
                     "changed_ordinary_round_up_lanes": changed_up,
                     "paired_prevalues": prevalues,
                     "square_required_in_joint_upstream_family": square_required,
                     "joint_upstream_square_choices": alternative_available})
    assert len(rows) == 144
    required = [row for row in rows if any(row["square_required_in_joint_upstream_family"].values())]
    required_ops = sorted({row["operand"] for row in required})
    contrasts = [row for row in rows if row["changed_output_lanes"] or row["changed_ordinary_round_up_lanes"]]
    ready = [row for row in required if row["changed_output_lanes"] or row["changed_ordinary_round_up_lanes"]]
    result = {
        "experiment": "h1601_paired_square_projection",
        "hardware_execution": "none", "hardware_labels_opened": 0,
        "tuple_freshness_audited": False, "manifest_frozen": False,
        "named_software_mode_rows": len(rows), "required_square_operands": required_ops,
        "observable_contrast_rows": len(contrasts),
        "required_square_with_observable_contrast_rows": len(ready),
        "claim_boundary": "fixed paired graph, square-only transport hypothesis; lane round-up is mathematical and is not assigned to physical FSINCOS C1; not a general upstream-versus-terminal separation or selector",
        "rows": rows,
        "sha256": {"script": digest(Path(__file__)), "evidence": LOCKS,
                   "paired_script": digest(Path(paired.__file__)), "spec": digest(Path(paired.spec.__file__))},
    }
    with args.output.open("x") as target:
        json.dump(result, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps({k: result[k] for k in ("required_square_operands", "observable_contrast_rows",
                                           "required_square_with_observable_contrast_rows")}, sort_keys=True))


if __name__ == "__main__":
    main()
