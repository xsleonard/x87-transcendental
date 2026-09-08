#!/usr/bin/env python3
"""Diagnostic 68-bit FADD carrier for finite-normal arithmetic.

The numerical value representation uses bit 67 for overflow, bit 66 for
J, and bit 65 for the signal/datatype bit.  It does *not* identify visible bits
2:0 as guard/round/sticky.  This module numerically treats all lower carrier
positions as fixed-point value bits and keeps discarded alignment state in a
separate Boolean.  Its sticky/borrow choices are hypotheses for testing an
adder boundary, not a literal claim about the undocumented P6 FADD circuit.
"""

from __future__ import annotations

from dataclasses import dataclass

from p6_arithmetic import (
    INTERNAL_EXPONENT_BIAS,
    PRECISION_FLAG,
    ArithmeticResult,
    BusPolicy,
    exact_from_p6,
    p6_from_exact,
    quantize_exact,
)
from p6_value import P6Value


@dataclass(frozen=True)
class AddBus:
    sign: int
    exponent: int
    word: int

    @classmethod
    def from_value(cls, value: P6Value) -> "AddBus":
        if not value.mantissa:
            return cls(value.sign, 0, 0)
        return cls(
            value.sign,
            value.exponent - INTERNAL_EXPONENT_BIAS,
            value.mantissa,
        )

    def to_value(self, flags: int = 0) -> P6Value:
        if not self.word:
            return P6Value.from_fields(self.sign, 0, 0, flags)
        return P6Value.from_fields(
            self.sign,
            self.exponent + INTERNAL_EXPONENT_BIAS,
            self.word,
            flags,
        )


@dataclass(frozen=True)
class AddBusTrace:
    operation: str
    exponent_difference: int
    discarded: bool
    normalized: bool


def shift_right(value: int, amount: int) -> tuple[int, bool]:
    if amount <= 0:
        return value << -amount, False
    if amount >= value.bit_length():
        return 0, bool(value)
    return value >> amount, bool(value & ((1 << amount) - 1))


def compare_magnitude(left: AddBus, right: AddBus) -> int:
    if not left.word:
        return -int(bool(right.word))
    if not right.word:
        return 1
    if left.exponent >= right.exponent:
        left_word = left.word << (left.exponent - right.exponent)
        right_word = right.word
    else:
        left_word = left.word
        right_word = right.word << (right.exponent - left.exponent)
    return (left_word > right_word) - (left_word < right_word)


def finish_raw(
    sign: int,
    exponent: int,
    raw: int,
    outgoing_sticky: bool,
    normalize: bool,
) -> AddBus:
    """Compress an aligned-adder integer with its binary point at bit 67."""

    if not raw:
        return AddBus(0, 0, 0)
    if raw < 0:
        raise ValueError("negative magnitude in FADD finish")
    if normalize:
        top = raw.bit_length() - 1
        if top > 67:
            raw, discarded = shift_right(raw, top - 67)
            outgoing_sticky |= discarded
            exponent += top - 67
        elif top < 67:
            sticky = bool(raw & 1) or outgoing_sticky
            shift = 67 - top
            raw <<= shift
            if sticky:
                raw |= 1
            outgoing_sticky = False
            exponent -= shift
    word = raw >> 1
    if (raw & 1) or outgoing_sticky:
        word |= 1
    if word.bit_length() > 68:
        raise ValueError(f"FADD carrier overflow: {word:#x}")
    if normalize and word.bit_length() != 67:
        raise ValueError(f"bad normalized FADD carrier: {word:#x}")
    return AddBus(sign, exponent, word)


