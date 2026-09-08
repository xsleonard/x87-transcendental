#!/usr/bin/env python3
"""Width-minimal exact QF_BV check for a second R1382 witness.

This is an analysis-only reformulation of the fixed-path query in
``h1404_exact_preimage_smt.py``.  Unlike that deliberately uniform 136-bit
graph, each multiplication and addition here has its mathematically required
width.  No input bits or carries are discarded: multiplication results use
the sum of the operand widths and addition results reserve a carry bit.

The query fixes the complete materialization path of the known d0d0 witness,
relaxes only the R1272 tree gate to its enabling value, and excludes d0d0.
Consequently UNSAT proves the physical fixed-path subset; SAT still has to
pass the independent Python and exact-tree replays in h1404 before it is
reported as a witness.  This program never executes x87 hardware and never
changes emulator defaults.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import z3
except ImportError as error:  # pragma: no cover
    raise SystemExit("z3-solver 4.15.3.0 is required") from error


HERE = Path(__file__).resolve().parent
H1404_PATH = HERE / "h1404_exact_preimage_smt.py"
H1404_SPEC = importlib.util.spec_from_file_location("h1404_exact", H1404_PATH)
if H1404_SPEC is None or H1404_SPEC.loader is None:  # pragma: no cover
    raise SystemExit(f"cannot load {H1404_PATH}")
h1404 = importlib.util.module_from_spec(H1404_SPEC)
sys.modules[H1404_SPEC.name] = h1404
H1404_SPEC.loader.exec_module(h1404)


TEMPLATE = "3ffc d0d000000cc0b3f8"
TEMPLATE_SIG = 0xD0D000000CC0B3F8
MODES = ("rn", "rd", "ru", "rz")


def bv(value: int, width: int) -> z3.BitVecNumRef:
    return z3.BitVecVal(value & ((1 << width) - 1), width)


def bit(value: z3.BitVecRef, position: int) -> z3.BitVecRef:
    return z3.Extract(position, position, value)


def unsigned_to(value: z3.BitVecRef, width: int) -> z3.BitVecRef:
    if value.size() > width:
        return z3.Extract(width - 1, 0, value)
    if value.size() < width:
        return z3.ZeroExt(width - value.size(), value)
    return value


def as_int(value: z3.ExprRef, model: z3.ModelRef) -> int:
    evaluated = model.eval(value, model_completion=True)
    if z3.is_bool(evaluated):
        return int(z3.is_true(evaluated))
    return evaluated.as_long()


@dataclass(frozen=True)
class BFP:
    sign: int
    e2: int
    sig: z3.BitVecRef
    bits: int


@dataclass
class NarrowGraph:
    solver: z3.Solver
    primary: z3.BitVecRef
    primary_kind: str
    values: dict[str, z3.ExprRef | int]
    template: dict[str, int]


def constant(value: tuple[int, int, int]) -> BFP:
    return BFP(value[0], value[1], bv(value[2], 67), 67)


def mul_chop67(
    left: BFP,
    right: BFP,
    shift: int,
    constraints: list[z3.BoolRef],
    values: dict[str, z3.ExprRef | int],
    name: str,
) -> tuple[BFP, z3.BitVecRef]:
    width = left.bits + right.bits
    product = unsigned_to(left.sig, width) * unsigned_to(right.sig, width)
    output = z3.Extract(shift + 66, shift, product)
    constraints.extend((
        bit(output, 66) == 1,
        z3.Extract(width - 1, shift + 67, product) == 0
        if shift + 67 < width else z3.BoolVal(True),
    ))
    values[f"{name}_product"] = product
    values[f"{name}_shift"] = shift
    values[f"{name}_sig"] = output
    values[f"{name}_e2"] = left.e2 + right.e2 + shift
    return BFP(left.sign ^ right.sign, left.e2 + right.e2 + shift,
               output, 67), product


def add_rn64(
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
        raise ValueError("fixed path requires same-sign Horner additions")
    scale = min(left.e2, right.e2)
    left_shift = left.e2 - scale
    right_shift = right.e2 - scale
    width = max(max(left.bits + left_shift, right.bits + right_shift) + 1,
                raw_shift + 65)
    magnitude = (unsigned_to(left.sig, width) << left_shift) \
        + (unsigned_to(right.sig, width) << right_shift)
    top = z3.Extract(raw_shift + 64, raw_shift, magnitude)
    remainder = z3.Extract(raw_shift - 1, 0, magnitude)
    half = bv(1 << (raw_shift - 1), raw_shift)
    increment = z3.Or(z3.UGT(remainder, half),
                      z3.And(remainder == half, bit(top, 0) == 1))
    rounded = top + z3.If(increment, bv(1, 65), bv(0, 65))
    overflow = bit(rounded, 64) == 1
    output = z3.If(overflow, z3.Extract(64, 1, rounded),
                   z3.Extract(63, 0, rounded))
    constraints.extend((
        bit(magnitude, raw_shift + 63) == 1,
        z3.Extract(width - 1, raw_shift + 64, magnitude) == 0
        if raw_shift + 64 < width else z3.BoolVal(True),
        increment == z3.BoolVal(bool(expected_round)),
        overflow == z3.BoolVal(bool(expected_overflow)),
        bit(output, 63) == 1,
    ))
    values[f"{name}_magnitude"] = magnitude
    values[f"{name}_shift"] = raw_shift
    values[f"{name}_round"] = increment
    values[f"{name}_overflow"] = overflow
    values[f"{name}_sig"] = output
    values[f"{name}_e2"] = scale + raw_shift + expected_overflow
    return BFP(left.sign, scale + raw_shift + expected_overflow, output, 64)


def chain(
    fourth: BFP,
    lead: tuple[int, int, int],
    middle: tuple[int, int, int],
    last: tuple[int, int, int],
    template: dict[str, int],
    constraints: list[z3.BoolRef],
    values: dict[str, z3.ExprRef | int],
    name: str,
) -> BFP:
    first, _ = mul_chop67(
        fourth, constant(lead), template[f"{name}_mul1_shift"],
        constraints, values, f"{name}_mul1")
    added = add_rn64(
        constant(middle), first, template[f"{name}_add1_shift"],
        template[f"{name}_add1_round"], template[f"{name}_add1_overflow"],
        constraints, values, f"{name}_add1")
    second, _ = mul_chop67(
        fourth, added, template[f"{name}_mul2_shift"], constraints,
        values, f"{name}_mul2")
    return add_rn64(
        constant(last), second, template[f"{name}_add2_shift"],
        template[f"{name}_add2_round"], template[f"{name}_add2_overflow"],
        constraints, values, f"{name}_add2")


def final_result(retained: z3.BitVecRef, correction_exponent: int,
                 mode: str) -> z3.BitVecRef:
    width = max(retained.size(), -correction_exponent + 1)
    numerator = bv(1 << -correction_exponent, width) \
        - unsigned_to(retained, width)
    shift = -correction_exponent - 64
    kept = z3.LShR(numerator, shift)
    remainder = z3.Extract(shift - 1, 0, numerator)
    half = bv(1 << (shift - 1), shift)
    if mode == "rn":
        upward = z3.Or(z3.UGT(remainder, half),
                       z3.And(remainder == half, bit(kept, 0) == 1))
    elif mode == "ru":
        upward = remainder != 0
    else:
        upward = z3.BoolVal(False)
    rounded = kept + z3.If(upward, bv(1, width), bv(0, width))
    normalized = z3.If(bit(rounded, 64) == 1,
                       z3.LShR(rounded, 1), rounded)
    return z3.Extract(63, 0, normalized)


def u0_for(first: z3.BitVecRef, second: z3.BitVecRef,
           template: dict[str, int]) -> z3.BitVecRef:
    table: dict[tuple[int, int], int] = {}
    low = template["low3"]
    distance = template["dist"]
    s4 = template["s4"]
    side = template["side"]
    for b1 in (0, 1):
        for b2 in (0, 1):
            if s4 == 66 and side == 1:
                base = 2 * low + 2 * b1 + b2 - 5 * (distance - 7)
                value = base // 4
            elif s4 == 66:
                base = 4 * low + b1 - 9 - 5 * (distance - 9)
                value = base // 2
            elif side == 0:
                base = 4 * low + 2 * b1 + b2 - 2 * (low & 1) \
                    - 5 * (distance - 7)
                value = 2 * (base // 4) + (low & 1)
            else:
                base = 2 * low + 2 * b1 + 3 * b2 - 3 * (low & 1) \
                    - 4 - 2 * (distance - 7)
                value = 2 * (base // 8) + (low & 1)
            table[b1, b2] = value
    result = bv(table[0, 0], 72)
    for b1 in (0, 1):
        for b2 in (0, 1):
            result = z3.If(z3.And(first == b1, second == b2),
                           bv(table[b1, b2], 72), result)
    return result


def endpoint_residue(base_retained: z3.BitVecRef) -> z3.BoolRef:
    """Exact visibility of base-1 versus base for ce=-72.

    RD/RZ expose the transition at retained residue 1, RU at residue 0,
    and RN at the two half-way residues with the appropriate even tie bit.
    The fixed path proves 2^66 <= base < 2^67, so normalization cannot add
    another case.
    """

    width = base_retained.size()
    numerator = bv(1 << 72, width) - base_retained
    low = z3.Extract(7, 0, base_retained)
    quotient_odd = bit(numerator, 8) == 1
    return z3.Or(
        low == 0,
        low == 1,
        z3.And(low == 129, quotient_odd),
        z3.And(low == 128, z3.Not(quotient_odd)),
    )


def build_graph(prefix: str = "h1410",
                primary_kind: str = "external") -> NarrowGraph:
    template = h1404.concrete_forward(TEMPLATE_SIG)
    solver = z3.SolverFor("QF_BV")
    solver.set(unsat_core=True)
    if primary_kind == "external":
        primary = z3.BitVec(f"{prefix}_sig", 64)
        values: dict[str, z3.ExprRef | int] = {
            "m": primary, "se": 0x3FFC}
        constraints: list[z3.BoolRef] = [bit(primary, 63) == 1]
        magnitude = BFP(0, -66, primary, 64)
        square, square_product = mul_chop67(
            magnitude, magnitude, template["square_shift"], constraints,
            values, "square")
        side_value: z3.ExprRef = z3.UGE(
            primary, bv(0xB504F333F9DE6800, 64))
    elif primary_kind == "square":
        # A sound superset decomposition: solve the deterministic downstream
        # graph first, then synthesize an exact 64-bit preimage separately.
        # On this binade floor(m*m/2^61) is injective because adjacent squares
        # differ by more than 2^61.
        primary = z3.BitVec(f"{prefix}_square_sig", 67)
        values = {"square_sig": primary}
        constraints = [bit(primary, 66) == 1]
        square = BFP(0, -71, primary, 67)
        square_product = bv(0, 128)  # not consumed downstream
        side_value = z3.BoolVal(True)
    else:  # pragma: no cover - CLI validates this
        raise ValueError(primary_kind)
    fourth, fourth_product = mul_chop67(
        square, square, template["fourth_shift"], constraints,
        values, "fourth")
    negative = chain(
        fourth, h1404.C6_5, h1404.C6_3, h1404.C6_1, template,
        constraints, values, "negative")
    positive = chain(
        fourth, h1404.C6_6, h1404.C6_4, h1404.C6_2, template,
        constraints, values, "positive")
    left, left_product = mul_chop67(
        square, negative, template["left_shift"], constraints,
        values, "left")
    right, right_product = mul_chop67(
        fourth, positive, template["right_shift"], constraints,
        values, "right")

    left_shift = template["left_shift"]
    right_shift = template["right_shift"]
    left_discard = z3.Extract(left_shift - 1, 0, left_product)
    upper5 = z3.Extract(left_shift - 1, left_shift - 5, left_product)
    upper3 = z3.Extract(4, 2, upper5)
    low3 = z3.Extract(2, 0, square.sig)
    distance = abs(left.e2 - right.e2)
    active = z3.And(low3 != 0,
                    z3.Or(upper3 != 0,
                          z3.And(distance == 7, upper5 != 0)))
    payload_width = 4
    payload = unsigned_to(low3, payload_width) + bv(8 - distance,
                                                        payload_width)
    right_discard = z3.Extract(right_shift - 1, 0, right_product)

    scale = min(left.e2, right.e2,
                left.e2 - 8 if template["payload"] else left.e2)
    dl, dr = left.e2 - scale, right.e2 - scale
    dp = left.e2 - 8 - scale
    terminal_width = max(left.bits + dl, right.bits + dr,
                         payload_width + dp) + 1
    source = (unsigned_to(left.sig, terminal_width) << dl) \
        + (z3.If(payload != 0,
                 unsigned_to(payload, terminal_width) << dp,
                 bv(0, terminal_width)))
    subtrahend = unsigned_to(right.sig, terminal_width) << dr
    umag = source - subtrahend
    k = template["k"]
    discard = z3.Extract(k - 1, 0, umag)

    s4 = template["s4"]
    t4 = z3.Extract(s4 - 1, 0, fourth_product)
    sqlow = square.sig - bv(1 << 66, 67)
    mreg_width = 72
    mreg = unsigned_to(payload, mreg_width) \
        * unsigned_to(sqlow, mreg_width) - unsigned_to(t4, mreg_width)

    # R1272 gate deliberately relaxed to its enabling value, just as h1409.
    merge_gate = z3.BoolVal(True)
    rd_width = right_shift + 2
    rd = unsigned_to(right_discard, rd_width)
    triple = bv(3, rd_width) * rd
    merge_mask = bv((1 << (right_shift - 16
                           - int(not bool(template["side"])))) - 1, rd_width)
    rd3_merge = triple - (triple & merge_mask)
    rd3_plain = triple - ((bv(2, rd_width) * rd) & merge_mask) \
        - (rd & merge_mask)
    threshold1 = bv(1 << right_shift, rd_width)
    threshold2 = bv(1 << (right_shift + 1), rd_width)

    def comparator(rd3: z3.BitVecRef) -> tuple[z3.BitVecRef, z3.BitVecRef]:
        return (z3.If(z3.UGE(rd3, threshold1), bv(1, 1), bv(0, 1)),
                z3.If(z3.UGE(rd3, threshold2), bv(1, 1), bv(0, 1)))

    current_b1, current_b2 = comparator(rd3_merge)
    candidate_b1, candidate_b2 = comparator(rd3_plain)
    current_u0 = u0_for(current_b1, current_b2, template)
    candidate_u0 = u0_for(candidate_b1, candidate_b2, template)
    current_fire = mreg < (current_u0 << 66)
    candidate_fire = mreg < (candidate_u0 << 66)
    retained_width = terminal_width
    base_retained = z3.LShR(umag, k)
    current_retained = base_retained \
        - z3.If(current_fire, bv(1, retained_width), bv(0, retained_width))
    candidate_retained = base_retained \
        - z3.If(candidate_fire, bv(1, retained_width), bv(0, retained_width))

    values.update({
        "square_sig": square.sig,
        "fourth_sig": fourth.sig,
        "negative_sig": negative.sig,
        "positive_sig": positive.sig,
        "left_sig": left.sig,
        "right_sig": right.sig,
        "active": active,
        "low3": low3,
        "dist": distance,
        "payload": payload,
        "S": source,
        "B": subtrahend,
        "umag": umag,
        "k": k,
        "disc": discard,
        "ce": scale + k,
        "s4": s4,
        "side": side_value,
        "t4": t4,
        "sqlow": sqlow,
        "Mreg": mreg,
        "merge_gate": merge_gate,
        "current_rd3": rd3_merge,
        "candidate_rd3": rd3_plain,
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
    })
    for mode in MODES:
        values[f"current_{mode}"] = final_result(
            current_retained, scale + k, mode)
        values[f"candidate_{mode}"] = final_result(
            candidate_retained, scale + k, mode)

    constraints.extend((
        z3.UGT(source, subtrahend),
        bit(umag, k + 66) == 1,
        z3.Extract(terminal_width - 1, k + 67, umag) == 0,
        low3 == template["low3"],
        payload == template["payload"],
        values["side"] == z3.BoolVal(bool(template["side"])),
    ))
    solver.assert_and_track(z3.And(*constraints),
                            f"{prefix}.exact_materialization_path")
    # This exact, locally proved endpoint form is much smaller than four
    # duplicated architectural rounding expressions.  prove_endpoint_lemma
    # checks its equivalence independently before the main query is run.
    endpoint = z3.And(
        active,
        discard == 0,
        current_b1 == 1,
        current_b2 == 1,
        candidate_b1 == 1,
        candidate_b2 == 0,
        mreg >= bv(0, mreg_width),
        mreg < bv(1 << 66, mreg_width),
        endpoint_residue(base_retained),
    )
    solver.assert_and_track(endpoint, f"{prefix}.endpoint_visible")
    return NarrowGraph(solver, primary, primary_kind, values, template)


def prove_endpoint_lemma() -> dict[str, Any]:
    """Exhaustively prove the local endpoint reduction in QF_BV."""

    template = h1404.concrete_forward(TEMPLATE_SIG)
    right_discard = z3.BitVec("lemma_right_discard", 64)
    mreg = z3.BitVec("lemma_mreg", 72)
    base = z3.BitVec("lemma_base_retained", 76)
    rd = z3.ZeroExt(2, right_discard)
    triple = bv(3, 66) * rd
    mask = bv((1 << 48) - 1, 66)
    merged = triple - (triple & mask)
    plain = triple - ((bv(2, 66) * rd) & mask) - (rd & mask)
    threshold1 = bv(1 << 64, 66)
    threshold2 = bv(1 << 65, 66)

    def comparator(word: z3.BitVecRef) -> tuple[z3.BitVecRef, z3.BitVecRef]:
        return (z3.If(z3.UGE(word, threshold1), bv(1, 1), bv(0, 1)),
                z3.If(z3.UGE(word, threshold2), bv(1, 1), bv(0, 1)))

    current_b1, current_b2 = comparator(merged)
    candidate_b1, candidate_b2 = comparator(plain)
    current_u0 = u0_for(current_b1, current_b2, template)
    candidate_u0 = u0_for(candidate_b1, candidate_b2, template)
    current_fire = mreg < (current_u0 << 66)
    candidate_fire = mreg < (candidate_u0 << 66)
    current = base - z3.If(current_fire, bv(1, 76), bv(0, 76))
    candidate = base - z3.If(candidate_fire, bv(1, 76), bv(0, 76))
    original = z3.And(
        current != candidate,
        z3.Or(*(final_result(current, -72, mode)
                != final_result(candidate, -72, mode) for mode in MODES)),
    )
    reduced = z3.And(
        current_b1 == 1, current_b2 == 1,
        candidate_b1 == 1, candidate_b2 == 0,
        mreg >= bv(0, 72), mreg < bv(1 << 66, 72),
        endpoint_residue(base),
    )
    solver = z3.SolverFor("QF_BV")
    solver.add(z3.UGE(base, bv(1 << 66, 76)),
               z3.ULT(base, bv(1 << 67, 76)),
               original != reduced)
    result = solver.check()
    if result != z3.unsat:
        raise AssertionError(f"endpoint reduction lemma failed: {result}")
    return {
        "result": "UNSAT",
        "meaning": (
            "no counterexample to equivalence between four-mode endpoint "
            "visibility and the reduced comparator/Mreg/residue predicate"
        ),
    }


def verify_values(graph: NarrowGraph, model: z3.ModelRef,
                  concrete: dict[str, Any]) -> None:
    names = (
        "square_sig", "fourth_sig", "negative_sig", "positive_sig",
        "left_sig", "right_sig", "active", "low3", "dist", "payload",
        "S", "B", "umag", "k", "disc", "ce", "s4", "side", "t4",
        "sqlow", "Mreg", "current_rd3", "candidate_rd3", "b1", "b2",
        "candidate_b1", "candidate_b2", "current_u0", "candidate_u0",
        "current_fire", "candidate_fire", "current_retained",
        "candidate_retained", *(f"current_{mode}" for mode in MODES),
        *(f"candidate_{mode}" for mode in MODES),
    )
    mismatches: dict[str, tuple[int, int]] = {}
    for name in names:
        got = graph.values[name]
        symbolic = got if isinstance(got, int) else as_int(got, model)
        if symbolic != concrete[name]:
            mismatches[name] = (symbolic, concrete[name])
    if mismatches:
        raise AssertionError(f"narrow/Python mismatch: {mismatches}")


def concrete_replay(graph: NarrowGraph, model: z3.ModelRef) -> dict[str, Any]:
    if graph.primary_kind != "external":
        raise ValueError("external replay requested for reduced graph")
    sig = as_int(graph.primary, model)
    concrete = h1404.concrete_forward(sig)
    verify_values(graph, model, concrete)
    return concrete


def synthesize_square_preimage(square_sig: int,
                               timeout_ms: int) -> tuple[str, int | None, str]:
    """Solve the exact first-square preimage; never scan candidate inputs."""

    solver = z3.SolverFor("QF_BV")
    solver.set(timeout=timeout_ms)
    m = z3.BitVec("h1410_preimage_sig", 64)
    wide = z3.ZeroExt(64, m)
    product = wide * wide
    solver.add(bit(m, 63) == 1,
               z3.Extract(127, 61, product) == bv(square_sig, 67))
    result = solver.check()
    if result == z3.sat:
        return "SAT", as_int(m, solver.model()), ""
    if result == z3.unsat:
        return "UNSAT", None, ""
    return "UNKNOWN", None, solver.reason_unknown()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_new(path: Path, content: bytes) -> None:
    if path.exists():
        raise SystemExit(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as target:
        target.write(content)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--query-output", required=True, type=Path)
    parser.add_argument("--timeout-ms", type=int, default=300_000)
    parser.add_argument("--primary", choices=("external", "square"),
                        default="external")
    parser.add_argument("--compact", type=Path)
    parser.add_argument("--incumbent", type=Path)
    parser.add_argument("--candidate", type=Path)
    args = parser.parse_args()

    endpoint_lemma = prove_endpoint_lemma()
    graph = build_graph(primary_kind=args.primary)
    graph.solver.set(timeout=args.timeout_ms)

    graph.solver.push()
    template_concrete = h1404.concrete_forward(TEMPLATE_SIG)
    template_primary = (TEMPLATE_SIG if args.primary == "external"
                        else template_concrete["square_sig"])
    graph.solver.add(graph.primary == bv(
        template_primary, graph.primary.size()))
    known_result = graph.solver.check()
    if known_result != z3.sat:
        raise AssertionError(f"known d0d0 witness is {known_result}")
    if args.primary == "external":
        known_concrete = concrete_replay(graph, graph.solver.model())
    else:
        known_concrete = template_concrete
        verify_values(graph, graph.solver.model(), known_concrete)
    graph.solver.pop()

    graph.solver.add(graph.primary != bv(
        template_primary, graph.primary.size()))
    query = graph.solver.to_smt2().encode()
    write_new(args.query_output, query)
    result = graph.solver.check()
    report: dict[str, Any] = {
        "query": ("r1382_endpoint_visible_second_witness_width_minimal_"
                  + args.primary),
        "solver": f"z3 {z3.get_version_string()}",
        "timeout_ms": args.timeout_ms,
        "result": str(result).upper(),
        "query_artifact": str(args.query_output),
        "query_bytes": len(query),
        "query_sha256": sha256_bytes(query),
        "known_witness": h1404.operand_text(0x3FFC, known_concrete["m"]),
        "known_python_replay": "exact",
        "endpoint_reduction_lemma": endpoint_lemma,
        "primary": args.primary,
        "scope": (
            "all positive normal 3ffc inputs in d0d0's exact complete "
            "materialization path, excluding d0d0; R1272 gate relaxed to "
            "the enabling value"
        ),
        "soundness": (
            "operation-specific widths retain every mathematical product "
            "and add carry; UNSAT proves the physical fixed-path subset"
        ),
        "hardware_execution": "none",
    }
    if result == z3.unknown:
        report["reason"] = graph.solver.reason_unknown()
    elif result == z3.unsat:
        report["unsat_core"] = sorted(
            str(item) for item in graph.solver.unsat_core())
    else:
        model = graph.solver.model()
        if args.primary == "external":
            concrete = concrete_replay(graph, model)
            sig = concrete["m"]
        else:
            square_sig = as_int(graph.primary, model)
            preimage_result, sig, preimage_reason = synthesize_square_preimage(
                square_sig, args.timeout_ms)
            report["reduced_square_sig"] = f"{square_sig:017x}"
            report["external_preimage_result"] = preimage_result
            if preimage_reason:
                report["external_preimage_reason"] = preimage_reason
            if sig is None:
                report["result"] = "SAT_REDUCED_" + preimage_result
                write_new(args.output,
                          (json.dumps(report, indent=2, sort_keys=True)
                           + "\n").encode())
                print(json.dumps({"output": str(args.output),
                                  "result": report["result"]},
                                 sort_keys=True))
                return
            concrete = h1404.concrete_forward(sig)
            verify_values(graph, model, concrete)
        exact_tree = h1404.build_fixed_path_graph(
            TEMPLATE_SIG, "h1410_exact_tree", derive_tree=True)
        exact_tree.solver.add(exact_tree.m == bv(sig, 64))
        tree_result = exact_tree.solver.check()
        if tree_result != z3.sat:
            report.update({
                "result": "SAT_RELAXED_SPURIOUS",
                "operand": h1404.operand_text(0x3FFC, sig),
                "exact_tree_replay": str(tree_result).upper(),
            })
        else:
            h1404.verify_fixed_witness(exact_tree, exact_tree.solver.model())
            replay = h1404.replay_c_witness(
                h1404.operand_text(0x3FFC, sig), concrete,
                args.compact, args.incumbent, args.candidate)
            report.update({
                "result": "SAT",
                "operand": h1404.operand_text(0x3FFC, sig),
                "python_replay": "exact",
                "exact_tree_replay": "exact",
                "c_replay": replay,
            })

    write_new(args.output, (json.dumps(report, indent=2, sort_keys=True)
                            + "\n").encode())
    print(json.dumps({"output": str(args.output), "result": report["result"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
