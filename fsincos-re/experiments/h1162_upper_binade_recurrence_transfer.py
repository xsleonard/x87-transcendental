#!/usr/bin/env python3
"""Test h1158's three-bit recurrence as an isomorphism on h1095.

The search is entirely against cached hardware rows.  It evaluates every
permutation and polarity of the correction-exponent, square-width, and
right-shift phase bits.  This can show whether the lower-binade recurrence
transfers by a simple phase relabeling; it cannot validate a newly selected
mapping without a separate blind.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
from collections import Counter
from pathlib import Path

from h1137_lower_binade_features import run_values


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def threshold(row: dict[str, str], e: int, a: int, h: int) -> int:
    theta = int(row["theta"])
    payload = int(row["payload"])
    b1, b2 = int(row["b1"]), int(row["b2"])
    slope = 2 + 3 * a + h * (1 - a)
    intercept0 = -1 - a - (1 - e) * (h + 2 * a)
    tap1 = tap2 = 0
    intercept = intercept0
    if theta == -2:
        tap1 = (
            2 * a * (1 - e * (1 - h))
            + (1 - e) * h * (1 - a)
        )
        intercept = -1 - a + a * h * (3 - e)
    elif theta == -1:
        tap2 = a * h * (2 - e)
        intercept += (1 - e) * (2 * a + h) + a * h
    elif theta == 0:
        tap1 = (1 - e) * h * (1 + a)
    elif theta == 1:
        tap2 = (1 - e) * (1 + a * (1 - h))
        intercept -= tap2
    else:
        tap1 = a + (1 - e) * (1 - a) * (1 - h)
        intercept -= (
            2 * (1 - e) * (1 + a * (1 - h))
            + 3 * a * h + a * e * (1 - h)
        )
    return slope * payload + tap1 * b1 + tap2 * b2 + intercept


def recurrence_fire(row: dict[str, str], bits: tuple[int, int, int]) -> int:
    theta = int(row["theta"])
    boundary = threshold(row, *bits) * (1 << 66)
    mreg = int(row["Mreg"], 16)
    if mreg >> 127:
        mreg -= 1 << 128
    return int(mreg < boundary if theta >= 0 else mreg >= boundary)


def physical_delta(row: dict[str, str], fire: int) -> int:
    return (1 if int(row["theta"]) < 0 else -1) if fire else 0


def incumbent_fire(row: dict[str, str]) -> int:
    branch = row["branch"]
    if branch == "tie":
        return int(row.get("br_tfire", "0") or 0)
    if branch in ("band", "corner"):
        return int(row.get("br_fire", "0") or 0)
    if branch == "q67th2":
        return 0
    raise RuntimeError(f"unsupported R59 branch {branch}: {row['op']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("force_minus1", type=Path)
    parser.add_argument("force_zero", type=Path)
    parser.add_argument("force_plus1", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    with args.features.open(newline="") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    paths = {-1: args.force_minus1, 0: args.force_zero, 1: args.force_plus1}
    outputs = {}
    for mode in ("rn", "rd", "ru", "rz"):
        mode_rows = [row for row in rows if row["mode"] == mode]
        for value, path in paths.items():
            predicted = run_values(path, mode, mode_rows)
            for row, output in zip(mode_rows, predicted):
                outputs[(row["op"], mode, value)] = output

    physical = Counter()
    for row in rows:
        allowed = [value for value in (-1, 0, 1)
                   if outputs[(row["op"], row["mode"], value)] == row["hw"]]
        physical[(row["label"], tuple(allowed))] += 1

    mappings = []
    compositions = []
    names = ("e", "a", "h")
    for permutation in itertools.permutations(range(3)):
        for flips in itertools.product((0, 1), repeat=3):
            counts = Counter()
            for row in rows:
                raw = (
                    -int(row["ce"]) - 72,
                    int(row["s4"]) - 66,
                    int(row["rsh"]) - 63,
                )
                if any(value not in (0, 1) for value in raw):
                    counts[(row["label"], "out_of_cube")] += 1
                    continue
                bits = tuple(raw[permutation[index]] ^ flips[index]
                             for index in range(3))
                choice = physical_delta(row, recurrence_fire(row, bits))
                output = outputs[(row["op"], row["mode"], choice)]
                verdict = "exact" if output == row["hw"] else "miss"
                counts[(row["label"], verdict)] += 1
            total_miss = sum(value for (label, verdict), value in counts.items()
                             if verdict != "exact")
            pos_miss = counts[("POS", "miss")] + counts[("POS", "out_of_cube")]
            neg_miss = counts[("NEG", "miss")] + counts[("NEG", "out_of_cube")]
            mappings.append((
                total_miss, pos_miss, neg_miss, permutation, flips, counts,
            ))
            for gate in range(16):
                counts = Counter()
                for row in rows:
                    raw = (
                        -int(row["ce"]) - 72,
                        int(row["s4"]) - 66,
                        int(row["rsh"]) - 63,
                    )
                    if any(value not in (0, 1) for value in raw):
                        counts[(row["label"], "out_of_cube")] += 1
                        continue
                    bits = tuple(raw[permutation[index]] ^ flips[index]
                                 for index in range(3))
                    old = incumbent_fire(row)
                    new = recurrence_fire(row, bits)
                    fire = (gate >> (2 * old + new)) & 1
                    choice = physical_delta(row, fire)
                    output = outputs[(row["op"], row["mode"], choice)]
                    verdict = "exact" if output == row["hw"] else "miss"
                    counts[(row["label"], verdict)] += 1
                total_miss = sum(
                    value for (label, verdict), value in counts.items()
                    if verdict != "exact")
                pos_miss = (counts[("POS", "miss")]
                            + counts[("POS", "out_of_cube")])
                neg_miss = (counts[("NEG", "miss")]
                            + counts[("NEG", "out_of_cube")])
                compositions.append((
                    total_miss, pos_miss, neg_miss, gate,
                    permutation, flips, counts,
                ))
    mappings.sort(key=lambda item: item[:5])
    compositions.sort(key=lambda item: item[:6])

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("w") as target:
        target.write(f"features_sha256\t{digest(args.features)}\n")
        for value, path in paths.items():
            target.write(f"force_{value}_sha256\t{digest(path)}\n")
        target.write(f"rows\t{len(rows)}\n")
        target.write("\n[physical-allowed]\n")
        for key, count in sorted(physical.items(), key=str):
            target.write(f"{key[0]}\t{','.join(map(str, key[1])) or '-'}\t{count}\n")
        target.write("\n[mappings]\n")
        target.write("total_miss\tpos_miss\tneg_miss\tinput_for_e\tinput_for_a\t"
                     "input_for_h\tflip_e\tflip_a\tflip_h\n")
        for total_miss, pos_miss, neg_miss, permutation, flips, _ in mappings:
            target.write(
                f"{total_miss}\t{pos_miss}\t{neg_miss}\t"
                f"{names[permutation[0]]}\t{names[permutation[1]]}\t"
                f"{names[permutation[2]]}\t{flips[0]}\t{flips[1]}\t{flips[2]}\n"
            )
        target.write("\n[boolean-compositions]\n")
        target.write("total_miss\tpos_miss\tneg_miss\tgate_hex\tinput_for_e\t"
                     "input_for_a\tinput_for_h\tflip_e\tflip_a\tflip_h\n")
        for total_miss, pos_miss, neg_miss, gate, permutation, flips, _ in compositions[:192]:
            target.write(
                f"{total_miss}\t{pos_miss}\t{neg_miss}\t{gate:x}\t"
                f"{names[permutation[0]]}\t{names[permutation[1]]}\t"
                f"{names[permutation[2]]}\t{flips[0]}\t{flips[1]}\t{flips[2]}\n"
            )
    best = mappings[0]
    print(f"rows={len(rows)} mappings={len(mappings)} best_miss={best[0]} "
          f"pos_miss={best[1]} neg_miss={best[2]} permutation={best[3]} "
          f"flips={best[4]}")
    composed = compositions[0]
    print(f"compositions={len(compositions)} best_miss={composed[0]} "
          f"pos_miss={composed[1]} neg_miss={composed[2]} gate={composed[3]:x} "
          f"permutation={composed[4]} flips={composed[5]}")


if __name__ == "__main__":
    main()
