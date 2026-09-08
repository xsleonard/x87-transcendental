#!/usr/bin/env python3
"""Packed numerical values used by the finite-arithmetic experiments.

The model stores a sign, a 17-bit exponent, a 68-bit mantissa carrier, and
six auxiliary flags. This module validates and exposes those fields.
"""

from __future__ import annotations

from dataclasses import dataclass


DATA_BITS = 86
FLAGS_BITS = 6
MANTISSA_BITS = 68
EXPONENT_BITS = 17

MANTISSA_MASK = (1 << MANTISSA_BITS) - 1
EXPONENT_MASK = (1 << EXPONENT_BITS) - 1
DATA_MASK = (1 << DATA_BITS) - 1
FLAGS_MASK = (1 << FLAGS_BITS) - 1

SIGN_SHIFT = 85
EXPONENT_SHIFT = 68
OVERFLOW_BIT = 67
J_BIT = 66
SIGNAL_BIT = 65
FRACTION_MASK = (1 << SIGNAL_BIT) - 1


@dataclass(frozen=True)
class P6Value:
    data: int
    flags: int = 0

    def __post_init__(self) -> None:
        if not 0 <= self.data <= DATA_MASK:
            raise ValueError(f"86-bit data out of range: {self.data:#x}")
        if not 0 <= self.flags <= FLAGS_MASK:
            raise ValueError(f"6-bit flags out of range: {self.flags:#x}")

    @classmethod
    def from_fields(
        cls, sign: int, exponent: int, mantissa: int, flags: int = 0
    ) -> "P6Value":
        if sign not in (0, 1):
            raise ValueError(f"invalid sign: {sign}")
        if not 0 <= exponent <= EXPONENT_MASK:
            raise ValueError(f"17-bit exponent out of range: {exponent:#x}")
        if not 0 <= mantissa <= MANTISSA_MASK:
            raise ValueError(f"68-bit mantissa out of range: {mantissa:#x}")
        return cls(
            (sign << SIGN_SHIFT) | (exponent << EXPONENT_SHIFT) | mantissa,
            flags,
        )

    @property
    def sign(self) -> int:
        return (self.data >> SIGN_SHIFT) & 1

    @property
    def exponent(self) -> int:
        return (self.data >> EXPONENT_SHIFT) & EXPONENT_MASK

    @property
    def mantissa(self) -> int:
        return self.data & MANTISSA_MASK

    @property
    def overflow(self) -> int:
        return (self.mantissa >> OVERFLOW_BIT) & 1

    @property
    def j(self) -> int:
        return (self.mantissa >> J_BIT) & 1

    @property
    def signal(self) -> int:
        return (self.mantissa >> SIGNAL_BIT) & 1

    @property
    def fraction(self) -> int:
        return self.mantissa & FRACTION_MASK


def selftest() -> None:
    zero = P6Value(0)
    assert (zero.sign, zero.exponent, zero.mantissa, zero.flags) == (0, 0, 0, 0)
    maximum = P6Value.from_fields(1, EXPONENT_MASK, MANTISSA_MASK, FLAGS_MASK)
    assert maximum == P6Value(DATA_MASK, FLAGS_MASK)
    assert (maximum.sign, maximum.exponent, maximum.mantissa) == (
        1, EXPONENT_MASK, MANTISSA_MASK
    )
    value = P6Value.from_fields(
        1, 0xFFFF, (1 << OVERFLOW_BIT) | (1 << J_BIT) | (1 << SIGNAL_BIT) | 0x123, 0x15
    )
    assert (value.overflow, value.j, value.signal, value.fraction) == (1, 1, 1, 0x123)
    assert value.flags == 0x15
    for data, flags in ((-1, 0), (DATA_MASK + 1, 0), (0, -1), (0, FLAGS_MASK + 1)):
        try:
            P6Value(data, flags)
        except ValueError:
            pass
        else:
            raise AssertionError("out-of-range packed value was accepted")
    for fields in ((2, 0, 0), (0, EXPONENT_MASK + 1, 0), (0, 0, MANTISSA_MASK + 1)):
        try:
            P6Value.from_fields(*fields)
        except ValueError:
            pass
        else:
            raise AssertionError("out-of-range field was accepted")


if __name__ == "__main__":
    selftest()
    print("p6_value selftest: OK")
