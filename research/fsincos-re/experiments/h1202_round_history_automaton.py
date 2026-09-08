#!/usr/bin/env python3
"""Search tiny recurrences for the P6 rounding-history tag.

The patent-motivated full Horner class sequence removes every post-R1186
order conflict, but retaining that sequence verbatim would just rename a
lookup key.  This experiment instead tests a one-bit state carried through
the fixed model operation graph.  A fixed Boolean transition consumes the prior
state and one documented rounding attribute; variants either share one law
across FMUL/FADD or use one law per operation class.  Odd and even Horner
chains carry independent copies of the same state machine.

All 16 one-bit/two-input transitions (or 16**2 FMUL/FADD pairs) are exhausted.
There are no operand constants or learned branches in the recurrence.  This
is cached-label localization; a surviving automaton is not promoted until a
separate adversarial bank is frozen and opened.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import defaultdict
from pathlib import Path

from h1178_round_history_state_audit import CELL, monotonicity, signed128
from h1196_reframed_history_partition import physical_deviation, row_histories


LANE_STAGES = {
    "odd": ("odd_p1", "odd_a1", "odd_p2", "odd_a2"),
    "even": ("even_p1", "even_a1", "even_p2", "even_a2"),
}
SCHEDULE = (
    "odd_p1", "even_p1", "odd_a1", "even_a1",
    "odd_p2", "even_p2", "odd_a2", "even_a2",
)
ENCODERS = {
    "guard": lambda history: int(
        history["class"] in ("half", "high", "all1")
    ),
    "sticky": lambda history: int(
        history["class"] not in ("exact", "half")
    ),
    "high": lambda history: int(history["class"] in ("high", "all1")),
    "inexact": lambda history: int(history["class"] != "exact"),
    "half": lambda history: int(history["class"] == "half"),
    "all1": lambda history: int(history["class"] == "all1"),
    "direction_positive": lambda history: int(history["direction"] > 0),
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def transition(law: int, state: int, symbol: int) -> int:
    return (law >> (2 * symbol + state)) & 1


def run_chain(symbols: tuple[int, ...], seed: int,
              mul_law: int, add_law: int) -> int:
    state = seed
    for index, symbol in enumerate(symbols):
        state = transition(mul_law if index % 2 == 0 else add_law,
                           state, symbol)
    return state


def recurrence_score(records, encoder_name: str, seed: int,
                     mul_law: int, add_law: int, topology: str):
    groups = defaultdict(list)
    target_states = []
    for row, histories in records:
        encode = ENCODERS[encoder_name]
        if topology == "lanes":
            odd = run_chain(
                tuple(encode(histories[name]) for name in LANE_STAGES["odd"]),
                seed, mul_law, add_law,
            )
            even = run_chain(
                tuple(encode(histories[name]) for name in LANE_STAGES["even"]),
                seed, mul_law, add_law,
            )
            state = 2 * odd + even
        elif topology == "schedule":
            state = seed
            for name in SCHEDULE:
                law = mul_law if "_p" in name else add_law
                state = transition(law, state, encode(histories[name]))
        else:
            raise AssertionError(topology)
        key = tuple(int(row[field]) for field in CELL)
        groups[key + (state,)].append(
            (signed128(row["Mreg"]), physical_deviation(row))
        )
        if row["label"] == "POS":
            target_states.append((row["op"], state))
    mixed, nonmonotone, bad_rows = monotonicity(groups)
    return nonmonotone, bad_rows, mixed, tuple(target_states)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rows", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    with args.rows.open(newline="") as source:
        all_rows = [
            row for row in csv.DictReader(source, delimiter="\t")
            if row["physical_status"] == "constraining"
        ]
    base_groups = defaultdict(list)
    for row in all_rows:
        key = tuple(int(row[field]) for field in CELL)
        base_groups[key].append(
            (signed128(row["Mreg"]), physical_deviation(row))
        )
    conflict_keys = {
        key for key, values in base_groups.items()
        if monotonicity({key: values})[1]
    }
    conflict_rows = [
        row for row in all_rows
        if tuple(int(row[field]) for field in CELL) in conflict_keys
    ]
    records = [(row, row_histories(row)) for row in conflict_rows]

    scores = []
    for encoder_name in ENCODERS:
        for seed in (0, 1):
            for topology in ("lanes", "schedule"):
                for mul_law in range(16):
                    # Shared-law candidates are retained as the simplest
                    # subset; the full loop additionally tests operation-
                    # dependent history, as explicitly allowed by the patent.
                    for add_law in range(16):
                        score = recurrence_score(
                            records, encoder_name, seed,
                            mul_law, add_law, topology,
                        )
                        complexity = int(mul_law != add_law)
                        scores.append((
                            score[0], score[1], score[2], complexity,
                            encoder_name, topology, seed,
                            mul_law, add_law, score[3],
                        ))
    scores.sort(key=lambda item: item[:9])
    exact = [score for score in scores if score[0] == 0]

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"rows_sha256\t{digest(args.rows)}\n")
        target.write(f"constraining_rows\t{len(all_rows)}\n")
        target.write(f"conflict_cells\t{len(conflict_keys)}\n")
        target.write(f"conflict_rows\t{len(conflict_rows)}\n")
        target.write(f"candidates\t{len(scores)}\n")
        target.write(f"zero_nonmonotone_candidates\t{len(exact)}\n")
        target.write("\n[ranking]\n")
        target.write(
            "nonmonotone\tbad_rows\tmixed\top_dependent\tencoder\t"
            "topology\tseed\tmul_law\tadd_law\ttarget_states\n"
        )
        for score in scores[:1000]:
            (*head, target_states) = score
            rendered = ",".join(
                f"{operand}={state}" for operand, state in target_states
            )
            target.write(
                "\t".join(map(str, head[:-2]))
                + f"\t{head[-2]:x}\t{head[-1]:x}\t{rendered}\n"
            )

    print(
        f"wrote {args.report} rows={len(conflict_rows)} "
        f"candidates={len(scores)} exact={len(exact)} best={scores[0][:9]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
