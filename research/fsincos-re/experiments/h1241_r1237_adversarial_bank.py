#!/usr/bin/env python3
"""Generate a no-repeat adversarial bank for the R1237 CPA/FADD rule.

The bank attacks the two boundaries used by R1237 rather than sampling more
ordinary operands: the exact-half excess q crosses -1/0 and 4/5, and the
selected bit of the P5-aligned four-bit product CPA crosses its incoming-carry
mux.  Candidates are deterministic neighbors of every causal R1200 operand.
Inputs already present in the immutable stage-A comb archives are excluded.

This is a software-only selection pass.  It does not execute x87 and it does
not use a hardware label when choosing an operand.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

from h1172_p5_cpa_predictor_mine import add_cpa_features, product_state
from h1184_upstream_halfway_audit import quantize, schedule
from h1210_stagea_residual_reframe import parse_dump, run
from h1222_r1200_enable_state import cut_fields
from h1224_r1200_named_wire_audit import read_classifications


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def generated(anchors: list[str], radius: int) -> dict[str, tuple[str, int]]:
    result: dict[str, tuple[str, int]] = {}
    for anchor in anchors:
        se, sig_text = anchor.split()
        sig0 = int(sig_text, 16)
        variants = set()
        for delta in range(1, radius + 1):
            variants.add(sig0 - delta)
            variants.add(sig0 + delta)
        for bit in range(48):
            variants.add(sig0 ^ (1 << bit))
        for width in range(4, 49, 4):
            mask = (1 << width) - 1
            prefix = sig0 & ~mask
            for suffix in (0, 1, mask >> 1, mask - 1, mask):
                variants.add(prefix | suffix)
        for sig in variants:
            if not (1 << 63) <= sig < (1 << 64) or sig == sig0:
                continue
            operand = f"{se} {sig:016x}"
            offset = sig - sig0
            prior = result.get(operand)
            if prior is None or abs(offset) < abs(prior[1]):
                result[operand] = (anchor, offset)
    return result


def primary_block(multiplicand: int, multiplier: int
                  ) -> tuple[int, int, int]:
    sum_vector, carry_vector, cut = product_state(multiplicand, multiplier)
    values: dict[str, int] = {}
    add_cpa_features(values, "P", sum_vector, carry_vector, cut)
    stem = "P.p5.w04.rel+0"
    sum0 = int(values[f"{stem}.sum0.b3"])
    selected = (multiplicand * multiplier >> 65) & 1
    incoming = int(values[f"{stem}.cin"])
    return sum0, selected, incoming


def event_for(operations, chain: str) -> dict[str, object]:
    stage = f"{chain}.add2"
    fields = cut_fields(operations[stage], 64)
    q = int(fields["half_delta"])
    increments = int(q > 0 or (q == 0 and (int(fields["retained"]) & 1)))
    if not -2 <= q <= 7:
        return {
            "stage": stage, "q": q, "retained_lsb": int(fields["retained"]) & 1,
            "increments": increments, "eligible": 0, "sum0_bit65": -1,
            "selected_bit65": -1, "incoming_carry": -1, "fires": 0,
            "categories": set(),
        }
    fourth = quantize(operations["fourth"], 67, False)
    first_add = quantize(operations[f"{chain}.add1"], 64, True)
    sum0, selected, incoming = primary_block(
        fourth.significand, first_add.significand)
    eligible = int(0 <= q <= 4 and increments)
    fires = int(eligible and ((q >> 2) & 1) == selected)
    categories = set()
    if -2 <= q <= 7:
        categories.add(f"{chain}.q{q:+d}")
    if eligible:
        categories.add(f"{chain}.eligible.fire{fires}")
        categories.add(f"q{q}.fire{fires}")
    if sum0 != selected:
        categories.add(f"{chain}.cpa_mux_changes_bit")
        if eligible:
            categories.add(f"cpa_mux_changes_bit.fire{fires}")
    if incoming:
        categories.add(f"{chain}.incoming_carry1")
    return {
        "stage": stage,
        "q": q,
        "retained_lsb": int(fields["retained"]) & 1,
        "increments": increments,
        "eligible": eligible,
        "sum0_bit65": sum0,
        "selected_bit65": selected,
        "incoming_carry": incoming,
        "fires": fires,
        "categories": categories,
    }


def stagea_members(capture_root: Path, operands: set[str]) -> set[str]:
    wanted = {operand.split()[1]: operand for operand in operands}
    found = set()
    for path in sorted(capture_root.glob("ties_comb*.txt")):
        with path.open() as source:
            for line in source:
                fields = line.split()
                if fields and fields[0].lower() in wanted:
                    found.add(wanted[fields[0].lower()])
    return found


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("changes", type=Path)
    parser.add_argument("capture_root", type=Path)
    parser.add_argument("output_prefix", type=Path)
    parser.add_argument("--radius", type=int, default=4096)
    parser.add_argument("--per-category", type=int, default=8)
    parser.add_argument("--chunk", type=int, default=5000)
    args = parser.parse_args()
    manifest_path = args.output_prefix.with_name(
        args.output_prefix.name + "_manifest.tsv")
    ops_path = args.output_prefix.with_name(args.output_prefix.name + "_ops.txt")
    report_path = args.output_prefix.with_name(
        args.output_prefix.name + "_report.txt")
    for path in (manifest_path, ops_path, report_path):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")

    anchors = sorted(read_classifications(args.changes))
    locations = generated(anchors, args.radius)
    operands = sorted(locations)
    candidates = []
    counts = Counter()
    for start in range(0, len(operands), args.chunk):
        chunk = operands[start:start + args.chunk]
        _, stderr = run(args.model, "rn", chunk, dump=True)
        rows = parse_dump(stderr, chunk)
        for row in rows:
            if "tc_f4_sig" not in row:
                counts["without_terminal_state"] += 1
                continue
            operations = schedule(row)
            for chain in ("negative", "positive"):
                event = event_for(operations, chain)
                counts[f"events.q.{event['q']}"] += 1
                if not event["categories"]:
                    continue
                anchor, offset = locations[row["op"]]
                candidates.append({
                    "op": row["op"], "anchor": anchor,
                    "offset": offset, **event,
                })
        print(
            f"scanned {min(start + len(chunk), len(operands))}/{len(operands)} "
            f"boundary_events={len(candidates)}", flush=True)

    existing = stagea_members(
        args.capture_root, {str(row["op"]) for row in candidates})
    counts["stagea_repeats_excluded"] = len(existing)
    fresh = [row for row in candidates if row["op"] not in existing]
    by_category = defaultdict(list)
    for row in fresh:
        for category in row["categories"]:
            by_category[category].append(row)
    selected: dict[tuple[str, str], dict[str, object]] = {}
    for category, rows in sorted(by_category.items()):
        rows.sort(key=lambda row: (
            abs(int(row["offset"])), row["anchor"], row["op"], row["stage"]))
        used_anchors = set()
        ordered = []
        for row in rows:
            if row["anchor"] not in used_anchors:
                ordered.append(row)
                used_anchors.add(row["anchor"])
        ordered.extend(row for row in rows if row not in ordered)
        for row in ordered[:args.per_category]:
            selected[row["op"], row["stage"]] = row

    output_rows = sorted(selected.values(), key=lambda row: (
        row["stage"], int(row["q"]), int(row["fires"]), row["op"]))
    columns = (
        "op", "stage", "anchor", "offset", "q", "retained_lsb",
        "increments", "eligible", "sum0_bit65", "selected_bit65",
        "incoming_carry", "fires", "categories",
    )
    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("x", newline="") as target, ops_path.open("x") as ops:
        writer = csv.DictWriter(target, columns, delimiter="\t")
        writer.writeheader()
        for row in output_rows:
            rendered = dict(row)
            rendered["categories"] = ",".join(sorted(row["categories"]))
            writer.writerow(rendered)
            ops.write(str(row["op"]) + "\n")

    with report_path.open("x") as target:
        target.write(f"model_sha256\t{digest(args.model)}\n")
        target.write(f"changes_sha256\t{digest(args.changes)}\n")
        target.write(f"capture_root\t{args.capture_root.resolve()}\n")
        target.write("selection_policy\tsoftware_only_no_hardware_labels\n")
        target.write("repeat_policy\texclude_every_stageA_comb_operand\n")
        target.write(f"anchors\t{len(anchors)}\n")
        target.write(f"generated_operands\t{len(operands)}\n")
        target.write(f"boundary_events\t{len(candidates)}\n")
        target.write(f"fresh_boundary_events\t{len(fresh)}\n")
        target.write(f"selected_events\t{len(output_rows)}\n")
        target.write(f"selected_operands\t{len({row['op'] for row in output_rows})}\n")
        target.write(f"manifest_sha256\t{digest(manifest_path)}\n")
        target.write(f"ops_sha256\t{digest(ops_path)}\n")
        target.write("\n[counts]\n")
        for name, value in sorted(counts.items()):
            target.write(f"{name}\t{value}\n")
        target.write("\n[category populations and selections]\n")
        for category in sorted(by_category):
            chosen = sum(category in row["categories"] for row in output_rows)
            target.write(f"{category}\t{len(by_category[category])}\t{chosen}\n")

    print(
        f"wrote {report_path} generated={len(operands)} "
        f"boundary={len(candidates)} fresh={len(fresh)} "
        f"selected={len(output_rows)}", flush=True)


if __name__ == "__main__":
    main()
