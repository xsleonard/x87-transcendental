#!/usr/bin/env python3
"""Test literal final-Horner FADD wires on the forced high-q factor labels.

h1317/h1318 exhaust the reconstructed multiplier-tree wires but reduce the
consuming FADD to q/cut controls.  This audit instead reuses h1123's literal
same-sign FADD transcription: aligned operand bits, generate/propagate/kill,
ripple carries, rounding increment propagation, four-bit sticky scanner, and
fixed 2/4/8/16-bit carry-select endpoints.  It tests unary wires and standard
two-input Boolean primitives without operand identities or numeric fitting.

This is a localization audit, not an accepted selector.  Any survivor still
requires a physical interpretation and a disjoint frozen challenge.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import defaultdict
from pathlib import Path

from h1123_horner_fadd_carry_mine import row_features
from h1184_upstream_halfway_audit import schedule
from h1210_stagea_residual_reframe import parse_dump, run
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
        schedule(row)
        values = {
            name: int(value)
            for name, value in row_features(row).items()
            if name.startswith("negative.add2.")
        }
        if schema is None:
            schema = tuple(sorted(values))
        elif tuple(sorted(values)) != schema:
            raise RuntimeError("FADD feature schema changed")
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

    unary = []
    exact_unary = []
    for signature, names in signature_names.items():
        for invert in (0, 1):
            predicted = signature ^ (mask if invert else 0)
            errors = (predicted ^ target).bit_count()
            item = (errors, invert, len(names), names[0])
            unary.append(item)
            if not errors:
                exact_unary.append(item[1:])
    unary.sort()

    exact_pairs = []
    best_pairs = []
    for left_index, left in enumerate(signatures):
        for right in signatures[left_index:]:
            for gate_name, gate in GATES:
                predicted = gate(left, right, mask)
                errors = (predicted ^ target).bit_count()
                item = (
                    errors, gate_name,
                    len(signature_names[left]), signature_names[left][0],
                    len(signature_names[right]), signature_names[right][0],
                )
                if not errors:
                    exact_pairs.append(item[1:])
                if len(best_pairs) < 64 or item < best_pairs[-1]:
                    best_pairs.append(item)
                    best_pairs.sort()
                    del best_pairs[64:]

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        for name, path in (
            ("model", args.model),
            ("causal_legs", args.causal_legs),
            ("sibling_labels", args.sibling_labels),
            ("direct_labels", args.direct_labels),
        ):
            output.write(f"{name}_sha256\t{digest(path)}\n")
        output.write("hardware_policy\tfrozen_factor_labels_no_x87_execution\n")
        output.write("candidate_policy\tliteral_same_sign_FADD_wires\n")
        output.write(f"operands\t{len(records)}\n")
        output.write(f"positive_operands\t{target.bit_count()}\n")
        output.write(f"named_wires\t{len(schema)}\n")
        output.write(f"distinct_signatures\t{len(signatures)}\n")
        output.write(f"exact_unary\t{len(exact_unary)}\n")
        output.write(f"exact_two_input\t{len(exact_pairs)}\n")
        output.write("\n[best unary]\n")
        output.write("errors\tinvert\taliases\twire\n")
        for item in unary[:128]:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[exact unary]\n")
        for item in exact_unary:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[best two-input primitives]\n")
        output.write("errors\tgate\tleft_aliases\tleft\tright_aliases\tright\n")
        for item in best_pairs:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[exact two-input primitives]\n")
        for item in exact_pairs[:4096]:
            output.write("\t".join(map(str, item)) + "\n")
        if len(exact_pairs) > 4096:
            output.write(f"truncated\t{len(exact_pairs) - 4096}\n")

    print(
        f"wrote {args.report}: operands={len(records)} wires={len(schema)} "
        f"signatures={len(signatures)} unary_exact={len(exact_unary)} "
        f"pair_exact={len(exact_pairs)} best={best_pairs[0][0]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
