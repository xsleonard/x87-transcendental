#!/usr/bin/env python3
"""Descend below R1290's falsified four-bit product word.

R1237 is exact on the cached q=0..4 causal set.  R1295 supplies five fresh
q=5 operands, and the cached R1281 widening experiment supplies the q=6/7
frontier.  This audit asks whether one fixed named wire in the literal P5
radix-8/4:2 multiplier tree qualifies the *same* q-bit/product-bit recurrence
above q=4.  It does not synthesize operand thresholds or lookup tables.

The output is only a candidate generator.  Any exact wire found on this small
frontier still requires independently generated preimages and blind labels.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

from h1100_p5_multiplier_tree import multiplier_tree
from h1172_p5_cpa_predictor_mine import add_cpa_features
from h1184_upstream_halfway_audit import quantize, schedule
from h1210_stagea_residual_reframe import parse_dump, run
from h1222_r1200_enable_state import scalar_schedule
from h1224_r1200_named_wire_audit import read_classifications


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def bit(value: int, position: int) -> int:
    return (value >> position) & 1


def product_for(row: dict[str, str], stage: str):
    operations = schedule(row)
    chain = stage.split(".", 1)[0]
    fourth = quantize(operations["fourth"], 67, False)
    first_add = quantize(operations[f"{chain}.add1"], 64, True)
    state = multiplier_tree(fourth.significand, first_add.significand)
    product = fourth.significand * first_add.significand
    if (state["sum"] + state["carry"]) & ((1 << 131) - 1) != product:
        raise RuntimeError(f"tree/product mismatch for {row['op']}")
    return fourth.significand, first_add.significand, product, state


def event(row: dict[str, str], stage: str) -> dict[str, object]:
    _, adds = scalar_schedule(row, False)
    fields = adds[stage]
    q = int(fields["half_delta"])
    # retained/remainder are reconstructed exact integers in cut_fields.
    remainder = int(fields["remainder"])
    denominator = int(fields["denominator"])
    half = denominator >> 1
    retained = int(fields["retained"])
    increments = int(remainder > half or (remainder == half and retained & 1))
    multiplicand, multiplier, product, state = product_for(row, stage)
    return {
        "stage": stage,
        "q": q,
        "increments": increments,
        "multiplicand": multiplicand,
        "multiplier": multiplier,
        "product": product,
        "state": state,
    }


def named_features(item: dict[str, object]) -> dict[str, int]:
    state = item["state"]
    product = int(item["product"])
    sum_vector = int(state["sum"])
    carry_vector = int(state["carry"])
    cut = product.bit_length() - 67
    values: dict[str, int] = {}

    carry = 0
    for position in range(131):
        a = bit(sum_vector, position)
        b = bit(carry_vector, position)
        values[f"final.sum.b{position}"] = a
        values[f"final.carry.b{position}"] = b
        values[f"final.generate.b{position}"] = a & b
        values[f"final.propagate.b{position}"] = a ^ b
        values[f"final.cin.b{position}"] = carry
        values[f"product.b{position}"] = bit(product, position)
        carry = (a & b) | ((a ^ b) & carry)

    for node_name, node in state["nodes"].items():
        for bus_name in ("sum", "carry", "first_sum", "first_carry"):
            bus = int(node[bus_name])
            for position in range(131):
                values[f"{node_name}.{bus_name}.b{position}"] = bit(
                    bus, position)

    for row_number, row_value in enumerate(state["rows"]):
        for position in range(131):
            values[f"row{row_number:02d}.b{position}"] = bit(
                int(row_value), position)
    for row_number, digit in enumerate(state["digits"]):
        values[f"digit{row_number:02d}.negative"] = int(digit < 0)
        values[f"digit{row_number:02d}.nonzero"] = int(digit != 0)
        for magnitude in range(5):
            values[f"digit{row_number:02d}.abs{magnitude}"] = int(
                abs(digit) == magnitude)

    add_cpa_features(values, "P", sum_vector, carry_vector, cut)
    return values


def identify_widening_event(row: dict[str, str]) -> dict[str, object]:
    _, adds = scalar_schedule(row, False)
    candidates = []
    for stage, fields in adds.items():
        q = int(fields["half_delta"])
        if not 5 <= q <= 7:
            continue
        item = event(row, stage)
        if not int(item["increments"]):
            continue
        if bit(int(item["product"]), 65) != ((q >> 2) & 1):
            continue
        candidates.append(item)
    if len(candidates) != 1:
        raise RuntimeError(
            f"expected one q=5..7 widening event for {row['op']}: "
            f"{[(item['stage'], item['q']) for item in candidates]}")
    return candidates[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("base_changes", type=Path)
    parser.add_argument("widening_changes", type=Path)
    parser.add_argument("blind_labels", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument(
        "--extra-blind-label", action="append", type=Path, default=[])
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    wanted: dict[str, int] = {}
    source: dict[str, str] = {}
    forced_stage: dict[str, str] = {}

    for operand, classification in read_classifications(
            args.base_changes).items():
        wanted[operand] = int(classification == "fix")
        source[operand] = "q0_4_cached"

    with args.widening_changes.open(newline="") as input_file:
        for row in csv.DictReader(input_file, delimiter="\t"):
            operand = row["op"].lower()
            value = int(row["classification"] == "fix")
            if operand in wanted and wanted[operand] != value:
                raise RuntimeError(f"label conflict for {operand}")
            wanted[operand] = value
            source[operand] = "q6_7_cached"

    blind_paths = [args.blind_labels, *args.extra_blind_label]
    for blind_path in blind_paths:
        with blind_path.open(newline="") as input_file:
            for row in csv.DictReader(input_file, delimiter="\t"):
                # h1309's reduced FSIN siblings carry the exact internal
                # cosine magnitude in residual66.  Rebase those rows to the
                # isomorphic direct-FCOS operand so the common polynomial
                # event can be reconstructed by this FCOS-only audit.
                operand = (
                    f"3ffc {row['residual66'].lower()}"
                    if row.get("residual66") else row["op"].lower()
                )
                value = int(row["verdict"] in ("candidate", "wide"))
                if row["verdict"] not in (
                        "candidate", "wide", "predecessor"):
                    raise RuntimeError(f"non-binary blind verdict: {row}")
                if operand in wanted and wanted[operand] != value:
                    raise RuntimeError(f"label conflict for {operand}")
                wanted[operand] = value
                source[operand] = f"q{row['q']}_blind"
                forced_stage[operand] = row.get("chain", "negative") + ".add2"

    operands = sorted(wanted)
    _, stderr = run(args.model, "rn", operands, dump=True)
    rows = parse_dump(stderr, operands)
    records = []
    schema = None
    for row in rows:
        operand = row["op"]
        if source[operand] == "q0_4_cached":
            _, enabled_adds = scalar_schedule(row, True)
            stages = [
                stage for stage, fields in enabled_adds.items()
                if fields["fires"]
            ]
            if len(stages) != 1:
                raise RuntimeError(
                    f"expected one base event for {operand}: {stages}")
            item = event(row, stages[0])
        elif operand in forced_stage:
            item = event(row, forced_stage[operand])
        else:
            item = identify_widening_event(row)
        values = named_features(item)
        if schema is None:
            schema = tuple(sorted(values))
        elif tuple(sorted(values)) != schema:
            raise RuntimeError("feature schema changed")
        records.append({
            "op": operand,
            "wanted": wanted[operand],
            "source": source[operand],
            "stage": item["stage"],
            "q": int(item["q"]),
            "increments": int(item["increments"]),
            "bit65": bit(int(item["product"]), 65),
            "word": (int(item["product"]) >> 62) & 15,
            "cut": int(item["product"]).bit_length() - 67,
            "multiplicand": int(item["multiplicand"]),
            "multiplier": int(item["multiplier"]),
            "product": int(item["product"]),
            "values": values,
        })
    if schema is None:
        raise SystemExit("empty frontier")

    ranking = []
    signatures: dict[tuple[int, ...], list[str]] = defaultdict(list)
    high_records = [record for record in records if int(record["q"]) >= 5]
    for name in schema:
        signature = tuple(record["values"][name] for record in high_records)
        signatures[signature].append(name)
        for invert in (0, 1):
            errors = high_errors = positives_missed = negatives_fired = 0
            for record in records:
                q = int(record["q"])
                bit_match = ((q >> 2) & 1) == int(record["bit65"])
                extension = int(record["values"][name]) ^ invert
                prediction = int(
                    record["increments"] and bit_match
                    and q <= 6 and (q <= 4 or extension))
                wrong = prediction != record["wanted"]
                errors += wrong
                high_errors += wrong and q >= 5
                positives_missed += wrong and record["wanted"]
                negatives_fired += wrong and not record["wanted"]
            ranking.append((
                errors, high_errors, positives_missed, negatives_fired,
                invert, name,
            ))
    ranking.sort(key=lambda entry: (entry[1], entry[0], *entry[2:]))
    exact = [entry for entry in ranking if entry[0] == 0]
    exact_high = [entry for entry in ranking if entry[1] == 0]

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"model_sha256\t{digest(args.model)}\n")
        target.write(f"base_changes_sha256\t{digest(args.base_changes)}\n")
        target.write(
            f"widening_changes_sha256\t{digest(args.widening_changes)}\n")
        for index, blind_path in enumerate(blind_paths):
            target.write(
                f"blind_labels_sha256.{index}\t{digest(blind_path)}\n")
        target.write("hardware_policy\tcached_plus_frozen_one_shot_blind\n")
        target.write(f"operands\t{len(records)}\n")
        target.write(f"high_q_operands\t{len(high_records)}\n")
        target.write(f"named_wires\t{len(schema)}\n")
        target.write(f"high_q_signatures\t{len(signatures)}\n")
        target.write(f"exact_extension_wires\t{len(exact)}\n")
        target.write(f"exact_high_extension_wires\t{len(exact_high)}\n")

        target.write("\n[ranking]\n")
        target.write(
            "errors\thigh_errors\tpositives_missed\tnegatives_fired\t"
            "invert\twire\n")
        for entry in ranking[:3000]:
            target.write("\t".join(map(str, entry)) + "\n")

        target.write("\n[exact extension wires]\n")
        for entry in exact:
            target.write("\t".join(map(str, entry)) + "\n")

        target.write("\n[exact high-q extension wires]\n")
        for entry in exact_high:
            target.write("\t".join(map(str, entry)) + "\n")

        diagnostic_names = []
        seen_signatures = set()
        for entry in ranking:
            signature = tuple(
                record["values"][entry[5]] ^ entry[4]
                for record in high_records)
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            diagnostic_names.append((entry[4], entry[5]))
            if len(diagnostic_names) == 24:
                break
        target.write("\n[high-q diagnostics]\n")
        target.write(
            "op\tlabel\tsource\tstage\tq\tword\tbit65\tcut\t"
            "multiplicand\tmultiplier\tproduct\ttail\t" +
            "\t".join(
                ("!" if invert else "") + name
                for invert, name in diagnostic_names) + "\n")
        for record in high_records:
            cut = int(record["cut"])
            tail = int(record["product"]) & ((1 << cut) - 1)
            target.write("\t".join(map(str, (
                record["op"], record["wanted"], record["source"],
                record["stage"], record["q"], f"{record['word']:x}",
                record["bit65"], cut, f"{record['multiplicand']:x}",
                f"{record['multiplier']:x}", f"{record['product']:x}",
                f"{tail:x}",
                *(record["values"][name] ^ invert
                  for invert, name in diagnostic_names),
            ))) + "\n")

        target.write("\n[counts]\n")
        counts = Counter(
            (record["source"], record["q"], record["wanted"])
            for record in records)
        for key, count in sorted(counts.items()):
            target.write(
                f"{key[0]}.q{key[1]:+d}.label{key[2]}\t{count}\n")

    print(
        f"wrote {args.report}: operands={len(records)} "
        f"high={len(high_records)} wires={len(schema)} exact={len(exact)} "
        f"best={ranking[0]}")


if __name__ == "__main__":
    main()
