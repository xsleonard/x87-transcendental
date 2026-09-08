#!/usr/bin/env python3
"""Solve the exact R1382 fixed path with its decisions hardwired.

H1410/H1463 retain generic normalization and round-selection circuitry even
after constraining every such decision to d0d0's materialization path.  This
formulation substitutes those proved path decisions directly, introduces a
named bit-vector for every intermediate, and keeps the exact discarded-bit
predicates which justify each fixed RN64 decision.  It is a decomposition of
the same integer operations, not an approximate polynomial.

The primary variable is the 67-bit chopped first square.  A SAT square is not
reported as an external witness until exact integer-square-root inversion and
the independent H1404 concrete replay both succeed.  No x87 instruction is
executed and no emulator default is changed.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import z3
except ImportError as error:  # pragma: no cover
    raise SystemExit("z3-solver 4.15.3.0 is required") from error


HERE = Path(__file__).resolve().parent
H1410_PATH = HERE / "h1410_width_reduced_r1382.py"
H1410_SPEC = importlib.util.spec_from_file_location("h1410_width", H1410_PATH)
if H1410_SPEC is None or H1410_SPEC.loader is None:  # pragma: no cover
    raise SystemExit(f"cannot load {H1410_PATH}")
h1410 = importlib.util.module_from_spec(H1410_SPEC)
sys.modules[H1410_SPEC.name] = h1410
H1410_SPEC.loader.exec_module(h1410)


TEMPLATE_SQUARE = 0x552954800A66EECBB
SIDE_BOUNDARY = 0xB504F333F9DE6800
RIGHT_LOW72 = 0x03AAAAAAAAAAAAAAAB
RIGHT_HIGH72 = 0x03AAAFFFFFFFFFFFFF
ENDPOINT_RESIDUES = (0x000, 0x100, 0x001, 0x101, 0x081, 0x180)


def bv(value: int, width: int) -> z3.BitVecNumRef:
    return z3.BitVecVal(value & ((1 << width) - 1), width)


def bit(value: z3.BitVecRef, position: int) -> z3.BitVecRef:
    return z3.Extract(position, position, value)


def unsigned_to(value: z3.BitVecRef, width: int) -> z3.BitVecRef:
    if value.size() < width:
        return z3.ZeroExt(width - value.size(), value)
    if value.size() > width:
        return z3.Extract(width - 1, 0, value)
    return value


def as_int(value: z3.ExprRef, model: z3.ModelRef) -> int:
    evaluated = model.eval(value, model_completion=True)
    if z3.is_bool(evaluated):
        return int(z3.is_true(evaluated))
    return evaluated.as_long()


@dataclass
class Graph:
    solver: z3.Solver
    square: z3.BitVecRef
    values: dict[str, z3.BitVecRef]


def named(
    solver: z3.Solver,
    values: dict[str, z3.BitVecRef],
    name: str,
    width: int,
    expression: z3.BitVecRef,
) -> z3.BitVecRef:
    value = z3.BitVec(f"h1468_{name}", width)
    solver.add(value == unsigned_to(expression, width))
    values[name] = value
    return value


def mul_chop67(
    solver: z3.Solver,
    values: dict[str, z3.BitVecRef],
    name: str,
    left: z3.BitVecRef,
    right: z3.BitVecRef,
    shift: int,
) -> z3.BitVecRef:
    width = left.size() + right.size()
    product = named(
        solver,
        values,
        f"{name}_product",
        width,
        unsigned_to(left, width) * unsigned_to(right, width),
    )
    output = named(
        solver,
        values,
        f"{name}_sig",
        67,
        z3.Extract(shift + 66, shift, product),
    )
    solver.add(bit(output, 66) == bv(1, 1))
    if shift + 67 < width:
        solver.add(z3.Extract(width - 1, shift + 67, product) == 0)
    return output


def add_rn64_fixed(
    solver: z3.Solver,
    values: dict[str, z3.BitVecRef],
    name: str,
    left_sig: int,
    left_e2: int,
    right: z3.BitVecRef,
    right_e2: int,
    raw_shift: int,
    expected_round: int,
) -> z3.BitVecRef:
    scale = min(left_e2, right_e2)
    left_shift = left_e2 - scale
    right_shift = right_e2 - scale
    width = max(
        max(67 + left_shift, right.size() + right_shift) + 1,
        raw_shift + 65,
    )
    magnitude = named(
        solver,
        values,
        f"{name}_magnitude",
        width,
        (bv(left_sig, width) << left_shift)
        + (unsigned_to(right, width) << right_shift),
    )
    top = z3.Extract(raw_shift + 64, raw_shift, magnitude)
    remainder = z3.Extract(raw_shift - 1, 0, magnitude)
    half = bv(1 << (raw_shift - 1), raw_shift)
    increment = z3.Or(
        z3.UGT(remainder, half),
        z3.And(remainder == half, bit(top, 0) == 1),
    )
    solver.add(
        bit(magnitude, raw_shift + 63) == 1,
        z3.Extract(width - 1, raw_shift + 64, magnitude) == 0,
        increment == bool(expected_round),
    )
    rounded = top + bv(expected_round, 65)
    solver.add(bit(rounded, 64) == 0)
    output = named(
        solver,
        values,
        f"{name}_sig",
        64,
        z3.Extract(63, 0, rounded),
    )
    solver.add(bit(output, 63) == 1)
    return output


def chain(
    solver: z3.Solver,
    values: dict[str, z3.BitVecRef],
    name: str,
    fourth: z3.BitVecRef,
    lead: tuple[int, int, int],
    middle: tuple[int, int, int],
    last: tuple[int, int, int],
    mul1_shift: int,
    add1_shift: int,
    add1_round: int,
    mul2_shift: int,
    add2_shift: int,
    add2_round: int,
) -> z3.BitVecRef:
    first = mul_chop67(
        solver, values, f"{name}_mul1", fourth, bv(lead[2], 67),
        mul1_shift,
    )
    first_e2 = -76 + lead[1] + mul1_shift
    added = add_rn64_fixed(
        solver, values, f"{name}_add1", middle[2], middle[1], first,
        first_e2, add1_shift, add1_round,
    )
    added_e2 = min(middle[1], first_e2) + add1_shift
    second = mul_chop67(
        solver, values, f"{name}_mul2", fourth, added, mul2_shift,
    )
    second_e2 = -76 + added_e2 + mul2_shift
    return add_rn64_fixed(
        solver, values, f"{name}_add2", last[2], last[1], second,
        second_e2, add2_shift, add2_round,
    )


def build_graph() -> Graph:
    solver = z3.SolverFor("QF_BV")
    values: dict[str, z3.BitVecRef] = {}
    square = z3.BitVec("h1468_square_sig", 67)
    values["square_sig"] = square
    solver.add(bit(square, 66) == 1, z3.Extract(2, 0, square) == 3)

    fourth = mul_chop67(solver, values, "fourth", square, square, 66)
    negative = chain(
        solver, values, "negative", fourth,
        h1410.h1404.C6_5, h1410.h1404.C6_3, h1410.h1404.C6_1,
        67, 24, 1, 64, 21, 0,
    )
    positive = chain(
        solver, values, "positive", fourth,
        h1410.h1404.C6_6, h1410.h1404.C6_4, h1410.h1404.C6_2,
        66, 26, 1, 64, 23, 0,
    )
    left = mul_chop67(solver, values, "left", square, negative, 63)
    right = mul_chop67(solver, values, "right", fourth, positive, 64)

    left_product = values["left_product"]
    upper3 = z3.Extract(60, 58, left_product)
    solver.add(upper3 != 0)

    right_product = values["right_product"]
    right_low72 = z3.Extract(71, 0, right_product)
    solver.add(
        z3.UGE(right_low72, bv(RIGHT_LOW72, 72)),
        z3.ULE(right_low72, bv(RIGHT_HIGH72, 72)),
    )

    square_product = values["fourth_product"]
    sqlow = named(
        solver, values, "sqlow", 67, square - bv(1 << 66, 67)
    )
    t4 = named(
        solver, values, "t4", 66, z3.Extract(65, 0, square_product)
    )
    mreg = named(
        solver,
        values,
        "Mreg",
        72,
        bv(3, 72) * unsigned_to(sqlow, 72) - unsigned_to(t4, 72),
    )
    solver.add(z3.Extract(71, 66, mreg) == 0)

    source = named(
        solver,
        values,
        "S",
        76,
        (unsigned_to(left, 76) << 8) + bv(3, 76),
    )
    subtrahend = named(solver, values, "B", 76, unsigned_to(right, 76))
    umag = named(solver, values, "umag", 76, source - subtrahend)
    solver.add(
        z3.UGT(source, subtrahend),
        bit(umag, 74) == 1,
        bit(umag, 75) == 0,
        z3.Extract(7, 0, umag) == 0,
    )

    reduced_base = left - z3.LShR(right, 8)
    base_low9 = named(
        solver, values, "base_low9", 9, z3.Extract(8, 0, reduced_base)
    )
    solver.add(z3.Or(*(base_low9 == item for item in ENDPOINT_RESIDUES)))
    return Graph(solver, square, values)


def exact_external_preimage(square_sig: int) -> int | None:
    lower_square = square_sig << 61
    upper_square = ((square_sig + 1) << 61) - 1
    lower = math.isqrt(lower_square)
    if lower * lower < lower_square:
        lower += 1
    upper = math.isqrt(upper_square)
    if lower != upper or not (1 << 63) <= lower < (1 << 64):
        return None
    if lower < SIDE_BOUNDARY or (lower * lower) >> 61 != square_sig:
        return None
    return lower


def verify_known(graph: Graph) -> dict[str, str]:
    graph.solver.push()
    graph.solver.add(graph.square == TEMPLATE_SQUARE)
    result = graph.solver.check()
    if result != z3.sat:
        raise AssertionError(f"known d0d0 square is {result}")
    model = graph.solver.model()
    concrete = h1410.h1404.concrete_forward(h1410.TEMPLATE_SIG)
    mapping = {
        "square_sig": "square_sig",
        "fourth_sig": "fourth_sig",
        "negative_add2_sig": "negative_sig",
        "positive_add2_sig": "positive_sig",
        "left_sig": "left_sig",
        "right_sig": "right_sig",
        "S": "S",
        "B": "B",
        "umag": "umag",
        "t4": "t4",
        "sqlow": "sqlow",
        "Mreg": "Mreg",
    }
    mismatches = {
        symbolic: [as_int(graph.values[symbolic], model), concrete[target]]
        for symbolic, target in mapping.items()
        if as_int(graph.values[symbolic], model) != concrete[target]
    }
    graph.solver.pop()
    if mismatches:
        raise AssertionError(f"hardwired/independent mismatch: {mismatches}")
    return {"result": "SAT", "independent_replay": "exact"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout-ms", type=int, default=300_000)
    parser.add_argument("--prefix-bits", type=int, default=0)
    parser.add_argument("--prefix", type=lambda value: int(value, 0))
    parser.add_argument("--low-bits", type=int, default=0)
    parser.add_argument("--low", type=lambda value: int(value, 0))
    parser.add_argument("--max-models", type=int, default=64)
    args = parser.parse_args()
    if not 0 <= args.prefix_bits <= 67:
        raise SystemExit("--prefix-bits must be in 0..67")
    if bool(args.prefix_bits) != (args.prefix is not None):
        raise SystemExit("--prefix-bits and --prefix must be supplied together")
    if args.prefix is not None and not 0 <= args.prefix < (1 << args.prefix_bits):
        raise SystemExit("--prefix does not fit --prefix-bits")
    if not 0 <= args.low_bits <= 67:
        raise SystemExit("--low-bits must be in 0..67")
    if bool(args.low_bits) != (args.low is not None):
        raise SystemExit("--low-bits and --low must be supplied together")
    if args.low is not None and not 0 <= args.low < (1 << args.low_bits):
        raise SystemExit("--low does not fit --low-bits")

    graph = build_graph()
    known = verify_known(graph)
    graph.solver.set(timeout=args.timeout_ms)
    graph.solver.add(graph.square != TEMPLATE_SQUARE)
    if args.prefix_bits:
        high = 66
        low = 67 - args.prefix_bits
        graph.solver.add(
            z3.Extract(high, low, graph.square) == bv(args.prefix, args.prefix_bits)
        )
    if args.low_bits:
        graph.solver.add(
            z3.Extract(args.low_bits - 1, 0, graph.square)
            == bv(args.low, args.low_bits)
        )

    rejected: list[dict[str, Any]] = []
    status = "UNKNOWN"
    reason = ""
    witness: dict[str, Any] | None = None
    for _ in range(args.max_models):
        result = graph.solver.check()
        if result == z3.unknown:
            reason = graph.solver.reason_unknown()
            break
        if result == z3.unsat:
            status = "UNSAT_SQUARE_SUPERSET"
            break
        model = graph.solver.model()
        square_sig = as_int(graph.square, model)
        external = exact_external_preimage(square_sig)
        if external is None:
            rejected.append({
                "square_sig": f"{square_sig:017x}",
                "reason": "no_exact_external_first_square_preimage",
            })
            graph.solver.add(graph.square != square_sig)
            continue
        concrete = h1410.h1404.concrete_forward(external)
        if concrete["square_sig"] != square_sig:
            raise AssertionError("external replay changed chopped square")
        if not (
            concrete["current_rd"] != concrete["candidate_rd"]
            or concrete["current_rn"] != concrete["candidate_rn"]
            or concrete["current_ru"] != concrete["candidate_ru"]
            or concrete["current_rz"] != concrete["candidate_rz"]
        ):
            rejected.append({
                "square_sig": f"{square_sig:017x}",
                "operand": h1410.h1404.operand_text(0x3FFC, external),
                "reason": "exact_tree_replay_not_endpoint_visible",
                "actual_merge_gate": int(concrete["merge_gate"]),
            })
            graph.solver.add(graph.square != square_sig)
            continue
        witness = {
            "operand": h1410.h1404.operand_text(0x3FFC, external),
            "square_sig": f"{square_sig:017x}",
            "changed_modes": [
                mode for mode in h1410.MODES
                if concrete[f"current_{mode}"] != concrete[f"candidate_{mode}"]
            ],
        }
        status = "SAT_EXTERNAL_WITNESS"
        break
    else:
        status = "MODEL_LIMIT_WITHOUT_EXTERNAL_PREIMAGE"

    print(json.dumps({
        "status": status,
        "reason": reason,
        "known": known,
        "prefix_bits": args.prefix_bits,
        "prefix": args.prefix,
        "low_bits": args.low_bits,
        "low": args.low,
        "rejected_square_models": rejected,
        "external_witness": witness,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
