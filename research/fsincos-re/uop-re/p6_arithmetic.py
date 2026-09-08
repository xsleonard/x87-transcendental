#!/usr/bin/env python3
"""Parameterized finite-normal arithmetic in the P6 value format.

The numerical representation uses one sign bit, a 17-bit biased exponent,
and a 68-bit carrier containing overflow, J, and low carrier bits.  A normalized scalar has J at bit 66 and therefore at most 67 significant
bits.  Wider unresolved FADD carriers are intentionally a later, separate
representation rather than being disguised as normalized scalar values here.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from p6_value import J_BIT, P6Value


INTERNAL_EXPONENT_BIAS = 0xFFFF
EXTENDED_EXPONENT_BIAS = 0x3FFF
PRECISION_FLAG = 0x10
QUANTIZATION_RE = re.compile(r"^(rn|chop|away|odd|rd|ru)([0-9]+)$")


@dataclass(frozen=True)
class ExactFP:
    sign: int
    significand: int
    scale: int

    def __post_init__(self) -> None:
        if self.sign not in (0, 1):
            raise ValueError(f"invalid sign: {self.sign}")
        if self.significand < 0:
            raise ValueError("significand must be nonnegative")

    @property
    def is_zero(self) -> bool:
        return self.significand == 0


ZERO = ExactFP(0, 0, 0)


@dataclass(frozen=True)
class Quantization:
    bits: int
    mode: str

    def __post_init__(self) -> None:
        if not 1 <= self.bits <= 67:
            raise ValueError(f"normalized scalar width must be 1..67: {self.bits}")
        if self.mode not in ("rn", "chop", "away", "odd", "rd", "ru"):
            raise ValueError(f"unsupported rounding mode: {self.mode}")

    def short(self) -> str:
        return f"{self.mode}{self.bits}"


def parse_quantization(text: str) -> Quantization:
    match = QUANTIZATION_RE.match(text.lower())
    if match is None:
        raise ValueError(f"bad quantization: {text}")
    return Quantization(int(match.group(2)), match.group(1))


@dataclass(frozen=True)
class BusPolicy:
    """Literal 68-bit FADD carrier controls and optional post-rounding."""

    sticky_mode: str
    normalize: bool = True
    materialize: Quantization | None = None

    def __post_init__(self) -> None:
        if self.sticky_mode not in (
            "jam-sub",
            "mark-after",
            "borrow-sticky",
            "borrow-clear",
        ):
            raise ValueError(f"unsupported FADD sticky mode: {self.sticky_mode}")

    def short(self) -> str:
        output = "retain" if self.materialize is None else self.materialize.short()
        return (
            f"{self.sticky_mode}/"
            f"{'norm' if self.normalize else 'raw'}/{output}"
        )


@dataclass(frozen=True)
class ArithmeticPolicy:
    ordinary_add: Quantization = Quantization(64, "rn")
    ordinary_sub: Quantization = Quantization(67, "chop")
    ordinary_mul: Quantization = Quantization(67, "chop")
    multiply_class: Quantization = Quantization(64, "rn")
    divide_class: Quantization = Quantization(67, "chop")
    add_bus: BusPolicy | None = None
    sub_bus: BusPolicy | None = None

    def short(self) -> str:
        result = (
            f"add={self.ordinary_add.short()} "
            f"sub={self.ordinary_sub.short()} "
            f"mul={self.ordinary_mul.short()} "
            f"mulclass={self.multiply_class.short()} "
            f"div={self.divide_class.short()}"
        )
        if self.add_bus is not None:
            result += f" addbus={self.add_bus.short()}"
        if self.sub_bus is not None:
            result += f" subbus={self.sub_bus.short()}"
        return result


@dataclass(frozen=True)
class ArithmeticResult:
    value: P6Value
    inexact: bool
    incremented: bool


@dataclass(frozen=True)
class RangeReductionResult:
    """Exact positive remainder plus the divider's six quotient bits.

    The trigonometric entry consumes the floating result as a remainder and
    the attached flags as a modulo-64 quotient code.  The raw, pre-F_FRACT
    carrier layout is a numerical hypothesis, so ``value`` is
    the normalized value-equivalent form used by the finite-normal executor.
    """

    value: P6Value
    floor_quotient: int
    quotient_code: int


def negate(value: ExactFP) -> ExactFP:
    if value.is_zero:
        return ExactFP(value.sign ^ 1, 0, value.scale)
    return ExactFP(value.sign ^ 1, value.significand, value.scale)


def add_exact(left: ExactFP, right: ExactFP) -> ExactFP:
    if left.is_zero:
        return right
    if right.is_zero:
        return left
    scale = min(left.scale, right.scale)
    left_integer = left.significand << (left.scale - scale)
    right_integer = right.significand << (right.scale - scale)
    if left.sign:
        left_integer = -left_integer
    if right.sign:
        right_integer = -right_integer
    total = left_integer + right_integer
    if not total:
        return ZERO
    return ExactFP(int(total < 0), abs(total), scale)


def multiply_exact(left: ExactFP, right: ExactFP) -> ExactFP:
    if left.is_zero or right.is_zero:
        return ExactFP(left.sign ^ right.sign, 0, 0)
    return ExactFP(
        left.sign ^ right.sign,
        left.significand * right.significand,
        left.scale + right.scale,
    )


def compare_exact(left: ExactFP, right: ExactFP) -> int:
    difference = add_exact(left, negate(right))
    if difference.is_zero:
        return 0
    return -1 if difference.sign else 1


def _round_increment(
    sign: int,
    retained: int,
    remainder: int,
    denominator: int,
    mode: str,
) -> bool:
    if not remainder:
        return False
    if mode == "rn":
        doubled = remainder << 1
        return doubled > denominator or (
            doubled == denominator and bool(retained & 1)
        )
    if mode == "chop":
        return False
    if mode == "away":
        return True
    if mode == "odd":
        return not bool(retained & 1)
    if mode == "rd":
        return bool(sign)
    if mode == "ru":
        return not bool(sign)
    raise ValueError(mode)


def quantize_exact(
    value: ExactFP, quantization: Quantization
) -> tuple[ExactFP, bool, bool]:
    if value.is_zero:
        return value, False, False
    shift = value.significand.bit_length() - quantization.bits
    if shift <= 0:
        return value, False, False
    retained = value.significand >> shift
    remainder = value.significand & ((1 << shift) - 1)
    increment = _round_increment(
        value.sign, retained, remainder, 1 << shift, quantization.mode
    )
    if quantization.mode == "odd" and remainder:
        retained |= 1
    elif increment:
        retained += 1
    output_scale = value.scale + shift
    if retained.bit_length() > quantization.bits:
        retained >>= 1
        output_scale += 1
    return (
        ExactFP(value.sign, retained, output_scale),
        bool(remainder),
        increment,
    )


def exact_from_p6(value: P6Value) -> ExactFP:
    if value.mantissa == 0:
        return ExactFP(value.sign, 0, 0)
    unbiased_exponent = value.exponent - INTERNAL_EXPONENT_BIAS
    return ExactFP(value.sign, value.mantissa, unbiased_exponent - J_BIT)


def p6_from_exact(value: ExactFP, flags: int = 0) -> P6Value:
    if value.is_zero:
        return P6Value.from_fields(value.sign, 0, 0, flags)
    width = value.significand.bit_length()
    if width > 67:
        raise ValueError(f"normalized scalar has {width} significant bits")
    unbiased_exponent = value.scale + width - 1
    exponent = unbiased_exponent + INTERNAL_EXPONENT_BIAS
    if not 0 < exponent < 0x1FFFF:
        raise OverflowError(f"internal finite-normal exponent out of range: {exponent:#x}")
    mantissa = value.significand << (67 - width)
    return P6Value.from_fields(value.sign, exponent, mantissa, flags)


def p6_from_extended(sign_exponent: int, significand: int) -> P6Value:
    sign = (sign_exponent >> 15) & 1
    exponent = sign_exponent & 0x7FFF
    if not significand:
        return P6Value.from_fields(sign, 0, 0)
    if exponent in (0, 0x7FFF):
        raise ValueError("finite-normal interpreter does not accept denormal/special input")
    return P6Value.from_fields(sign, exponent + 0xC000, significand << 3)


def extended_from_p6(
    value: P6Value, rounding_mode: str
) -> tuple[tuple[int, int], bool, bool]:
    exact = exact_from_p6(value)
    if exact.is_zero:
        return ((exact.sign << 15, 0), False, False)
    rounded, inexact, increment = quantize_exact(
        exact, Quantization(64, rounding_mode)
    )
    width = rounded.significand.bit_length()
    exponent = rounded.scale + width - 1
    significand = rounded.significand << (64 - width)
    sign_exponent = (
        (rounded.sign << 15) | (exponent + EXTENDED_EXPONENT_BIAS)
    )
    return (sign_exponent, significand), inexact, increment


def _materialize(exact: ExactFP, quantization: Quantization) -> ArithmeticResult:
    rounded, inexact, increment = quantize_exact(exact, quantization)
    flags = PRECISION_FLAG if inexact else 0
    return ArithmeticResult(p6_from_exact(rounded, flags), inexact, increment)


def materialize_exact(
    exact: ExactFP, quantization: Quantization
) -> ArithmeticResult:
    """Materialize an already computed exact value under one unit policy."""

    return _materialize(exact, quantization)


def add(left: P6Value, right: P6Value, quantization: Quantization) -> ArithmeticResult:
    return _materialize(
        add_exact(exact_from_p6(left), exact_from_p6(right)), quantization
    )


def subtract(
    left: P6Value, right: P6Value, quantization: Quantization
) -> ArithmeticResult:
    return _materialize(
        add_exact(exact_from_p6(left), negate(exact_from_p6(right))),
        quantization,
    )


def multiply(
    left: P6Value, right: P6Value, quantization: Quantization
) -> ArithmeticResult:
    return _materialize(
        multiply_exact(exact_from_p6(left), exact_from_p6(right)),
        quantization,
    )


def divide(
    numerator: P6Value,
    denominator: P6Value,
    quantization: Quantization,
) -> ArithmeticResult:
    left = exact_from_p6(numerator)
    right = exact_from_p6(denominator)
    if right.is_zero:
        raise ZeroDivisionError("finite-normal divide by zero")
    if left.is_zero:
        return ArithmeticResult(
            P6Value.from_fields(left.sign ^ right.sign, 0, 0), False, False
        )

    sign = left.sign ^ right.sign
    ratio_exponent = (
        left.significand.bit_length() - right.significand.bit_length()
    )
    if ratio_exponent >= 0:
        if left.significand < right.significand << ratio_exponent:
            ratio_exponent -= 1
    elif left.significand << -ratio_exponent < right.significand:
        ratio_exponent -= 1
    exponent = ratio_exponent + left.scale - right.scale
    shift = quantization.bits - 1 - ratio_exponent
    if shift >= 0:
        dividend = left.significand << shift
        divisor = right.significand
    else:
        dividend = left.significand
        divisor = right.significand << -shift
    retained, remainder = divmod(dividend, divisor)
    if not (1 << (quantization.bits - 1) <= retained < 1 << quantization.bits):
        raise AssertionError("bad normalized division quotient")
    increment = _round_increment(
        sign, retained, remainder, divisor, quantization.mode
    )
    if quantization.mode == "odd" and remainder:
        retained |= 1
    elif increment:
        retained += 1
    if retained == 1 << quantization.bits:
        retained >>= 1
        exponent += 1
    rounded = ExactFP(sign, retained, exponent - (quantization.bits - 1))
    inexact = bool(remainder)
    return ArithmeticResult(
        p6_from_exact(rounded, PRECISION_FLAG if inexact else 0),
        inexact,
        increment,
    )


def range_reduce_divide(
    numerator: P6Value,
    denominator: P6Value,
) -> RangeReductionResult:
    """Return ``numerator mod denominator`` and the P6 quotient flag code.

    This is the visible finite-positive contract of the range-reduction divide
    used by the trigonometric entries, not ordinary floating-point division.
    The exact dyadic remainder is representable because both inputs are finite
    internal values.  The quotient code is a redundant divider result.  The
    common trig reduction sequence adds one in the lower half, reconstructing
    the nearest centered quotient modulo 64; FCOS adds its phase offset
    separately.
    """

    left = exact_from_p6(numerator)
    right = exact_from_p6(denominator)
    if left.sign or right.sign:
        raise ValueError("range-reduction divide requires positive operands")
    if right.is_zero:
        raise ZeroDivisionError("range-reduction divide by zero")
    if left.is_zero:
        return RangeReductionResult(
            P6Value.from_fields(0, 0, 0, 0x3F), 0, 0x3F
        )

    common_scale = min(left.scale, right.scale)
    dividend = left.significand << (left.scale - common_scale)
    divisor = right.significand << (right.scale - common_scale)
    quotient, remainder = divmod(dividend, divisor)
    # The model encodes floor(q)-1 in the lower half of the divisor interval
    # and floor(q)+1 in the upper half.  Adding one in the lower half gives
    # the centered quotient consumed by the kernel.
    upper_half = (remainder << 1) > divisor
    quotient_code = (quotient + (1 if upper_half else -1)) & 0x3F
    remainder_value = p6_from_exact(
        ExactFP(0, remainder, common_scale), quotient_code
    )
    return RangeReductionResult(
        remainder_value, quotient, quotient_code
    )


def compare(left: P6Value, right: P6Value) -> int:
    return compare_exact(exact_from_p6(left), exact_from_p6(right))


def selftest() -> None:
    one = p6_from_extended(0x3FFF, 1 << 63)
    half = p6_from_extended(0x3FFE, 1 << 63)
    assert exact_from_p6(one) == ExactFP(0, 1 << 66, -66)
    assert extended_from_p6(one, "rn")[0] == (0x3FFF, 1 << 63)
    assert add(half, half, Quantization(64, "rn")).value == one

    third = divide(one, p6_from_exact(ExactFP(0, 3, 0)), Quantization(67, "rn"))
    assert third.inexact
    assert compare(one, half) > 0
    assert compare(half, half) == 0

    low = ExactFP(0, (1 << 70) + 3, -70)
    chopped, inexact, increment = quantize_exact(low, Quantization(67, "chop"))
    assert inexact and not increment and chopped.significand.bit_length() == 67
    odd, inexact, _ = quantize_exact(low, Quantization(67, "odd"))
    assert inexact and odd.significand & 1

    seven = p6_from_exact(ExactFP(0, 7, 0))
    two = p6_from_exact(ExactFP(0, 2, 0))
    reduced = range_reduce_divide(seven, two)
    assert reduced.floor_quotient == 3
    assert reduced.quotient_code == 2
    assert compare_exact(exact_from_p6(reduced.value), ExactFP(0, 1, 0)) == 0
    assert reduced.value.flags == reduced.quotient_code


if __name__ == "__main__":
    selftest()
    print("p6_arithmetic selftest: OK")
