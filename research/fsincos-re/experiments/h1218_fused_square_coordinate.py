#!/usr/bin/env python3
"""Audit fused-square quotient/remainder coordinates on stage-A collisions.

R60 forms its signed selector coordinate from the materialized 67-bit first
square ``mu`` and the residue of ``mu*mu``.  A distinct, label-independent
hardware representation is possible: the low tail discarded while producing
``mu`` may remain attached to the multiplier and participate in the next
square.  This script tests that representation exactly and at every prefix
precision from one through sixteen retained tail bits.

For x = mu + tail/2**g, the tested coordinate is

    low3 * (x - 2**66) - (x*x mod 2**s4).

Three projections isolate the mechanism: tail in the linear term only, tail
in the square residue only, and tail in both.  Coordinates are evaluated as
integers over their exact common denominator.  No threshold, operand identity,
or hardware label enters their construction.  Labels are used only to test
whether each physical response becomes monotone within the pre-existing R59
digit cells.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import defaultdict
from pathlib import Path

from h1178_round_history_state_audit import CELL
from h1196_reframed_history_partition import physical_deviation


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def signed128(text: str) -> int:
    value = int(text, 16)
    return value - (1 << 128) if value >> 127 else value


def first_square(row: dict[str, str]) -> tuple[int, int, int]:
    magnitude = int(row["tc_mag_sig"], 16)
    product = magnitude * magnitude
    mu = int(row["tc_mul_sig"], 16)
    shift = product.bit_length() - 67
    if shift <= 0 or product >> shift != mu:
        raise RuntimeError("first-square reconstruction mismatch: " + row["op"])
    return mu, product & ((1 << shift) - 1), shift


def prefix_fraction(tail: int, shift: int, bits: int) -> tuple[int, int]:
    """Return x numerator/denominator for mu plus a tail prefix."""
    if bits == 0:
        return 0, 1
    kept = min(bits, shift)
    numerator = tail >> (shift - kept)
    return numerator, 1 << kept


def coordinate(
    mu: int,
    tail_numerator: int,
    denominator: int,
    low3: int,
    s4: int,
    linear_tail: bool,
    square_tail: bool,
) -> tuple[int, int]:
    """Return an exact signed coordinate as numerator/positive denominator."""
    linear_numerator = mu * denominator
    if linear_tail:
        linear_numerator += tail_numerator
    square_numerator = mu * denominator
    if square_tail:
        square_numerator += tail_numerator

    common_denominator = denominator * denominator
    linear_term = low3 * (
        linear_numerator * denominator - (1 << 66) * common_denominator
    )
    modulus = (1 << s4) * common_denominator
    square_residue = (square_numerator * square_numerator) % modulus
    return linear_term - square_residue, common_denominator


def is_nonmonotone(
    theta: int, entries: list[tuple[int, int, str, bool]]
) -> bool:
    fires = [value for value, label, _, _ in entries if label]
    cleans = [value for value, label, _, _ in entries if not label]
    if not fires or not cleans:
        return False
    return max(fires) >= min(cleans) if theta >= 0 else max(cleans) >= min(fires)


def score(
    records: list[tuple[tuple[int, ...], int, int, str, bool]],
) -> tuple[int, int, int, int, int]:
    groups: dict[tuple[int, ...], list[tuple[int, int, str, bool]]] = defaultdict(list)
    for key, coordinate_value, response, operand, target in records:
        # Every candidate in one score has one fixed denominator, so integer
        # numerators preserve exact order without division.
        groups[key].append((coordinate_value, response, operand, target))

    mixed = 0
    nonmonotone = 0
    bad_rows = 0
    target_nonmonotone = set()
    target_groups = set()
    for key, entries in groups.items():
        labels = [label for _, label, _, _ in entries]
        if any(labels) and not all(labels):
            mixed += 1
        targets = {operand for _, _, operand, target in entries if target}
        target_groups.update(targets)
        if is_nonmonotone(key[0], entries):
            nonmonotone += 1
            bad_rows += len(entries)
            target_nonmonotone.update(targets)
    return (
        nonmonotone,
        bad_rows,
        mixed,
        len(target_nonmonotone),
        len(target_groups),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rows", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    source_rows = []
    with args.rows.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            if row["physical_status"] != "constraining":
                continue
            source_rows.append(row)
    if not source_rows:
        raise SystemExit("no constraining rows")

    candidate_records: dict[
        tuple[int, str], list[tuple[tuple[int, ...], int, int, str, bool]]
    ] = defaultdict(list)
    tail_diagnostics = []
    for row in source_rows:
        key = tuple(int(row[field]) for field in CELL)
        response = physical_deviation(row)
        operand = row["op"]
        target = row["label"] == "POS"
        mu, tail, shift = first_square(row)
        current = signed128(row["Mreg"])
        candidate_records[(0, "materialized")].append(
            (key, current, response, operand, target)
        )
        for bits in range(1, 17):
            tail_numerator, denominator = prefix_fraction(tail, shift, bits)
            for name, linear_tail, square_tail in (
                ("linear", True, False),
                ("square", False, True),
                ("both", True, True),
            ):
                value, value_denominator = coordinate(
                    mu, tail_numerator, denominator, int(row["low3"]),
                    int(row["s4"]), linear_tail, square_tail,
                )
                if value_denominator != denominator * denominator:
                    raise AssertionError("coordinate denominator mismatch")
                candidate_records[(bits, name)].append(
                    (key, value, response, operand, target)
                )
        if target:
            tail_diagnostics.append((
                operand, key, shift, tail,
                tail >> max(0, shift - 16),
                current,
            ))

    scores = []
    for (bits, name), records in candidate_records.items():
        result = score(records)
        scores.append((*result, bits, name))
    scores.sort(key=lambda item: (item[:4], item[5], item[6]))

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target_file:
        target_file.write(f"rows_sha256\t{digest(args.rows)}\n")
        target_file.write(f"constraining_rows\t{len(source_rows)}\n")
        target_file.write(f"candidates\t{len(scores)}\n")
        target_file.write("\n[coordinate ranking]\n")
        target_file.write(
            "nonmonotone\tbad_rows\tmixed\ttarget_nonmonotone\t"
            "targets\ttail_prefix_bits\tprojection\n"
        )
        for result in scores:
            target_file.write("\t".join(map(str, result)) + "\n")
        target_file.write("\n[target first-square tails]\n")
        target_file.write(
            "op\tcell\tshift\ttail_hex\ttop16_hex\tmaterialized_M\n"
        )
        for operand, key, shift, tail, top16, current in sorted(tail_diagnostics):
            target_file.write(
                f"{operand}\t{'/'.join(map(str, key))}\t{shift}\t{tail:x}\t"
                f"{top16:04x}\t{current}\n"
            )

    best = scores[0]
    print(
        f"wrote {args.report} rows={len(source_rows)} candidates={len(scores)} "
        f"best={best}",
        flush=True,
    )


if __name__ == "__main__":
    main()
