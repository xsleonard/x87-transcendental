#!/usr/bin/env python3
"""Exact bit-vector synthesis for the open R59/R1382 states.

This is a solver, not a scanner.  The symbolic forward graph is a direct
translation of ``h491_scan3.c`` for a normal positive ``3ffc`` operand:

* exact 64x64 square and 67-bit chopped materialization;
* exact square-of-square and 67-bit chopped fourth power;
* both three-coefficient Horner chains with RN64 additions;
* exact terminal products, payload alignment, and near-tie reduction; and
* the R1270/R1272 hard-3x merge and R60 tie endpoint.

Every SAT witness is independently replayed through a concrete Python copy
of the graph.  When C binaries are supplied it is also replayed through the
compact C graph and both full incumbent/candidate models.  No x87 instruction
is executed by this program.

The second query family encodes a complete finite-normal x87 input and the
M66 reduction equation.  It distinguishes a direct q=0 representative from
an exact, nonzero-quotient external preimage.  In particular, an odd reduced
integer cannot be hidden below discarded external significand bits.

Capture manifests are deliberately a separate, gated operation.  ``freeze``
requires one or more private ledger paths, checks them without reporting
their paths or contents, checks repository-visible tuples, and writes only a
software-selected ``FROZEN_UNOPENED`` manifest.  It never runs hardware.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    import z3
except ImportError as error:  # pragma: no cover - exercised by CLI setup
    raise SystemExit(
        "z3-solver is required (validated with 4.15.3.0); install it in an "
        "isolated environment and rerun"
    ) from error


M66 = (3 << 64) | 0x243F6A8885A308D3
MODES = ("rn", "rd", "ru", "rz")
# The widest exact value is a 67x67 product (134 bits); the patent tree is
# explicitly 136 bits.  M66 times a 64-bit quotient fits in 131 bits.  Using
# the proven envelope rather than a generic 192-bit carrier materially lowers
# the SAT bit-blast without discarding any reachable bit.
W = 136
MASK_W = (1 << W) - 1

C6_1 = (1, -68, (0x7 << 64) | 0xFFFFFFFFFFFFFFFE)
C6_2 = (0, -71, (0x5 << 64) | 0x5555555555554277)
C6_3 = (1, -76, (0x5 << 64) | 0xB05B05B05A18A1BA)
C6_4 = (0, -82, (0x6 << 64) | 0x80680675B559F2CF)
C6_5 = (1, -88, (0x4 << 64) | 0x9F93AF61F5349300)
C6_6 = (0, -95, (0x4 << 64) | 0x7A4F2483514C1AF8)

# This is the selector-level state exposed in DI_R59/DI_TC and used by the
# existing branch-bank searches.  Raw S/B/umag words are intentionally not
# called selector features: equality on those injective values would merely
# demand the same operand and make a collision query vacuous.
OBSERVED_SELECTOR_FEATURES = (
    "theta",
    "k",
    "ce",
    "s4",
    "side",
    "b1",
    "b2",
    "low3",
    "dist",
    "rsh",
    "payload",
    "t4hi12",
    "rdhi12",
    "branch_code",
)

UNRESOLVED_QUOTIENTS = {
    "3ffc b0000000044ca2bf": (1, 1),
    "3ffc ba100000056e0a67": (4, 1),
    "3ffc cca0000009242f0c": (5, 1),
    "3ffc d920000000749eaa": (1, 1),
    "3ffc d0d000000cc0b3f8": (4, -1),
    "3ffc f4100000059862dd": (8, 1),
    "3ffc fa50000007503a2f": (9, 1),
    "3ffc ffffc00024077827": (16, 1),
    "3ffc ffffc0006e4548d9": (17, 1),
    "3ffc fffff00047c167a3": (32, 1),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_operand(text: str) -> tuple[int, int]:
    fields = text.lower().replace(":", " ").split()
    if len(fields) != 2:
        raise ValueError(f"bad x87 operand {text!r}")
    return int(fields[0], 16), int(fields[1], 16)


def operand_text(se: int, sig: int) -> str:
    return f"{se:04x} {sig:016x}"


def bv(value: int, width: int = W) -> z3.BitVecNumRef:
    return z3.BitVecVal(value & ((1 << width) - 1), width)


def bvi(value: z3.ArithRef) -> z3.BitVecRef:
    return z3.Int2BV(value, W)


def bit(value: z3.BitVecRef, position: int) -> z3.BitVecRef:
    return z3.Extract(position, position, value)


def as_int(value: z3.ExprRef, model: z3.ModelRef) -> int:
    evaluated = model.eval(value, model_completion=True)
    if z3.is_bool(evaluated):
        return int(z3.is_true(evaluated))
    return evaluated.as_long()


def ite_min(left: z3.ArithRef, right: z3.ArithRef) -> z3.ArithRef:
    return z3.If(left <= right, left, right)


def bit_length(value: z3.BitVecRef, maximum: int) -> z3.ArithRef:
    """Bit length of a nonnegative word known to fit below ``maximum``."""

    result: z3.ArithRef = z3.IntVal(0)
    for position in range(maximum):
        result = z3.If(bit(value, position) == 1, position + 1, result)
    return result


def dynamic_bit(value: z3.BitVecRef, position: z3.ArithRef,
                choices: Iterable[int]) -> z3.BitVecRef:
    result: z3.BitVecRef = bv(0, 1)
    for candidate in choices:
        result = z3.If(position == candidate, bit(value, candidate), result)
    return result


def dynamic_low_mask(position: z3.ArithRef) -> z3.BitVecRef:
    return (bv(1) << bvi(position)) - bv(1)


@dataclass(frozen=True)
class SFP:
    sign: int
    e2: z3.ArithRef
    sig: z3.BitVecRef
    bits: int


@dataclass(frozen=True)
class Cfp:
    sign: int
    e2: int
    sig: int
    bits: int


@dataclass
class SymGraph:
    solver: z3.Solver
    se: z3.BitVecRef
    m: z3.BitVecRef
    values: dict[str, z3.ExprRef]


def sym_constant(value: tuple[int, int, int]) -> SFP:
    sign, exponent, significand = value
    return SFP(sign, z3.IntVal(exponent), bv(significand), 67)


def sym_mul_chop67(left: SFP, right: SFP,
                   values: dict[str, z3.ExprRef], name: str) -> tuple[SFP, z3.BitVecRef, z3.ArithRef]:
    product = left.sig * right.sig
    lower_length = left.bits + right.bits - 1
    lower_shift = lower_length - 67
    high = bit(product, lower_length) == 1
    shift = z3.If(high, lower_shift + 1, lower_shift)
    significand = z3.LShR(product, bvi(shift))
    exponent = left.e2 + right.e2 + shift
    values[f"{name}_product"] = product
    values[f"{name}_shift"] = shift
    values[f"{name}_sig"] = significand
    values[f"{name}_e2"] = exponent
    return SFP(left.sign ^ right.sign, exponent, significand, 67), product, shift


def sym_add_rn64(left: SFP, right: SFP,
                 values: dict[str, z3.ExprRef], name: str) -> SFP:
    if left.sign != right.sign:
        raise ValueError("h1404 compact graph expects same-sign Horner adds")
    scale = ite_min(left.e2, right.e2)
    left_shift = left.e2 - scale
    right_shift = right.e2 - scale
    magnitude = ((left.sig << bvi(left_shift))
                 + (right.sig << bvi(right_shift)))
    length = bit_length(magnitude, 128)
    shift = length - 64
    top = z3.LShR(magnitude, bvi(shift))
    guard = dynamic_bit(magnitude, shift - 1, range(1, 128))
    below_mask = dynamic_low_mask(shift - 1)
    below = magnitude & below_mask
    increment = z3.If(
        z3.And(guard == 1, z3.Or(below != 0, (top & bv(1)) != 0)),
        bv(1),
        bv(0),
    )
    rounded = top + increment
    overflow = bit(rounded, 64) == 1
    output = z3.If(overflow, z3.LShR(rounded, 1), rounded)
    output_shift = z3.If(overflow, shift + 1, shift)
    values[f"{name}_scale"] = scale
    values[f"{name}_magnitude"] = magnitude
    values[f"{name}_shift"] = shift
    values[f"{name}_round"] = increment
    values[f"{name}_sig"] = output
    values[f"{name}_e2"] = scale + output_shift
    return SFP(left.sign, scale + output_shift, output, 64)


def sym_chain(fourth: SFP, lead: tuple[int, int, int],
              middle: tuple[int, int, int], last: tuple[int, int, int],
              values: dict[str, z3.ExprRef], name: str) -> SFP:
    value = sym_constant(lead)
    product1, _, _ = sym_mul_chop67(
        fourth, value, values, f"{name}_mul1")
    value = sym_add_rn64(
        sym_constant(middle), product1, values, f"{name}_add1")
    product2, _, _ = sym_mul_chop67(
        fourth, value, values, f"{name}_mul2")
    return sym_add_rn64(
        sym_constant(last), product2, values, f"{name}_add2")


def sym_csa3(a: z3.BitVecRef, b: z3.BitVecRef,
             c: z3.BitVecRef) -> tuple[z3.BitVecRef, z3.BitVecRef]:
    return a ^ b ^ c, ((a & b) | (a & c) | (b & c)) << 1


def sym_compress4(d: z3.BitVecRef, a: z3.BitVecRef,
                  b: z3.BitVecRef, c: z3.BitVecRef) -> tuple[z3.BitVecRef, z3.BitVecRef]:
    first_sum, first_carry = sym_csa3(a, b, c)
    return sym_csa3(d, first_sum, first_carry)


BOOTH8 = (0, 1, 1, 2, 2, 3, 3, 4, -4, -3, -3, -2, -2, -1, -1, 0)


def sym_booth_abs_neg(code: z3.BitVecRef) -> tuple[z3.BitVecRef, z3.BoolRef]:
    absolute: z3.BitVecRef = z3.BitVecVal(abs(BOOTH8[0]), 3)
    negative: z3.BoolRef = z3.BoolVal(BOOTH8[0] < 0)
    for index, item in enumerate(BOOTH8[1:], 1):
        absolute = z3.If(code == index, z3.BitVecVal(abs(item), 3), absolute)
        negative = z3.If(code == index, z3.BoolVal(item < 0), negative)
    return absolute, negative


def sym_booth_code(multiplier: z3.BitVecRef, row: int) -> z3.BitVecRef:
    code: z3.BitVecRef = bv(0, 4)
    for out_bit in range(4):
        source = 3 * row - 1 + out_bit
        if 0 <= source < 64:
            code = code | (z3.ZeroExt(3, bit(multiplier, source)) << out_bit)
    return code


def sym_product_tree(multiplicand: z3.BitVecRef,
                     multiplier: z3.BitVecRef) -> dict[str, tuple[z3.BitVecRef, z3.BitVecRef]]:
    pp_mask = bv((1 << 70) - 1)
    rows: list[z3.BitVecRef] = []
    prior_negative: z3.BoolRef = z3.BoolVal(False)
    for row in range(22):
        absolute, negative = sym_booth_abs_neg(
            sym_booth_code(multiplier, row))
        magnitude = multiplicand * z3.ZeroExt(W - 3, absolute)
        encoded = bv(1 << 69) | magnitude
        encoded = z3.If(negative, (~encoded) & pp_mask, encoded)
        physical = (encoded | bv(3 << 70)) << (3 * row)
        if row:
            physical = physical | z3.If(
                prior_negative, bv(1 << (3 * (row - 1))), bv(0))
        rows.append(physical)
        prior_negative = negative
    rows.extend((bv(1 << 69), bv(0)))

    level1 = [sym_compress4(*rows[4 * index:4 * index + 4])
              for index in range(6)]
    level2 = [sym_compress4(*(level1[2 * index] + level1[2 * index + 1]))
              for index in range(3)]
    level3 = sym_compress4(*(level2[0] + level2[1]))
    final = sym_compress4(*(level3 + level2[2]))
    return {"final": final, "level2_high": level2[2]}


def sym_carry_into(sum_word: z3.BitVecRef, carry_word: z3.BitVecRef,
                   maximum: int) -> list[z3.BoolRef]:
    carries: list[z3.BoolRef] = [z3.BoolVal(False)]
    for position in range(maximum):
        abit = bit(sum_word, position) == 1
        bbit = bit(carry_word, position) == 1
        carries.append(z3.Or(z3.And(abit, bbit),
                             z3.And(z3.Xor(abit, bbit), carries[-1])))
    return carries


def final_result_sym(retained: z3.BitVecRef, correction_exponent: z3.ArithRef,
                     mode: str) -> z3.BitVecRef:
    one = bv(1) << bvi(-correction_exponent)
    numerator = one - retained
    length = bit_length(numerator, 128)
    shift = length - 64
    kept = z3.LShR(numerator, bvi(shift))
    remainder = numerator & dynamic_low_mask(shift)
    half = bv(1) << bvi(shift - 1)
    if mode == "rn":
        upward = z3.Or(z3.UGT(remainder, half),
                       z3.And(remainder == half, (kept & bv(1)) != 0))
    elif mode == "ru":
        upward = remainder != 0
    elif mode in ("rd", "rz"):
        upward = z3.BoolVal(False)
    else:
        raise ValueError(mode)
    rounded = kept + z3.If(upward, bv(1), bv(0))
    return z3.Extract(63, 0, z3.If(bit(rounded, 64) == 1,
                                      z3.LShR(rounded, 1), rounded))


def build_symbolic_graph(prefix: str = "x") -> SymGraph:
    solver = z3.Solver()
    solver.set(unsat_core=True)
    se = z3.BitVec(f"{prefix}_se", 16)
    m64 = z3.BitVec(f"{prefix}_sig", 64)
    m = z3.ZeroExt(W - 64, m64)
    values: dict[str, z3.ExprRef] = {"se": se, "m": m64}

    external = z3.And(
        se == bv(0x3FFC, 16),
        bit(m64, 63) == 1,
    )
    solver.assert_and_track(external, f"{prefix}.external_normal_3ffc")
    magnitude = SFP(0, z3.IntVal(-66), m, 64)

    square, square_product, square_shift = sym_mul_chop67(
        magnitude, magnitude, values, "square")
    fourth, fourth_product, fourth_shift = sym_mul_chop67(
        square, square, values, "fourth")
    negative = sym_chain(
        fourth, C6_5, C6_3, C6_1, values, "negative")
    positive = sym_chain(
        fourth, C6_6, C6_4, C6_2, values, "positive")
    left, left_product, left_shift = sym_mul_chop67(
        square, negative, values, "left")
    right, right_product, right_shift = sym_mul_chop67(
        fourth, positive, values, "right")

    left_discard = left_product & dynamic_low_mask(left_shift)
    left_top5 = z3.LShR(left_discard, bvi(left_shift - 5)) & bv(31)
    upper5 = left_top5
    upper3 = z3.LShR(left_top5, 2)
    low3 = square.sig & bv(7)
    distance_signed = left.e2 - right.e2
    distance = z3.If(distance_signed < 0, -distance_signed, distance_signed)
    active = z3.And(low3 != 0,
                    z3.Or(upper3 != 0, z3.And(distance == 7, upper5 != 0)))
    payload = z3.BV2Int(z3.Extract(3, 0, low3), is_signed=False) + 8 - distance

    right_discard = right_product & dynamic_low_mask(right_shift)
    right_top12 = z3.LShR(right_discard, bvi(right_shift - 12)) & bv(0xFFF)
    right_upper = z3.LShR(right_top12, 11) & bv(1)

    scale = ite_min(left.e2, right.e2)
    scale = z3.If(z3.And(payload != 0, left.e2 - 8 < scale),
                  left.e2 - 8, scale)
    dl = left.e2 - scale
    dr = right.e2 - scale
    dp = left.e2 - 8 - scale
    source = left.sig << bvi(dl)
    source = source + z3.If(
        payload != 0, bvi(payload) << bvi(dp), bv(0))
    subtrahend = right.sig << bvi(dr)
    umag = source - subtrahend
    magnitude_length = bit_length(umag, 128)
    k = magnitude_length - 67
    discard_mask = dynamic_low_mask(k)
    discard = umag & discard_mask
    theta = z3.If(
        discard == 0,
        0,
        z3.If(
            z3.ULE(discard, bv(2)),
            z3.BV2Int(discard),
            z3.If(
                z3.UGE(discard, discard_mask - bv(1)),
                z3.BV2Int(discard - discard_mask) - 1,
                99,
            ),
        ),
    )
    ce = scale + k

    s4 = fourth_shift
    t4 = fourth_product & dynamic_low_mask(s4)
    side = z3.If(z3.UGE(z3.Extract(63, 0, m64),
                        z3.BitVecVal(0xB504F333F9DE6800, 64)), 1, 0)
    sqlow = square.sig - bv(1 << 66)
    mreg = bvi(z3.BV2Int(z3.Extract(2, 0, low3))) * sqlow - t4

    tree = sym_product_tree(fourth.sig, positive.sig)
    level2_carry = tree["level2_high"][1]
    merge_gate = dynamic_bit(level2_carry, right_shift + 4, (67, 68)) == 0
    final_sum, final_carry = tree["final"]
    tree_carries = sym_carry_into(final_sum, final_carry, 80)
    cpa_cut_carry = z3.If(right_shift == 63, tree_carries[63],
                          tree_carries[64])

    mexp = right_shift - 16 - z3.If(side == 0, 1, 0)
    merge_mask = dynamic_low_mask(mexp)
    triple = bv(3) * right_discard
    rd3_merge = triple - (triple & merge_mask)
    rd3_plain = triple - ((bv(2) * right_discard) & merge_mask) \
        - (right_discard & merge_mask)

    def comparator_bits(rd3: z3.BitVecRef) -> tuple[z3.ArithRef, z3.ArithRef]:
        threshold1 = bv(1) << bvi(right_shift)
        threshold2 = bv(1) << bvi(right_shift + 1)
        first = z3.If(z3.UGE(rd3, threshold1), 1, 0)
        second = z3.If(z3.UGE(rd3, threshold2), 1, 0)
        equality_carry = dynamic_bit(level2_carry, right_shift + 4,
                                     (67, 68)) == 1
        kill_bit = dynamic_bit(final_sum | final_carry, right_shift + 15,
                               (78, 79)) == 0
        strict = z3.And(equality_carry, kill_bit)
        first = z3.If(z3.And(strict, rd3 == threshold1), 0, first)
        second = z3.If(z3.And(strict, rd3 == threshold2), 0, second)
        return first, second

    incumbent_merge = z3.And(
        discard == 0,
        z3.Or(low3 == 1, z3.And(low3 == 3, merge_gate)),
    )
    candidate_merge = z3.And(
        discard == 0,
        z3.Or(low3 == 1,
              z3.And(low3 == 3, s4 == 67, merge_gate)),
    )
    current_rd3 = z3.If(incumbent_merge, rd3_merge, rd3_plain)
    candidate_rd3 = z3.If(candidate_merge, rd3_merge, rd3_plain)
    current_b1, current_b2 = comparator_bits(current_rd3)
    candidate_b1, candidate_b2 = comparator_bits(candidate_rd3)

    # The s4=66/side=1 R60 tie quadrant.  The general quadrant expressions
    # are retained so collision queries can use all ordinary tie quadrants.
    lp = z3.BV2Int(z3.Extract(0, 0, low3))
    low3_int = z3.BV2Int(z3.Extract(2, 0, low3))

    def tie_endpoint(b1: z3.ArithRef, b2: z3.ArithRef) -> tuple[z3.ArithRef, z3.BoolRef, z3.BitVecRef]:
        qa = z3.If(s4 == 66, z3.If(side == 1, 2, 4),
                   z3.If(side == 0, 4, 2))
        qg1 = z3.If(s4 == 66, z3.If(side == 1, 2, 1), 2)
        qg2 = z3.If(s4 == 66, z3.If(side == 1, 1, 0),
                    z3.If(side == 0, 1, 3))
        qp = z3.If(s4 == 66, 0, z3.If(side == 0, -2, -3))
        qq = z3.If(s4 == 66, z3.If(side == 1, 4, 2),
                   z3.If(side == 0, 4, 8))
        qk = z3.If(s4 == 66, 1, 2)
        qpar = z3.If(s4 == 66, 0, 1)
        wd = z3.If(
            z3.And(s4 == 66, side == 0),
            -9 - 5 * (distance - 9),
            z3.If(z3.And(s4 == 67, side == 1),
                  -4 - 2 * (distance - 7),
                  -5 * (distance - 7)),
        )
        base = qa * low3_int + qg1 * b1 + qg2 * b2 + qp * lp + wd
        # All divisors are positive.  Z3 integer division is floor division,
        # matching r59_floordiv for negative and positive numerators.
        u0 = qk * (base / qq) + qpar * lp
        boundary = bvi(u0) << 66
        fire = z3.BV2Int(mreg, is_signed=True) < z3.BV2Int(boundary, is_signed=True)
        retained = z3.LShR(umag, bvi(k)) - z3.If(fire, bv(1), bv(0))
        return u0, fire, retained

    current_u0, current_fire, current_retained = tie_endpoint(
        current_b1, current_b2)
    candidate_u0, candidate_fire, candidate_retained = tie_endpoint(
        candidate_b1, candidate_b2)

    t4hi12 = z3.LShR(t4, bvi(s4 - 12)) & bv(0xFFF)
    branch_code = z3.If(
        z3.And(s4 == 67, side == 1, distance == 8, right_shift == 64),
        1,  # corner
        z3.If(discard == 0, 2, 3),  # tie / band
    )

    values.update({
        "square_sig": square.sig,
        "square_e2": square.e2,
        "fourth_sig": fourth.sig,
        "fourth_e2": fourth.e2,
        "negative_sig": negative.sig,
        "negative_e2": negative.e2,
        "positive_sig": positive.sig,
        "positive_e2": positive.e2,
        "left_sig": left.sig,
        "left_e2": left.e2,
        "right_sig": right.sig,
        "right_e2": right.e2,
        "active": active,
        "low3": z3.BV2Int(z3.Extract(2, 0, low3)),
        "dist": distance,
        "payload": payload,
        "rsh": right_shift,
        "rud": z3.BV2Int(z3.Extract(0, 0, right_upper)),
        "rdhi12": z3.BV2Int(z3.Extract(11, 0, right_top12)),
        "scale": scale,
        "S": source,
        "B": subtrahend,
        "umag": umag,
        "k": k,
        "disc": discard,
        "theta": theta,
        "ce": ce,
        "s4": s4,
        "t4": t4,
        "t4hi12": z3.BV2Int(z3.Extract(11, 0, t4hi12)),
        "side": side,
        "sqlow": sqlow,
        "Mreg": mreg,
        "merge_gate": merge_gate,
        "right_l2_high_carry": z3.Not(merge_gate),
        "right_cpa_carry_into_cut": cpa_cut_carry,
        "rd3_kill_carry": rd3_merge != rd3_plain,
        "current_rd3": current_rd3,
        "candidate_rd3": candidate_rd3,
        "b1": current_b1,
        "b2": current_b2,
        "candidate_b1": candidate_b1,
        "candidate_b2": candidate_b2,
        "current_u0": current_u0,
        "candidate_u0": candidate_u0,
        "current_fire": current_fire,
        "candidate_fire": candidate_fire,
        "current_retained": current_retained,
        "candidate_retained": candidate_retained,
        "branch_code": branch_code,
    })
    for mode in MODES:
        values[f"current_{mode}"] = final_result_sym(current_retained, ce, mode)
        values[f"candidate_{mode}"] = final_result_sym(candidate_retained, ce, mode)

    # These range constraints are invariants of the compact path and prevent
    # a malformed dynamic shift from gaining modulo-bit-vector semantics.
    path_safety = z3.And(
        values["square_shift"] >= 60, values["square_shift"] <= 61,
        values["fourth_shift"] >= 66, values["fourth_shift"] <= 67,
        values["left_shift"] >= 63, values["left_shift"] <= 64,
        values["right_shift"] >= 63, values["right_shift"] <= 64,
        values["negative_add1_shift"] > 0,
        values["negative_add2_shift"] > 0,
        values["positive_add1_shift"] > 0,
        values["positive_add2_shift"] > 0,
        k >= 3, k <= 60,
        source > subtrahend,
    )
    solver.assert_and_track(path_safety, f"{prefix}.pipeline_shift_safety")
    return SymGraph(solver, se, m64, values)


def c_mul_chop67(left: Cfp, right: Cfp) -> tuple[Cfp, int, int]:
    product = left.sig * right.sig
    shift = product.bit_length() - 67
    output = product >> shift if shift > 0 else product << -shift
    return Cfp(left.sign ^ right.sign, left.e2 + right.e2 + shift,
               output, 67), product, shift


def c_add_rn64(left: Cfp, right: Cfp,
               trace: dict[str, int] | None = None,
               name: str = "add") -> Cfp:
    if left.sign != right.sign:
        raise ValueError("compact Horner chain unexpectedly changed sign")
    scale = min(left.e2, right.e2)
    magnitude = (left.sig << (left.e2 - scale)) \
        + (right.sig << (right.e2 - scale))
    shift = magnitude.bit_length() - 64
    if shift <= 0:
        if trace is not None:
            trace[f"{name}_shift"] = shift
            trace[f"{name}_round"] = 0
            trace[f"{name}_overflow"] = 0
        return Cfp(left.sign, scale + shift, magnitude << -shift, 64)
    top = magnitude >> shift
    remainder = magnitude & ((1 << shift) - 1)
    half = 1 << (shift - 1)
    increment = int(remainder > half or (remainder == half and (top & 1)))
    overflow = 0
    if increment:
        top += 1
        if top >> 64:
            top >>= 1
            shift += 1
            overflow = 1
    if trace is not None:
        trace[f"{name}_shift"] = shift - overflow
        trace[f"{name}_round"] = increment
        trace[f"{name}_overflow"] = overflow
    return Cfp(left.sign, scale + shift, top, 64)


def c_constant(value: tuple[int, int, int]) -> Cfp:
    return Cfp(value[0], value[1], value[2], 67)


def c_chain(fourth: Cfp, lead: tuple[int, int, int],
            middle: tuple[int, int, int], last: tuple[int, int, int],
            trace: dict[str, int] | None = None, name: str = "chain") -> Cfp:
    value = c_constant(lead)
    first, _, first_shift = c_mul_chop67(fourth, value)
    if trace is not None:
        trace[f"{name}_mul1_shift"] = first_shift
    value = c_add_rn64(
        c_constant(middle), first, trace, f"{name}_add1")
    second, _, second_shift = c_mul_chop67(fourth, value)
    if trace is not None:
        trace[f"{name}_mul2_shift"] = second_shift
    return c_add_rn64(
        c_constant(last), second, trace, f"{name}_add2")


def c_product_tree(multiplicand: int, multiplier: int) -> dict[str, tuple[int, int]]:
    pp_mask = (1 << 70) - 1
    rows = []
    prior_negative = False
    for row in range(22):
        code = 0
        for out_bit in range(4):
            source = 3 * row - 1 + out_bit
            if 0 <= source < 64:
                code |= ((multiplier >> source) & 1) << out_bit
        digit = BOOTH8[code]
        encoded = (1 << 69) | (multiplicand * abs(digit))
        if digit < 0:
            encoded = (~encoded) & pp_mask
        physical = (encoded | (3 << 70)) << (3 * row)
        if prior_negative:
            physical |= 1 << (3 * (row - 1))
        rows.append(physical & MASK_W)
        prior_negative = digit < 0
    rows.extend((1 << 69, 0))

    def csa3(a: int, b: int, c: int) -> tuple[int, int]:
        return (a ^ b ^ c) & MASK_W, \
            (((a & b) | (a & c) | (b & c)) << 1) & MASK_W

    def compressor(d: int, a: int, b: int, c: int) -> tuple[int, int]:
        first = csa3(a, b, c)
        return csa3(d, *first)

    level1 = [compressor(*rows[4 * index:4 * index + 4])
              for index in range(6)]
    level2 = [compressor(*(level1[2 * index] + level1[2 * index + 1]))
              for index in range(3)]
    level3 = compressor(*(level2[0] + level2[1]))
    final = compressor(*(level3 + level2[2]))
    return {"final": final, "level2_high": level2[2]}


def c_carry_into(sum_word: int, carry_word: int, position: int) -> int:
    carry = 0
    for column in range(position):
        a = (sum_word >> column) & 1
        b = (carry_word >> column) & 1
        carry = (a & b) | ((a ^ b) & carry)
    return carry


def c_final_result(retained: int, correction_exponent: int, mode: str) -> int:
    numerator = (1 << -correction_exponent) - retained
    shift = numerator.bit_length() - 64
    if shift <= 0:
        return numerator << -shift
    kept = numerator >> shift
    remainder = numerator & ((1 << shift) - 1)
    half = 1 << (shift - 1)
    upward = False
    if mode == "rn":
        upward = remainder > half or (remainder == half and (kept & 1))
    elif mode == "ru":
        upward = remainder != 0
    kept += int(upward)
    if kept >> 64:
        kept >>= 1
    return kept


def concrete_forward(m: int) -> dict[str, int]:
    if not (1 << 63) <= m < (1 << 64):
        raise ValueError("3ffc input significand is not normal")
    magnitude = Cfp(0, -66, m, 64)
    square, square_product, square_shift = c_mul_chop67(magnitude, magnitude)
    fourth, fourth_product, fourth_shift = c_mul_chop67(square, square)
    path_trace: dict[str, int] = {}
    negative = c_chain(
        fourth, C6_5, C6_3, C6_1, path_trace, "negative")
    positive = c_chain(
        fourth, C6_6, C6_4, C6_2, path_trace, "positive")
    left, left_product, left_shift = c_mul_chop67(square, negative)
    right, right_product, right_shift = c_mul_chop67(fourth, positive)

    left_discard = left_product & ((1 << left_shift) - 1)
    upper5 = left_discard >> (left_shift - 5)
    upper3 = upper5 >> 2
    low3 = square.sig & 7
    distance = abs(left.e2 - right.e2)
    active = bool(low3 and (upper3 or (distance == 7 and upper5)))
    payload = low3 + 8 - distance
    right_discard = right_product & ((1 << right_shift) - 1)
    right_top12 = right_discard >> (right_shift - 12)

    scale = min(left.e2, right.e2)
    if payload and left.e2 - 8 < scale:
        scale = left.e2 - 8
    dl, dr, dp = left.e2 - scale, right.e2 - scale, left.e2 - 8 - scale
    source = left.sig << dl
    if payload:
        source += payload << dp
    subtrahend = right.sig << dr
    umag = source - subtrahend
    k = umag.bit_length() - 67
    discard_mask = (1 << k) - 1
    discard = umag & discard_mask
    if discard == 0:
        theta = 0
    elif discard <= 2:
        theta = discard
    elif discard >= discard_mask - 1:
        theta = discard - discard_mask - 1
    else:
        theta = 99
    ce = scale + k
    s4 = fourth_shift
    t4 = fourth_product & ((1 << s4) - 1)
    side = int(m >= 0xB504F333F9DE6800)
    sqlow = square.sig - (1 << 66)
    mreg = low3 * sqlow - t4

    tree = c_product_tree(fourth.sig, positive.sig)
    level2_carry = tree["level2_high"][1]
    merge_gate = not bool((level2_carry >> (right_shift + 4)) & 1)
    final_sum, final_carry = tree["final"]
    cpa_cut_carry = c_carry_into(final_sum, final_carry, right_shift)
    mexp = right_shift - 16 - int(side == 0)
    mask = (1 << mexp) - 1
    triple = 3 * right_discard
    merged = triple - (triple & mask)
    plain = triple - ((2 * right_discard) & mask) - (right_discard & mask)

    def comparator(rd3: int) -> tuple[int, int]:
        threshold1, threshold2 = 1 << right_shift, 1 << (right_shift + 1)
        b1, b2 = int(rd3 >= threshold1), int(rd3 >= threshold2)
        equality_carry = (level2_carry >> (right_shift + 4)) & 1
        kill = not bool(((final_sum | final_carry) >> (right_shift + 15)) & 1)
        if equality_carry and kill and rd3 == threshold1:
            b1 = 0
        if equality_carry and kill and rd3 == threshold2:
            b2 = 0
        return b1, b2

    incumbent_merge = discard == 0 and (low3 == 1 or (low3 == 3 and merge_gate))
    candidate_merge = discard == 0 and (
        low3 == 1 or (low3 == 3 and s4 == 67 and merge_gate))
    current_rd3 = merged if incumbent_merge else plain
    candidate_rd3 = merged if candidate_merge else plain
    current_b1, current_b2 = comparator(current_rd3)
    candidate_b1, candidate_b2 = comparator(candidate_rd3)

    def floor_div(numerator: int, denominator: int) -> int:
        return numerator // denominator

    def endpoint(b1: int, b2: int) -> tuple[int, int, int]:
        if s4 == 66 and side == 1:
            qa, qg1, qg2, qp, qq, qk, qpar = 2, 2, 1, 0, 4, 1, 0
            wd = -5 * (distance - 7)
        elif s4 == 66 and side == 0:
            qa, qg1, qg2, qp, qq, qk, qpar = 4, 1, 0, 0, 2, 1, 0
            wd = -9 - 5 * (distance - 9)
        elif s4 == 67 and side == 0:
            qa, qg1, qg2, qp, qq, qk, qpar = 4, 2, 1, -2, 4, 2, 1
            wd = -5 * (distance - 7)
        else:
            qa, qg1, qg2, qp, qq, qk, qpar = 2, 2, 3, -3, 8, 2, 1
            wd = -4 - 2 * (distance - 7)
        lp = low3 & 1
        base = qa * low3 + qg1 * b1 + qg2 * b2 + qp * lp + wd
        u0 = qk * floor_div(base, qq) + qpar * lp
        fire = int(mreg < (u0 << 66))
        retained = (umag >> k) - fire
        return u0, fire, retained

    current_u0, current_fire, current_retained = endpoint(current_b1, current_b2)
    candidate_u0, candidate_fire, candidate_retained = endpoint(candidate_b1, candidate_b2)
    branch_code = 1 if (s4 == 67 and side == 1 and distance == 8
                        and right_shift == 64) else (2 if theta == 0 else 3)
    values = {
        "m": m,
        "square_sig": square.sig,
        "square_e2": square.e2,
        "square_shift": square_shift,
        "fourth_sig": fourth.sig,
        "fourth_e2": fourth.e2,
        "fourth_shift": fourth_shift,
        "negative_sig": negative.sig,
        "negative_e2": negative.e2,
        "positive_sig": positive.sig,
        "positive_e2": positive.e2,
        "left_sig": left.sig,
        "left_e2": left.e2,
        "left_shift": left_shift,
        "right_sig": right.sig,
        "right_e2": right.e2,
        "right_shift": right_shift,
        "active": int(active),
        "low3": low3,
        "dist": distance,
        "payload": payload,
        "rsh": right_shift,
        "rud": (right_top12 >> 11) & 1,
        "rdhi12": right_top12,
        "scale": scale,
        "S": source,
        "B": subtrahend,
        "umag": umag,
        "k": k,
        "disc": discard,
        "theta": theta,
        "ce": ce,
        "s4": s4,
        "t4": t4,
        "t4hi12": t4 >> (s4 - 12),
        "side": side,
        "sqlow": sqlow,
        "Mreg": mreg,
        "merge_gate": int(merge_gate),
        "right_l2_high_carry": int(not merge_gate),
        "right_cpa_carry_into_cut": cpa_cut_carry,
        "rd3_kill_carry": int(merged != plain),
        "current_rd3": current_rd3,
        "candidate_rd3": candidate_rd3,
        "b1": current_b1,
        "b2": current_b2,
        "candidate_b1": candidate_b1,
        "candidate_b2": candidate_b2,
        "current_u0": current_u0,
        "candidate_u0": candidate_u0,
        "current_fire": current_fire,
        "candidate_fire": candidate_fire,
        "current_retained": current_retained,
        "candidate_retained": candidate_retained,
        "branch_code": branch_code,
        **path_trace,
    }
    for mode in MODES:
        values[f"current_{mode}"] = c_final_result(current_retained, ce, mode)
        values[f"candidate_{mode}"] = c_final_result(candidate_retained, ce, mode)
    return values


@dataclass(frozen=True)
class BFP:
    sign: int
    e2: int
    sig: z3.BitVecRef
    bits: int


@dataclass
class FixedGraph:
    """Pure-QF_BV graph for one complete materialization path signature."""

    solver: z3.Solver
    m: z3.BitVecRef
    values: dict[str, z3.ExprRef | int]
    template: dict[str, int]
    derives_tree: bool


def fixed_constant(value: tuple[int, int, int]) -> BFP:
    return BFP(value[0], value[1], bv(value[2]), 67)


def fixed_mul_chop67(
    left: BFP,
    right: BFP,
    shift: int,
    constraints: list[z3.BoolRef],
    values: dict[str, z3.ExprRef | int],
    name: str,
) -> tuple[BFP, z3.BitVecRef]:
    product = left.sig * right.sig
    output = z3.LShR(product, shift)
    # These two facts state exactly that bit_length(product)-67 == shift.
    constraints.extend((bit(output, 66) == 1,
                        z3.LShR(output, 67) == 0))
    values[f"{name}_product"] = product
    values[f"{name}_shift"] = shift
    values[f"{name}_sig"] = output
    values[f"{name}_e2"] = left.e2 + right.e2 + shift
    return BFP(left.sign ^ right.sign, left.e2 + right.e2 + shift,
               output, 67), product


def fixed_add_rn64(
    left: BFP,
    right: BFP,
    raw_shift: int,
    expected_round: int,
    expected_overflow: int,
    constraints: list[z3.BoolRef],
    values: dict[str, z3.ExprRef | int],
    name: str,
) -> BFP:
    if left.sign != right.sign:
        raise ValueError("fixed compact graph expects same-sign Horner adds")
    scale = min(left.e2, right.e2)
    magnitude = (left.sig << (left.e2 - scale)) \
        + (right.sig << (right.e2 - scale))
    top = z3.LShR(magnitude, raw_shift)
    remainder = magnitude & bv((1 << raw_shift) - 1)
    half = bv(1 << (raw_shift - 1))
    increment = z3.Or(z3.UGT(remainder, half),
                      z3.And(remainder == half, (top & bv(1)) != 0))
    rounded = top + z3.If(increment, bv(1), bv(0))
    overflow = bit(rounded, 64) == 1
    output = z3.If(overflow, z3.LShR(rounded, 1), rounded)
    constraints.extend((
        bit(magnitude, raw_shift + 63) == 1,
        z3.LShR(magnitude, raw_shift + 64) == 0,
        increment == z3.BoolVal(bool(expected_round)),
        overflow == z3.BoolVal(bool(expected_overflow)),
        bit(output, 63) == 1,
        z3.LShR(output, 64) == 0,
    ))
    exponent = scale + raw_shift + expected_overflow
    values[f"{name}_magnitude"] = magnitude
    values[f"{name}_shift"] = raw_shift
    values[f"{name}_round"] = increment
    values[f"{name}_overflow"] = overflow
    values[f"{name}_sig"] = output
    values[f"{name}_e2"] = exponent
    return BFP(left.sign, exponent, output, 64)


def fixed_chain(
    fourth: BFP,
    lead: tuple[int, int, int],
    middle: tuple[int, int, int],
    last: tuple[int, int, int],
    template: dict[str, int],
    constraints: list[z3.BoolRef],
    values: dict[str, z3.ExprRef | int],
    name: str,
) -> BFP:
    value = fixed_constant(lead)
    first, _ = fixed_mul_chop67(
        fourth, value, template[f"{name}_mul1_shift"], constraints,
        values, f"{name}_mul1")
    value = fixed_add_rn64(
        fixed_constant(middle), first, template[f"{name}_add1_shift"],
        template[f"{name}_add1_round"], template[f"{name}_add1_overflow"],
        constraints, values, f"{name}_add1")
    second, _ = fixed_mul_chop67(
        fourth, value, template[f"{name}_mul2_shift"], constraints,
        values, f"{name}_mul2")
    return fixed_add_rn64(
        fixed_constant(last), second, template[f"{name}_add2_shift"],
        template[f"{name}_add2_round"], template[f"{name}_add2_overflow"],
        constraints, values, f"{name}_add2")


def fixed_final_result(retained: z3.BitVecRef, correction_exponent: int,
                       mode: str) -> z3.BitVecRef:
    numerator = bv(1 << -correction_exponent) - retained
    shift = -correction_exponent - 64
    kept = z3.LShR(numerator, shift)
    remainder = numerator & bv((1 << shift) - 1)
    half = bv(1 << (shift - 1))
    if mode == "rn":
        upward = z3.Or(z3.UGT(remainder, half),
                       z3.And(remainder == half, (kept & bv(1)) != 0))
    elif mode == "ru":
        upward = remainder != 0
    elif mode in ("rd", "rz"):
        upward = z3.BoolVal(False)
    else:
        raise ValueError(mode)
    rounded = kept + z3.If(upward, bv(1), bv(0))
    return z3.Extract(63, 0, z3.If(bit(rounded, 64) == 1,
                                      z3.LShR(rounded, 1), rounded))


def build_fixed_path_graph(template_sig: int, prefix: str = "fixed",
                           derive_tree: bool = True) -> FixedGraph:
    """Build a pure bit-vector graph for the template's exact path partition.

    Normalization shifts, Horner rounding directions, and RN64 overflow bits
    are fixed to the template, with their defining arithmetic predicates also
    asserted.  Thus this is an exact path partition rather than an
    approximation or a neighborhood restriction.
    """

    template = concrete_forward(template_sig)
    solver = z3.SolverFor("QF_BV")
    solver.set(unsat_core=True)
    m64 = z3.BitVec(f"{prefix}_sig", 64)
    m = z3.ZeroExt(W - 64, m64)
    values: dict[str, z3.ExprRef | int] = {"m": m64, "se": 0x3FFC}
    constraints: list[z3.BoolRef] = [bit(m64, 63) == 1]
    magnitude = BFP(0, -66, m, 64)

    square, square_product = fixed_mul_chop67(
        magnitude, magnitude, template["square_shift"], constraints,
        values, "square")
    fourth, fourth_product = fixed_mul_chop67(
        square, square, template["fourth_shift"], constraints,
        values, "fourth")
    negative = fixed_chain(
        fourth, C6_5, C6_3, C6_1, template, constraints, values, "negative")
    positive = fixed_chain(
        fourth, C6_6, C6_4, C6_2, template, constraints, values, "positive")
    left, left_product = fixed_mul_chop67(
        square, negative, template["left_shift"], constraints, values, "left")
    right, right_product = fixed_mul_chop67(
        fourth, positive, template["right_shift"], constraints, values, "right")

    left_shift = template["left_shift"]
    right_shift = template["right_shift"]
    left_discard = left_product & bv((1 << left_shift) - 1)
    upper5 = z3.LShR(left_discard, left_shift - 5) & bv(31)
    upper3 = z3.LShR(upper5, 2)
    low3 = square.sig & bv(7)
    distance = abs(left.e2 - right.e2)
    active = z3.And(low3 != 0,
                    z3.Or(upper3 != 0, z3.And(distance == 7, upper5 != 0)))
    payload = z3.ZeroExt(W - 3, z3.Extract(2, 0, low3)) \
        + bv(8 - distance)
    right_discard = right_product & bv((1 << right_shift) - 1)
    right_top12 = z3.LShR(right_discard, right_shift - 12) & bv(0xFFF)

    scale = min(left.e2, right.e2,
                left.e2 - 8 if template["payload"] else left.e2)
    dl, dr, dp = left.e2 - scale, right.e2 - scale, left.e2 - 8 - scale
    source = left.sig << dl
    source = source + z3.If(payload != 0, payload << dp, bv(0))
    subtrahend = right.sig << dr
    umag = source - subtrahend
    k = template["k"]
    discard = umag & bv((1 << k) - 1)
    ce = scale + k
    s4 = template["s4"]
    t4 = fourth_product & bv((1 << s4) - 1)
    side = z3.UGE(m64, z3.BitVecVal(0xB504F333F9DE6800, 64))
    sqlow = square.sig - bv(1 << 66)
    mreg = payload * sqlow - t4

    if derive_tree:
        tree = sym_product_tree(fourth.sig, positive.sig)
        level2_carry = tree["level2_high"][1]
        merge_gate = bit(level2_carry, right_shift + 4) == 0
        final_sum, final_carry = tree["final"]
        cpa_cut_carry = sym_carry_into(
            final_sum, final_carry, right_shift)[right_shift]
        equality_strict = z3.And(
            bit(level2_carry, right_shift + 4) == 1,
            bit(final_sum | final_carry, right_shift + 15) == 0,
        )
    else:
        # Relax the R1272 gate to its enabling value.  This removes the
        # multiplier-tree representation from preimage synthesis; every SAT
        # result is then checked against the exact concrete tree and blocked
        # if the gate is actually clear.  UNSAT remains a valid proof because
        # the relaxed solution set is a superset of physical candidates.
        merge_gate = z3.BoolVal(True)
        cpa_cut_carry = z3.BoolVal(False)
        equality_strict = z3.BoolVal(False)
    mexp = right_shift - 16 - int(not bool(template["side"]))
    merge_mask = bv((1 << mexp) - 1)
    triple = bv(3) * right_discard
    rd3_merge = triple - (triple & merge_mask)
    rd3_plain = triple - ((bv(2) * right_discard) & merge_mask) \
        - (right_discard & merge_mask)

    def comparator(rd3: z3.BitVecRef) -> tuple[z3.BitVecRef, z3.BitVecRef]:
        threshold1 = bv(1 << right_shift)
        threshold2 = bv(1 << (right_shift + 1))
        first = z3.If(z3.UGE(rd3, threshold1), bv(1, 1), bv(0, 1))
        second = z3.If(z3.UGE(rd3, threshold2), bv(1, 1), bv(0, 1))
        first = z3.If(z3.And(equality_strict, rd3 == threshold1),
                      bv(0, 1), first)
        second = z3.If(z3.And(equality_strict, rd3 == threshold2),
                       bv(0, 1), second)
        return first, second

    incumbent_merge = z3.And(
        discard == 0,
        z3.Or(low3 == 1, z3.And(low3 == 3, merge_gate)),
    )
    candidate_merge = z3.And(
        discard == 0,
        z3.Or(low3 == 1,
              z3.And(low3 == 3, z3.BoolVal(s4 == 67), merge_gate)),
    )
    current_rd3 = z3.If(incumbent_merge, rd3_merge, rd3_plain)
    candidate_rd3 = z3.If(candidate_merge, rd3_merge, rd3_plain)
    current_b1, current_b2 = comparator(current_rd3)
    candidate_b1, candidate_b2 = comparator(candidate_rd3)

    def u0_for(b1: z3.BitVecRef, b2: z3.BitVecRef) -> z3.BitVecRef:
        table = {}
        for first in (0, 1):
            for second in (0, 1):
                probe = dict(template)
                # Reuse the concrete quadrant formulas without relying on a
                # fitted table: only the four binary comparator endpoints are
                # enumerated here.
                low = template["low3"]
                if s4 == 66 and template["side"] == 1:
                    base = 2 * low + 2 * first + second \
                        - 5 * (distance - 7)
                    value = base // 4
                elif s4 == 66:
                    base = 4 * low + first - 9 - 5 * (distance - 9)
                    value = base // 2
                elif template["side"] == 0:
                    base = 4 * low + 2 * first + second \
                        - 2 * (low & 1) - 5 * (distance - 7)
                    value = 2 * (base // 4) + (low & 1)
                else:
                    base = 2 * low + 2 * first + 3 * second \
                        - 3 * (low & 1) - 4 - 2 * (distance - 7)
                    value = 2 * (base // 8) + (low & 1)
                table[first, second] = value
        result = bv(table[0, 0])
        for first in (0, 1):
            for second in (0, 1):
                result = z3.If(
                    z3.And(b1 == first, b2 == second),
                    bv(table[first, second]), result)
        return result

    current_u0 = u0_for(current_b1, current_b2)
    candidate_u0 = u0_for(candidate_b1, candidate_b2)
    current_fire = mreg < (current_u0 << 66)
    candidate_fire = mreg < (candidate_u0 << 66)
    current_retained = z3.LShR(umag, k) \
        - z3.If(current_fire, bv(1), bv(0))
    candidate_retained = z3.LShR(umag, k) \
        - z3.If(candidate_fire, bv(1), bv(0))

    branch_code = 1 if (s4 == 67 and template["side"] == 1
                        and distance == 8 and right_shift == 64) else 2
    values.update({
        "square_sig": square.sig, "square_e2": square.e2,
        "fourth_sig": fourth.sig, "fourth_e2": fourth.e2,
        "negative_sig": negative.sig, "negative_e2": negative.e2,
        "positive_sig": positive.sig, "positive_e2": positive.e2,
        "left_sig": left.sig, "left_e2": left.e2,
        "right_sig": right.sig, "right_e2": right.e2,
        "active": active,
        "low3": z3.Extract(2, 0, low3),
        "dist": distance,
        "payload": z3.Extract(7, 0, payload),
        "rsh": right_shift,
        "rdhi12": z3.Extract(11, 0, right_top12),
        "S": source, "B": subtrahend, "umag": umag,
        "k": k, "disc": discard, "theta": 0, "ce": ce, "s4": s4,
        "t4": t4,
        "t4hi12": z3.Extract(11, 0, z3.LShR(t4, s4 - 12)),
        "side": side,
        "sqlow": sqlow, "Mreg": mreg,
        "merge_gate": merge_gate,
        "right_l2_high_carry": z3.Not(merge_gate),
        "right_cpa_carry_into_cut": cpa_cut_carry,
        "rd3_kill_carry": rd3_merge != rd3_plain,
        "current_rd3": current_rd3, "candidate_rd3": candidate_rd3,
        "b1": current_b1, "b2": current_b2,
        "candidate_b1": candidate_b1, "candidate_b2": candidate_b2,
        "current_u0": current_u0, "candidate_u0": candidate_u0,
        "current_fire": current_fire, "candidate_fire": candidate_fire,
        "current_retained": current_retained,
        "candidate_retained": candidate_retained,
        "branch_code": branch_code,
    })
    for mode in MODES:
        values[f"current_{mode}"] = fixed_final_result(
            current_retained, ce, mode)
        values[f"candidate_{mode}"] = fixed_final_result(
            candidate_retained, ce, mode)

    constraints.extend((
        z3.UGT(source, subtrahend),
        bit(umag, k + 66) == 1,
        z3.LShR(umag, k + 67) == 0,
        low3 == template["low3"],
        payload == template["payload"],
        side == z3.BoolVal(bool(template["side"])),
    ))
    solver.assert_and_track(z3.And(*constraints),
                            f"{prefix}.exact_materialization_path")
    return FixedGraph(solver, m64, values, template, derive_tree)


def fixed_value_equal(value: z3.ExprRef | int, expected: int) -> z3.BoolRef:
    if isinstance(value, int):
        return z3.BoolVal(value == expected)
    if z3.is_bool(value):
        return value == z3.BoolVal(bool(expected))
    return value == expected


def verify_fixed_witness(graph: FixedGraph, model: z3.ModelRef) -> dict[str, int]:
    significand = as_int(graph.m, model)
    concrete = concrete_forward(significand)
    names = (
        "square_sig", "square_e2", "fourth_sig", "fourth_e2",
        "negative_sig", "negative_e2", "positive_sig", "positive_e2",
        "left_sig", "left_e2", "right_sig", "right_e2", "active",
        "low3", "dist", "payload", "rsh", "rdhi12", "S", "B",
        "umag", "k", "disc", "theta", "ce", "s4", "t4", "t4hi12",
        "side", "sqlow", "Mreg", "merge_gate", "right_l2_high_carry",
        "right_cpa_carry_into_cut", "rd3_kill_carry", "current_rd3",
        "candidate_rd3", "b1", "b2", "candidate_b1", "candidate_b2",
        "current_u0", "candidate_u0", "current_fire", "candidate_fire",
        "current_retained", "candidate_retained", "branch_code",
        *(f"current_{mode}" for mode in MODES),
        *(f"candidate_{mode}" for mode in MODES),
    )
    differences = {}
    tree_dependent = {
        "merge_gate", "right_l2_high_carry", "right_cpa_carry_into_cut",
        "current_rd3", "b1", "b2", "current_u0", "current_fire",
        "current_retained", *(f"current_{mode}" for mode in MODES),
    }
    for name in names:
        if not graph.derives_tree and name in tree_dependent:
            continue
        symbolic = graph.values[name]
        got = symbolic if isinstance(symbolic, int) else as_int(symbolic, model)
        if got != concrete[name]:
            differences[name] = (got, concrete[name])
    if differences:
        raise AssertionError(
            f"fixed-symbolic/Python mismatch: {list(differences.items())[:8]}")
    return concrete


def add_r1382_separator_constraints(graph: SymGraph) -> None:
    values = graph.values
    structural = z3.And(
        values["active"],
        values["low3"] == 3,
        values["disc"] == 0,
        values["theta"] == 0,
        values["s4"] == 66,
        values["merge_gate"],
        values["dist"] >= 7,
        values["dist"] <= 10,
        z3.Or(values["ce"] == -72, values["ce"] == -73,
              values["ce"] == -74),
        values["payload"] >= 0,
        values["payload"] <= 8,
    )
    graph.solver.assert_and_track(structural, "r1382.structural_parent")
    endpoint = z3.And(
        values["current_retained"] != values["candidate_retained"],
        z3.Or(*(values[f"current_{mode}"] != values[f"candidate_{mode}"]
                for mode in MODES)),
    )
    graph.solver.assert_and_track(endpoint, "r1382.endpoint_visible")


def model_values(graph: SymGraph, model: z3.ModelRef,
                 names: Iterable[str]) -> dict[str, int]:
    return {name: as_int(graph.values[name], model) for name in names}


def verify_symbolic_witness(graph: SymGraph, model: z3.ModelRef) -> dict[str, int]:
    significand = as_int(graph.m, model)
    concrete = concrete_forward(significand)
    check_names = (
        "square_sig", "square_e2", "fourth_sig", "fourth_e2",
        "negative_sig", "negative_e2", "positive_sig", "positive_e2",
        "left_sig", "left_e2", "right_sig", "right_e2", "active",
        "low3", "dist", "payload", "rsh", "rdhi12", "S", "B",
        "umag", "k", "disc", "theta", "ce", "s4", "t4", "t4hi12",
        "side", "sqlow", "Mreg", "merge_gate", "right_l2_high_carry",
        "right_cpa_carry_into_cut", "rd3_kill_carry", "current_rd3",
        "candidate_rd3", "b1", "b2", "candidate_b1", "candidate_b2",
        "current_u0", "candidate_u0", "current_fire", "candidate_fire",
        "current_retained", "candidate_retained", "branch_code",
        *(f"current_{mode}" for mode in MODES),
        *(f"candidate_{mode}" for mode in MODES),
    )
    symbolic = model_values(graph, model, check_names)
    differences = {
        name: (symbolic[name], concrete[name])
        for name in check_names if symbolic[name] != concrete[name]
    }
    if differences:
        first = list(differences.items())[:8]
        raise AssertionError(f"symbolic/Python replay mismatch: {first}")
    return concrete


def run_instruction_model(binary: Path, instruction: str, operand: str,
                          mode: str, dump: bool = False) -> tuple[str, str]:
    if instruction not in ("fsin", "fcos"):
        raise ValueError(f"unsupported model instruction {instruction}")
    command = [str(binary.resolve()), "--batch", f"--rc={mode}",
               f"--{instruction}-standalone"]
    if dump:
        command.append("--dump-internals")
    completed = subprocess.run(
        command,
        input=operand + "\n",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    lines = [line.strip() for line in completed.stdout.splitlines()
             if line.startswith(("OK ", "C2 ", "UNSUPPORTED "))]
    if len(lines) != 1:
        raise RuntimeError(f"{binary} produced {len(lines)} result lines")
    return lines[0], completed.stderr


def run_model(binary: Path, operand: str, mode: str,
              dump: bool = False) -> tuple[str, str]:
    return run_instruction_model(binary, "fcos", operand, mode, dump)


def replay_c_witness(operand: str, concrete: dict[str, int],
                     compact: Path | None, incumbent: Path | None,
                     candidate: Path | None) -> dict[str, Any]:
    _, significand = parse_operand(operand)
    replay: dict[str, Any] = {"python": "exact"}
    if compact is not None:
        completed = subprocess.run(
            [str(compact.resolve()), f"{significand:016x}", "1"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        rows = completed.stdout.splitlines()
        if len(rows) != 1:
            raise AssertionError("compact C graph did not reproduce witness")
        fields = rows[0].split()
        if fields[0].lower() != f"{significand:016x}":
            raise AssertionError("compact C graph returned another operand")
        if int(fields[1]) != concrete["dist"] \
                or int(fields[2]) != concrete["low3"] \
                or int(fields[3]) != concrete["k"] \
                or int(fields[-2]) != concrete["theta"] \
                or int(fields[-1]) != concrete["s4"]:
            raise AssertionError("compact C graph state differs from Python")
        replay["compact_c"] = "exact"
        replay["compact_c_sha256"] = sha256(compact)
    if incumbent is not None and candidate is not None:
        changed_modes = []
        incumbent_outputs = {}
        candidate_outputs = {}
        for mode in MODES:
            current, stderr = run_model(incumbent, operand, mode, dump=(mode == "rn"))
            alternate, _ = run_model(candidate, operand, mode)
            incumbent_outputs[mode] = current
            candidate_outputs[mode] = alternate
            if current != alternate:
                changed_modes.append(mode)
            if mode == "rn":
                match = re.search(
                    r"DI_R59 .*?theta=(-?\d+).*?k=(\d+).*?ce=(-?\d+).*?"
                    r"s4=(\d+).*?side=(\d+).*?b1=(\d+).*?b2=(\d+)",
                    stderr,
                )
                if not match:
                    raise AssertionError("full C model did not reach DI_R59")
                got = tuple(map(int, match.groups()))
                want = tuple(concrete[name] for name in
                             ("theta", "k", "ce", "s4", "side", "b1", "b2"))
                if got != want:
                    raise AssertionError(f"full C/Python state mismatch {got} != {want}")
        replay.update({
            "full_c": "exact",
            "incumbent_sha256": sha256(incumbent),
            "candidate_sha256": sha256(candidate),
            "changed_modes": changed_modes,
            "incumbent_outputs": incumbent_outputs,
            "candidate_outputs": candidate_outputs,
        })
    return replay


def repository_operand_collision(repo: Path, operand: str,
                                 exclude: Path | None = None) -> bool:
    patterns = f"{operand}\n{operand.replace(' ', ':')}\n"
    command = ["rg", "-I", "-i", "-F", "-f", "-"]
    if exclude is not None:
        try:
            relative = exclude.resolve().relative_to(repo.resolve())
            command.extend(("--glob", f"!{relative}"))
        except ValueError:
            pass
    command.append(str(repo))
    completed = subprocess.run(
        command, input=patterns, text=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if completed.returncode not in (0, 1):
        raise RuntimeError(f"repository freshness scan failed: {completed.stderr}")
    return completed.returncode == 0


def write_json_new(path: Path, data: Any) -> None:
    if path.exists():
        raise SystemExit(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as target:
        json.dump(data, target, indent=2, sort_keys=True)
        target.write("\n")


def solve_separator(args: argparse.Namespace) -> dict[str, Any]:
    if args.fixed_template:
        _, template_sig = parse_operand(args.fixed_template)
        graph = build_fixed_path_graph(
            template_sig, "separator_fixed", derive_tree=False)
        graph.solver.set(timeout=args.timeout_ms)
        values = graph.values
        graph.solver.assert_and_track(
            z3.And(
                values["active"],
                values["disc"] == 0,
                values["merge_gate"],
                values["current_retained"] != values["candidate_retained"],
                z3.Or(*(values[f"current_{mode}"]
                        != values[f"candidate_{mode}"] for mode in MODES)),
            ),
            "r1382.endpoint_visible_in_fixed_path",
        )
        repo = args.repo.resolve()
        blocked: list[str] = []
        witnesses = []
        known_witnesses = []
        attempts = 0

        # Prove and replay the known d0d0 endpoint first.  Keeping this SAT
        # result separate prevents a bounded second-witness search from
        # erasing established positive evidence when it returns UNKNOWN.
        graph.solver.push()
        graph.solver.add(graph.m == z3.BitVecVal(template_sig, 64))
        known_result = graph.solver.check()
        if known_result != z3.sat:
            raise RuntimeError(
                f"fixed template did not satisfy its exact path: {known_result}")
        known_model = graph.solver.model()
        known = verify_fixed_witness(graph, known_model)
        known_operand = operand_text(0x3FFC, known["m"])
        known_replay = replay_c_witness(
            known_operand, known, args.compact, args.incumbent, args.candidate)
        known_witnesses.append({
            "operand": known_operand,
            "result": "SAT",
            "changed_modes": [
                mode for mode in MODES
                if known[f"current_{mode}"] != known[f"candidate_{mode}"]
            ],
            "features": {name: known[name] for name in
                         (*OBSERVED_SELECTOR_FEATURES, "merge_gate",
                          "current_rd3", "candidate_rd3",
                          "current_retained", "candidate_retained")},
            "replay": known_replay,
            "freshness": "repository_known_not_capture_eligible",
        })
        graph.solver.pop()
        graph.solver.add(graph.m != z3.BitVecVal(template_sig, 64))

        while len(witnesses) < args.limit:
            attempts += 1
            result = graph.solver.check()
            if result == z3.unsat:
                return {
                    "query": "r1382_endpoint_visible_separator",
                    "solver": z3.get_version_string(),
                    "result": "SAT_KNOWN_FRESH_UNSAT" if not witnesses
                    else "SAT_FRESH_EXHAUSTED",
                    "unsat_core": sorted(
                        str(item) for item in graph.solver.unsat_core()),
                    "attempts": attempts,
                    "blocked_repository_operands": len(blocked),
                    "known_witnesses": known_witnesses,
                    "witnesses": witnesses,
                    "scope": (
                        "all positive normal 3ffc inputs in the exact complete "
                        f"materialization path of {args.fixed_template}; "
                        "second-witness search relaxes the R1272 gate to its "
                        "enabling value, so UNSAT also proves the physical subset"
                    ),
                    "hardware_execution": "none",
                }
            if result == z3.unknown:
                return {
                    "query": "r1382_endpoint_visible_separator",
                    "solver": z3.get_version_string(),
                    "result": "SAT_KNOWN_FRESH_UNKNOWN",
                    "reason": graph.solver.reason_unknown(),
                    "attempts": attempts,
                    "blocked_repository_operands": len(blocked),
                    "known_witnesses": known_witnesses,
                    "witnesses": witnesses,
                    "timeout_ms": args.timeout_ms,
                    "hardware_execution": "none",
                }
            model = graph.solver.model()
            concrete = verify_fixed_witness(graph, model)
            operand = operand_text(0x3FFC, concrete["m"])
            graph.solver.add(graph.m != z3.BitVecVal(concrete["m"], 64))
            if repository_operand_collision(repo, operand, args.output):
                blocked.append(operand)
                continue
            replay = replay_c_witness(
                operand, concrete, args.compact, args.incumbent, args.candidate)
            changed = [mode for mode in MODES
                       if concrete[f"current_{mode}"]
                       != concrete[f"candidate_{mode}"]]
            witnesses.append({
                "operand": operand,
                "changed_modes": changed,
                "features": {name: concrete[name] for name in
                             (*OBSERVED_SELECTOR_FEATURES, "merge_gate",
                              "current_rd3", "candidate_rd3",
                              "current_retained", "candidate_retained")},
                "replay": replay,
                "freshness": "repository_operand_absent_private_audit_pending",
            })
        return {
            "query": "r1382_endpoint_visible_separator",
            "solver": z3.get_version_string(),
            "result": "SAT",
            "attempts": attempts,
            "blocked_repository_operands": len(blocked),
            "known_witnesses": known_witnesses,
            "witnesses": witnesses,
            "scope": (
                "all positive normal 3ffc inputs in the exact complete "
                f"materialization path of {args.fixed_template}"
            ),
            "hardware_execution": "none",
        }

    graph = build_symbolic_graph("separator")
    add_r1382_separator_constraints(graph)
    repo = args.repo.resolve()
    blocked: list[str] = []
    witnesses = []
    attempts = 0
    while len(witnesses) < args.limit:
        attempts += 1
        result = graph.solver.check()
        if result == z3.unsat:
            core = sorted(str(item) for item in graph.solver.unsat_core())
            return {
                "query": "r1382_endpoint_visible_separator",
                "solver": z3.get_version_string(),
                "result": "UNSAT" if not witnesses else "SAT_EXHAUSTED",
                "unsat_core": core,
                "attempts": attempts,
                "blocked_repository_operands": len(blocked),
                "witnesses": witnesses,
                "scope": "all positive normal 3ffc inputs in exact compact pipeline",
                "hardware_execution": "none",
            }
        if result == z3.unknown:
            return {
                "query": "r1382_endpoint_visible_separator",
                "solver": z3.get_version_string(),
                "result": "UNKNOWN",
                "reason": graph.solver.reason_unknown(),
                "attempts": attempts,
                "blocked_repository_operands": len(blocked),
                "witnesses": witnesses,
                "hardware_execution": "none",
            }
        model = graph.solver.model()
        concrete = verify_symbolic_witness(graph, model)
        operand = operand_text(0x3FFC, concrete["m"])
        graph.solver.add(graph.m != z3.BitVecVal(concrete["m"], 64))
        if repository_operand_collision(repo, operand, args.output):
            blocked.append(operand)
            continue
        replay = replay_c_witness(
            operand, concrete, args.compact, args.incumbent, args.candidate)
        changed = [mode for mode in MODES
                   if concrete[f"current_{mode}"] != concrete[f"candidate_{mode}"]]
        if not changed:
            raise AssertionError("SAT witness lost endpoint visibility in Python")
        witnesses.append({
            "operand": operand,
            "changed_modes": changed,
            "features": {name: concrete[name] for name in
                         (*OBSERVED_SELECTOR_FEATURES, "merge_gate",
                          "current_rd3", "candidate_rd3", "current_retained",
                          "candidate_retained")},
            "replay": replay,
            "freshness": "repository_operand_absent_private_audit_pending",
        })
    return {
        "query": "r1382_endpoint_visible_separator",
        "solver": z3.get_version_string(),
        "result": "SAT",
        "attempts": attempts,
        "blocked_repository_operands": len(blocked),
        "witnesses": witnesses,
        "scope": "all positive normal 3ffc inputs in exact compact pipeline",
        "hardware_execution": "none",
    }


def solve_collision(args: argparse.Namespace) -> dict[str, Any]:
    _, anchor_sig = parse_operand(args.anchor)
    anchor = concrete_forward(anchor_sig)
    if anchor["theta"] != 0:
        raise SystemExit("collision anchor is not an exact tie in the compact graph")
    if args.hidden_source not in anchor:
        raise SystemExit(f"unknown hidden source {args.hidden_source}")
    graph = build_fixed_path_graph(anchor_sig, "collision")
    graph.solver.set(timeout=args.timeout_ms)
    values = graph.values
    feature_equalities = []
    for name in OBSERVED_SELECTOR_FEATURES:
        feature_equalities.append(fixed_value_equal(values[name], anchor[name]))
    graph.solver.assert_and_track(
        z3.And(values["active"], values["disc"] == 0,
               *feature_equalities),
        "collision.observed_selector_features_equal",
    )
    hidden = values[args.hidden_source]
    anchor_hidden = bool(anchor[args.hidden_source])
    graph.solver.assert_and_track(
        hidden != z3.BoolVal(anchor_hidden),
        "collision.hidden_carry_differs",
    )
    graph.solver.assert_and_track(
        graph.m != z3.BitVecVal(anchor_sig, 64),
        "collision.distinct_operands",
    )
    result = graph.solver.check()
    report: dict[str, Any] = {
        "query": "observed_feature_collision_hidden_carry_difference",
        "solver": z3.get_version_string(),
        "anchor": operand_text(*parse_operand(args.anchor)),
        "hidden_source": args.hidden_source,
        "anchor_hidden_value": int(anchor_hidden),
        "observed_features": list(OBSERVED_SELECTOR_FEATURES),
        "hardware_execution": "none",
    }
    if result == z3.unsat:
        report.update({
            "result": "UNSAT",
            "unsat_core": sorted(str(item) for item in graph.solver.unsat_core()),
            "scope": (
                "all positive normal 3ffc inputs in the anchor's exact "
                "complete materialization path"
            ),
        })
        return report
    if result == z3.unknown:
        report.update({"result": "UNKNOWN", "reason": graph.solver.reason_unknown()})
        return report
    model = graph.solver.model()
    witness = verify_fixed_witness(graph, model)
    operand = operand_text(0x3FFC, witness["m"])
    if any(witness[name] != anchor[name] for name in OBSERVED_SELECTOR_FEATURES):
        raise AssertionError("Python replay does not preserve collision features")
    if bool(witness[args.hidden_source]) == anchor_hidden:
        raise AssertionError("Python replay does not separate hidden carry")
    replay = replay_c_witness(
        operand, witness, args.compact, args.incumbent, args.candidate)
    report.update({
        "result": "SAT",
        "pair": [operand_text(0x3FFC, anchor_sig), operand],
        "hidden_values": [int(anchor_hidden), witness[args.hidden_source]],
        "feature_values": {name: anchor[name] for name in OBSERVED_SELECTOR_FEATURES},
        "witness_freshness": (
            "repository_operand_present" if repository_operand_collision(
                args.repo.resolve(), operand, args.output)
            else "repository_operand_absent_private_audit_pending"
        ),
        "replay": replay,
    })
    return report


def nearest_x80_bracket(exact_integer: int, residual_scale: int) -> list[dict[str, Any]]:
    width = exact_integer.bit_length()
    shift = max(0, width - 64)
    unit = 1 << shift
    lower = exact_integer & -unit
    rows = []
    for kind, represented in (("lower", lower), ("upper", lower + unit)):
        sig = represented >> shift
        unbiased = residual_scale + shift + 63
        se = 0x3FFF + unbiased
        rows.append({
            "kind": kind,
            "operand": operand_text(se, sig),
            "integer_error_at_residual_scale": represented - exact_integer,
        })
    return rows


def solve_preimage_one(anchor: str, quotient_hint: int, side_hint: int) -> dict[str, Any]:
    _, residual_sig = parse_operand(anchor)
    solver = z3.Solver()
    solver.set(unsat_core=True)
    se = z3.BitVec("preimage_se", 16)
    sig = z3.BitVec("preimage_sig", 64)
    quotient = z3.BitVec("preimage_q", 64)
    shift16 = se - z3.BitVecVal(0x3FFC, 16)
    shift = z3.ZeroExt(W - 16, shift16)
    external = z3.ZeroExt(W - 64, sig) << shift
    qwide = z3.ZeroExt(W - 64, quotient)
    residual = bv(residual_sig)

    solver.assert_and_track(
        z3.And(z3.UGE(se, z3.BitVecVal(0x3FFD, 16)),
               z3.ULE(se, z3.BitVecVal(0x403D, 16)), bit(sig, 63) == 1),
        "preimage.external_positive_finite_normal_below_2^63",
    )
    solver.assert_and_track(
        z3.And(z3.UGT(quotient, z3.BitVecVal(0, 64)),
               z3.ULE(quotient, z3.BitVecVal((1 << 63) - 1, 64))),
        "preimage.nonzero_quotient",
    )
    side = z3.Int("preimage_side")
    solver.assert_and_track(z3.Or(side == -1, side == 1),
                            "preimage.residual_sign")
    target = bv(2 * M66) * qwide + z3.If(side == 1, residual, -residual)
    solver.assert_and_track(external == target, "preimage.exact_M66_equation")
    # Prefer the already-frozen small transfer coordinate when it is exact;
    # only then ask for any positive quotient.  This keeps old exact witnesses
    # stable while still discovering globally reachable states missed by a
    # fixed-quotient construction.
    solver.push()
    solver.add(quotient == z3.BitVecVal(quotient_hint, 64), side == side_hint)
    hint_result = solver.check()
    if hint_result == z3.sat:
        result = hint_result
        search_policy = "preferred_frozen_quotient"
    else:
        solver.pop()
        result = solver.check()
        search_policy = "any_nonzero_quotient"
    row: dict[str, Any] = {
        "anchor": anchor,
        "residual_sig": f"{residual_sig:016x}",
        "residual_parity": residual_sig & 1,
        "result": str(result).upper(),
        "search_policy": search_policy,
    }
    if result == z3.sat:
        model = solver.model()
        se_value = as_int(se, model)
        sig_value = as_int(sig, model)
        q_value = as_int(quotient, model)
        side_value = as_int(side, model)
        lhs = sig_value << (se_value - 0x3FFC)
        rhs = 2 * q_value * M66 + side_value * residual_sig
        if lhs != rhs:
            raise AssertionError("preimage witness fails Python exact equation")
        row.update({
            "operand": operand_text(se_value, sig_value),
            "quotient": q_value,
            "residual_side": side_value,
            "python_replay": "exact_M66_equation",
        })
    elif result == z3.unsat:
        exact_hint = 2 * quotient_hint * M66 + side_hint * residual_sig
        row.update({
            "unsat_core": sorted(str(item) for item in solver.unsat_core()),
            "bracket_quotient": quotient_hint,
            "bracket_residual_side": side_hint,
            "brackets": nearest_x80_bracket(exact_hint, -66),
        })
    else:
        row["reason"] = solver.reason_unknown()
    return row


def replay_external_reduction(binary: Path, row: dict[str, Any]) -> None:
    if row["result"] != "SAT":
        return
    _, stderr = run_model(binary, row["operand"], "rn", dump=True)
    match = re.search(
        r"DI_RED .*?rsn=(\d+) mag=(\d+):(-?\d+):([0-9a-fA-F]+)", stderr)
    if not match:
        raise AssertionError(f"full C model did not expose reduced state for {row['anchor']}")
    residual_sign = int(match.group(1))
    exponent = int(match.group(3))
    significand = int(match.group(4), 16)
    expected_sign = int(int(row["residual_side"]) < 0)
    if residual_sign != expected_sign or exponent != -66 \
            or significand != int(row["residual_sig"], 16):
        raise AssertionError(
            f"C reduction mismatch for {row['anchor']}: "
            f"{residual_sign}:{exponent}:{significand:x}")
    row["c_replay"] = "exact_reduced_state"
    row["c_model_sha256"] = sha256(binary)


def solve_preimages(args: argparse.Namespace) -> dict[str, Any]:
    rows = []
    for anchor, (quotient, side) in UNRESOLVED_QUOTIENTS.items():
        row = solve_preimage_one(anchor, quotient, side)
        if args.incumbent is not None:
            replay_external_reduction(args.incumbent, row)
        rows.append(row)
    return {
        "query": "nonzero_quotient_exact_external_preimages",
        "solver": z3.get_version_string(),
        "external_encoding": "positive finite normal x87, abs(x)<2^63",
        "reduction_equation_at_2^-66": "sig<<(se-0x3ffc) = 2*q*M66 +/- residual",
        "rows": rows,
        "sat": sum(row["result"] == "SAT" for row in rows),
        "unsat": sum(row["result"] == "UNSAT" for row in rows),
        "hardware_execution": "none",
    }


PIPELINE_TRACE_PREFIXES = (
    "DI_RED ",
    "DI_POLY ",
    "DI_TC ",
    "DI_R59 ",
    "DI_CRIT ",
    "DI_BS ",
    "DI_BR ",
)


def reduction_add_carry_into_column(addend: int, residual: int,
                                    column: int) -> int:
    """Return the exact ripple carry entering ``column`` from lower bits."""

    if column <= 0:
        return 0
    mask = (1 << column) - 1
    return int((addend & mask) + (residual & mask) >= (1 << column))


def observed_pipeline_trace(stderr: str) -> list[str]:
    return [line.strip() for line in stderr.splitlines()
            if line.startswith(PIPELINE_TRACE_PREFIXES)]


def trace_key_values(line: str) -> dict[str, str]:
    return {field.split("=", 1)[0]: field.split("=", 1)[1]
            for field in line.split()[1:] if "=" in field}


def trace_sfp(text: str) -> tuple[int, int, int]:
    sign, exponent, significand = text.split(":")
    return int(sign), int(exponent), int(significand, 16)


def verify_concrete_pipeline_trace(concrete: dict[str, int],
                                   trace: list[str]) -> None:
    by_prefix = {line.split()[0]: trace_key_values(line) for line in trace}
    polynomial = by_prefix["DI_POLY"]
    terminal = by_prefix["DI_TC"]
    r59 = by_prefix["DI_R59"]
    sfp_checks = (
        (polynomial["sq"], (0, concrete["square_e2"], concrete["square_sig"])),
        (polynomial["f4"], (0, concrete["fourth_e2"], concrete["fourth_sig"])),
        (polynomial["odd"], (1, concrete["negative_e2"], concrete["negative_sig"])),
        (polynomial["even"], (0, concrete["positive_e2"], concrete["positive_sig"])),
        (terminal["left"], (1, concrete["left_e2"], concrete["left_sig"])),
        (terminal["right"], (0, concrete["right_e2"], concrete["right_sig"])),
    )
    if any(trace_sfp(got) != want for got, want in sfp_checks):
        raise AssertionError("C/Python square/fourth/Horner/terminal mismatch")
    decimal_fields = (
        "theta", "k", "ce", "s4", "side", "b1", "b2", "low3",
        "dist", "rsh", "payload",
    )
    if any(int(r59[name]) != concrete[name] for name in decimal_fields):
        raise AssertionError("C/Python observed selector-feature mismatch")
    hex_fields = {
        "umag": "umag",
        "S": "S",
        "B": "B",
        "Mreg": "Mreg",
        "t4": "t4",
        "sqlow": "sqlow",
        "rd3": "current_rd3",
        "disc": "disc",
    }
    if any(int(r59[c_name], 16) != concrete[py_name]
           for c_name, py_name in hex_fields.items()):
        raise AssertionError("C/Python raw R59-state mismatch")


def solve_reduction_collision(args: argparse.Namespace) -> dict[str, Any]:
    """Construct an exact q=0/q>0 collision with distinct carry history.

    The direct FCOS operand and the nonzero-quotient FSIN operand reduce to
    the same signed fixed-point residual.  Consequently the entire exposed
    polynomial/terminal trace collides, while the exact M66 addition that
    precedes reduction has a different carry into column 64.  This is an
    actual preimage synthesis result, not a sequential operand search.
    """

    anchor = args.anchor.lower()
    if anchor not in UNRESOLVED_QUOTIENTS:
        raise SystemExit("reduction collision anchor is not an unresolved state")
    _, residual_sig = parse_operand(anchor)
    quotient_hint, side_hint = UNRESOLVED_QUOTIENTS[anchor]
    row = solve_preimage_one(anchor, quotient_hint, side_hint)
    if row["result"] != "SAT":
        raise SystemExit(f"anchor has no exact external preimage: {row['result']}")
    if int(row["residual_side"]) != 1:
        raise SystemExit(
            "collision construction currently requires a positive residual")

    quotient = int(row["quotient"])
    external = row["operand"]
    direct_carry = reduction_add_carry_into_column(0, residual_sig, 64)
    external_addend = 2 * quotient * M66
    external_carry = reduction_add_carry_into_column(
        external_addend, residual_sig, 64)
    if direct_carry == external_carry:
        raise AssertionError("synthesized pair did not separate the hidden carry")

    concrete = concrete_forward(residual_sig)
    python_features = {
        name: concrete[name] for name in OBSERVED_SELECTOR_FEATURES
    }
    report: dict[str, Any] = {
        "query": "exact_reduction_history_collision",
        "solver": z3.get_version_string(),
        "result": "SAT",
        "pair": [
            {"instruction": "fcos", "operand": anchor, "quotient": 0},
            {"instruction": "fsin", "operand": external,
             "quotient": quotient},
        ],
        "exact_reduction_equation_at_2^-66": {
            "external_integer": (
                parse_operand(external)[1]
                << (parse_operand(external)[0] - 0x3FFC)
            ),
            "m66_addend": external_addend,
            "residual": residual_sig,
            "residual_side": 1,
            "python_replay": row["python_replay"],
        },
        "observed_features": list(OBSERVED_SELECTOR_FEATURES),
        "feature_values": python_features,
        "proposed_hidden_source": "M66 reduction-add carry into column 64",
        "hidden_values": [direct_carry, external_carry],
        "scope": (
            "exact positive finite x87 preimage and exact reduced-state "
            "square/fourth/Horner/terminal pipeline"
        ),
        "hardware_execution": "none",
    }

    if args.incumbent is not None:
        replay_external_reduction(args.incumbent, row)
        direct_outputs: dict[str, str] = {}
        external_outputs: dict[str, str] = {}
        direct_trace: list[str] | None = None
        external_trace: list[str] | None = None
        for mode in MODES:
            direct_result, direct_stderr = run_instruction_model(
                args.incumbent, "fcos", anchor, mode, dump=(mode == "rn"))
            external_result, external_stderr = run_instruction_model(
                args.incumbent, "fsin", external, mode, dump=(mode == "rn"))
            direct_outputs[mode] = direct_result
            external_outputs[mode] = external_result
            if mode == "rn":
                direct_trace = observed_pipeline_trace(direct_stderr)
                external_trace = observed_pipeline_trace(external_stderr)
        if not direct_trace or not external_trace:
            raise AssertionError("full C model emitted no observable pipeline trace")
        required = ("DI_RED ", "DI_POLY ", "DI_TC ", "DI_R59 ", "DI_BR ")
        for prefix in required:
            if not any(line.startswith(prefix) for line in direct_trace):
                raise AssertionError(f"full C trace omitted {prefix.strip()}")
        if direct_trace != external_trace:
            raise AssertionError("C replay does not collide on the exposed pipeline")
        verify_concrete_pipeline_trace(concrete, direct_trace)
        report["c_replay"] = {
            "result": "exact_observed_pipeline_collision",
            "model_sha256": sha256(args.incumbent),
            "common_trace": direct_trace,
            "direct_outputs": direct_outputs,
            "external_outputs": external_outputs,
            "output_difference_modes": [
                mode for mode in MODES
                if direct_outputs[mode] != external_outputs[mode]
            ],
        }
    return report


def solve_cvc5_separator_crosscheck(args: argparse.Namespace) -> dict[str, Any]:
    """Run the independent CVC5 stopping check on the exact fixed-path query."""

    try:
        import cvc5
    except ImportError as error:
        raise SystemExit(
            "cvc5 is required for crosscheck-separator (validated with 1.3.1)"
        ) from error

    _, template_sig = parse_operand(args.fixed_template)
    graph = build_fixed_path_graph(
        template_sig, "separator_fixed", derive_tree=False)
    values = graph.values
    graph.solver.assert_and_track(
        z3.And(
            values["active"],
            values["disc"] == 0,
            values["merge_gate"],
            values["current_retained"] != values["candidate_retained"],
            z3.Or(*(values[f"current_{mode}"]
                    != values[f"candidate_{mode}"] for mode in MODES)),
        ),
        "r1382.endpoint_visible_in_fixed_path",
    )
    graph.solver.add(graph.m != z3.BitVecVal(template_sig, 64))

    # Z3's SMT-LIB export represents tracked constraints as implications and
    # relies on check-time assumptions that are not printed.  Assert both
    # tracking literals explicitly so another solver receives the same query.
    query = graph.solver.to_smt2()
    query = query.replace(
        "(set-info :status unknown)",
        "(set-logic QF_BV)\n(set-info :status unknown)",
        1,
    )
    query = query.replace(
        "(check-sat)",
        "(assert separator_fixed.exact_materialization_path)\n"
        "(assert r1382.endpoint_visible_in_fixed_path)\n"
        "(check-sat)",
        1,
    )
    if args.query_output.exists():
        raise SystemExit(f"refusing to overwrite {args.query_output}")
    args.query_output.parent.mkdir(parents=True, exist_ok=True)
    with args.query_output.open("x") as target:
        target.write(query)

    solver = cvc5.Solver()
    solver.setOption("produce-models", "true")
    solver.setOption("produce-unsat-cores", "true")
    solver.setOption("tlimit-per", str(args.timeout_ms))
    parser = cvc5.InputParser(solver)
    parser.setStringInput(cvc5.InputLanguage.SMT_LIB_2_6, query,
                          str(args.query_output))
    result_text = ""
    while not parser.done():
        command = parser.nextCommand()
        if command.isNull():
            break
        response = command.invoke(solver, parser.getSymbolManager())
        if command.getCommandName() == "check-sat":
            result_text = str(response).strip()
    if not result_text:
        raise RuntimeError("CVC5 parser executed no check-sat command")

    report: dict[str, Any] = {
        "query": "r1382_endpoint_visible_second_witness_crosscheck",
        "solver": f"cvc5 {cvc5.__version__}",
        "timeout_ms": args.timeout_ms,
        "query_artifact": str(args.query_output),
        "query_bytes": len(query.encode()),
        "query_sha256": sha256(args.query_output),
        "scope": (
            "all positive normal 3ffc inputs in the exact complete "
            f"materialization path of {args.fixed_template}, excluding that "
            "operand; R1272 gate relaxed to the enabling value, so UNSAT "
            "would also prove the physical subset"
        ),
        "hardware_execution": "none",
    }
    if result_text.startswith("unknown"):
        report.update({"result": "UNKNOWN", "reason": result_text})
    elif result_text == "unsat":
        report.update({
            "result": "UNSAT",
            "unsat_core": sorted(str(term) for term in solver.getUnsatCore()),
        })
    elif result_text == "sat":
        declared = parser.getSymbolManager().getDeclaredTerms()
        matches = [term for term in declared
                   if str(term) == "separator_fixed_sig"]
        if len(matches) != 1:
            raise AssertionError("CVC5 model omitted separator_fixed_sig")
        model_text = str(solver.getValue(matches[0]))
        if not model_text.startswith("#b"):
            raise AssertionError(f"unexpected CVC5 bit-vector {model_text}")
        witness_sig = int(model_text[2:], 2)
        concrete = concrete_forward(witness_sig)
        replay_solver = build_fixed_path_graph(
            template_sig, "cvc5_replay", derive_tree=True)
        replay_solver.solver.add(
            replay_solver.m == z3.BitVecVal(witness_sig, 64))
        replay_values = replay_solver.values
        replay_solver.solver.add(
            replay_values["active"], replay_values["disc"] == 0,
            replay_values["merge_gate"],
            replay_values["current_retained"]
            != replay_values["candidate_retained"],
            z3.Or(*(replay_values[f"current_{mode}"]
                    != replay_values[f"candidate_{mode}"] for mode in MODES)),
        )
        replay_result = replay_solver.solver.check()
        if replay_result != z3.sat:
            report.update({
                "result": "SAT_RELAXED_SPURIOUS",
                "operand": operand_text(0x3FFC, witness_sig),
                "exact_tree_replay": str(replay_result).upper(),
            })
        else:
            verify_fixed_witness(replay_solver, replay_solver.solver.model())
            replay = replay_c_witness(
                operand_text(0x3FFC, witness_sig), concrete,
                args.compact, args.incumbent, args.candidate)
            report.update({
                "result": "SAT",
                "operand": operand_text(0x3FFC, witness_sig),
                "exact_tree_replay": "SAT",
                "replay": replay,
            })
    else:
        raise RuntimeError(f"unrecognized CVC5 result {result_text!r}")
    return report


TUPLE_RE = re.compile(
    r"\b(fsin|fcos|fsincos|sin|cos)\b.*?\b(rn|rd|ru|rz)\b.*?"
    r"\b([0-9a-fA-F]{4})[ :]([0-9a-fA-F]{16})\b",
    re.IGNORECASE,
)


def private_tuple_collision(paths: list[Path], keys: set[tuple[str, str, str]]) -> bool:
    collision = False
    aliases = {"sin": "fsin", "cos": "fcos"}
    for path in paths:
        with path.open(errors="replace") as source:
            for line in source:
                match = TUPLE_RE.search(line)
                if not match:
                    continue
                instruction = aliases.get(match.group(1).lower(), match.group(1).lower())
                mode = match.group(2).lower()
                operand = f"{match.group(3).lower()} {match.group(4).lower()}"
                if (instruction, mode, operand) in keys:
                    collision = True
    return collision


def repository_tuple_collision(repo: Path,
                               keys: set[tuple[str, str, str]],
                               exclude: Path | None) -> bool:
    # First find exact operand spellings, then demand instruction and mode on
    # the same text line.  This is conservative for ordinary capture TSV/log
    # formats and does not emit the matching line.
    collision = False
    for instruction, mode, operand in keys:
        pattern = re.compile(
            rf"\b(?:{re.escape(instruction)}|"
            rf"{'sin' if instruction == 'fsin' else 'cos' if instruction == 'fcos' else 'fsincos'})\b"
            rf".*\b{re.escape(mode)}\b.*\b{re.escape(operand.split()[0])}"
            rf"[ :]?{re.escape(operand.split()[1])}\b",
            re.IGNORECASE,
        )
        for path in repo.rglob("*"):
            if not path.is_file() or (exclude is not None and path == exclude):
                continue
            try:
                with path.open(errors="ignore") as source:
                    if any(pattern.search(line) for line in source):
                        collision = True
                        break
            except (OSError, UnicodeError):
                continue
        if collision:
            break
    return collision


def freeze_manifest(args: argparse.Namespace) -> dict[str, Any]:
    if not args.private_ledger:
        raise SystemExit(
            "freeze refuses without --private-ledger; private tuple audit is mandatory")
    source = json.loads(args.source.read_text())
    witnesses = source.get("witnesses", [])
    if not witnesses:
        raise SystemExit("source report contains no SAT separator witnesses")
    rows = []
    for index, witness in enumerate(witnesses, 1):
        for mode in witness["changed_modes"]:
            rows.append({
                "case_id": f"H1404-{index:03d}-{mode.upper()}",
                "instruction": "fcos",
                "mode": mode,
                "operand": witness["operand"],
                "candidate": "R1382_s4_qualified_hard3x_merge",
                "capture_state": "FROZEN_UNOPENED",
            })
    keys = {(row["instruction"], row["mode"], row["operand"]) for row in rows}
    if len(keys) != len(rows):
        raise SystemExit("software report contains duplicate capture tuples")
    if repository_tuple_collision(args.repo.resolve(), keys, args.output):
        raise SystemExit("freeze rejected a repository-visible capture tuple")
    if private_tuple_collision(args.private_ledger, keys):
        raise SystemExit("freeze rejected a private-ledger capture tuple")
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", newline="") as target:
        writer = csv.DictWriter(target, tuple(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    return {
        "operation": "freeze",
        "result": "FROZEN_UNOPENED",
        "rows": len(rows),
        "unique_capture_keys": len(keys),
        "repository_tuple_audit": "passed",
        "private_tuple_audit": "passed_contents_not_published",
        "manifest": str(args.output),
        "manifest_sha256": sha256(args.output),
        "hardware_execution": "none",
    }


def add_common_paths(parser: argparse.ArgumentParser) -> None:
    repo = Path(__file__).resolve().parents[1]
    parser.add_argument("--repo", type=Path, default=repo)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compact", type=Path,
                        help="MERGE_STATE h491 compact C graph")
    parser.add_argument("--incumbent", type=Path,
                        help="full current C model (never hardware)")
    parser.add_argument("--candidate", type=Path,
                        help="full G_R1382MERGES4=1 C model")
    parser.add_argument("--timeout-ms", type=int, default=60_000,
                        help="per-check solver bound; UNKNOWN is preserved")


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    separator = subparsers.add_parser("separator")
    add_common_paths(separator)
    separator.add_argument("--limit", type=int, default=1)
    separator.add_argument(
        "--fixed-template",
        default="3ffc d0d000000cc0b3f8",
        help=("partition the exact graph by this operand's complete "
              "materialization path; pass an empty string for the slower "
              "all-path encoding"),
    )

    collision = subparsers.add_parser("collision")
    add_common_paths(collision)
    collision.add_argument("--anchor", required=True)
    collision.add_argument(
        "--hidden-source",
        choices=("right_l2_high_carry", "right_cpa_carry_into_cut",
                 "rd3_kill_carry"),
        default="right_cpa_carry_into_cut",
    )

    preimages = subparsers.add_parser("preimages")
    repo = Path(__file__).resolve().parents[1]
    preimages.add_argument("--repo", type=Path, default=repo)
    preimages.add_argument("--output", type=Path, required=True)
    preimages.add_argument("--incumbent", type=Path,
                           help="full C model for reduced-state replay")

    reduction_collision = subparsers.add_parser("reduction-collision")
    reduction_collision.add_argument("--output", type=Path, required=True)
    reduction_collision.add_argument(
        "--anchor", default="3ffc d920000000749eaa",
        help="positive-residual unresolved state with an exact preimage",
    )
    reduction_collision.add_argument(
        "--incumbent", type=Path,
        help="full C model for reduction and exposed-pipeline replay",
    )

    crosscheck = subparsers.add_parser("crosscheck-separator")
    add_common_paths(crosscheck)
    crosscheck.add_argument("--query-output", type=Path, required=True)
    crosscheck.add_argument(
        "--fixed-template", default="3ffc d0d000000cc0b3f8",
        help="exact materialization-path template",
    )

    freeze = subparsers.add_parser("freeze")
    freeze.add_argument("--repo", type=Path, default=repo)
    freeze.add_argument("--source", type=Path, required=True)
    freeze.add_argument("--output", type=Path, required=True)
    freeze.add_argument("--private-ledger", action="append", type=Path,
                        default=[])

    args = parser.parse_args()
    for name in ("compact", "incumbent", "candidate"):
        path = getattr(args, name, None)
        if path is not None and not path.is_file():
            parser.error(f"--{name} is not a file: {path}")
    if args.command == "separator":
        report = solve_separator(args)
    elif args.command == "collision":
        report = solve_collision(args)
    elif args.command == "preimages":
        report = solve_preimages(args)
    elif args.command == "reduction-collision":
        report = solve_reduction_collision(args)
    elif args.command == "crosscheck-separator":
        report = solve_cvc5_separator_crosscheck(args)
    else:
        report = freeze_manifest(args)
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    write_json_new(args.output, report)
    print(json.dumps({
        "output": str(args.output),
        "result": report["result"] if "result" in report else {
            "sat": report["sat"], "unsat": report["unsat"]},
        "hardware_execution": "none",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
