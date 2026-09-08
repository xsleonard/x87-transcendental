#!/usr/bin/env python3
"""Transfer table-derived operation classes into F2XM1's long path."""

from __future__ import annotations

import collections
import fractions

import h58_constraint_search as h58
import h251_f2xm1_exact_baseline as h251
import h252_f2xm1_literal_graph as h252
import h254_f2xm1_operation_search as h254


CANDIDATE = h254.Candidate("chop67", "rn64", "rn64")
QUARTER = fractions.Fraction(1, 4)
ONE = fractions.Fraction(1)


def ordinary_mul(
    left: h58.FP, right: h58.FP, candidate: h254.Candidate = CANDIDATE
) -> h58.FP:
    return h254.mul(left, right, candidate.ordinary_mul)


def scale_mul(
    left: h58.FP, right: h58.FP, candidate: h254.Candidate = CANDIDATE
) -> h58.FP:
    return h254.mul(left, right, candidate.scale_mul)


def ordinary_add(
    left: h58.FP, right: h58.FP, candidate: h254.Candidate = CANDIDATE
) -> h58.FP:
    return h254.add(left, right, candidate.ordinary_add)


def long_value(
    x: h58.FP, candidate: h254.Candidate = CANDIDATE
) -> h58.FP:
    # Preserve the two separately materialized ln(2)*x producers and the
    # numerical dependency order; algebraic simplification changes rounding.
    tmp1 = ordinary_mul(h252.LN2, x, candidate)
    tmp2 = scale_mul(h252.LN2, x, candidate)
    tmp2 = ordinary_mul(tmp1, tmp2, candidate)
    c2, c3, c4, c5, c6, c7, c8, c9, c10, c11, c12 = (
        h58.ROM[row] for row in h252.LONG
    )

    tmp5 = ordinary_mul(tmp2, c11, candidate)
    tmp6 = ordinary_mul(tmp2, c12, candidate)
    tmp5 = ordinary_add(c9, tmp5, candidate)
    tmp6 = ordinary_add(c10, tmp6, candidate)
    tmp5 = ordinary_mul(tmp2, tmp5, candidate)
    tmp6 = ordinary_mul(tmp2, tmp6, candidate)
    tmp5 = ordinary_add(c7, tmp5, candidate)
    tmp6 = ordinary_add(c8, tmp6, candidate)
    tmp5 = ordinary_mul(tmp2, tmp5, candidate)
    tmp6 = ordinary_mul(tmp2, tmp6, candidate)
    tmp5 = ordinary_add(c5, tmp5, candidate)
    tmp6 = ordinary_add(c6, tmp6, candidate)
    tmp5 = ordinary_mul(tmp2, tmp5, candidate)
    tmp6 = ordinary_mul(tmp2, tmp6, candidate)
    tmp5 = ordinary_add(c3, tmp5, candidate)
    tmp6 = ordinary_add(c4, tmp6, candidate)
    tmp5 = scale_mul(tmp2, tmp5, candidate)
    tmp6 = scale_mul(tmp2, tmp6, candidate)
    tmp5 = ordinary_mul(tmp1, tmp5, candidate)
    tmp6 = ordinary_mul(tmp2, tmp6, candidate)
    tmp3 = ordinary_mul(tmp2, c2, candidate)
    tmp6 = ordinary_add(tmp5, tmp6, candidate)
    tmp3 = ordinary_add(tmp3, tmp6, candidate)
    return h58.add_exact(tmp1, tmp3)  # final add/writeback class


def linear_value(x: h58.FP) -> h58.FP:
    return h58.mul_exact(h252.LN2, x)  # final multiply/writeback class


def rounded(value: h58.FP, rc: str, zero_sign: int = 0) -> tuple[int, int]:
    return h251.round_x87(h252.fp_fraction(value), rc, zero_sign)[0]


def table_outputs(point: h254.Point) -> tuple[tuple[int, int], ...]:
    x_fraction = h251.decode_input(point.se, point.sig)
    if x_fraction == 1:
        return ((0x3FFF, 0x8000000000000000),) * 3
    if x_fraction == -1:
        return ((0xBFFE, 0x8000000000000000),) * 3
    result = h254.value(point, CANDIDATE)
    return tuple(rounded(result, rc) for rc in h251.RCS)


def rows():
    result = []
    for dataset in ("dense", "sweep", "target"):
        inputs = [
            tuple(int(field, 16) for field in line.split())
            for line in h251.INPUTS[dataset].read_text().splitlines()
        ]
        captures = {
            rc: [
                h251.parse_output(line)[0]
                for line in (
                    h251.CAPTURE / f"{dataset}_f2xm1_{rc}_status.txt"
                ).read_text().splitlines()
            ]
            for rc in h251.RCS
        }
        for index, (se, sig) in enumerate(inputs):
            x_fraction = h251.decode_input(se, sig)
            if abs(x_fraction) > ONE:
                continue
            exponent_field = se & 0x7FFF
            exponent = (
                exponent_field - 16383
                if sig and exponent_field
                else h251.MIN_NORMAL_EXP
            )
            hardware = tuple(captures[rc][index] for rc in h251.RCS)
            point = h254.Point(dataset, index, se, sig, hardware)
            x = h252.input_fp(se, sig)
            if abs(x_fraction) >= QUARTER:
                predictions = {"table": table_outputs(point)}
            else:
                linear_result = linear_value(x)
                long_result = long_value(x)
                exact_result = h252.long_polynomial(
                    h58.mul_exact(h252.LN2, x)
                )
                zero_sign = se >> 15 if not sig else 0
                predictions = {
                    "linear": tuple(
                        rounded(linear_result, rc, zero_sign)
                        for rc in h251.RCS
                    ),
                    "long": tuple(
                        rounded(long_result, rc, zero_sign)
                        for rc in h251.RCS
                    ),
                    "long_exact": tuple(
                        rounded(exact_result, rc, zero_sign)
                        for rc in h251.RCS
                    ),
                }
            misses = {
                path: sum(a != b for a, b in zip(values, hardware))
                for path, values in predictions.items()
            }
            result.append((dataset, abs(x_fraction), exponent, misses))
    return result


def score(all_rows, cutoff: int):
    by_dataset = collections.defaultdict(lambda: [0, 0])
    for dataset, magnitude, exponent, misses in all_rows:
        if magnitude >= QUARTER:
            path = "table"
        elif exponent >= cutoff:
            path = "long"
        else:
            path = "linear"
        by_dataset[dataset][0] += misses[path]
        by_dataset[dataset][1] += bool(misses[path])
    return {key: tuple(value) for key, value in by_dataset.items()}


def main() -> None:
    all_rows = rows()
    path_totals = collections.Counter()
    path_inputs = collections.Counter()
    for _, magnitude, _, misses in all_rows:
        if magnitude >= QUARTER:
            continue
        for path, value in misses.items():
            path_totals[path] += value
            path_inputs[path] += bool(value)
    print("non-table path scores:")
    for path in ("linear", "long_exact", "long"):
        print(
            f"  {path}: mode misses={path_totals[path]} "
            f"input misses={path_inputs[path]}"
        )

    ranked = []
    for cutoff in range(-80, -39):
        results = score(all_rows, cutoff)
        objective = tuple(sum(value[i] for value in results.values()) for i in range(2))
        ranked.append((objective, cutoff, results))
    ranked.sort()
    print("complete schedule leaders:")
    for item in ranked[:12]:
        print(f"  cutoff={item[1]} total={item[0]} {item[2]}")


if __name__ == "__main__":
    main()
