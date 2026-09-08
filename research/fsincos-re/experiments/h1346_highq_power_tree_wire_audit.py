#!/usr/bin/env python3
"""Mine literal upstream square/fourth P5 tree wires on the high-q bank.

The h1317/h1318/h1327 multiplier features describe the second negative
Horner product.  They do not expose the two earlier products that create the
square and fourth-power temporaries.  The strong but incomplete 65-bit power
endpoint models in h1340--h1345 make those producer trees the next causal
layer to test.

This audit transcribes both producers into the radix-8 Booth/four-level 4:2
tree of US 5,195,051.  The 64-bit input magnitude enters the first product as
``(magnitude << 3) * magnitude``; shifting the product cut by three preserves
the architectural 67-bit square.  The 67-bit square enters the second product
through its upper 64 bits, then its low radix-8 digit is restored with one
3:2 compression, as in h1101.  These are arithmetic port isomorphisms, not a
claim that the unpublished FSINCOS routing has already been identified.

Every literal Booth row, compressor node, final redundant bit, resolved
product bit, and documented CPA/carry-select feature is scored.  Candidate
predicates are a unary signal or a standard two-input Boolean primitive,
qualified by the already observed cut-63 enable.  Operand identity and
numeric boundary thresholds are absent.  Hardware labels are immutable
one-shot inputs and this program executes no x87 instruction.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import defaultdict
from pathlib import Path

from h1100_p5_multiplier_tree import TREE_MASK, csa3, multiplier_tree
from h1172_p5_cpa_predictor_mine import add_cpa_features
from h1184_upstream_halfway_audit import row_value, schedule
from h1210_stagea_residual_reframe import parse_dump, run
from h1296_faddword_deeper_tree import event
from h1316_highq_fixed_schedule_representations import load_direct
from h1318_highq_two_wire_gate_audit import GATES, controls


TREE_COLUMNS = range(136)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def bit(value: int, position: int) -> int:
    return (value >> position) & 1 if position >= 0 else 0


def add_pair_features(
        values: dict[str, int], prefix: str, sum_vector: int,
        carry_vector: int, product: int, cut: int) -> None:
    """Expose a redundant pair and the corresponding final-adder signals."""

    carry_in = 0
    propagate_run = 0
    for position in TREE_COLUMNS:
        sum_bit = bit(sum_vector, position)
        carry_bit = bit(carry_vector, position)
        propagate = sum_bit ^ carry_bit
        values[f"{prefix}.final.sum.b{position}"] = sum_bit
        values[f"{prefix}.final.carry.b{position}"] = carry_bit
        values[f"{prefix}.final.generate.b{position}"] = sum_bit & carry_bit
        values[f"{prefix}.final.propagate.b{position}"] = propagate
        values[f"{prefix}.final.kill.b{position}"] = 1 ^ (
            sum_bit | carry_bit)
        values[f"{prefix}.final.cin.b{position}"] = carry_in
        values[f"{prefix}.product.b{position}"] = bit(product, position)
        carry_in = (sum_bit & carry_bit) | (propagate & carry_in)

    for position in range(cut - 1, -1, -1):
        if bit(sum_vector ^ carry_vector, position):
            propagate_run += 1
        else:
            break
    for threshold in range(1, 65):
        values[f"{prefix}.run_below.ge{threshold:02d}"] = int(
            propagate_run >= threshold)

    retained = product >> cut
    remainder = product & ((1 << cut) - 1)
    values[f"{prefix}.round.retained_lsb"] = retained & 1
    values[f"{prefix}.round.guard"] = bit(remainder, cut - 1)
    values[f"{prefix}.round.round"] = bit(remainder, cut - 2)
    values[f"{prefix}.round.sticky"] = int(bool(
        remainder & ((1 << max(0, cut - 2)) - 1)))
    add_cpa_features(values, prefix + ".cpa", sum_vector, carry_vector, cut)


def add_tree_features(
        values: dict[str, int], prefix: str, state: dict[str, object],
        product: int, cut: int, coordinate_shift: int = 0) -> None:
    """Expose a complete multiplier tree in a selected product coordinate."""

    sum_vector = int(state["sum"]) << coordinate_shift
    carry_vector = int(state["carry"]) << coordinate_shift
    product_mask = (1 << 131) - 1
    native_product = product >> coordinate_shift
    if ((int(state["sum"]) + int(state["carry"])) & product_mask
            ) != native_product:
        raise AssertionError(f"{prefix} tree/product mismatch")
    add_pair_features(
        values, prefix, sum_vector, carry_vector, product, cut)

    for node_name, node in state["nodes"].items():
        for bus_name in ("sum", "carry", "first_sum", "first_carry"):
            bus = int(node[bus_name]) << coordinate_shift
            for position in TREE_COLUMNS:
                values[
                    f"{prefix}.{node_name}.{bus_name}.b{position}"
                ] = bit(bus, position)

    for row_number, row_bits in enumerate(state["rows"]):
        bus = int(row_bits) << coordinate_shift
        for position in TREE_COLUMNS:
            values[f"{prefix}.row{row_number:02d}.b{position}"] = bit(
                bus, position)
    for row_number, digit in enumerate(state["digits"]):
        digit = int(digit)
        values[f"{prefix}.digit{row_number:02d}.negative"] = int(digit < 0)
        values[f"{prefix}.digit{row_number:02d}.nonzero"] = int(digit != 0)
        for magnitude in range(5):
            values[f"{prefix}.digit{row_number:02d}.abs{magnitude}"] = int(
                abs(digit) == magnitude)


def power_features(row: dict[str, str]) -> dict[str, int]:
    """Return structural signals from the two upstream power producers."""

    schedule(row)
    magnitude = row_value(row, "mag").significand
    square = row_value(row, "mul").significand
    fourth = row_value(row, "f4").significand
    if not (1 << 63) <= magnitude < (1 << 64):
        raise AssertionError(f"unnormalized magnitude for {row['op']}")
    if not (1 << 66) <= square < (1 << 67):
        raise AssertionError(f"unnormalized square for {row['op']}")

    values: dict[str, int] = {}

    # Port-normalize the first 64x64 square to the patented 67x64 input.
    square_port_product = (magnitude * magnitude) << 3
    square_cut = square_port_product.bit_length() - 67
    square_state = multiplier_tree(magnitude << 3, magnitude)
    if square_port_product >> square_cut != square:
        raise AssertionError(f"square endpoint mismatch for {row['op']}")
    add_tree_features(
        values, "square.port", square_state,
        square_port_product, square_cut)

    # The main 67x64 fourth-power tree consumes the upper 64 square bits.
    fourth_main_product = square * (square >> 3)
    fourth_main_cut = fourth_main_product.bit_length() - 67
    fourth_state = multiplier_tree(square, square >> 3)
    add_tree_features(
        values, "fourth.main.native", fourth_state,
        fourth_main_product, fourth_main_cut)

    # Rebase the main tree by three columns and restore the missing low digit.
    rebased_sum = (int(fourth_state["sum"]) << 3) & TREE_MASK
    rebased_carry = (int(fourth_state["carry"]) << 3) & TREE_MASK
    rebased_product = fourth_main_product << 3
    rebased_cut = rebased_product.bit_length() - 67
    add_tree_features(
        values, "fourth.main.rebased", fourth_state,
        rebased_product, rebased_cut, coordinate_shift=3)

    low_product = square * (square & 7)
    full_sum, full_carry = csa3(rebased_sum, rebased_carry, low_product)
    full_product = square * square
    full_cut = full_product.bit_length() - 67
    if ((full_sum + full_carry) & ((1 << 134) - 1)) != full_product:
        raise AssertionError(f"fourth reconstruction mismatch for {row['op']}")
    if full_product >> full_cut != fourth:
        raise AssertionError(f"fourth endpoint mismatch for {row['op']}")
    add_pair_features(
        values, "fourth.full", full_sum, full_carry,
        full_product, full_cut)
    for position in TREE_COLUMNS:
        values[f"fourth.external.main_sum.b{position}"] = bit(
            rebased_sum, position)
        values[f"fourth.external.main_carry.b{position}"] = bit(
            rebased_carry, position)
        values[f"fourth.external.low_product.b{position}"] = bit(
            low_product, position)

    item = event(row, "negative.add2")
    q = int(item["q"])
    product = int(item["product"])
    if not (
        5 <= q <= 7
        and int(item["increments"])
        and bit(product, 65) == ((q >> 2) & 1)
    ):
        raise RuntimeError(f"not a high-q separator: {row['op']}")
    for name, value in controls(item).items():
        values[name] = int(value)
    return values


def family(name: str) -> str:
    if name.startswith("square."):
        return "square"
    if name.startswith("fourth."):
        return "fourth"
    return "control"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument(
        "--direct-label", action="append", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")
    if len(args.direct_label) != 2:
        raise SystemExit("supply the older bank and extension bank in order")

    labels: dict[str, int] = {}
    for path in args.direct_label:
        bank_labels: dict[str, int] = {}
        load_direct(path, bank_labels)
        overlap = set(labels) & set(bank_labels)
        if overlap:
            raise RuntimeError(f"direct-label banks overlap: {sorted(overlap)}")
        labels.update(bank_labels)
    operands = sorted(labels)
    _, stderr = run(args.model, "rn", operands, dump=True)
    rows = parse_dump(stderr, operands)

    records = []
    schema = None
    for index, row in enumerate(rows):
        values = power_features(row)
        names = tuple(sorted(values))
        if schema is None:
            schema = names
        elif names != schema:
            raise RuntimeError("power-tree signal schema changed")
        item = event(row, "negative.add2")
        product_cut = int(item["product"]).bit_length() - 67
        records.append((row["op"], labels[row["op"]], product_cut, values))
        if (index + 1) % 32 == 0:
            print(f"features {index + 1}/{len(rows)}", flush=True)
    if schema is None:
        raise SystemExit("empty label set")

    target = sum(record[1] << index for index, record in enumerate(records))
    cut63 = sum((record[2] == 63) << index
                for index, record in enumerate(records))
    mask = (1 << len(records)) - 1
    if target & ~cut63:
        raise RuntimeError("wider label exists outside the cut-63 enable")

    signature_names: dict[int, list[str]] = defaultdict(list)
    signature_families: dict[int, set[str]] = defaultdict(set)
    for name in schema:
        signature = sum(
            int(record[3][name]) << index
            for index, record in enumerate(records))
        signature_names[signature].append(name)
        signature_families[signature].add(family(name))
    signatures = sorted(signature_names)

    unary = []
    unary_exact = []
    for signature in signatures:
        for invert in (0, 1):
            predicted = (signature ^ (mask if invert else 0)) & cut63
            errors = (predicted ^ target).bit_count()
            false_negatives = (target & ~predicted & mask).bit_count()
            false_positives = (predicted & ~target & mask).bit_count()
            item = (
                errors, false_negatives, false_positives,
                predicted.bit_count(), invert,
                len(signature_names[signature]), signature_names[signature][0],
            )
            unary.append(item)
            if not errors:
                unary_exact.append(item[4:])
    unary.sort()

    best = []
    exact = []
    cross_family_exact = 0
    for left_index, left in enumerate(signatures):
        for right in signatures[left_index:]:
            for gate_name, gate in GATES:
                predicted = gate(left, right, mask) & cut63
                errors = (predicted ^ target).bit_count()
                false_negatives = (target & ~predicted & mask).bit_count()
                false_positives = (predicted & ~target & mask).bit_count()
                item = (
                    errors, false_negatives, false_positives,
                    predicted.bit_count(), gate_name,
                    len(signature_names[left]), signature_names[left][0],
                    len(signature_names[right]), signature_names[right][0],
                )
                if not errors:
                    exact.append(item[4:])
                    if signature_families[left] != signature_families[right]:
                        cross_family_exact += 1
                if len(best) < 512 or item < best[-1]:
                    best.append(item)
                    best.sort()
                    del best[512:]

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        output.write(f"model_sha256\t{digest(args.model)}\n")
        for index, path in enumerate(args.direct_label):
            output.write(f"direct_labels_sha256.{index}\t{digest(path)}\n")
        output.write("hardware_policy\tfrozen_one_shot_labels_no_x87_execution\n")
        output.write(
            "candidate_policy\tcut63_AND_literal_power_tree_boolean_gate\n")
        output.write("tree_topology\tpatent_default_d_slot_0\n")
        output.write(
            "port_status\tarithmetic_isomorphism_not_proven_fsincos_routing\n")
        output.write(f"operands\t{len(records)}\n")
        output.write(f"positive_operands\t{target.bit_count()}\n")
        output.write(f"cut63_operands\t{cut63.bit_count()}\n")
        output.write(f"named_signals\t{len(schema)}\n")
        output.write(f"distinct_signatures\t{len(signatures)}\n")
        output.write(f"unary_exact\t{len(unary_exact)}\n")
        output.write(f"exact_gates\t{len(exact)}\n")
        output.write(f"cross_family_exact_gates\t{cross_family_exact}\n")
        output.write("\n[family signature counts]\n")
        counts: dict[str, set[int]] = defaultdict(set)
        for signature, families in signature_families.items():
            for family_name in families:
                counts[family_name].add(signature)
        for family_name, values in sorted(counts.items()):
            output.write(f"{family_name}\t{len(values)}\n")
        output.write("\n[best unary]\n")
        output.write(
            "errors\tfalse_negatives\tfalse_positives\t"
            "predicted_positives\tinvert\taliases\tsignal\n")
        for item in unary[:256]:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[exact unary]\n")
        output.write("invert\taliases\tsignal\n")
        for item in unary_exact[:4096]:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[best cut-gated pairs]\n")
        output.write(
            "errors\tfalse_negatives\tfalse_positives\t"
            "predicted_positives\tgate\tleft_aliases\tleft\t"
            "right_aliases\tright\n")
        for item in best:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[exact cut-gated pairs]\n")
        output.write(
            "gate\tleft_aliases\tleft\tright_aliases\tright\n")
        for item in exact[:4096]:
            output.write("\t".join(map(str, item)) + "\n")
        if len(exact) > 4096:
            output.write(f"truncated\t{len(exact) - 4096}\n")

    print(
        f"wrote {args.report}: operands={len(records)} "
        f"signals={len(schema)} signatures={len(signatures)} "
        f"unary_exact={len(unary_exact)} exact={len(exact)} "
        f"best={best[0][:5]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
