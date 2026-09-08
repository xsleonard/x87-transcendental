#!/usr/bin/env python3
"""Audit whether h1095's residuals remain a threshold in signed Mreg.

For each cached hardware row, absolute retained deltas -1, 0, and +1 are
evaluated.  Rows that uniquely determine the physical R59 fire/clean state
are grouped by the same discrete digit cell used in the lower-binade proof.
Mixed cells are then checked for an exact monotone Mreg separator.  This is
a cached-label analysis and performs no hardware capture.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

from h1137_lower_binade_features import run_values


CELL = ("theta", "ce", "s4", "side", "low3", "dist", "rsh", "b1", "b2")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def signed128(text: str) -> int:
    value = int(text, 16)
    return value - (1 << 128) if value >> 127 else value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("force_minus1", type=Path)
    parser.add_argument("force_zero", type=Path)
    parser.add_argument("force_plus1", type=Path)
    parser.add_argument("row_output", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    for path in (args.row_output, args.report):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")

    with args.features.open(newline="") as source:
        reader = csv.DictReader(source, delimiter="\t")
        if reader.fieldnames is None:
            raise SystemExit("features have no header")
        columns = list(reader.fieldnames)
        rows = list(reader)
    paths = {-1: args.force_minus1, 0: args.force_zero, 1: args.force_plus1}
    for mode in ("rn", "rd", "ru", "rz"):
        mode_rows = [row for row in rows if row["mode"] == mode]
        values = {delta: run_values(path, mode, mode_rows)
                  for delta, path in paths.items()}
        for index, row in enumerate(mode_rows):
            allowed = [delta for delta in (-1, 0, 1)
                       if values[delta][index] == row["hw"]]
            row["target_allowed"] = ",".join(map(str, allowed))
            physical = set(allowed) & ({-1, 0} if int(row["theta"]) >= 0
                                       else {0, 1})
            row["physical_label"] = (
                str(int(next(iter(physical)) != 0)) if len(physical) == 1 else "")
            row["physical_status"] = (
                "constraining" if len(physical) == 1
                else "neutral" if len(physical) == 2
                else "unrepresented"
            )
            for delta in (-1, 0, 1):
                row[f"force_{delta}"] = values[delta][index]

    args.row_output.parent.mkdir(parents=True, exist_ok=True)
    output_columns = columns + [
        "target_allowed", "physical_label", "physical_status",
        "force_-1", "force_0", "force_1",
    ]
    with args.row_output.open("w", newline="") as target:
        writer = csv.DictWriter(target, output_columns, delimiter="\t",
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    groups = defaultdict(list)
    status = Counter()
    for row in rows:
        status[(row["label"], row["physical_status"])] += 1
        if row["physical_status"] != "constraining":
            continue
        key = tuple(int(row[field]) for field in CELL)
        groups[key].append((
            signed128(row["Mreg"]), int(row["physical_label"]), row,
        ))

    mixed = []
    nonmonotone = []
    for key, entries in sorted(groups.items()):
        fires = [item for item in entries if item[1]]
        cleans = [item for item in entries if not item[1]]
        if not fires or not cleans:
            continue
        theta = key[0]
        if theta >= 0:
            fire_edge = max(fires, key=lambda item: item[0])
            clean_edge = min(cleans, key=lambda item: item[0])
            separable = fire_edge[0] < clean_edge[0]
        else:
            clean_edge = max(cleans, key=lambda item: item[0])
            fire_edge = min(fires, key=lambda item: item[0])
            separable = clean_edge[0] < fire_edge[0]
        record = (key, len(entries), len(fires), len(cleans), separable,
                  fire_edge, clean_edge)
        mixed.append(record)
        if not separable:
            nonmonotone.append(record)

    with args.report.open("w") as target:
        target.write(f"features_sha256\t{digest(args.features)}\n")
        target.write(f"row_output_sha256\t{digest(args.row_output)}\n")
        for delta, path in paths.items():
            target.write(f"force_{delta}_sha256\t{digest(path)}\n")
        target.write(f"rows\t{len(rows)}\n")
        for key, count in sorted(status.items()):
            target.write(f"status {key[0]}/{key[1]}\t{count}\n")
        target.write(f"constraining_cells\t{len(groups)}\n")
        target.write(f"mixed_cells\t{len(mixed)}\n")
        target.write(f"nonmonotone_cells\t{len(nonmonotone)}\n")
        target.write("\n[nonmonotone]\n")
        target.write("cell\trows\tfire\tclean\tfire_M\tfire_label\tfire_op\t"
                     "clean_M\tclean_label\tclean_op\n")
        for key, count, fires, cleans, _, fire_edge, clean_edge in nonmonotone:
            target.write(
                f"{'/'.join(map(str, key))}\t{count}\t{fires}\t{cleans}\t"
                f"{fire_edge[0]}\t{fire_edge[2]['label']}\t{fire_edge[2]['op']}\t"
                f"{clean_edge[0]}\t{clean_edge[2]['label']}\t{clean_edge[2]['op']}\n"
            )
        target.write("\n[positive-rows]\n")
        target.write("op\ttheta\tcell\tMreg\ttarget_allowed\tstatus\tphysical_label\n")
        for row in rows:
            if row["label"] == "POS":
                key = tuple(row[field] for field in CELL)
                target.write(
                    f"{row['op']}\t{row['theta']}\t{'/'.join(key)}\t"
                    f"{signed128(row['Mreg'])}\t{row['target_allowed'] or '-'}\t"
                    f"{row['physical_status']}\t{row['physical_label'] or '-'}\n"
                )
    print(f"rows={len(rows)} cells={len(groups)} mixed={len(mixed)} "
          f"nonmonotone={len(nonmonotone)} report={args.report}")


if __name__ == "__main__":
    main()
