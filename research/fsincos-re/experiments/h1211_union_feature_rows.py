#!/usr/bin/env python3
"""Union target feature rows with the frozen R59 negative controls.

Only rows labeled NEG are retained from the control bank, so the target
all-mode response file can be supplied independently to downstream audits.
The output schema is the union of both input schemas; absent diagnostic-only
fields remain empty and are not interpreted as selector state.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def read(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="") as source:
        reader = csv.DictReader(source, delimiter="\t")
        return list(reader), list(reader.fieldnames or ())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("controls", type=Path)
    parser.add_argument("targets", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    controls, control_columns = read(args.controls)
    targets, target_columns = read(args.targets)
    controls = [row for row in controls if row["label"] == "NEG"]
    if not targets or any(row["label"] != "POS" for row in targets):
        raise RuntimeError("target bank must contain only POS rows")
    control_operands = {row["op"] for row in controls}
    overlap = sorted(control_operands & {row["op"] for row in targets})
    if overlap:
        raise RuntimeError(f"target/control overlap: {overlap[:5]}")

    columns = list(control_columns)
    columns.extend(column for column in target_columns if column not in columns)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", newline="") as target:
        writer = csv.DictWriter(
            target, columns, delimiter="\t", extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(controls)
        writer.writerows(targets)
    print(
        f"wrote {args.output} controls={len(controls)} targets={len(targets)} "
        f"columns={len(columns)}"
    )


if __name__ == "__main__":
    main()
