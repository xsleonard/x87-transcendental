#!/usr/bin/env python3
"""Test one-state-bit block carry recurrences for the R59 selector.

R96 describes the terminal endpoint selector as a large comparison tree.  A
more credible isomorphic representation would be a fixed carry automaton: each
aligned block of S + ~B contributes one of the ordinary kill, propagate, or
generate symbols, and one transition law advances a single hidden carry bit.

This cached-label audit enumerates all 64 Boolean transition laws over
``(state, symbol)`` for block widths 2/4/8/16, three alignments, several suffix
depths, and fixed/exact entry carries.  The family is frozen by construction;
it contains no operand constants, learned thresholds, or per-cell cases.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path

import numpy as np


WIDTHS = (2, 4, 8, 16)
ALIGNMENTS = ("integer", "absolute", "cut")
DEPTHS = (1, 2, 3, 4, 6, 8, 999)
SEEDS = ("zero", "one", "exact")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def bit(value: int, position: int) -> int:
    return (value >> position) & 1


def segment_relation(s_value: int, b_value: int,
                     start: int, end: int) -> tuple[int, int]:
    """Return (generate, propagate) for S + ~B over [start,end)."""
    carry0, carry1 = 0, 1
    for position in range(start, end):
        a = bit(s_value, position)
        bn = 1 ^ bit(b_value, position)
        generate = a & bn
        propagate = a ^ bn
        carry0 = generate | (propagate & carry0)
        carry1 = generate | (propagate & carry1)
    if carry0 and not carry1:
        raise AssertionError("nonmonotone carry relation")
    return carry0, carry0 ^ carry1


def symbol(relation: tuple[int, int]) -> int:
    generate, propagate = relation
    if generate:
        return 2
    if propagate:
        return 1
    return 0


def carry_from_relation(relation: tuple[int, int], carry: int) -> int:
    return relation[0] | (relation[1] & carry)


def row_sequence(row: dict[str, str], width: int, alignment: str
                 ) -> tuple[list[int], list[int], tuple[int, int]]:
    s_value = int(row["S"], 16)
    b_value = int(row["B"], 16)
    cut = int(row["k"])
    scale = int(row["rscale"])
    if alignment == "integer":
        first = 0
    elif alignment == "absolute":
        first = (-scale) % width
    elif alignment == "cut":
        first = cut % width
    else:
        raise AssertionError(alignment)
    first = min(first, cut)

    boundary_carries = [
        carry_from_relation(segment_relation(s_value, b_value, 0, first), 1)
    ]
    symbols = []
    position = first
    while position + width <= cut:
        relation = segment_relation(
            s_value, b_value, position, position + width)
        symbols.append(symbol(relation))
        boundary_carries.append(
            carry_from_relation(relation, boundary_carries[-1]))
        position += width
    tail = segment_relation(s_value, b_value, position, cut)
    exact = carry_from_relation(tail, boundary_carries[-1])
    direct = carry_from_relation(segment_relation(s_value, b_value, 0, cut), 1)
    if exact != direct:
        raise AssertionError("block decomposition changed exact carry")
    return symbols, boundary_carries, tail


def transition_tables() -> np.ndarray:
    # table[law,state,symbol].  Law 0x38 is the exact G | P*C recurrence.
    tables = np.empty((64, 2, 3), dtype=np.uint8)
    for law in range(64):
        for state in (0, 1):
            for input_symbol in range(3):
                tables[law, state, input_symbol] = (
                    law >> (2 * input_symbol + state)) & 1
    return tables


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("physical_rows", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    with args.physical_rows.open(newline="") as source:
        rows = [row for row in csv.DictReader(source, delimiter="\t")
                if row["physical_status"] == "constraining"]
    truth = np.asarray([
        # h1163's label denotes the nonzero displacement.  In the exact
        # delta=borrow-1+carry convention that is carry=1 for theta<0 and
        # carry=0 for theta>=0.
        int(row["physical_label"])
        if int(row["theta"]) < 0 else 1 - int(row["physical_label"])
        for row in rows
    ], dtype=np.uint8)
    positives = np.asarray([row["label"] == "POS" for row in rows])
    # All retained rows have one physical endpoint.  NEG rows already select
    # it; POS rows select the opposite binary carry endpoint.
    incumbent = truth ^ positives.astype(np.uint8)
    tables = transition_tables()
    laws = np.arange(64)[:, None]
    results = []
    compositions = []
    baselines = []

    for width in WIDTHS:
        for alignment in ALIGNMENTS:
            decomposed = [row_sequence(row, width, alignment) for row in rows]
            exact_predictions = np.asarray([
                carry_from_relation(tail, boundary[-1])
                for _, boundary, tail in decomposed
            ], dtype=np.uint8)
            baselines.append((
                int(np.count_nonzero(exact_predictions != truth)),
                int(np.count_nonzero((exact_predictions != truth) & positives)),
                width, alignment,
            ))
            for depth in DEPTHS:
                for seed_name in SEEDS:
                    max_steps = min(
                        depth, max((len(item[0]) for item in decomposed), default=0))
                    sequence = np.full(
                        (len(rows), max_steps), -1, dtype=np.int8)
                    seed_values = np.empty(len(rows), dtype=np.uint8)
                    tail_g = np.empty(len(rows), dtype=np.uint8)
                    tail_p = np.empty(len(rows), dtype=np.uint8)
                    for index, (symbols, boundary, tail) in enumerate(decomposed):
                        take = min(depth, len(symbols))
                        suffix = symbols[len(symbols) - take:]
                        if suffix:
                            sequence[index, max_steps - len(suffix):] = suffix
                        if seed_name == "zero":
                            seed_values[index] = 0
                        elif seed_name == "one":
                            seed_values[index] = 1
                        else:
                            seed_values[index] = boundary[len(symbols) - take]
                        tail_g[index], tail_p[index] = tail

                    state = np.broadcast_to(
                        seed_values, (64, len(rows))).copy()
                    for position in range(max_steps):
                        inputs = sequence[:, position]
                        valid = inputs >= 0
                        if not np.any(valid):
                            continue
                        selected_state = state[:, valid]
                        selected_symbol = np.broadcast_to(
                            inputs[valid], selected_state.shape)
                        state[:, valid] = tables[
                            laws, selected_state, selected_symbol]
                    prediction = tail_g | (tail_p & state)
                    wrong = prediction != truth
                    target_wrong = np.count_nonzero(
                        wrong & positives[None, :], axis=1)
                    control_wrong = np.count_nonzero(
                        wrong & (~positives)[None, :], axis=1)
                    total_wrong = target_wrong + control_wrong
                    for law in range(64):
                        results.append((
                            int(total_wrong[law]), int(target_wrong[law]),
                            int(control_wrong[law]), width, alignment,
                            depth, seed_name, law,
                        ))
                        codes = (4 * truth + 2 * incumbent
                                 + prediction[law]).astype(np.uint8)
                        contingency = np.bincount(codes, minlength=8)
                        for gate in range(16):
                            errors = 0
                            positive_errors = 0
                            for physical in (0, 1):
                                for current in (0, 1):
                                    for predicted in (0, 1):
                                        output = (gate >> (
                                            2 * current + predicted)) & 1
                                        if output == physical:
                                            continue
                                        count = int(contingency[
                                            4 * physical
                                            + 2 * current + predicted])
                                        errors += count
                                        # Incumbent differs from physical
                                        # exactly on the frozen POS rows.
                                        if current != physical:
                                            positive_errors += count
                            compositions.append((
                                errors, positive_errors,
                                errors - positive_errors, width, alignment,
                                depth, seed_name, law, gate,
                            ))

    results.sort()
    compositions.sort()
    baselines.sort()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"physical_rows_sha256\t{digest(args.physical_rows)}\n")
        target.write(f"rows\t{len(rows)}\n")
        target.write(f"positive_rows\t{int(positives.sum())}\n")
        target.write("transition_laws\t64\n")
        target.write("exact_law_hex\t38\n")
        target.write("\n[exact ripple baselines]\n")
        target.write("total_miss\tpositive_miss\twidth\talignment\n")
        for result in baselines:
            target.write("\t".join(map(str, result)) + "\n")
        target.write("\n[block automaton ranking]\n")
        target.write(
            "total_miss\tpositive_miss\tcontrol_miss\twidth\t"
            "alignment\tdepth\tseed\tlaw_hex\n")
        for total, pos, neg, width, alignment, depth, seed, law in results[:1000]:
            target.write(
                f"{total}\t{pos}\t{neg}\t{width}\t{alignment}\t"
                f"{depth}\t{seed}\t{law:02x}\n")
        target.write("\n[incumbent boolean compositions]\n")
        target.write(
            "total_miss\tpositive_miss\tcontrol_miss\twidth\t"
            "alignment\tdepth\tseed\tlaw_hex\tgate_hex\n")
        for (total, pos, neg, width, alignment, depth, seed,
             law, gate) in compositions[:1000]:
            target.write(
                f"{total}\t{pos}\t{neg}\t{width}\t{alignment}\t"
                f"{depth}\t{seed}\t{law:02x}\t{gate:x}\n")

    print(
        f"rows={len(rows)} positives={int(positives.sum())} "
        f"ripple_miss={baselines[0][0]} best={results[0]} "
        f"best_composition={compositions[0]} "
        f"report={args.report}", flush=True)


if __name__ == "__main__":
    main()
