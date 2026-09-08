#!/usr/bin/env python3
"""Test upstream power-tree wires against downstream high-q circuit state.

h1346 closes 16 of 19 wider operands with a zero-collateral Boolean pair,
but no unary or two-wire rule inside the square/fourth producer layer is
exact.  h1327 separately proved that two wires from the second negative
Horner product, its FADD, attached history, and controls are not exact.  This
audit tests the missing cross-layer grammar:

    wide = (terminal_product_cut == 63)
           AND gate(power_producer_wire, downstream_wire)

The producer bank is the complete literal P5 square/fourth reconstruction
from h1346.  The downstream bank is exactly the multiplier/FADD/history bank
from h1327.  Signals are fixed circuit coordinates and only standard Boolean
primitives are allowed; operand identity and learned numeric boundaries are
not features.  Even an exact survivor would remain a candidate pending a
separately frozen challenge and a plausible physical-routing account.

Hardware labels are immutable one-shot inputs and this program executes no
x87 instruction.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import defaultdict
from pathlib import Path

from h1210_stagea_residual_reframe import parse_dump, run
from h1316_highq_fixed_schedule_representations import load_direct
from h1318_highq_two_wire_gate_audit import GATES
from h1327_highq_cut_gated_pair_audit import signal_families
from h1346_highq_power_tree_wire_audit import power_features


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def signatures_for(
        records: list[tuple[str, int, int, dict[str, int], dict[str, int]]],
        names: tuple[str, ...], value_index: int,
        family_by_name: dict[str, str],
        ) -> tuple[dict[int, list[str]], dict[int, set[str]]]:
    aliases: dict[int, list[str]] = defaultdict(list)
    families: dict[int, set[str]] = defaultdict(set)
    for name in names:
        signature = sum(
            int(record[value_index][name]) << index
            for index, record in enumerate(records))
        aliases[signature].append(name)
        families[signature].add(family_by_name[name])
    return aliases, families


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
    power_schema = None
    downstream_schema = None
    downstream_family_by_name = None
    for index, row in enumerate(rows):
        all_power = power_features(row)
        power = {
            name: value for name, value in all_power.items()
            if name.startswith(("square.", "fourth."))
        }
        downstream, downstream_families, cut = signal_families(row)
        power_names = tuple(sorted(power))
        downstream_names = tuple(sorted(downstream))
        if power_schema is None:
            power_schema = power_names
            downstream_schema = downstream_names
            downstream_family_by_name = downstream_families
        elif (
            power_names != power_schema
            or downstream_names != downstream_schema
            or downstream_families != downstream_family_by_name
        ):
            raise RuntimeError("cross-layer signal schema changed")
        records.append((row["op"], labels[row["op"]], cut, power, downstream))
        if (index + 1) % 32 == 0:
            print(f"features {index + 1}/{len(rows)}", flush=True)
    if (
        power_schema is None
        or downstream_schema is None
        or downstream_family_by_name is None
    ):
        raise SystemExit("empty label set")

    target = sum(record[1] << index for index, record in enumerate(records))
    cut63 = sum((record[2] == 63) << index
                for index, record in enumerate(records))
    mask = (1 << len(records)) - 1
    if target & ~cut63:
        raise RuntimeError("wider label exists outside the cut-63 enable")

    power_family_by_name = {
        name: "square" if name.startswith("square.") else "fourth"
        for name in power_schema
    }
    power_aliases, power_families = signatures_for(
        records, power_schema, 3, power_family_by_name)
    downstream_aliases, downstream_families = signatures_for(
        records, downstream_schema, 4, downstream_family_by_name)
    power_signatures = sorted(power_aliases)
    downstream_signatures = sorted(downstream_aliases)

    best = []
    exact = []
    exact_count = 0
    for power_signature in power_signatures:
        for downstream_signature in downstream_signatures:
            for gate_name, gate in GATES:
                predicted = gate(
                    power_signature, downstream_signature, mask) & cut63
                errors = (predicted ^ target).bit_count()
                false_negatives = (target & ~predicted & mask).bit_count()
                false_positives = (predicted & ~target & mask).bit_count()
                item = (
                    errors, false_negatives, false_positives,
                    predicted.bit_count(), gate_name,
                    len(power_aliases[power_signature]),
                    power_aliases[power_signature][0],
                    len(downstream_aliases[downstream_signature]),
                    downstream_aliases[downstream_signature][0],
                    power_signature, downstream_signature,
                )
                if not errors:
                    exact_count += 1
                    if len(exact) < 4096:
                        exact.append(item[4:9])
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
            "candidate_policy\tcut63_AND_power_wire_downstream_wire_gate\n")
        output.write("tree_topology\tpatent_default_d_slot_0\n")
        output.write(
            "port_status\tarithmetic_isomorphism_not_proven_fsincos_routing\n")
        output.write(f"operands\t{len(records)}\n")
        output.write(f"positive_operands\t{target.bit_count()}\n")
        output.write(f"cut63_operands\t{cut63.bit_count()}\n")
        output.write(f"power_named_signals\t{len(power_schema)}\n")
        output.write(f"power_distinct_signatures\t{len(power_signatures)}\n")
        output.write(f"downstream_named_signals\t{len(downstream_schema)}\n")
        output.write(
            f"downstream_distinct_signatures\t{len(downstream_signatures)}\n")
        output.write(f"exact_gates\t{exact_count}\n")
        output.write("\n[power family signature counts]\n")
        power_counts: dict[str, set[int]] = defaultdict(set)
        for signature, family_names in power_families.items():
            for family_name in family_names:
                power_counts[family_name].add(signature)
        for family_name, values in sorted(power_counts.items()):
            output.write(f"{family_name}\t{len(values)}\n")
        output.write("\n[downstream family signature counts]\n")
        downstream_counts: dict[str, set[int]] = defaultdict(set)
        for signature, family_names in downstream_families.items():
            for family_name in family_names:
                downstream_counts[family_name].add(signature)
        for family_name, values in sorted(downstream_counts.items()):
            output.write(f"{family_name}\t{len(values)}\n")
        output.write("\n[best cross-layer pairs]\n")
        output.write(
            "errors\tfalse_negatives\tfalse_positives\t"
            "predicted_positives\tgate\tpower_aliases\tpower_wire\t"
            "downstream_aliases\tdownstream_wire\n")
        for item in best:
            output.write("\t".join(map(str, item[:9])) + "\n")
        output.write("\n[best candidate disagreements]\n")
        if best:
            best_item = best[0]
            gate = dict(GATES)[best_item[4]]
            predicted = gate(best_item[9], best_item[10], mask) & cut63
            output.write("op\tlabel\tpredicted\n")
            for index, record in enumerate(records):
                prediction = (predicted >> index) & 1
                if prediction != record[1]:
                    output.write(f"{record[0]}\t{record[1]}\t{prediction}\n")
        output.write("\n[exact cross-layer pairs]\n")
        output.write(
            "gate\tpower_aliases\tpower_wire\t"
            "downstream_aliases\tdownstream_wire\n")
        for item in exact:
            output.write("\t".join(map(str, item)) + "\n")
        if exact_count > len(exact):
            output.write(f"truncated\t{exact_count - len(exact)}\n")

    print(
        f"wrote {args.report}: operands={len(records)} "
        f"power_signatures={len(power_signatures)} "
        f"downstream_signatures={len(downstream_signatures)} "
        f"exact={exact_count} best={best[0][:5]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
