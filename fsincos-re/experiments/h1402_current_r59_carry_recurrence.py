#!/usr/bin/env python3
"""Test one structural carry recurrence across every current R59 residual.

This is the current-source counterpart of h1180.  It uses the unified h1386
branch bank and adds the separately tracked d0d0 tie row from a software dump.
The target is the physical final R59 carry fixed by all four cached rounding
modes, not the architectural endpoint value.

Candidates are fixed one-bit automata over radix-block K/P/G summaries of
S + ~B.  Width, alignment, suffix depth, entry state, transition law, and a
single Boolean composition with the incumbent carry are exhausted.  There
are no operand constants, branch names, or per-row selectors in the grammar.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path

import numpy as np

from h1110_carry_gate_mine import allmode_allowed, extract_carry_state
from h1180_block_carry_automaton import (
    carry_from_relation,
    row_sequence,
    transition_tables,
)
from h1386_current_r59_feature_bank import dump


WIDTHS = (1, 2, 4, 8, 16, 32)
ALIGNMENTS = ("integer", "absolute", "cut")
DEPTHS = (1, 2, 3, 4, 6, 8, 12, 999)
SEEDS = ("zero", "one", "exact")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        return list(csv.DictReader(source, delimiter="\t"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--positive-allmode", type=Path, required=True)
    parser.add_argument("--control-allmode", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--extra-op", default="3ffc d0d000000cc0b3f8")
    parser.add_argument("--extra-mode", default="rd")
    parser.add_argument("--extra-carry", type=int, choices=(0, 1), default=1)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    positive_allowed = allmode_allowed(args.positive_allmode)
    control_allowed = allmode_allowed(args.control_allmode)
    rows = read_rows(args.features)
    extra = dump(str(args.model), args.extra_mode, [args.extra_op])[0]
    extra.update({
        "label": "POS",
        "desired": f"carry{args.extra_carry}",
        "mode": args.extra_mode,
        "op": args.extra_op,
    })
    rows.append(extra)

    constrained = []
    for row in rows:
        if row["op"] == args.extra_op:
            s_value = int(row["S"], 16)
            b_value = int(row["B"], 16)
            mask = (1 << int(row["k"])) - 1
            borrow = int((s_value & mask) < (b_value & mask))
            allowed_delta = {borrow - 1 + args.extra_carry}
        else:
            allowed_delta = (
                positive_allowed if row["label"] == "POS"
                else control_allowed
            )[row["op"]]
        state = extract_carry_state(row, allowed_delta)
        if len(state[3]) == 1:
            constrained.append((row, state))

    truth = np.asarray(
        [next(iter(state[3])) for _, state in constrained], dtype=np.uint8)
    incumbent = np.asarray(
        [state[2] for _, state in constrained], dtype=np.uint8)
    positives = np.asarray(
        [row["label"] == "POS" for row, _ in constrained], dtype=bool)
    tables = transition_tables()
    laws = np.arange(64)[:, None]
    direct_scores = []
    composition_scores = []
    exact_direct = []
    exact_composed = []

    for width in WIDTHS:
        for alignment in ALIGNMENTS:
            decomposed = [
                row_sequence(row, width, alignment)
                for row, _ in constrained
            ]
            for depth in DEPTHS:
                for seed_name in SEEDS:
                    max_steps = min(
                        depth,
                        max((len(item[0]) for item in decomposed), default=0),
                    )
                    sequence = np.full(
                        (len(constrained), max_steps), -1, dtype=np.int8)
                    seed_values = np.empty(len(constrained), dtype=np.uint8)
                    tail_g = np.empty(len(constrained), dtype=np.uint8)
                    tail_p = np.empty(len(constrained), dtype=np.uint8)
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

                    state_values = np.broadcast_to(
                        seed_values, (64, len(constrained))).copy()
                    for position in range(max_steps):
                        symbols = sequence[:, position]
                        valid = symbols >= 0
                        if not np.any(valid):
                            continue
                        old = state_values[:, valid]
                        inputs = np.broadcast_to(symbols[valid], old.shape)
                        state_values[:, valid] = tables[laws, old, inputs]
                    prediction = tail_g | (tail_p & state_values)

                    for law in range(64):
                        wrong = prediction[law] != truth
                        direct = (
                            int(np.count_nonzero(wrong)),
                            int(np.count_nonzero(wrong & positives)),
                            int(np.count_nonzero(wrong & ~positives)),
                            width, alignment, depth, seed_name, law,
                        )
                        direct_scores.append(direct)
                        if direct[0] == 0:
                            exact_direct.append(direct)

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
                                            4 * physical + 2 * current
                                            + predicted])
                                        errors += count
                                        if current != physical:
                                            positive_errors += count
                            composed = (
                                errors, positive_errors,
                                errors - positive_errors,
                                width, alignment, depth, seed_name, law, gate,
                            )
                            composition_scores.append(composed)
                            if errors == 0:
                                exact_composed.append(composed)

    direct_scores.sort()
    composition_scores.sort()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        for name, path in (
            ("features", args.features),
            ("positive_allmode", args.positive_allmode),
            ("control_allmode", args.control_allmode),
            ("model", args.model),
        ):
            target.write(f"{name}_sha256\t{digest(path)}\n")
        target.write("hardware_policy\tcached_labels_only_no_x87_execution\n")
        target.write("candidate_policy\tfixed_one_bit_radix_KPG_recurrence\n")
        target.write(f"source_rows\t{len(rows)}\n")
        target.write(f"constrained_rows\t{len(constrained)}\n")
        target.write(f"positive_rows\t{int(positives.sum())}\n")
        target.write(f"extra_operand\t{args.extra_op}\n")
        target.write(f"extra_required_carry\t{args.extra_carry}\n")
        target.write(f"exact_direct\t{len(exact_direct)}\n")
        target.write(f"exact_composed\t{len(exact_composed)}\n")
        target.write("\n[direct recurrence ranking]\n")
        target.write("all_bad\tpositive_bad\tcontrol_bad\twidth\talignment"
                     "\tdepth\tseed\tlaw_hex\n")
        for score in direct_scores[:256]:
            target.write("\t".join(map(str, (*score[:-1],
                                               f"{score[-1]:02x}"))) + "\n")
        target.write("\n[incumbent-composed recurrence ranking]\n")
        target.write("all_bad\tpositive_bad\tcontrol_bad\twidth\talignment"
                     "\tdepth\tseed\tlaw_hex\tgate_hex\n")
        for score in composition_scores[:256]:
            target.write("\t".join(map(str, (*score[:-2],
                                               f"{score[-2]:02x}",
                                               f"{score[-1]:x}"))) + "\n")

    print(
        f"wrote {args.report}: rows={len(constrained)} "
        f"positives={int(positives.sum())} direct_best={direct_scores[0][:3]} "
        f"composed_best={composition_scores[0][:3]} "
        f"exact={len(exact_direct)}/{len(exact_composed)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
