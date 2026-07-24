#!/usr/bin/env python3
"""Test whether the reconstructed FSINCOS state predicts FPTAN.

FPTAN uses the same reduction, table kernel, and reconstruction states before
its final division.  This pass divides the reconstructed hidden sine/cosine
states exactly, rounds that quotient directly to x87 extended precision, and
compares it with the independent FPTAN capture under RN/RD/RU.
"""

from __future__ import annotations

import pathlib

import h58_constraint_search as h58
import h218_fadd_residual_programs as h218
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230


ROOT = pathlib.Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "capture-kit-captures" / "skylake-sibling-h245"


def quotient_exponent(numerator: int, denominator: int) -> int:
    exponent = numerator.bit_length() - denominator.bit_length()
    if exponent >= 0:
        if numerator < denominator << exponent:
            exponent -= 1
    elif numerator << -exponent < denominator:
        exponent -= 1
    return exponent


def round_div(
    numerator: h58.FP, denominator: h58.FP, rc: str
) -> tuple[tuple[int, int], bool]:
    if not numerator[1]:
        return (numerator[0] << 15, 0), False
    sign = numerator[0] ^ denominator[0]
    ratio_exponent = quotient_exponent(numerator[1], denominator[1])
    exponent = ratio_exponent + numerator[2] - denominator[2]
    shift = 63 - ratio_exponent
    if shift >= 0:
        dividend = numerator[1] << shift
        divisor = denominator[1]
    else:
        dividend = numerator[1]
        divisor = denominator[1] << -shift
    significand, remainder = divmod(dividend, divisor)
    assert 1 << 63 <= significand < 1 << 64

    if rc == "rn":
        doubled = remainder << 1
        increment = doubled > divisor or (
            doubled == divisor and bool(significand & 1)
        )
    elif rc == "rd":
        increment = bool(remainder) and bool(sign)
    elif rc == "ru":
        increment = bool(remainder) and not sign
    else:
        raise ValueError(rc)
    if increment:
        significand += 1
        if significand == 1 << 64:
            significand >>= 1
            exponent += 1
    return ((sign << 15) | (exponent + 16383), significand), increment


def parse(line: str) -> tuple[tuple[int, int] | None, int]:
    fields = line.split()
    if len(fields) == 3 and fields[:2] == ["C2", "SW"]:
        return None, int(fields[2], 16)
    if len(fields) != 7 or fields[0] != "OK" or fields[5] != "SW":
        raise ValueError(line)
    if (int(fields[3], 16), int(fields[4], 16)) != (
        0x3FFF,
        0x8000000000000000,
    ):
        raise ValueError(f"bad FPTAN pushed value: {line}")
    return (int(fields[1], 16), int(fields[2], 16)), int(fields[6], 16)


def captures(name: str):
    return {
        rc: [
            parse(line)
            for line in (CAPTURE / f"{name}_fptan_{rc}_status.txt")
            .read_text()
            .splitlines()
        ]
        for rc in h58.RCS
    }


def score(name: str, value_fn) -> tuple[int, int, int, int]:
    hardware = captures(name)
    mode_misses = 0
    input_misses = 0
    c1_misses = 0
    points = h228.points(name)
    for point in points:
        sine, cosine = value_fn(point)
        misses = 0
        for rc in h58.RCS:
            predicted, increment = round_div(sine, cosine, rc)
            expected, sw = hardware[rc][point.prepared.joint.observed.index]
            if expected is None:
                raise AssertionError("table-path FPTAN unexpectedly returned C2")
            misses += predicted != expected
            if predicted == expected:
                c1_misses += increment != bool(sw & 0x0200)
        mode_misses += misses
        input_misses += bool(misses)
    return mode_misses, input_misses, c1_misses, len(points)


def current(point):
    return h230.hidden_values(point, h228.CANDIDATE)


def previous(point):
    return h218.current_values(point)


def fptan_exact_graph(point):
    prepared = point.prepared.joint.observed.point
    sine_a, cosine_tail = h230.state(point, h228.CANDIDATE)
    sine = h58.add_exact(
        prepared.sin_t,
        h58.add_exact(
            h58.mul_exact(prepared.cos_t, sine_a),
            h58.mul_exact(prepared.sin_t, cosine_tail),
        ),
    )
    cosine = h58.add_exact(
        prepared.cos_t,
        h58.add_exact(
            h58.neg(h58.mul_exact(prepared.sin_t, sine_a)),
            h58.mul_exact(prepared.cos_t, cosine_tail),
        ),
    )
    if prepared.raw.sign:
        sine = h58.neg(sine)
    return h230.h60.rotate(
        (sine, cosine), point.prepared.joint.observed.signed_n
    )


def main() -> None:
    # Exact quotient-rounding sanity checks.
    one = (0, 1, 0)
    three = (0, 3, 0)
    assert round_div(one, one, "rn")[0] == (0x3FFF, 1 << 63)
    assert round_div(one, three, "rd")[0] < round_div(one, three, "ru")[0]

    for label, value_fn in (
        ("Round36", previous),
        ("Round37", current),
        ("FPTAN exact combine", fptan_exact_graph),
    ):
        print(label)
        for name in ("dense", "sweep"):
            mode, inputs, c1, total = score(name, value_fn)
            print(
                f"  {name}: mode={mode}/{3 * total} "
                f"input={inputs}/{total} C1={c1}/{3 * total}"
            )


if __name__ == "__main__":
    main()
