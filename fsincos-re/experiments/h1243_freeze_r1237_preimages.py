#!/usr/bin/env python3
"""Freeze a software-only adversarial preimage bank for R1237.

For every causal R1200 anchor, scan a fixed dense interval centered on the
anchor and collect exact preimages of the second-Horner-FADD halfway surface.
The C generator supplies only arithmetic state; selection never consults a
hardware result.  Operands already present in any stage-A comb archive are
excluded so a future hardware comparison, if desired, would contain no
repeat inputs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from h1224_r1200_named_wire_audit import read_classifications
from h1241_r1237_adversarial_bank import stagea_members


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def categories(row: dict[str, object]) -> set[str]:
    q = int(row["q"])
    chain = str(row["chain"])
    increments = int(row["increments"])
    bit65 = int(row["product_bit65"])
    fires = int(row["r1237_fires"])
    result = {
        f"q.{q:+d}", f"chain.{chain}", f"increments.{increments}",
        f"product_bit65.{bit65}", f"r1237_fires.{fires}",
        f"chain_q.{chain}.{q:+d}",
    }
    if q == 0:
        result.add(f"exact_half.retained_lsb.{int(row['retained_lsb'])}")
    if 0 <= q <= 4 and increments:
        result.add(f"eligible.bit65.{bit65}.fires.{fires}")
        result.add(f"eligible.q.{q:+d}.bit65.{bit65}")
    if q in (-1, 0):
        result.add("lower_gate_boundary")
    if q in (4, 5):
        result.add("upper_gate_boundary")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("scanner", type=Path)
    parser.add_argument("changes", type=Path)
    parser.add_argument("capture_root", type=Path)
    parser.add_argument("output_prefix", type=Path)
    parser.add_argument("--radius", type=int, default=5_000_000)
    parser.add_argument("--per-category", type=int, default=8)
    args = parser.parse_args()

    manifest_path = args.output_prefix.with_name(
        args.output_prefix.name + "_manifest.tsv")
    operands_path = args.output_prefix.with_name(
        args.output_prefix.name + "_ops.txt")
    raw_path = args.output_prefix.with_name(
        args.output_prefix.name + "_raw.tsv")
    report_path = args.output_prefix.with_name(
        args.output_prefix.name + "_report.txt")
    for path in (manifest_path, operands_path, raw_path, report_path):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")

    classifications = read_classifications(args.changes)
    anchors = sorted(classifications)
    rows_by_key: dict[tuple[str, str], dict[str, object]] = {}
    intervals = []
    for position, anchor in enumerate(anchors, 1):
        exponent, significand_text = anchor.split()
        if exponent != "3ffc":
            raise RuntimeError(f"unsupported anchor exponent: {anchor}")
        significand = int(significand_text, 16)
        start = max(1 << 63, significand - args.radius)
        stop = min(1 << 64, significand + args.radius + 1)
        count = stop - start
        intervals.append((anchor, start, count))
        completed = subprocess.run(
            [str(args.scanner.resolve()), f"{start:016x}", str(count)],
            check=True, capture_output=True, text=True,
        )
        for line in completed.stdout.splitlines():
            fields = line.split()
            if len(fields) != 7:
                raise RuntimeError(f"malformed scanner output: {line!r}")
            operand = f"3ffc {fields[0].lower()}"
            row: dict[str, object] = {
                "op": operand,
                "chain": fields[1],
                "q": int(fields[2]),
                "retained_lsb": int(fields[3]),
                "increments": int(fields[4]),
                "product_bit65": int(fields[5]),
                "r1237_fires": int(fields[6]),
                "nearest_anchor": anchor,
                "anchor_offset": int(fields[0], 16) - significand,
            }
            key = operand, str(row["chain"])
            previous = rows_by_key.get(key)
            if previous is None or abs(int(row["anchor_offset"])) < abs(
                    int(previous["anchor_offset"])):
                rows_by_key[key] = row
        print(
            f"scanned {position}/{len(anchors)} anchors "
            f"events={len(rows_by_key)}", flush=True)

    all_rows = sorted(rows_by_key.values(), key=lambda row: (
        row["op"], row["chain"]))
    repeats = stagea_members(
        args.capture_root, {str(row["op"]) for row in all_rows})
    fresh_rows = [row for row in all_rows if row["op"] not in repeats]
    by_category: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in fresh_rows:
        row["categories"] = categories(row)
        for category in row["categories"]:
            by_category[category].append(row)

    selected: dict[tuple[str, str], dict[str, object]] = {}
    for category, rows in sorted(by_category.items()):
        ordered = sorted(rows, key=lambda row: (
            abs(int(row["anchor_offset"])), row["nearest_anchor"],
            row["op"], row["chain"]))
        used_anchors = set()
        diverse = []
        for row in ordered:
            if row["nearest_anchor"] not in used_anchors:
                diverse.append(row)
                used_anchors.add(row["nearest_anchor"])
        diverse.extend(row for row in ordered if row not in diverse)
        for row in diverse[:args.per_category]:
            selected[str(row["op"]), str(row["chain"])] = row

    selected_rows = sorted(selected.values(), key=lambda row: (
        int(row["q"]), row["chain"], int(row["product_bit65"]), row["op"]))
    columns = (
        "op", "chain", "q", "retained_lsb", "increments",
        "product_bit65", "r1237_fires", "nearest_anchor",
        "anchor_offset", "categories",
    )
    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    with raw_path.open("x", newline="") as target:
        writer = csv.DictWriter(target, columns, delimiter="\t")
        writer.writeheader()
        for row in fresh_rows:
            rendered = dict(row)
            rendered["categories"] = ",".join(sorted(row["categories"]))
            writer.writerow(rendered)
    with manifest_path.open("x", newline="") as target:
        writer = csv.DictWriter(target, columns, delimiter="\t")
        writer.writeheader()
        for row in selected_rows:
            rendered = dict(row)
            rendered["categories"] = ",".join(sorted(row["categories"]))
            writer.writerow(rendered)
    with operands_path.open("x") as target:
        for operand in sorted({str(row["op"]) for row in selected_rows}):
            target.write(operand + "\n")

    counts = Counter()
    for row in fresh_rows:
        counts[f"q.{int(row['q']):+d}"] += 1
        counts[f"chain.{row['chain']}"] += 1
        counts[f"product_bit65.{row['product_bit65']}"] += 1
        counts[f"r1237_fires.{row['r1237_fires']}"] += 1
    with report_path.open("x") as target:
        target.write(f"scanner_sha256\t{digest(args.scanner)}\n")
        target.write(f"changes_sha256\t{digest(args.changes)}\n")
        target.write("selection_policy\tsoftware_only_no_hardware_labels\n")
        target.write("capture_policy\tno_x87_execution\n")
        target.write("repeat_policy\texclude_every_stageA_comb_operand\n")
        target.write(f"anchors\t{len(anchors)}\n")
        target.write(f"radius\t{args.radius}\n")
        target.write(f"raw_interval_operands\t{sum(count for _, _, count in intervals)}\n")
        target.write(f"unique_boundary_events\t{len(all_rows)}\n")
        target.write(f"stageA_repeats_excluded\t{len(repeats)}\n")
        target.write(f"fresh_boundary_events\t{len(fresh_rows)}\n")
        target.write(f"selected_events\t{len(selected_rows)}\n")
        target.write(
            f"selected_operands\t{len({row['op'] for row in selected_rows})}\n")
        target.write(f"raw_sha256\t{digest(raw_path)}\n")
        target.write(f"manifest_sha256\t{digest(manifest_path)}\n")
        target.write(f"operands_sha256\t{digest(operands_path)}\n")
        target.write("\n[counts]\n")
        for name, value in sorted(counts.items()):
            target.write(f"{name}\t{value}\n")
        target.write("\n[category populations and selections]\n")
        for category, rows in sorted(by_category.items()):
            chosen = sum(
                category in row["categories"] for row in selected_rows)
            target.write(f"{category}\t{len(rows)}\t{chosen}\n")

    print(
        f"wrote {report_path} raw={len(all_rows)} fresh={len(fresh_rows)} "
        f"selected={len(selected_rows)}", flush=True)


if __name__ == "__main__":
    main()
