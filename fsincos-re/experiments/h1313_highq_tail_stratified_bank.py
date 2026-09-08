#!/usr/bin/env python3
"""Freeze fresh high-q separators across the exact FMUL tail coordinate.

The h1312 scanner emits exact discarded-product remainders for the second
negative Horner multiply.  This generator scans merged neighborhoods around
the causally labelled high-q operands, excludes every cached stage-A operand
and explicit prior capture, and retains only points where the predecessor and
q<=7 factor models differ architecturally.  One point nearest the center of
each occupied (q, product-cut, tail top-nibble) stratum is selected.

Selection is entirely software-side and does not read or execute hardware.
The uniform hexadecimal tail partition is fixed independently of the known
positive/negative labels, so the output is an adversarial bank rather than a
fit to the three newly observed positive operands.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from h1210_stagea_residual_reframe import run
from h1241_r1237_adversarial_bank import stagea_members


MODES = ("rn", "rd", "ru")
OPERAND = re.compile(r"\b([0-9a-fA-F]{4})[ :\t]+([0-9a-fA-F]{16})\b")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def operands_in(path: Path) -> set[str]:
    paths = sorted(path.glob("*_inputs.txt")) if path.is_dir() else [path]
    result = set()
    for source in paths:
        for match in OPERAND.finditer(source.read_text()):
            result.add(f"{match.group(1).lower()} {match.group(2).lower()}")
    return result


def anchors(causal_legs: Path, sibling_labels: Path) -> list[int]:
    result = set()
    with causal_legs.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            se, significand = row["op"].lower().split()
            if se == "3ffc":
                result.add(int(significand, 16))
    with sibling_labels.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            result.add(int(row["residual66"], 16))
    return sorted(result)


def merged_intervals(values: list[int], radius: int) -> list[tuple[int, int]]:
    minimum = 1 << 63
    maximum = (1 << 64) - 1
    result: list[tuple[int, int]] = []
    for value in values:
        first = max(minimum, value - radius)
        last = min(maximum, value + radius)
        if result and first <= result[-1][1] + 1:
            result[-1] = result[-1][0], max(last, result[-1][1])
        else:
            result.append((first, last))
    return result


def scan_interval(scanner: Path, interval: tuple[int, int]
                  ) -> list[dict[str, object]]:
    first, last = interval
    process = subprocess.run(
        [str(scanner.resolve()), f"{first:016x}", str(last - first + 1)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    rows = []
    for line in process.stdout.splitlines():
        fields = line.split()
        if len(fields) != 10:
            raise RuntimeError(f"bad h1312 scanner row: {line}")
        (input_sig, chain, q_text, retained_lsb, increments, product_bit65,
         r1237_fire, word, cut_text, remainder) = fields
        q = int(q_text)
        cut = int(cut_text)
        if (
            chain != "negative"
            or q not in (5, 6, 7)
            or increments != "1"
            or int(product_bit65) != ((q >> 2) & 1)
        ):
            continue
        tail = int(remainder, 16)
        rows.append({
            "op": f"3ffc {input_sig.lower()}",
            "q": q,
            "cut": cut,
            "retained_lsb": int(retained_lsb),
            "product_bit65": int(product_bit65),
            "r1237_fire": int(r1237_fire),
            "word": word.lower(),
            "remainder": tail,
            "tail_top4": (tail << 4) >> cut,
            "tail_top8": (tail << 8) >> cut,
            "tail_leading_zeros": cut - tail.bit_length() if tail else cut,
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("scanner", type=Path)
    parser.add_argument("predecessor", type=Path)
    parser.add_argument("wide", type=Path)
    parser.add_argument("causal_legs", type=Path)
    parser.add_argument("sibling_labels", type=Path)
    parser.add_argument("capture_root", type=Path)
    parser.add_argument("output_prefix", type=Path)
    parser.add_argument("--exclude", action="append", type=Path, default=[])
    parser.add_argument("--radius", type=int, default=50_000_000)
    args = parser.parse_args()
    manifest_path = args.output_prefix.with_name(
        args.output_prefix.name + "_manifest.tsv")
    report_path = args.output_prefix.with_name(
        args.output_prefix.name + "_report.txt")
    for output_path in (manifest_path, report_path):
        if output_path.exists():
            raise SystemExit(f"refusing to overwrite {output_path}")

    anchor_values = anchors(args.causal_legs, args.sibling_labels)
    intervals = merged_intervals(anchor_values, args.radius)
    with ThreadPoolExecutor(max_workers=min(4, len(intervals))) as executor:
        scanned_lists = list(executor.map(
            lambda interval: scan_interval(args.scanner, interval), intervals))
    scanned = {}
    for rows in scanned_lists:
        for row in rows:
            scanned[str(row["op"])] = row
    candidates = set(scanned)

    excluded = set()
    for path in args.exclude:
        excluded.update(operands_in(path))
    stagea = stagea_members(args.capture_root, candidates)
    fresh_rows = [
        row for operand, row in scanned.items()
        if operand not in excluded and operand not in stagea
    ]
    fresh_rows.sort(key=lambda row: str(row["op"]))

    operands = [str(row["op"]) for row in fresh_rows]
    outputs = {}
    for mode in MODES:
        predecessor_values, _ = run(args.predecessor, mode, operands)
        wide_values, _ = run(args.wide, mode, operands)
        outputs[mode, "predecessor"] = predecessor_values
        outputs[mode, "wide"] = wide_values
    separators = []
    for index, row in enumerate(fresh_rows):
        changed_modes = [
            mode for mode in MODES
            if outputs[mode, "predecessor"][index]
            != outputs[mode, "wide"][index]
        ]
        if not changed_modes:
            continue
        row = dict(row)
        row["changed_modes"] = ",".join(changed_modes)
        for mode in MODES:
            row[f"{mode}_predecessor"] = outputs[mode, "predecessor"][index]
            row[f"{mode}_wide"] = outputs[mode, "wide"][index]
        separators.append(row)

    by_stratum: dict[tuple[int, int, int], list[dict[str, object]]] = {}
    for row in separators:
        key = int(row["q"]), int(row["cut"]), int(row["tail_top4"])
        by_stratum.setdefault(key, []).append(row)
    selected = []
    for (q, cut, top4), rows in sorted(by_stratum.items()):
        center_numerator = 2 * top4 + 1
        rows.sort(key=lambda row: (
            abs((int(row["remainder"]) << 5)
                - center_numerator * (1 << int(row["cut"]))),
            str(row["op"]),
        ))
        selected.append(rows[0])
    selected.sort(key=lambda row: (
        int(row["q"]), int(row["cut"]), int(row["tail_top4"]),
        str(row["op"]),
    ))
    if not selected:
        raise RuntimeError("no fresh architectural separators")

    columns = (
        "op", "q", "cut", "retained_lsb", "product_bit65",
        "r1237_fire", "word", "remainder", "tail_top4", "tail_top8",
        "tail_leading_zeros", "changed_modes",
        "rn_predecessor", "rn_wide", "rd_predecessor", "rd_wide",
        "ru_predecessor", "ru_wide",
    )
    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("x", newline="") as target:
        writer = csv.DictWriter(target, columns, delimiter="\t")
        writer.writeheader()
        for row in selected:
            rendered = dict(row)
            rendered["remainder"] = f"{int(row['remainder']):016x}"
            rendered["tail_top4"] = f"{int(row['tail_top4']):x}"
            rendered["tail_top8"] = f"{int(row['tail_top8']):02x}"
            writer.writerow(rendered)

    counts = Counter()
    for row in selected:
        counts[f"q.{row['q']}.cut.{row['cut']}"] += 1
        counts[f"q.{row['q']}.cut.{row['cut']}.top4.{int(row['tail_top4']):x}"] += 1
        for mode in str(row["changed_modes"]).split(","):
            counts[f"mode.{mode}"] += 1
    with report_path.open("x") as target:
        target.write(f"scanner_sha256\t{digest(args.scanner)}\n")
        target.write(f"predecessor_sha256\t{digest(args.predecessor)}\n")
        target.write(f"wide_sha256\t{digest(args.wide)}\n")
        target.write(f"causal_legs_sha256\t{digest(args.causal_legs)}\n")
        target.write(f"sibling_labels_sha256\t{digest(args.sibling_labels)}\n")
        target.write("selection_policy\tuniform_q_cut_tail_top4_strata\n")
        target.write("hardware_execution\tnone\n")
        target.write(f"radius\t{args.radius}\n")
        target.write(f"anchors\t{len(anchor_values)}\n")
        target.write(f"merged_intervals\t{len(intervals)}\n")
        target.write(
            f"scanner_input_significands\t"
            f"{sum(last-first+1 for first, last in intervals)}\n")
        target.write(f"high_events\t{len(scanned)}\n")
        target.write(f"explicit_excluded\t{len(candidates & excluded)}\n")
        target.write(f"stagea_excluded\t{len(stagea)}\n")
        target.write(f"fresh_high_events\t{len(fresh_rows)}\n")
        target.write(f"architectural_separators\t{len(separators)}\n")
        target.write(f"selected_operands\t{len(selected)}\n")
        target.write(f"manifest_sha256\t{digest(manifest_path)}\n")
        target.write("\n[counts]\n")
        for name, count in sorted(counts.items()):
            target.write(f"{name}\t{count}\n")

    print(
        f"wrote {report_path}: scanned={sum(last-first+1 for first,last in intervals)} "
        f"events={len(scanned)} separators={len(separators)} "
        f"selected={len(selected)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
