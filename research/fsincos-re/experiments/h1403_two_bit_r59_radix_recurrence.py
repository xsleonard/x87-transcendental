#!/usr/bin/env python3
"""Search a fixed two-bit radix recurrence for the current R59 carry flips.

The one-bit K/P/G family is eliminated by h1402.  This bounded successor is
the smallest recurrence that can retain both a carry and one attached-history
bit while walking the same fixed radix blocks:

    state_next = (a*state + b*symbol + c) mod 4

where symbol is the ordinary kill/propagate/generate code 0/1/2.  Width,
alignment, suffix depth, seed, optional final partial-block symbol, and the
four-state decoder are exhausted.  The decoder is tested both as the physical
carry and as a complement-enable on the incumbent carry.  No branch, operand
constant, or input interval is available to the grammar.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
from pathlib import Path

import numpy as np

from h1110_carry_gate_mine import allmode_allowed, extract_carry_state
from h1180_block_carry_automaton import row_sequence, symbol
from h1386_current_r59_feature_bank import dump


WIDTHS = (1, 2, 4, 8, 16, 32)
ALIGNMENTS = ("integer", "absolute", "cut")
DEPTHS = (1, 2, 3, 4, 6, 8, 12, 999)
SEEDS = ("zero", "one", "two", "three", "exact")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def load_dataset(args: argparse.Namespace):
    positive_allowed = allmode_allowed(args.positive_allmode)
    control_allowed = allmode_allowed(args.control_allmode)
    with args.features.open(newline="") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    extra = dump(str(args.model), args.extra_mode, [args.extra_op])[0]
    extra.update({"label": "POS", "op": args.extra_op,
                  "mode": args.extra_mode})
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
    return constrained


def decoder_scores(states: np.ndarray, truth: np.ndarray,
                   positives: np.ndarray):
    # state x truth x positive/control contingency makes the 16 decoders a
    # tiny fixed loop instead of rescanning every row for every decoder.
    codes = 4 * states + 2 * truth + positives.astype(np.uint8)
    counts = np.bincount(codes, minlength=16)
    scores = []
    for decoder in range(16):
        positive_bad = 0
        control_bad = 0
        for state in range(4):
            prediction = (decoder >> state) & 1
            for expected in (0, 1):
                if prediction == expected:
                    continue
                control_bad += int(counts[4 * state + 2 * expected])
                positive_bad += int(counts[4 * state + 2 * expected + 1])
        scores.append((
            positive_bad + control_bad,
            positive_bad,
            control_bad,
            decoder,
        ))
    return scores


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

    constrained = load_dataset(args)
    rows = [row for row, _ in constrained]
    truth = np.asarray(
        [next(iter(state[3])) for _, state in constrained], dtype=np.uint8)
    incumbent = np.asarray(
        [state[2] for _, state in constrained], dtype=np.uint8)
    flip_truth = truth ^ incumbent
    positives = np.asarray(
        [row["label"] == "POS" for row in rows], dtype=bool)

    direct_scores = []
    flip_scores = []
    exact_direct = []
    exact_flip = []
    laws = tuple(itertools.product(range(4), repeat=3))
    for width in WIDTHS:
        for alignment in ALIGNMENTS:
            decomposed = [row_sequence(row, width, alignment) for row in rows]
            for depth in DEPTHS:
                max_steps = min(
                    depth,
                    max((len(item[0]) for item in decomposed), default=0),
                )
                base_sequence = np.full(
                    (len(rows), max_steps), -1, dtype=np.int8)
                exact_seeds = np.empty(len(rows), dtype=np.uint8)
                tail_symbols = np.empty(len(rows), dtype=np.uint8)
                for index, (symbols, boundary, tail) in enumerate(decomposed):
                    take = min(depth, len(symbols))
                    suffix = symbols[len(symbols) - take:]
                    if suffix:
                        base_sequence[index, max_steps - len(suffix):] = suffix
                    exact_seeds[index] = boundary[len(symbols) - take]
                    tail_symbols[index] = symbol(tail)

                for include_tail in (0, 1):
                    if include_tail:
                        sequence = np.concatenate(
                            (base_sequence, tail_symbols[:, None]), axis=1)
                    else:
                        sequence = base_sequence
                    for seed_name in SEEDS:
                        if seed_name == "exact":
                            seed = exact_seeds
                        else:
                            seed = np.full(
                                len(rows),
                                {"zero": 0, "one": 1,
                                 "two": 2, "three": 3}[seed_name],
                                dtype=np.uint8,
                            )
                        for a, b, c in laws:
                            state = seed.copy()
                            for position in range(sequence.shape[1]):
                                inputs = sequence[:, position]
                                valid = inputs >= 0
                                state[valid] = (
                                    a * state[valid] + b * inputs[valid] + c
                                ) & 3
                            prefix = (width, alignment, depth, include_tail,
                                      seed_name, a, b, c)
                            for all_bad, pos_bad, control_bad, decoder \
                                    in decoder_scores(state, truth, positives):
                                score = (all_bad, pos_bad, control_bad,
                                         *prefix, decoder)
                                direct_scores.append(score)
                                if len(direct_scores) == 8192:
                                    direct_scores.sort()
                                    del direct_scores[1024:]
                                if all_bad == 0:
                                    exact_direct.append(score)
                            for all_bad, pos_bad, control_bad, decoder \
                                    in decoder_scores(
                                        state, flip_truth, positives):
                                score = (all_bad, pos_bad, control_bad,
                                         *prefix, decoder)
                                flip_scores.append(score)
                                if len(flip_scores) == 8192:
                                    flip_scores.sort()
                                    del flip_scores[1024:]
                                if all_bad == 0:
                                    exact_flip.append(score)

    direct_scores.sort()
    flip_scores.sort()
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
        target.write("candidate_policy\tfixed_two_bit_affine_radix_"
                     "KPG_recurrence\n")
        target.write(f"constrained_rows\t{len(rows)}\n")
        target.write(f"positive_rows\t{int(positives.sum())}\n")
        target.write(f"exact_direct\t{len(exact_direct)}\n")
        target.write(f"exact_flip\t{len(exact_flip)}\n")
        columns = (
            "all_bad", "positive_bad", "control_bad", "width",
            "alignment", "depth", "include_tail", "seed",
            "a", "b", "c", "decoder_hex",
        )
        for title, scores in (
            ("physical-carry recurrence ranking", direct_scores),
            ("incumbent-flip recurrence ranking", flip_scores),
        ):
            target.write("\n[" + title + "]\n")
            target.write("\t".join(columns) + "\n")
            for score in scores[:256]:
                target.write("\t".join(map(
                    str, (*score[:-1], f"{score[-1]:x}"))) + "\n")
        if exact_direct or exact_flip:
            target.write("\n[exact candidates]\n")
            for kind, scores in (("direct", exact_direct),
                                 ("flip", exact_flip)):
                for score in scores:
                    target.write(kind + "\t" + "\t".join(map(
                        str, (*score[:-1], f"{score[-1]:x}"))) + "\n")

    print(
        f"wrote {args.report}: rows={len(rows)} positives="
        f"{int(positives.sum())} direct_best={direct_scores[0][:3]} "
        f"flip_best={flip_scores[0][:3]} exact="
        f"{len(exact_direct)}/{len(exact_flip)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
