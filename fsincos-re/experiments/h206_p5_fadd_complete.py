#!/usr/bin/env python3
"""Complete the exercised P5 FADD/FIRC bus model.

h200 models only unlike-sign far subtraction.  The final Tang reconstruction
also contains like-sign addition and can create close subtraction after an
intermediate topology change.  This module adds those paths while retaining
the patent's explicit representation:

* FAMUBUS bit 67 is overflow, bit 66 is J, and bits 2/1/0 are G/R/S;
* the aligned operand occupies X2 bits 68:1 with discarded-tail sticky;
* the X2 result is kept as an integer bit vector before FAMUBUS compression;
* FRND normalization and rounding remain independent controls;
* a J=0 retained carrier can be routed directly to FMUL's X67 input.

The four h200/h204 sticky interpretations remain bounded alternatives.  They
differ only where the separately drawn sticky signal can affect subtraction;
like-sign addition retains a positive discarded tail in all four cases.
"""

from __future__ import annotations

import dataclasses

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h200_p5_fadd_bitvector as h200
import h204_fadd_borrow_sticky as h204


Bus = h200.Bus
MODES = (*h200.FADD_MODES, *h204.MODES)
RN64 = h110.Quant(64, "rn")
CHOP64 = h110.Quant(64, "chop")
AWAY64 = h110.Quant(64, "away")
ODD64 = h110.Quant(64, "odd")
ODD67 = h110.Quant(67, "odd")


@dataclasses.dataclass(frozen=True)
class AddTrace:
    operation: str
    exponent_difference: int
    normalized: bool


def compare_magnitude(left: Bus, right: Bus) -> int:
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
) -> Bus:
    """Map an X2 integer at exponent-67 onto FAMUBUS."""
    if not raw:
        return Bus(0, 0, 0)
    if raw < 0:
        raise ValueError("finish_raw requires a magnitude")
    if normalize:
        top = raw.bit_length() - 1
        if top > 67:
            raw, discarded = h200.shift_right(raw, top - 67)
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
        raise ValueError(f"FAMUBUS overflow: {word:#x}")
    if normalize and word.bit_length() != 67:
        raise ValueError(f"normalized FAMUBUS has bad width: {word:#x}")
    return Bus(sign, exponent, word)


def like_sign_add(
    left: Bus,
    right: Bus,
    mode: str,
    normalize: bool,
) -> tuple[Bus, AddTrace]:
    exponent = max(left.exponent, right.exponent)
    aligned = []
    discarded = []
    for operand in (left, right):
        word, tail = h200.shift_right(
            operand.word << 1, exponent - operand.exponent
        )
        aligned.append(word)
        discarded.append(tail)
    if mode == "jam-sub":
        aligned = [
            word | int(tail) for word, tail in zip(aligned, discarded)
        ]
        outgoing = False
    elif mode in ("mark-after", "borrow-sticky", "borrow-clear"):
        outgoing = any(discarded)
    else:
        raise ValueError(mode)
    result = finish_raw(
        left.sign,
        exponent,
        aligned[0] + aligned[1],
        outgoing,
        normalize,
    )
    return result, AddTrace(
        "add",
        abs(left.exponent - right.exponent),
        normalize,
    )


def near_subtract(
    left: Bus,
    right: Bus,
    mode: str,
    normalize: bool,
) -> tuple[Bus, AddTrace]:
    """Replay the X1/left-shifter subtraction for exponent distance <= 1."""
    exponent = max(left.exponent, right.exponent)
    signed = []
    tails = []
    for operand in (left, right):
        word, tail = h200.shift_right(
            operand.word << 1, exponent - operand.exponent
        )
        if mode == "jam-sub" and tail:
            word |= 1
        signed.append(-word if operand.sign else word)
        tails.append(tail)
    raw = signed[0] + signed[1]
    if not raw:
        return Bus(0, 0, 0), AddTrace(
            "near-sub", abs(left.exponent - right.exponent), normalize
        )
    sign = int(raw < 0)
    result = finish_raw(
        sign,
        exponent,
        abs(raw),
        mode != "jam-sub" and any(tails),
        normalize,
    )
    return result, AddTrace(
        "near-sub",
        abs(left.exponent - right.exponent),
        normalize,
    )


