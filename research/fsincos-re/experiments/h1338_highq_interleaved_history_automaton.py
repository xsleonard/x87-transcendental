#!/usr/bin/env python3
"""Exhaust one-bit history recurrences in physical two-chain UOP order.

h1328 follows only the negative Horner dependency.  The independently
recovered two-chain cosine schedule is interleaved: after square/fourth, the
negative and positive multiply/add operations alternate.  If the relevant
history is execution-unit state rather than a tag attached solely to the
negative temporary, the sibling operations are causal inputs.  This audit
therefore repeats the complete h1328 Boolean recurrence search in that
interleaved order and tests the state both immediately before and immediately
after the target negative.add2 operation.

There are no operand thresholds or identities.  Hardware labels are immutable
inputs and this program executes no x87 instruction.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from pathlib import Path

from h1184_upstream_halfway_audit import schedule
from h1210_stagea_residual_reframe import parse_dump, run
from h1296_faddword_deeper_tree import event
from h1322_attached_history_field_audit import history_fields
from h1328_highq_history_automaton import load_labels, transition


STAGES = (
    "square",
    "fourth",
    "negative.mul1",
    "positive.mul1",
    "negative.add1",
    "positive.add1",
    "negative.mul2",
    "positive.mul2",
    "negative.add2",
)
KINDS = ("mul", "mul", "mul", "mul", "add", "add", "mul", "mul", "add")
NATIVE = {
    "square": (67, False),
    "fourth": (67, False),
    "negative.mul1": (67, False),
    "positive.mul1": (67, False),
    "negative.add1": (64, True),
    "positive.add1": (64, True),
    "negative.mul2": (67, False),
    "positive.mul2": (67, False),
    "negative.add2": (64, True),
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


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
    for row in rows:
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
        stage_fields = {}
        for stage in STAGES:
            fields, _ = history_fields(operations[stage], *NATIVE[stage])
            stage_fields[stage] = fields
        names = tuple(sorted(stage_fields[STAGES[0]]))
        if any(tuple(sorted(stage_fields[stage])) != names for stage in STAGES):
            raise RuntimeError("history field schema differs by stage")
        if schema is None:
            schema = names
        elif schema != names:
            raise RuntimeError("history field schema differs by operand")
        records.append((
            row["op"], labels[row["op"]], cut,
            tuple(stage_fields[stage] for stage in STAGES),
        ))
    if schema is None:
        raise SystemExit("empty label set")
    if any(wanted and cut != 63 for _, wanted, cut, _ in records):
        raise RuntimeError("wider label exists outside cut 63")

    scores = []
    exact = []
    signature_count = 0
    for field in schema:
        groups = Counter()
        for _, wanted, cut, fields in records:
            sequence = sum(
                int(stage_fields[field]) << index
                for index, stage_fields in enumerate(fields)
            )
            groups[sequence, wanted, cut == 63] += 1
        signature_count += len({key[0] for key in groups})

        for seed in (0, 1):
            for mul_law in range(16):
                for add_law in range(16):
                    for tap in ("before_target", "after_target"):
                        for output_invert in (0, 1):
                            errors = positive_errors = negative_errors = 0
                            predicted_positives = 0
                            for (sequence, wanted, cut63), count in groups.items():
                                state = seed
                                stop = len(STAGES) - (tap == "before_target")
                                for index, kind in enumerate(KINDS[:stop]):
                                    symbol = (sequence >> index) & 1
                                    state = transition(
                                        mul_law if kind == "mul" else add_law,
                                        state, symbol)
                                predicted = int(
                                    cut63 and (state ^ output_invert))
                                wrong = predicted != wanted
                                errors += count * wrong
                                positive_errors += count * wrong * wanted
                                negative_errors += count * wrong * (1 - wanted)
                                predicted_positives += count * predicted
                            item = (
                                errors, positive_errors, negative_errors,
                                predicted_positives, field, seed,
                                mul_law, add_law, tap, output_invert,
                            )
                            scores.append(item)
                            if errors == 0:
                                exact.append(item)
    scores.sort()

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        output.write(f"model_sha256\t{digest(args.model)}\n")
        for index, path in enumerate(args.direct_label):
            output.write(f"direct_labels_sha256.{index}\t{digest(path)}\n")
        output.write("hardware_policy\tfrozen_one_shot_labels_no_x87_execution\n")
        output.write(
            "candidate_policy\tfixed_interleaved_one_bit_history_recurrences\n")
        output.write(f"operands\t{len(records)}\n")
        output.write(f"positive_operands\t{sum(labels.values())}\n")
        output.write(
            f"cut63_operands\t{sum(cut == 63 for _, _, cut, _ in records)}\n")
        output.write(f"rounding_attributes\t{len(schema)}\n")
        output.write(f"attribute_sequence_signatures\t{signature_count}\n")
        output.write(f"recurrences\t{len(scores)}\n")
        output.write(f"exact_recurrences\t{len(exact)}\n")
        output.write("stage_order\t" + ",".join(STAGES) + "\n")
        output.write("\n[ranking]\n")
        output.write(
            "errors\tpositive_errors\tnegative_errors\t"
            "predicted_positives\tattribute\tseed\t"
            "mul_law\tadd_law\ttap\toutput_invert\n")
        for item in scores[:1024]:
            rendered = (
                *item[:6], f"{item[6]:x}", f"{item[7]:x}", *item[8:])
            output.write("\t".join(map(str, rendered)) + "\n")
        output.write("\n[exact recurrences]\n")
        for item in exact:
            rendered = (
                *item[:6], f"{item[6]:x}", f"{item[7]:x}", *item[8:])
            output.write("\t".join(map(str, rendered)) + "\n")

    print(
        f"wrote {args.report}: operands={len(records)} "
        f"attributes={len(schema)} recurrences={len(scores)} "
        f"exact={len(exact)} best={scores[0][:4]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
