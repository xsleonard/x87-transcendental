#!/usr/bin/env python3
"""Score precommitted H1479 alias classes after H1478 opens H1477."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1478_score", type=Path)
    parser.add_argument("h1480_predictions", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    with args.h1478_score.open(newline="") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    predictions = json.loads(args.h1480_predictions.read_text())
    case_order = predictions["case_order"]
    by_case = {row["case_id"]: row for row in rows}
    if len(rows) != 10 or sorted(by_case) != sorted(case_order):
        raise RuntimeError("H1478 score rows differ from H1480 case set")
    ordered = [by_case[case_id] for case_id in case_order]
    if any(row["endpoint"] == "other" for row in ordered):
        hardware_pattern = None
    else:
        hardware_pattern = "".join(row["hardware_merge"] for row in ordered)

    classes = []
    for item in predictions["classes"]:
        exact = hardware_pattern is not None and item["pattern"] == hardware_pattern
        classes.append({**item, "exact": exact})
    r1475_exact = (
        hardware_pattern is not None
        and predictions["r1475_pattern"] == hardware_pattern
    )
    surviving = [item for item in classes if item["exact"]]

    report = {
        "experiment": "h1481_score_h1479_alias_predictions",
        "rows": len(rows),
        "hardware_pattern": hardware_pattern,
        "other_endpoint_present": hardware_pattern is None,
        "r1475_pattern": predictions["r1475_pattern"],
        "r1475_exact": r1475_exact,
        "alternate_classes": classes,
        "surviving_alternate_classes": len(surviving),
        "surviving_alternate_signals": sum(
            len(item["signals"]) for item in surviving),
        "claim_boundary": (
            "H1477 is a fresh ten-row discriminator, not proof of a global "
            "selector even if one precommitted class is exact."
        ),
        "paper_change": "none",
        "emulator_change": "none",
        "sha256": {
            "h1478_score": digest(args.h1478_score),
            "h1480_predictions": digest(args.h1480_predictions),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps({
        "output": str(args.output),
        "hardware_pattern": hardware_pattern,
        "r1475_exact": r1475_exact,
        "surviving_alternate_classes": len(surviving),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