def far_subtract(
    left: Bus,
    right: Bus,
    mode: str,
    normalize: bool,
) -> tuple[Bus, AddTrace]:
    comparison = compare_magnitude(left, right)
    if not comparison:
        return Bus(0, 0, 0), AddTrace(
            "far-sub", abs(left.exponent - right.exponent), normalize
        )
    big, small = (left, right) if comparison > 0 else (right, left)
    difference = big.exponent - small.exponent
    if difference <= 1:
        return near_subtract(left, right, mode, normalize)
    if difference < 0:
        raise ValueError("unnormalized far subtraction reversed exponents")
    shifted, discarded = h200.shift_right(small.word << 1, difference)
    if mode == "jam-sub":
        shifted |= int(discarded)
        raw = (big.word << 1) - shifted
        outgoing = False
    elif mode == "mark-after":
        raw = (big.word << 1) - shifted
        outgoing = discarded
    elif mode == "borrow-sticky":
        raw = (big.word << 1) - shifted - int(discarded)
        outgoing = discarded
    elif mode == "borrow-clear":
        raw = (big.word << 1) - shifted - int(discarded)
        outgoing = False
    else:
        raise ValueError(mode)
    result = finish_raw(big.sign, big.exponent, raw, outgoing, normalize)
    return result, AddTrace("far-sub", difference, normalize)


def fadd(
    left: Bus,
    right: Bus,
    mode: str,
    normalize: bool = True,
) -> tuple[Bus, AddTrace]:
    if not left.word:
        return right, AddTrace("pass", 0, normalize)
    if not right.word:
        return left, AddTrace("pass", 0, normalize)
    if left.sign == right.sign:
        return like_sign_add(left, right, mode, normalize)
    difference = abs(left.exponent - right.exponent)
    if difference <= 1:
        return near_subtract(left, right, mode, normalize)
    return far_subtract(left, right, mode, normalize)


def materialize(bus: Bus, action: str) -> Bus:
    if action in ("retain", "retain-raw"):
        return bus
    quant = {
        "rn64": RN64,
        "chop64": CHOP64,
        "away64": AWAY64,
        "odd64": ODD64,
        "odd67": ODD67,
    }[action]
    return h200.normalized_bus(h110.quantize(bus.value(), quant))


def fmul_x67_y64(
    x: Bus,
    y: Bus,
    y_mode: str = "rn64",
    output: str = "odd67",
) -> Bus:
    """Route a retained FADD carrier through FMUL's X67/Y64 inputs."""
    if x.word.bit_length() > 67:
        raise ValueError("X67 cannot accept FAMUBUS overflow")
    y_quant = {
        "rn64": RN64,
        "chop64": CHOP64,
        "away64": AWAY64,
        "odd64": ODD64,
    }[y_mode]
    y_value = h110.quantize(y.value(), y_quant)
    product = h58.mul_exact(x.value(), y_value)
    output_quant = {
        "odd67": ODD67,
        "rn64": RN64,
        "chop64": CHOP64,
        "away64": AWAY64,
        "odd64": ODD64,
    }[output]
    return h200.normalized_bus(h110.quantize(product, output_quant))


def assert_far_compatibility() -> None:
    samples = (
        ((0, 1 << 66, 0), (1, (1 << 66) | 17, -11)),
        ((1, (1 << 66) | 7, 4), (0, (1 << 66) | 9, -8)),
    )
    for left_fields, right_fields in samples:
        left = Bus(left_fields[0], left_fields[2], left_fields[1])
        right = Bus(right_fields[0], right_fields[2], right_fields[1])
        comparison = compare_magnitude(left, right)
        big, small = (left, right) if comparison > 0 else (right, left)
        for mode in MODES:
            for normalize in (False, True):
                expected = h200.fadd_far_sub(
                    big, small, mode, normalize
                )
                actual, trace = fadd(left, right, mode, normalize)
                if actual != expected or trace.operation != "far-sub":
                    raise SystemExit(
                        f"h206 far mismatch {mode=} {normalize=}: "
                        f"{expected=} {actual=} {trace=}"
                    )


def main() -> None:
    assert_far_compatibility()
    print("h206 complete FADD: far compatibility PASS")


if __name__ == "__main__":
    main()
