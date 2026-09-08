#!/usr/bin/env python3
"""Audit the integrated low-radix-digit isomorphism of the fourth-power tree.

The P5 multiplier reduces 22 Booth rows, its W correction, and a zero input
through six first-level 4:2 compressors.  A 67-by-67 square can be decomposed
exactly into a shifted 67-by-64 main product plus the missing low radix-8
digit.  h1346 reduced the main product first and appended that low product in
one final 3:2 compressor.  An equally exact, and more hardware-local,
representation replaces the tree's zero input with the low product so all 24
inputs are reduced by the documented four-level topology.

This audit exposes every input, compressor, final redundant-pair, and CPA
wire for that integrated representation.  The last first-level compressor is
also evaluated under each of its four possible distinguished-D assignments;
the natural patented ordering is d0 (row 20 is D, low product occupies the
former zero input).  Unary and standard two-input Boolean responses include
literal q/cut controls.  Any survivor remains a candidate requiring physical
routing evidence and a disjoint blind test.  Hardware labels are immutable;
no x87 instruction is executed.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import defaultdict
from pathlib import Path

from h1100_p5_multiplier_tree import TREE_MASK, csa42, physical_rows
from h1184_upstream_halfway_audit import row_value, schedule
from h1210_stagea_residual_reframe import parse_dump, run
from h1296_faddword_deeper_tree import event
from h1318_highq_two_wire_gate_audit import GATES, controls
from h1346_highq_power_tree_wire_audit import add_pair_features
from h1353_upstream_cpa_word_relations import load_labels


TREE_COLUMNS = range(136)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def bit(value: int, position: int) -> int:
    return (value >> position) & 1


def integrated_tree(square: int, last_d_slot: int) -> dict[str, object]:
    rows, w, _, digits = physical_rows(square, square >> 3)
    low_product = square * (square & 7)
    inputs = [((row << 3) & TREE_MASK) for row in rows]
    inputs.extend(((w << 3) & TREE_MASK, low_product & TREE_MASK))
    if len(inputs) != 24:
        raise AssertionError("integrated tree does not have 24 inputs")
    nodes = {}

    def compress(name: str, wires: list[int], d_slot: int = 0
                 ) -> tuple[int, int]:
        ordered = list(wires)
        distinguished = ordered.pop(d_slot)
        out_sum, out_carry, first_sum, first_carry = csa42(
            ordered[0], ordered[1], ordered[2], distinguished)
        nodes[name] = {
            "in": tuple(wires), "sum": out_sum, "carry": out_carry,
            "first_sum": first_sum, "first_carry": first_carry,
        }
        return out_sum, out_carry

    level1 = []
    for index in range(6):
        slot = last_d_slot if index == 5 else 0
        level1.append(compress(
            f"l1_{index}", inputs[4 * index:4 * index + 4], slot))
    level2 = [compress(
        f"l2_{index}", list(level1[2 * index] + level1[2 * index + 1]))
        for index in range(3)]
    level3 = compress("l3_0", list(level2[0] + level2[1]))
    final_sum, final_carry = compress("l4_0", list(level3 + level2[2]))
    return {
        "sum": final_sum, "carry": final_carry, "nodes": nodes,
        "inputs": tuple(inputs), "digits": tuple(digits),
        "low_product": low_product,
    }


def tree_features(square: int, fourth: int) -> dict[str, int]:
    full_product = square * square
    cut = full_product.bit_length() - 67
    if full_product >> cut != fourth:
        raise AssertionError("fourth-power endpoint mismatch")
    values = {}
    for last_d_slot in range(4):
        state = integrated_tree(square, last_d_slot)
        if ((int(state["sum"]) + int(state["carry"]))
                & ((1 << 134) - 1)) != full_product:
            raise AssertionError("integrated tree/product mismatch")
        prefix = f"fourth.integrated.d{last_d_slot}"
        add_pair_features(
            values, prefix, int(state["sum"]), int(state["carry"]),
            full_product, cut)
        for input_number, bus in enumerate(state["inputs"]):
            for position in TREE_COLUMNS:
                values[f"{prefix}.input{input_number:02d}.b{position}"] = bit(
                    int(bus), position)
        for node_name, node in state["nodes"].items():
            for bus_name in ("sum", "carry", "first_sum", "first_carry"):
                bus = int(node[bus_name])
                for position in TREE_COLUMNS:
                    values[
                        f"{prefix}.{node_name}.{bus_name}.b{position}"
                    ] = bit(bus, position)
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument(
        "--direct-label", action="append", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    labels, _ = load_labels(args.direct_label)
    operands = sorted(labels)
    _, stderr = run(args.model, "rn", operands, dump=True)
    rows = parse_dump(stderr, operands)
    records = []
    schema = None
    for index, row in enumerate(rows):
        schedule(row)
        item = event(row, "negative.add2")
        q = int(item["q"])
        product = int(item["product"])
        if not (
            5 <= q <= 7 and int(item["increments"])
            and bit(product, 65) == ((q >> 2) & 1)
        ):
            raise RuntimeError(f"not a high-q separator: {row['op']}")
        values = tree_features(
            row_value(row, "mul").significand,
            row_value(row, "f4").significand)
        values.update(controls(item))
        names = tuple(sorted(values))
        if schema is None:
            schema = names
        elif names != schema:
            raise RuntimeError("integrated-tree schema changed")
        records.append((row["op"], labels[row["op"]], values))
        if (index + 1) % 32 == 0:
            print(f"features {index + 1}/{len(rows)}", flush=True)
    if schema is None:
        raise SystemExit("empty label set")

    signature_names: dict[int, list[str]] = defaultdict(list)
    for name in schema:
        signature = sum(
            int(record[2][name]) << index
            for index, record in enumerate(records))
        signature_names[signature].append(name)
    signatures = sorted(signature_names)
    target = sum(record[1] << index for index, record in enumerate(records))
    mask = (1 << len(records)) - 1

    unary = []
    exact_unary = []
    for signature in signatures:
        for invert in (0, 1):
            predicted = signature ^ (mask if invert else 0)
            errors = (predicted ^ target).bit_count()
            item = (
                errors, (target & ~predicted & mask).bit_count(),
                (predicted & ~target & mask).bit_count(),
                predicted.bit_count(), invert,
                len(signature_names[signature]), signature_names[signature][0],
            )
            unary.append(item)
            if not errors:
                exact_unary.append(item[4:])
    unary.sort()

    best = []
    exact = []
    for left_index, left in enumerate(signatures):
        for right in signatures[left_index:]:
            for gate_name, gate in GATES:
                predicted = gate(left, right, mask)
                errors = (predicted ^ target).bit_count()
                item = (
                    errors, (target & ~predicted & mask).bit_count(),
                    (predicted & ~target & mask).bit_count(),
                    predicted.bit_count(), gate_name,
                    len(signature_names[left]), signature_names[left][0],
                    len(signature_names[right]), signature_names[right][0],
                )
                if not errors:
                    exact.append(item[4:])
                if len(best) < 1024 or item < best[-1]:
                    best.append(item)
                    best.sort()
                    del best[1024:]

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        output.write(f"model_sha256\t{digest(args.model)}\n")
        for index, path in enumerate(args.direct_label):
            output.write(f"direct_labels_sha256.{index}\t{digest(path)}\n")
        output.write("hardware_policy\tfrozen_one_shot_labels_no_x87_execution\n")
        output.write(
            "candidate_policy\tintegrated_low_digit_four_level_tree_wires\n")
        output.write("natural_topology\td0_low_product_replaces_zero_input23\n")
        output.write(f"operands\t{len(records)}\n")
        output.write(f"positive_operands\t{target.bit_count()}\n")
        output.write(f"named_signals\t{len(schema)}\n")
        output.write(f"distinct_signatures\t{len(signatures)}\n")
        output.write(f"exact_unary\t{len(exact_unary)}\n")
        output.write(f"exact_two_input\t{len(exact)}\n")
        output.write("\n[best unary]\n")
        output.write(
            "errors\tfalse_negatives\tfalse_positives\t"
            "predicted_positives\tinvert\taliases\tsignal\n")
        for item in unary[:1024]:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[best two-input gates]\n")
        output.write(
            "errors\tfalse_negatives\tfalse_positives\t"
            "predicted_positives\tgate\tleft_aliases\tleft\t"
            "right_aliases\tright\n")
        for item in best:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[exact unary]\n")
        for item in exact_unary:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[exact two-input gates]\n")
        for item in exact[:4096]:
            output.write("\t".join(map(str, item)) + "\n")
        if len(exact) > 4096:
            output.write(f"truncated\t{len(exact)-4096}\n")

    print(
        f"wrote {args.report}: operands={len(records)} signals={len(schema)} "
        f"signatures={len(signatures)} exact_unary={len(exact_unary)} "
        f"exact_pairs={len(exact)} best_unary={unary[0][:4]} "
        f"best_pair={best[0][:5]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
