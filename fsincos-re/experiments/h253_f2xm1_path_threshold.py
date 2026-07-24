#!/usr/bin/env python3
"""Infer F2XM1's linear/long/table path boundaries from captured outputs."""

from __future__ import annotations

import collections
import fractions

import h251_f2xm1_exact_baseline as h251
import h252_f2xm1_literal_graph as h252


def dataset(name: str):
    inputs = [
        tuple(int(field, 16) for field in line.split())
        for line in h251.INPUTS[name].read_text().splitlines()
    ]
    captures = {
        rc: [
            h251.parse_output(line)[0]
            for line in (
                h251.CAPTURE / f"{name}_f2xm1_{rc}_status.txt"
            ).read_text().splitlines()
        ]
        for rc in h251.RCS
    }
    rows = []
    for index, (se, sig) in enumerate(inputs):
        x_fraction = h251.decode_input(se, sig)
        if abs(x_fraction) > 1:
            continue
        exponent_field = se & 0x7FFF
        exponent = (
            exponent_field - 16383
            if sig and exponent_field
            else h251.MIN_NORMAL_EXP
        )
        values = h252.values(h252.input_fp(se, sig))
        misses = {
            path: sum(
                h252.rounded(value, rc) != captures[rc][index]
                for rc in h251.RCS
            )
            for path, value in values.items()
        }
        rows.append((abs(x_fraction), exponent, misses))
    return rows


def score(rows, cutoff: int) -> tuple[int, int]:
    mode_misses = 0
    input_misses = 0
    for magnitude, exponent, misses in rows:
        if magnitude >= fractions.Fraction(1, 4):
            path = "table"
        elif exponent >= cutoff:
            path = "long"
        else:
            path = "linear"
        value = misses[path]
        mode_misses += value
        input_misses += bool(value)
    return mode_misses, input_misses


def main() -> None:
    datasets = {name: dataset(name) for name in ("dense", "sweep", "target")}
    ranked = []
    for cutoff in range(-100, -19):
        results = {name: score(rows, cutoff) for name, rows in datasets.items()}
        objective = tuple(sum(result[i] for result in results.values()) for i in range(2))
        ranked.append((objective, cutoff, results))
    ranked.sort()
    print("path-threshold leaders (long when exponent >= cutoff):")
    for objective, cutoff, results in ranked[:16]:
        print(f"  cutoff={cutoff}: total={objective} {results}")

    best_cutoff = ranked[0][1]
    sweep_rows = datasets["sweep"]
    print("linear-versus-long evidence near the boundary:")
    for exponent in range(best_cutoff - 5, best_cutoff + 6):
        counts = collections.Counter()
        for magnitude, row_exponent, misses in sweep_rows:
            if magnitude >= fractions.Fraction(1, 4) or row_exponent != exponent:
                continue
            if misses["linear"] < misses["long"]:
                counts["linear"] += 1
            elif misses["long"] < misses["linear"]:
                counts["long"] += 1
            else:
                counts["tie"] += 1
        print(f"  exponent={exponent}: {dict(counts)}")


if __name__ == "__main__":
    main()
