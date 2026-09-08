#!/usr/bin/env python3
"""Test a cut-gated two-wire explanation on the complete high-q bank.

Every wider-factor observation in h1315+h1326 has product cut 63, whereas
every cut-64 separator selects the predecessor.  This audit treats that
normalization split as a fixed physical enable and asks whether the enabled
state is one standard two-input Boolean gate over the already reconstructed
multiplier-tree, FADD, or attached-history signals.  Cross-family pairs are
included; the earlier audits tested the families separately.

The candidate form is

    wide = (product_cut == 63) AND gate(signal_a, signal_b).

This is a diagnostic circuit grammar, not a promoted selector.  Even an exact
survivor would need a physical routing argument and a disjoint frozen bank.
No x87 instruction is executed here.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import defaultdict
from pathlib import Path

from h1123_horner_fadd_carry_mine import row_features
from h1184_upstream_halfway_audit import schedule
from h1210_stagea_residual_reframe import parse_dump, run
from h1296_faddword_deeper_tree import event, named_features
from h1318_highq_two_wire_gate_audit import controls
from h1322_attached_history_field_audit import NATIVE, history_fields, q_relations


GATES = (
    ("and", lambda a, b, mask: a & b),
    ("or", lambda a, b, mask: a | b),
    ("xor", lambda a, b, mask: a ^ b),
    ("a_and_not_b", lambda a, b, mask: a & (~b & mask)),
    ("not_a_and_b", lambda a, b, mask: (~a & mask) & b),
    ("nand", lambda a, b, mask: ~(a & b) & mask),
    ("nor", lambda a, b, mask: ~(a | b) & mask),
    ("xnor", lambda a, b, mask: ~(a ^ b) & mask),
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def load_labels(paths: list[Path]) -> dict[str, int]:
    labels: dict[str, int] = {}
    for path in paths:
        with path.open(newline="") as source:
            for row in csv.DictReader(source, delimiter="\t"):
                if row["verdict"] not in ("wide", "predecessor"):
                    raise RuntimeError(f"non-binary direct label: {row}")
                operand = row["op"].lower()
                wanted = int(row["verdict"] == "wide")
                previous = labels.setdefault(operand, wanted)
                if previous != wanted:
                    raise RuntimeError(f"factor-label conflict for {operand}")
    return labels


def signal_families(row: dict[str, str]
                    ) -> tuple[dict[str, int], dict[str, str], int]:
    operations = schedule(row)
    item = event(row, "negative.add2")
    q = int(item["q"])
    product = int(item["product"])
    cut = product.bit_length() - 67
    if not (
        5 <= q <= 7
        and int(item["increments"])
        and ((product >> 65) & 1) == ((q >> 2) & 1)
    ):
        raise RuntimeError(f"not a high-q separator: {row['op']}")

    values: dict[str, int] = {}
    families: dict[str, str] = {}

    for name, value in named_features(item).items():
        values[name] = int(value)
        families[name] = "multiplier"
    for name, value in controls(item).items():
        values[name] = int(value)
        families[name] = "control"
    for name, value in row_features(row).items():
        if not name.startswith("negative.add2."):
            continue
        values[name] = int(value)
        families[name] = "fadd"

    for stage, (bits, nearest) in NATIVE.items():
        fields, words = history_fields(operations[stage], bits, nearest)
        for name, value in fields.items():
            full_name = f"history.{stage}.{name}"
            values[full_name] = int(value)
            families[full_name] = "history"
        for name, value in q_relations(stage, q, words).items():
            full_name = f"history.{name}"
            values[full_name] = int(value)
            families[full_name] = "history"
    return values, families, cut


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument(
        "--direct-label", action="append", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    labels = load_labels(args.direct_label)
    operands = sorted(labels)
    _, stderr = run(args.model, "rn", operands, dump=True)
    rows = parse_dump(stderr, operands)

    records = []
    schema = None
    family_by_name = None
    for row in rows:
        values, families, cut = signal_families(row)
        names = tuple(sorted(values))
        if schema is None:
            schema = names
            family_by_name = families
        elif names != schema or families != family_by_name:
            raise RuntimeError("signal schema changed")
        records.append((row["op"], labels[row["op"]], cut, values))
    if schema is None or family_by_name is None:
        raise SystemExit("empty label set")

    target = sum(record[1] << index for index, record in enumerate(records))
    cut63 = sum((record[2] == 63) << index
                for index, record in enumerate(records))
    mask = (1 << len(records)) - 1
    if target & ~cut63:
        raise RuntimeError("wider label exists outside the cut-63 enable")

    names_by_signature: dict[int, list[str]] = defaultdict(list)
    families_by_signature: dict[int, set[str]] = defaultdict(set)
    for name in schema:
        signature = sum(
            record[3][name] << index
            for index, record in enumerate(records))
        names_by_signature[signature].append(name)
        families_by_signature[signature].add(family_by_name[name])
    signatures = sorted(names_by_signature)

    best = []
    exact = []
    cross_family_exact = 0
    for left_index, left in enumerate(signatures):
        for right in signatures[left_index:]:
            for gate_name, gate in GATES:
                predicted = gate(left, right, mask) & cut63
                errors = (predicted ^ target).bit_count()
                left_name = names_by_signature[left][0]
                right_name = names_by_signature[right][0]
                item = (
                    errors, gate_name,
                    len(names_by_signature[left]), left_name,
                    len(names_by_signature[right]), right_name,
                )
                if errors == 0:
                    exact.append(item[1:])
                    if families_by_signature[left] != families_by_signature[right]:
                        cross_family_exact += 1
                if len(best) < 128 or item < best[-1]:
                    best.append(item)
                    best.sort()
                    del best[128:]

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        output.write(f"model_sha256\t{digest(args.model)}\n")
        for index, path in enumerate(args.direct_label):
            output.write(
                f"direct_labels_sha256.{index}\t{digest(path)}\n")
        output.write("hardware_policy\tfrozen_one_shot_labels_no_x87_execution\n")
        output.write(
            "candidate_policy\tcut63_AND_standard_two_signal_gate\n")
        output.write(f"operands\t{len(records)}\n")
        output.write(f"positive_operands\t{target.bit_count()}\n")
        output.write(f"cut63_operands\t{cut63.bit_count()}\n")
        output.write(f"named_signals\t{len(schema)}\n")
        output.write(f"distinct_signatures\t{len(signatures)}\n")
        output.write(f"exact_gates\t{len(exact)}\n")
        output.write(f"cross_family_exact_gates\t{cross_family_exact}\n")
        output.write("\n[family signature counts]\n")
        family_counts = defaultdict(set)
        for signature, families in families_by_signature.items():
            for family in families:
                family_counts[family].add(signature)
        for family, values in sorted(family_counts.items()):
            output.write(f"{family}\t{len(values)}\n")
        output.write("\n[best cut-gated pairs]\n")
        output.write(
            "errors\tgate\tleft_aliases\tleft\t"
            "right_aliases\tright\n")
        for item in best:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[exact cut-gated pairs]\n")
        output.write(
            "gate\tleft_aliases\tleft\tright_aliases\tright\n")
        for item in exact[:4096]:
            output.write("\t".join(map(str, item)) + "\n")
        if len(exact) > 4096:
            output.write(f"truncated\t{len(exact)-4096}\n")

    print(
        f"wrote {args.report}: operands={len(records)} "
        f"positive={target.bit_count()} signals={len(schema)} "
        f"signatures={len(signatures)} exact={len(exact)} "
        f"best={best[0][0]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