def _like_sign(
    left: AddBus, right: AddBus, policy: BusPolicy
) -> tuple[AddBus, AddBusTrace]:
    exponent = max(left.exponent, right.exponent)
    aligned: list[int] = []
    discarded: list[bool] = []
    for operand in (left, right):
        word, tail = shift_right(
            operand.word << 1, exponent - operand.exponent
        )
        aligned.append(word)
        discarded.append(tail)
    if policy.sticky_mode == "jam-sub":
        aligned = [
            word | int(tail) for word, tail in zip(aligned, discarded)
        ]
        outgoing = False
    else:
        outgoing = any(discarded)
    result = finish_raw(
        left.sign,
        exponent,
        aligned[0] + aligned[1],
        outgoing,
        policy.normalize,
    )
    return result, AddBusTrace(
        "add", abs(left.exponent - right.exponent), any(discarded), policy.normalize
    )


def _subtract(
    left: AddBus, right: AddBus, policy: BusPolicy
) -> tuple[AddBus, AddBusTrace]:
    comparison = compare_magnitude(left, right)
    difference = abs(left.exponent - right.exponent)
    operation = "near-sub" if difference <= 1 else "far-sub"
    if not comparison:
        return AddBus(0, 0, 0), AddBusTrace(
            operation, difference, False, policy.normalize
        )
    big, small = (left, right) if comparison > 0 else (right, left)
    exponent = big.exponent
    shifted, discarded = shift_right(
        small.word << 1, exponent - small.exponent
    )
    if policy.sticky_mode == "jam-sub":
        shifted |= int(discarded)
        raw = (big.word << 1) - shifted
        outgoing = False
    elif policy.sticky_mode == "mark-after":
        raw = (big.word << 1) - shifted
        outgoing = discarded
    elif policy.sticky_mode == "borrow-sticky":
        raw = (big.word << 1) - shifted - int(discarded)
        outgoing = discarded
    elif policy.sticky_mode == "borrow-clear":
        raw = (big.word << 1) - shifted - int(discarded)
        outgoing = False
    else:
        raise ValueError(policy.sticky_mode)
    return (
        finish_raw(
            big.sign, exponent, raw, outgoing, policy.normalize
        ),
        AddBusTrace(operation, difference, discarded, policy.normalize),
    )


def add_bus(
    left: P6Value, right: P6Value, policy: BusPolicy
) -> tuple[ArithmeticResult, AddBusTrace]:
    left_bus = AddBus.from_value(left)
    right_bus = AddBus.from_value(right)
    if not left_bus.word:
        bus = right_bus
        trace = AddBusTrace("pass", 0, False, policy.normalize)
    elif not right_bus.word:
        bus = left_bus
        trace = AddBusTrace("pass", 0, False, policy.normalize)
    elif left_bus.sign == right_bus.sign:
        bus, trace = _like_sign(left_bus, right_bus, policy)
    else:
        bus, trace = _subtract(left_bus, right_bus, policy)

    retained = bus.to_value(PRECISION_FLAG if trace.discarded else 0)
    if policy.materialize is None:
        return ArithmeticResult(retained, trace.discarded, False), trace
    rounded, rounded_inexact, increment = quantize_exact(
        exact_from_p6(retained), policy.materialize
    )
    inexact = trace.discarded or rounded_inexact
    result = p6_from_exact(rounded, PRECISION_FLAG if inexact else 0)
    return ArithmeticResult(result, inexact, increment), trace


def subtract_bus(
    left: P6Value, right: P6Value, policy: BusPolicy
) -> tuple[ArithmeticResult, AddBusTrace]:
    negated = P6Value.from_fields(
        right.sign ^ 1, right.exponent, right.mantissa, right.flags
    )
    return add_bus(left, negated, policy)


def selftest() -> None:
    one = P6Value.from_fields(0, INTERNAL_EXPONENT_BIAS, 1 << 66)
    half = P6Value.from_fields(0, INTERNAL_EXPONENT_BIAS - 1, 1 << 66)
    policy = BusPolicy("mark-after", True, None)
    result, trace = add_bus(one, half, policy)
    assert trace.operation == "add"
    assert result.value.mantissa == 3 << 65
    zero, trace = subtract_bus(one, one, policy)
    assert trace.operation == "near-sub" and zero.value.mantissa == 0


if __name__ == "__main__":
    selftest()
    print("p6_fadd selftest: OK")
