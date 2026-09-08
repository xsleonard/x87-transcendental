#!/usr/bin/env python3
"""Validate h81's held-out table-bias bit rules on the master RN sweep.

The decision rules below are the highest-ranked mechanically plausible h81
survivors.  None was selected using the master sweep.  This script applies
each narrow/wide pair to exact direct or M66-reduced kernel states, rotates
the result through the quadrant, and reports whole-input RN failures.

This is validation, not permission to port a rule: a winning bit still needs
an independently generated discriminator before it can replace the constant
Round-21 state representation.
"""

from __future__ import annotations

import pathlib
import typing

import h58_constraint_search as h58
import h60_round16_parity as h60
import h79_table_state_bias as h79
import h80_round21_parity as h80
import h81_table_bias_bit_search as h81


ROOT = pathlib.Path(__file__).resolve().parents[1]
INPUTS = ROOT / "capture-kit" / "inputs" / "sweep_inputs.txt"
CAPTURE = ROOT / "capture-kit-captures" / "pentiumII" / "sweep_rn.txt"


Rule = tuple[str, typing.Optional[str], tuple[int, int]]

NARROW_RULES: tuple[Rule, ...] = (
    ("fixed-4", None, (4, 4)),
    (
        "sum-discard-3",
        "a+correction.discarded.bit3",
        (5, 4),
    ),
    (
        "correction-bit-10",
        "correction.retained.bit10",
        (4, 5),
    ),
    (
        "correction-bit-9",
        "correction.retained.bit9",
        (4, 5),
    ),
    (
        "q-product-discard-1",
        "q*asq.discarded.bit1",
        (5, 4),
    ),
    ("t-bit-3", "t.retained.bit3", (5, 4)),
)

WIDE_RULES: tuple[Rule, ...] = (
    ("fixed-5", None, (5, 5)),
    ("a-bit-11", "a.retained.bit11", (4, 5)),
    ("p-bit-12", "p.retained.bit12", (5, 4)),
    ("a-bit-10", "a.retained.bit10", (5, 4)),
    ("S-bit-5", "S.retained.bit5", (5, 4)),
    ("S-bit-7", "S.retained.bit7", (5, 4)),
)


def rule_numerator(
    point: h58.PreparedPoint,
    rule: Rule,
    name_to_index: dict[str, int],
) -> int:
    _, feature_name, biases = rule
    if feature_name is None:
        return biases[0]
    feature = h81.feature_vector(point)[name_to_index[feature_name]]
    return biases[feature]


def main() -> None:
    input_rows = [
        tuple(int(field, 16) for field in line.split())
        for line in INPUTS.read_text().splitlines()
    ]
    hardware = [
        None if line == "C2" else h58.parse_sincos(line)
        for line in CAPTURE.read_text().splitlines()
    ]
    active = [
        h80.active_table_input(se, sig) for se, sig in input_rows
    ]
    name_to_index = {
        name: index
        for index, name in enumerate(h81.feature_names())
    }
    non_table = sum(item is None for item in active)
    print(
        f"loaded {len(active)} master inputs; "
        f"table-active={len(active) - non_table}; non-table={non_table}"
    )

    rows = []
    for narrow_rule in NARROW_RULES:
        for wide_rule in WIDE_RULES:
            misses = 0
            narrow_misses = 0
            wide_misses = 0
            for item, expected in zip(active, hardware):
                if item is None:
                    continue
                if expected is None:
                    raise AssertionError("table input unexpectedly returned C2")
                signed_n, point, _ = item
                rule = wide_rule if point.wide else narrow_rule
                numerator = rule_numerator(
                    point, rule, name_to_index
                )
                values = h79.values(point, h79.BASE, numerator)
                actual = tuple(
                    h58.x87_round(value, "rn")
                    for value in h60.rotate(values, signed_n)
                )
                mismatch = actual != expected
                misses += mismatch
                if point.wide:
                    wide_misses += mismatch
                else:
                    narrow_misses += mismatch
            rows.append(
                (
                    misses,
                    narrow_misses,
                    wide_misses,
                    narrow_rule[0],
                    wide_rule[0],
                )
            )
    rows.sort()
    for (
        misses,
        narrow_misses,
        wide_misses,
        narrow_name,
        wide_name,
    ) in rows[:16]:
        print(
            f"{narrow_name:24s} + {wide_name:10s}: "
            f"table-miss={misses} "
            f"(narrow={narrow_misses}, wide={wide_misses})"
        )


if __name__ == "__main__":
    main()
