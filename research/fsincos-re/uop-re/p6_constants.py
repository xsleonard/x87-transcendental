#!/usr/bin/env python3
"""Load named cosine coefficients from the public sibling literal fixture."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from p6_arithmetic import INTERNAL_EXPONENT_BIAS
from p6_value import P6Value


def load_cosine_constants(paths: Sequence[Path]) -> dict[str, P6Value]:
    """Read the six public C6 literals, rejecting conflicting input files."""

    constants: dict[str, P6Value] = {}
    for path in paths:
        document = json.loads(path.read_text())
        if document.get("format") != "x87-sibling-literals-v1":
            raise ValueError(f"expected public sibling literal fixture: {path}")
        rows = document["constants"]["C6"]
        if len(rows) != 6:
            raise ValueError("expected six cosine coefficients")
        for index, row in enumerate(rows, 1):
            significand = int(row["significand"], 16)
            sign = row["sign"]
            if sign not in (0, 1) or significand.bit_length() != 67:
                raise ValueError("expected a signed 67-bit coefficient")
            exponent = INTERNAL_EXPONENT_BIAS + row["scale"] + 66
            value = P6Value.from_fields(sign, exponent, significand)
            name = f"C{index}"
            previous = constants.setdefault(name, value)
            if previous != value:
                raise ValueError(f"conflicting coefficient {name} in {path}")
    if not constants:
        raise ValueError("no coefficient fixture supplied")
    constants["one"] = P6Value.from_fields(0, INTERNAL_EXPONENT_BIAS, 1 << 66)
    return constants


def selftest() -> None:
    from fractions import Fraction

    fixture = Path(__file__).resolve().parents[3] / "tests/data/sibling-constants.json"
    constants = load_cosine_constants([fixture])
    rows = json.loads(fixture.read_text())["constants"]["C6"]
    for index, row in enumerate(rows, 1):
        value = constants[f"C{index}"]
        expected = (-1) ** row["sign"] * Fraction(int(row["significand"], 16)) * Fraction(2) ** row["scale"]
        actual = (-1) ** value.sign * Fraction(value.mantissa) * Fraction(2) ** (value.exponent - INTERNAL_EXPONENT_BIAS - 66)
        assert actual == expected
    assert constants["one"].mantissa == 1 << 66


if __name__ == "__main__":
    selftest()
    print("p6_constants selftest: OK")
