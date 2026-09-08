#!/usr/bin/env python3
"""Generate fresh preimages that split the ten h1300 P5-tree wires.

The DEEP_TREE h1242 scanner emits a ten-bit mask for the named wires that
still agree on every cached/high-q label after R1290, R1297, and R1299 were
falsified.  This pass scans around all q=5/6/7 anchors, keeps only q=5/6 RN
increment events with the R1237 product-bit relation, excludes every staged
or previously selected operand, and freezes every remaining mask class.

No x87 instruction or hardware label is consulted here.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import subprocess
from collections import Counter
from pathlib import Path

from h1241_r1237_adversarial_bank import stagea_members


OPERAND = re.compile(r"\b([0-9a-fA-F]{4})[ :\t]+([0-9a-fA-F]{16})\b")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def operands_in(path: Path) -> set[str]:
    result = set()
    if path.is_dir():
        paths = sorted(path.glob("*_inputs.txt"))
    else:
        paths = [path]
    for source in paths:
        for match in OPERAND.finditer(source.read_text()):
            result.add(f"{match.group(1).lower()} {match.group(2).lower()}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("scanner", type=Path)
    parser.add_argument("capture_root", type=Path)
    parser.add_argument("output_prefix", type=Path)
    parser.add_argument("--anchor-file", action="append", type=Path,
                        required=True)
    parser.add_argument("--exclude", action="append", type=Path, default=[])
    parser.add_argument("--radius", type=int, default=10_000_000)
    args = parser.parse_args()

    manifest_path = args.output_prefix.with_name(
        args.output_prefix.name + "_manifest.tsv")
    ops_path = args.output_prefix.with_name(args.output_prefix.name + "_ops.txt")
    report_path = args.output_prefix.with_name(
        args.output_prefix.name + "_report.txt")
    for path in (manifest_path, ops_path, report_path):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")

    anchors = set()
    for path in args.anchor_file:
        anchors.update(operands_in(path))
    anchors = sorted(op for op in anchors if op.startswith("3ffc "))
    if not anchors:
        raise SystemExit("no 3ffc anchors")

    scanned: dict[tuple[str, str], dict[str, object]] = {}
    counts = Counter()
    for ordinal, anchor in enumerate(anchors, 1):
        _, sig_text = anchor.split()
        sig = int(sig_text, 16)
        start = max(1 << 63, sig - args.radius)
        end = min((1 << 64) - 1, sig + args.radius)
        process = subprocess.run(
            [str(args.scanner.resolve()), f"{start:016x}",
             str(end - start + 1)],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=True,
        )
        for line in process.stdout.splitlines():
            fields = line.split()
            if len(fields) != 10:
                raise RuntimeError(f"bad DEEP_TREE scanner row: {line}")
            (input_sig, chain, q_text, retained_lsb, increments, bit65,
             old_fire, word, cut, mask) = fields
            q = int(q_text)
            if q not in (5, 6) or increments != "1" or bit65 != "1":
                continue
            operand = f"3ffc {input_sig}"
            key = (operand, chain)
            row: dict[str, object] = {
                "op": operand,
                "chain": chain,
                "q": q,
                "word": word,
                "cut": int(cut),
                "retained_lsb": int(retained_lsb),
                "increments": int(increments),
                "product_bit65": int(bit65),
                "r1237_fire": int(old_fire),
                "tree_mask": int(mask, 16),
                "nearest_anchor": anchor,
                "anchor_offset": int(input_sig, 16) - sig,
            }
            prior = scanned.get(key)
            if prior is None or abs(int(row["anchor_offset"])) < abs(
                    int(prior["anchor_offset"])):
                scanned[key] = row
        counts["scanner_intervals"] += 1
        counts["scanner_input_significands"] += end - start + 1
        print(
            f"scanned {ordinal}/{len(anchors)} high-events={len(scanned)}",
            flush=True,
        )

    candidates = {str(row["op"]) for row in scanned.values()}
    excluded = set()
    for path in args.exclude:
        excluded.update(operands_in(path))
    staged = stagea_members(args.capture_root, candidates)
    fresh = [
        row for row in scanned.values()
        if row["op"] not in excluded and row["op"] not in staged
    ]
    fresh.sort(key=lambda row: (
        int(row["tree_mask"]), int(row["q"]), int(row["cut"]),
        row["chain"], abs(int(row["anchor_offset"])), row["op"],
    ))

    columns = (
        "op", "chain", "q", "word", "cut", "retained_lsb",
        "increments", "product_bit65", "r1237_fire", "tree_mask",
        "nearest_anchor", "anchor_offset",
    )
    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("x", newline="") as target, ops_path.open("x") as ops:
        writer = csv.DictWriter(target, columns, delimiter="\t")
        writer.writeheader()
        seen_ops = set()
        for row in fresh:
            rendered = dict(row)
            rendered["tree_mask"] = f"{int(row['tree_mask']):03x}"
            writer.writerow(rendered)
            if row["op"] not in seen_ops:
                ops.write(str(row["op"]) + "\n")
                seen_ops.add(row["op"])

    populations = Counter(int(row["tree_mask"]) for row in fresh)
    pair_splits = Counter()
    for left in range(10):
        for right in range(left + 1, 10):
            pair_splits[left, right] = sum(
                ((int(row["tree_mask"]) >> left) & 1)
                != ((int(row["tree_mask"]) >> right) & 1)
                for row in fresh)

    with report_path.open("x") as target:
        target.write(f"scanner_sha256\t{digest(args.scanner)}\n")
        for index, path in enumerate(args.anchor_file):
            target.write(f"anchor_sha256.{index}\t{digest(path)}\n")
        target.write("selection_policy\tsoftware_only_no_hardware_labels\n")
        target.write("hardware_execution\tnone\n")
        target.write(f"radius\t{args.radius}\n")
        target.write(f"anchors\t{len(anchors)}\n")
        target.write(f"high_events\t{len(scanned)}\n")
        target.write(f"stagea_excluded\t{len(staged)}\n")
        target.write(f"explicit_excluded\t{len(candidates & excluded)}\n")
        target.write(f"fresh_events\t{len(fresh)}\n")
        target.write(f"fresh_operands\t{len(set(row['op'] for row in fresh))}\n")
        target.write(f"tree_masks\t{len(populations)}\n")
        target.write(f"manifest_sha256\t{digest(manifest_path)}\n")
        target.write(f"ops_sha256\t{digest(ops_path)}\n")
        target.write("\n[tree-mask populations]\n")
        for mask, count in sorted(populations.items()):
            target.write(f"{mask:03x}\t{count}\n")
        target.write("\n[pairwise wire separators]\n")
        for (left, right), count in sorted(pair_splits.items()):
            target.write(f"wire{left}.wire{right}\t{count}\n")
        target.write("\n[counts]\n")
        for name, value in sorted(counts.items()):
            target.write(f"{name}\t{value}\n")

    print(
        f"wrote {report_path}: high={len(scanned)} fresh={len(fresh)} "
        f"masks={len(populations)}", flush=True)


if __name__ == "__main__":
    main()
