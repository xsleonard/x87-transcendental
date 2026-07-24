#!/usr/bin/env python3
"""Compare the Skylake F2XM1 capture with correctly rounded 2**x - 1.

The reference is evaluated twice with independent Decimal precisions.  Only
rows whose complete RN/RD/RU encodings agree are scored.  Decimal values are
converted to exact integer ratios before the x87 rounding step, so host
binary floating point is never involved.
"""

from __future__ import annotations

import collections
import decimal
import fractions
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "capture-kit-captures" / "skylake-sibling-h245"
INPUTS = {
    "dense": ROOT / "capture-kit" / "inputs" / "dense_qn.txt",
    "sweep": ROOT / "capture-kit" / "inputs" / "sweep_inputs.txt",
    "target": (
        ROOT / "capture-kit" / "inputs" / "sibling_fptan_f2xm1_h245.txt"
    ),
}
RCS = ("rn", "rd", "ru")
MIN_NORMAL_EXP = -16382
SUBNORMAL_SCALE = -16445


def decode_input(se: int, sig: int) -> fractions.Fraction:
    if not sig:
        return fractions.Fraction(0)
    sign = -1 if se >> 15 else 1
    exponent = (se & 0x7FFF) - 16383
    if (se & 0x7FFF) == 0:
        exponent = MIN_NORMAL_EXP
    return sign * fractions.Fraction(sig) * fractions.Fraction(2) ** (
        exponent - 63
    )


def parse_output(line: str) -> tuple[tuple[int, int], int]:
    fields = line.split()
    if len(fields) != 5 or fields[0] != "OK" or fields[3] != "SW":
        raise ValueError(line)
    return (int(fields[1], 16), int(fields[2], 16)), int(fields[4], 16)


def floor_log2(value: fractions.Fraction) -> int:
    numerator = value.numerator
    denominator = value.denominator
    exponent = numerator.bit_length() - denominator.bit_length()
    if exponent >= 0:
        if numerator < denominator << exponent:
            exponent -= 1
    elif numerator << -exponent < denominator:
        exponent -= 1
    return exponent


def round_integer(
    numerator: int, denominator: int, sign: int, rc: str
) -> tuple[int, bool]:
    quotient, remainder = divmod(numerator, denominator)
    if not remainder:
        return quotient, False
    if rc == "rn":
        increment = 2 * remainder > denominator or (
            2 * remainder == denominator and bool(quotient & 1)
        )
    elif rc == "rd":
        increment = bool(sign)
    elif rc == "ru":
        increment = not sign
    else:
        raise ValueError(rc)
    return quotient + increment, increment


def round_x87(
    value: fractions.Fraction, rc: str, zero_sign: int = 0
) -> tuple[tuple[int, int], bool]:
    if not value:
        return ((zero_sign << 15), 0), False
    sign = int(value < 0)
    magnitude = abs(value)
    exponent = floor_log2(magnitude)

    if exponent < MIN_NORMAL_EXP:
        scaled = magnitude * fractions.Fraction(2) ** -SUBNORMAL_SCALE
        significand, increment = round_integer(
            scaled.numerator, scaled.denominator, sign, rc
        )
        if significand >= 1 << 63:
            return ((sign << 15) | 1, 1 << 63), increment
        return ((sign << 15), significand), increment

    scaled = magnitude * fractions.Fraction(2) ** (63 - exponent)
    significand, increment = round_integer(
        scaled.numerator, scaled.denominator, sign, rc
    )
    if significand == 1 << 64:
        significand >>= 1
        exponent += 1
    return ((sign << 15) | (exponent + 16383), significand), increment


def expm1_decimal(x: fractions.Fraction, precision: int) -> fractions.Fraction:
    with decimal.localcontext() as context:
        context.prec = precision
        dx = decimal.Decimal(x.numerator) / decimal.Decimal(x.denominator)
        z = dx * decimal.Decimal(2).ln()
        if abs(z) < decimal.Decimal("1e-80"):
            total = z
            term = z
            index = 2
            while True:
                term = term * z / index
                updated = total + term
                if updated == total:
                    break
                total = updated
                index += 1
            result = +total
        else:
            result = z.exp() - 1
        numerator, denominator = result.as_integer_ratio()
        return fractions.Fraction(numerator, denominator)


def reference(
    x: fractions.Fraction, zero_sign: int, precision: int
) -> tuple[tuple[tuple[int, int], bool], ...]:
    if not x:
        return tuple(round_x87(x, rc, zero_sign) for rc in RCS)
    value = expm1_decimal(x, precision)
    return tuple(round_x87(value, rc) for rc in RCS)


def magnitude_rank(value: tuple[int, int]) -> int:
    se, significand = value
    exponent_field = se & 0x7FFF
    if not exponent_field:
        return significand
    return (exponent_field - 1) * (1 << 63) + significand


def representable_distance(
    left: tuple[int, int], right: tuple[int, int]
) -> int | None:
    if (left[0] >> 15) != (right[0] >> 15):
        if not left[1] and not right[1]:
            return 0
        return None
    return abs(magnitude_rank(left) - magnitude_rank(right))


def score(name: str) -> None:
    input_rows = [
        tuple(int(field, 16) for field in line.split())
        for line in INPUTS[name].read_text().splitlines()
    ]
    captures = {
        rc: [
            parse_output(line)
            for line in (
                CAPTURE / f"{name}_f2xm1_{rc}_status.txt"
            ).read_text().splitlines()
        ]
        for rc in RCS
    }
    if any(len(rows) != len(input_rows) for rows in captures.values()):
        raise SystemExit(f"{name}: input/output row count mismatch")

    exact = collections.Counter()
    distances = {rc: collections.Counter() for rc in RCS}
    c1_good = collections.Counter()
    c1_total = collections.Counter()
    in_domain = 0
    unstable = 0
    input_misses = 0
    all_mode_exact = 0

    for index, (se, sig) in enumerate(input_rows):
        x = decode_input(se, sig)
        if abs(x) > 1:
            continue
        in_domain += 1
        zero_sign = se >> 15 if not sig else 0
        low = reference(x, zero_sign, 110)
        high = reference(x, zero_sign, 170)
        if tuple(item[0] for item in low) != tuple(item[0] for item in high):
            unstable += 1
            continue

        row_exact = True
        for rc_index, rc in enumerate(RCS):
            predicted, increment = high[rc_index]
            actual, status = captures[rc][index]
            matched = predicted == actual
            exact[rc] += matched
            row_exact &= matched
            distance = representable_distance(predicted, actual)
            distances[rc][distance if distance is not None else "sign"] += 1
            if matched:
                c1_total[rc] += 1
                c1_good[rc] += increment == bool(status & 0x0200)
        all_mode_exact += row_exact
        input_misses += not row_exact

    print(
        f"{name}: domain={in_domain}/{len(input_rows)} "
        f"stable={in_domain - unstable} unstable={unstable}"
    )
    print(
        f"  all-mode exact inputs={all_mode_exact}/{in_domain - unstable}; "
        f"input misses={input_misses}"
    )
    for rc in RCS:
        ordered = sorted(
            distances[rc].items(),
            key=lambda item: (isinstance(item[0], str), str(item[0])),
        )
        print(
            f"  {rc}: exact={exact[rc]}/{in_domain - unstable} "
            f"distance={dict(ordered)} "
            f"C1-on-exact={c1_good[rc]}/{c1_total[rc]}"
        )


def main() -> None:
    for name in ("dense", "sweep", "target"):
        score(name)


if __name__ == "__main__":
    main()
