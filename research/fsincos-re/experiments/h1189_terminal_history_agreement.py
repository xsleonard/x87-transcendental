#!/usr/bin/env python3
"""Census full-product terminal choices by fixed rounding-history state.

For each constraining cached row, compare the incumbent materialized-product
endpoint with the one-chop exact-product endpoint from h1188.  Rows are then
grouped only by the patent-motivated history classes of the two terminal
products and two Horner factors, plus the existing terminal theta/branch.
This is a mechanism audit, not a selector synthesis.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

from h1178_round_history_state_audit import row_states
from h1188_exact_terminal_history_audit import full_terminal_delta


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def current_delta(row: dict[str, str]) -> int:
    base = int(row["umag"], 16) >> int(row["k"])
    return int(row["br_r"], 16) - base


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("physical_rows", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    groups = defaultdict(Counter)
    totals = Counter()
    diagnostics = []
    with args.physical_rows.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            if row["physical_status"] != "constraining":
                continue
            full_delta = full_terminal_delta(row)[0]
            incumbent_delta = current_delta(row)
            theta = int(row["theta"])
            expected_delta = (-int(row["physical_label"])
                              if theta >= 0 else int(row["physical_label"]))
            if full_delta not in (-1, 0, 1):
                totals["full_out_of_domain"] += 1
                continue
            states = row_states(row)
            terminal_pair = states["terminal.class_pair"]
            factor_pair = states["factor.class_pair"]
            key = (row["branch"], theta, terminal_pair, factor_pair)
            target = row["label"] == "POS"
            full_match = full_delta == expected_delta
            incumbent_match = incumbent_delta == expected_delta
            changed = full_delta != incumbent_delta
            group = groups[key]
            group["rows"] += 1
            group[f"target.{int(target)}"] += 1
            group[f"changed.{int(changed)}"] += 1
            group[f"full_match.{int(full_match)}"] += 1
            group[f"incumbent_match.{int(incumbent_match)}"] += 1
            if changed:
                group[f"changed.target.{int(target)}"] += 1
                group[f"changed.full_match.{int(full_match)}"] += 1
            totals["rows"] += 1
            totals[f"target.{int(target)}"] += 1
            totals[f"changed.{int(changed)}"] += 1
            totals[f"full_match.{int(full_match)}"] += 1
            if target:
                diagnostics.append((
                    row["op"], row["branch"], theta,
                    "/".join(terminal_pair), "/".join(factor_pair),
                    incumbent_delta, full_delta, expected_delta,
                    int(full_match),
                ))

    ranked = sorted(
        groups.items(),
        key=lambda item: (
            -item[1]["changed.target.1"],
            item[1]["changed.target.0"],
            item[0],
        ),
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"physical_rows_sha256\t{digest(args.physical_rows)}\n")
        target.write("\n[counts]\n")
        for name, value in sorted(totals.items()):
            target.write(f"{name}\t{value}\n")
        target.write("\n[changed-endpoint history groups]\n")
        target.write(
            "branch\ttheta\tterminal_pair\tfactor_pair\trows\ttargets\t"
            "changed\tchanged_targets\tchanged_controls\t"
            "changed_full_matches\tchanged_full_misses\n"
        )
        for key, values in ranked:
            if not values["changed.1"]:
                continue
            branch, theta, terminal_pair, factor_pair = key
            target.write(
                f"{branch}\t{theta}\t{'/'.join(terminal_pair)}\t"
                f"{'/'.join(factor_pair)}\t{values['rows']}\t"
                f"{values['target.1']}\t{values['changed.1']}\t"
                f"{values['changed.target.1']}\t"
                f"{values['changed.target.0']}\t"
                f"{values['changed.full_match.1']}\t"
                f"{values['changed.full_match.0']}\n"
            )
        target.write("\n[target diagnostics]\n")
        target.write(
            "op\tbranch\ttheta\tterminal_pair\tfactor_pair\t"
            "incumbent_delta\tfull_delta\texpected_delta\tfull_match\n"
        )
        for entry in sorted(diagnostics):
            target.write("\t".join(map(str, entry)) + "\n")

    print(f"wrote {args.report} rows={totals['rows']}")


if __name__ == "__main__":
    main()
