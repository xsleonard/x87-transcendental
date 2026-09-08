#!/usr/bin/env python3
"""Test the published P5 -57/128 exp-table word against mathematical RN67."""

from __future__ import annotations

import fractions

import h58_constraint_search as h58
import h254_f2xm1_operation_search as h254


ANCHOR = fractions.Fraction(-57, 128)
CANDIDATE = h254.Candidate("chop67", "rn64", "rn64")


def score(points, lookup):
    mode_misses = 0
    input_misses = 0
    for point in points:
        misses = h254.metric_override(point, CANDIDATE, lookup)
        mode_misses += misses
        input_misses += bool(misses)
    return mode_misses, input_misses


def main() -> None:
    selected = []
    for point in h254.points():
        x = h254.h252.input_fp(point.se, point.sig)
        if h254.h252.table_anchor(x) == ANCHOR:
            selected.append(point)

    mathematical = h254.h252.table_value(ANCHOR)
    published_p5 = h58.ROM[110]
    print(f"selected -57/128 cell inputs: {len(selected)}")
    print(
        f"mathematical RN67 payload={mathematical[1]:017x} "
        f"score={score(selected, mathematical)}"
    )
    print(
        f"published P5 payload={published_p5[1]:017x} "
        f"score={score(selected, published_p5)}"
    )


if __name__ == "__main__":
    main()
