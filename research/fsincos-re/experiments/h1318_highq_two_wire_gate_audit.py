#!/usr/bin/env python3
"""Search fixed two-input gates over literal high-q circuit signals.

This is an exploratory circuit-localization pass, not a promoted selector.
It evaluates ordinary two-input Boolean primitives over the documented P5
multiplier-tree wires plus the explicit FADD q/cut controls.  Signatures are
deduplicated before pairing.  Exact pairs, if any, still require a physical
connection argument and a separately frozen adversarial challenge.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import defaultdict
from pathlib import Path

from h1184_upstream_halfway_audit import schedule
from h1210_stagea_residual_reframe import parse_dump, run
from h1296_faddword_deeper_tree import event, named_features
from h1316_highq_fixed_schedule_representations import (
    load_causal,
    load_direct,
    load_siblings,
)


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


def trailing_zeros(value: int) -> int:
    return (value & -value).bit_length() - 1 if value else 0


def controls(item: dict[str, object]) -> dict[str, int]:
    q = int(item["q"])
    product = int(item["product"])
    cut = product.bit_length() - 67
    remainder = product & ((1 << cut) - 1)
    multiplicand = int(item["multiplicand"])
    multiplier = int(item["multiplier"])
    result = {
        "control.q.b0": q & 1,
        "control.q.b1": (q >> 1) & 1,
        "control.q.b2": (q >> 2) & 1,
        "control.q.eq5": int(q == 5),
        "control.q.eq6": int(q == 6),
        "control.q.eq7": int(q == 7),
        "control.cut.eq63": int(cut == 63),
        "control.cut.eq64": int(cut == 64),
        "control.product.guard": (remainder >> (cut - 1)) & 1,
        "control.product.round": (remainder >> (cut - 2)) & 1,
        "control.product.sticky": int(
            bool(remainder & ((1 << (cut - 2)) - 1))),
        "control.operand_tz_sum.ge_cut": int(
            trailing_zeros(multiplicand) + trailing_zeros(multiplier) >= cut),
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("causal_legs", type=Path)
    parser.add_argument("sibling_labels", type=Path)
    parser.add_argument("direct_labels", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    labels: dict[str, int] = {}
    load_causal(args.causal_legs, labels)
    load_siblings(args.sibling_labels, labels)
    load_direct(args.direct_labels, labels)
    operands = sorted(labels)
    _, stderr = run(args.model, "rn", operands, dump=True)
    rows = parse_dump(stderr, operands)

    records = []
    schema = None
    for row in rows:
        # Assert the dump still represents the recovered arithmetic graph.
        schedule(row)
        item = event(row, "negative.add2")
        q = int(item["q"])
        product = int(item["product"])
        if not (
            5 <= q <= 7
            and int(item["increments"])
            and ((product >> 65) & 1) == ((q >> 2) & 1)
        ):
            raise RuntimeError(f"operand is not a high-q separator: {row['op']}")
        values = named_features(item)
        values.update(controls(item))
        if schema is None:
            schema = tuple(sorted(values))
        elif tuple(sorted(values)) != schema:
            raise RuntimeError("feature schema changed")
        records.append((row["op"], labels[row["op"]], values))
    if schema is None:
        raise SystemExit("empty label set")

    signature_names: dict[int, list[str]] = defaultdict(list)
    for name in schema:
        signature = sum(
            record[2][name] << index for index, record in enumerate(records))
        signature_names[signature].append(name)
    signatures = sorted(signature_names)
    target = sum(record[1] << index for index, record in enumerate(records))
    mask = (1 << len(records)) - 1

    unary_exact = [
        (name, invert)
        for signature, names in signature_names.items()
        for invert in (0, 1)
        if (signature ^ (mask if invert else 0)) == target
        for name in names
    ]
    exact = []
    best = []
    for left_index, left in enumerate(signatures):
        for right in signatures[left_index:]:
            for gate_name, gate in GATES:
                predicted = gate(left, right, mask)
                errors = (predicted ^ target).bit_count()
                if errors == 0:
                    exact.append((
                        gate_name,
                        len(signature_names[left]), signature_names[left][0],
                        len(signature_names[right]), signature_names[right][0],
                    ))
                if len(best) < 32 or errors < best[-1][0]:
                    best.append((
                        errors, gate_name,
                        len(signature_names[left]), signature_names[left][0],
                        len(signature_names[right]), signature_names[right][0],
                    ))
                    best.sort()
                    del best[32:]

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target_file:
        for name, path in (
            ("model", args.model),
            ("causal_legs", args.causal_legs),
            ("sibling_labels", args.sibling_labels),
            ("direct_labels", args.direct_labels),
        ):
            target_file.write(f"{name}_sha256\t{digest(path)}\n")
        target_file.write("hardware_policy\tfrozen_factor_labels_no_x87_execution\n")
        target_file.write("candidate_policy\tfixed_two_input_boolean_primitives\n")
        target_file.write(f"operands\t{len(records)}\n")
        target_file.write(f"positive_operands\t{target.bit_count()}\n")
        target_file.write(f"named_signals\t{len(schema)}\n")
        target_file.write(f"distinct_signatures\t{len(signatures)}\n")
        target_file.write(f"unary_exact\t{len(unary_exact)}\n")
        target_file.write(f"exact_signature_gates\t{len(exact)}\n")
        target_file.write("\n[best signature gates]\n")
        target_file.write(
            "errors\tgate\tleft_aliases\tleft\tright_aliases\tright\n")
        for row in best:
            target_file.write("\t".join(map(str, row)) + "\n")
        target_file.write("\n[exact signature gates]\n")
        target_file.write(
            "gate\tleft_aliases\tleft\tright_aliases\tright\n")
        for row in exact[:2048]:
            target_file.write("\t".join(map(str, row)) + "\n")
        if len(exact) > 2048:
            target_file.write(f"truncated\t{len(exact)-2048}\n")
        target_file.write("\n[labels]\n")
        for operand, wanted, _ in records:
            target_file.write(f"{operand}\t{wanted}\n")

    print(
        f"wrote {args.report}: operands={len(records)} "
        f"positive={target.bit_count()} signals={len(schema)} "
        f"signatures={len(signatures)} exact_gates={len(exact)} "
        f"best_errors={best[0][0]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
