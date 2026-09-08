#!/usr/bin/env python3
"""Generate fresh software-only adversaries for the R1290 FADD word law.

The fast h1242 scanner (compiled with ``FULL_WORD=1``) exposes the exact
near-half distance q, the selected P5 CPA word W at columns 62..65, and the
67-bit product cut.  This pass scans symmetric intervals around every known
q=5..7 challenge, excludes all stage-A operands and explicit prior preimage
banks, then samples the actual structural boundaries of

    q <= 6, same_half(W, 2*q), W >= 2*q.

Selection never reads a hardware result and never executes an x87
instruction.  The output is suitable for a later one-shot hardware capture,
but is useful immediately as a coverage bank for implementation checks.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from h1241_r1237_adversarial_bank import stagea_members


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def read_anchors(path: Path) -> list[str]:
    with path.open(newline="") as source:
        rows = csv.DictReader(source, delimiter="\t")
        return sorted({row["op"].lower() for row in rows})


def read_exclusions(paths: list[Path]) -> set[str]:
    excluded = set()
    for path in paths:
        if not path.exists():
            continue
        with path.open() as source:
            for line in source:
                fields = line.lower().split()
                if len(fields) >= 2 and len(fields[0]) == 4:
                    excluded.add(f"{fields[0]} {fields[1]}")
    return excluded


def categories(row: dict[str, object]) -> set[str]:
    q = int(row["q"])
    word = int(row["word"])
    increment = int(row["increments"])
    threshold = 2 * q
    same_half = int(q >= 0 and ((word ^ threshold) & 8) == 0)
    compare_delta = word - threshold
    candidate = int(
        increment and 0 <= q <= 6 and same_half and compare_delta >= 0)
    result = {
        f"chain.{row['chain']}",
        f"q.{q:+d}",
        f"cut.{row['cut']}",
        f"increment.{increment}",
        f"candidate.{candidate}",
        f"word.{word:x}",
    }
    if q >= 0:
        result.add(f"same_half.{same_half}")
    if same_half and compare_delta in (-2, -1, 0, 1, 2):
        result.add(f"compare_delta.{compare_delta:+d}")
        result.add(
            f"q.{q:+d}.compare_delta.{compare_delta:+d}")
    if q in (5, 6):
        result.add(f"upper_extension.q{q}.candidate{candidate}")
    if q == 7:
        counterfactual = int(
            increment and same_half and compare_delta >= 0)
        result.add(f"saturation.q7.counterfactual{counterfactual}")
    if q in (3, 4) and word in (7, 8):
        result.add(f"sign_split.q{q}.word{word}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("scanner", type=Path)
    parser.add_argument("anchors", type=Path)
    parser.add_argument("capture_root", type=Path)
    parser.add_argument("output_prefix", type=Path)
    parser.add_argument("--exclude", action="append", type=Path, default=[])
    parser.add_argument("--radius", type=int, default=10_000_000)
    parser.add_argument("--per-category", type=int, default=12)
    args = parser.parse_args()

    manifest_path = args.output_prefix.with_name(
        args.output_prefix.name + "_manifest.tsv")
    ops_path = args.output_prefix.with_name(args.output_prefix.name + "_ops.txt")
    report_path = args.output_prefix.with_name(
        args.output_prefix.name + "_report.txt")
    for path in (manifest_path, ops_path, report_path):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")

    anchors = read_anchors(args.anchors)
    scanned: dict[tuple[str, str], dict[str, object]] = {}
    counts = Counter()
    for ordinal, anchor in enumerate(anchors, 1):
        se, sig_text = anchor.split()
        if se != "3ffc":
            counts["non_3ffc_anchor_skipped"] += 1
            continue
        sig = int(sig_text, 16)
        start = max(1 << 63, sig - args.radius)
        end = min((1 << 64) - 1, sig + args.radius)
        count = end - start + 1
        process = subprocess.run(
            [str(args.scanner.resolve()), f"{start:016x}", str(count)],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=True,
        )
        for line in process.stdout.splitlines():
            fields = line.split()
            if len(fields) != 9:
                raise RuntimeError(f"bad FULL_WORD scanner row: {line}")
            (input_sig, chain, q, retained_lsb, increments, bit65, old_fire,
             word, cut) = fields
            operand = f"3ffc {input_sig}"
            key = (operand, chain)
            row: dict[str, object] = {
                "op": operand,
                "chain": chain,
                "q": int(q),
                "retained_lsb": int(retained_lsb),
                "increments": int(increments),
                "product_bit65": int(bit65),
                "r1237_fire": int(old_fire),
                "word": int(word, 16),
                "cut": int(cut),
                "nearest_anchor": anchor,
                "anchor_offset": int(input_sig, 16) - sig,
            }
            row["categories"] = categories(row)
            prior = scanned.get(key)
            if prior is None or abs(int(row["anchor_offset"])) < abs(
                    int(prior["anchor_offset"])):
                scanned[key] = row
        counts["scanner_intervals"] += 1
        counts["scanner_input_significands"] += count
        print(
            f"scanned {ordinal}/{len(anchors)} intervals "
            f"events={len(scanned)}", flush=True)

    stagea = stagea_members(
        args.capture_root, {str(row["op"]) for row in scanned.values()})
    explicit_excluded = read_exclusions(args.exclude)
    counts["stagea_operands_excluded"] = len(stagea)
    counts["explicit_operands_excluded"] = len(
        explicit_excluded & {str(row["op"]) for row in scanned.values()})
    fresh = [
        row for row in scanned.values()
        if row["op"] not in stagea and row["op"] not in explicit_excluded
    ]

    by_category: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in fresh:
        for category in row["categories"]:
            by_category[category].append(row)
    selected: dict[tuple[str, str], dict[str, object]] = {}
    for category, rows in sorted(by_category.items()):
        rows.sort(key=lambda row: (
            abs(int(row["anchor_offset"])), row["nearest_anchor"],
            row["op"], row["chain"],
        ))
        used_anchors = set()
        ordered = []
        for row in rows:
            if row["nearest_anchor"] not in used_anchors:
                ordered.append(row)
                used_anchors.add(row["nearest_anchor"])
        ordered.extend(row for row in rows if row not in ordered)
        for row in ordered[:args.per_category]:
            selected[(str(row["op"]), str(row["chain"]))] = row

    output_rows = sorted(selected.values(), key=lambda row: (
        int(row["q"]), int(row["word"]), int(row["cut"]),
        row["chain"], row["op"],
    ))
    columns = (
        "op", "chain", "q", "word", "cut", "retained_lsb",
        "increments", "product_bit65", "r1237_fire", "candidate_fire",
        "same_half", "compare_delta", "nearest_anchor", "anchor_offset",
        "categories",
    )
    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("x", newline="") as target, ops_path.open("x") as ops:
        writer = csv.DictWriter(target, columns, delimiter="\t")
        writer.writeheader()
        seen_ops = set()
        for row in output_rows:
            rendered = dict(row)
            q = int(row["q"])
            word = int(row["word"])
            threshold = 2 * q
            same_half = int(q >= 0 and ((word ^ threshold) & 8) == 0)
            compare_delta = word - threshold
            rendered.update({
                "word": f"{word:x}",
                "same_half": same_half,
                "compare_delta": compare_delta,
                "candidate_fire": int(
                    int(row["increments"]) and 0 <= q <= 6
                    and same_half and compare_delta >= 0),
                "categories": ",".join(sorted(row["categories"])),
            })
            writer.writerow(rendered)
            if row["op"] not in seen_ops:
                ops.write(str(row["op"]) + "\n")
                seen_ops.add(row["op"])

    with report_path.open("x") as target:
        target.write(f"scanner_sha256\t{digest(args.scanner)}\n")
        target.write(f"anchors_sha256\t{digest(args.anchors)}\n")
        target.write("selection_policy\tsoftware_only_no_hardware_labels\n")
        target.write("hardware_execution\tnone\n")
        target.write(f"radius\t{args.radius}\n")
        target.write(f"anchors\t{len(anchors)}\n")
        target.write(f"near_half_events\t{len(scanned)}\n")
        target.write(f"fresh_events\t{len(fresh)}\n")
        target.write(f"selected_events\t{len(output_rows)}\n")
        target.write(f"selected_operands\t{len(set(row['op'] for row in output_rows))}\n")
        target.write(f"manifest_sha256\t{digest(manifest_path)}\n")
        target.write(f"ops_sha256\t{digest(ops_path)}\n")
        target.write("\n[counts]\n")
        for name, value in sorted(counts.items()):
            target.write(f"{name}\t{value}\n")
        target.write("\n[category populations and selections]\n")
        for category in sorted(by_category):
            chosen = sum(
                category in row["categories"] for row in output_rows)
            target.write(
                f"{category}\t{len(by_category[category])}\t{chosen}\n")

    print(
        f"wrote {report_path} events={len(scanned)} fresh={len(fresh)} "
        f"selected={len(output_rows)}", flush=True,
    )


if __name__ == "__main__":
    main()
