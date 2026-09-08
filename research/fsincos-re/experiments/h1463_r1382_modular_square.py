#!/usr/bin/env python3
"""Factor the exact R1382 second-witness query at the square boundary.

H1410 retains general comparator and four-mode endpoint circuitry even though
three local equivalences are independent of the polynomial graph.  This
analysis proves those equivalences in QF_BV and substitutes their much smaller
forms:

* the current/plain 3x comparator split is one interval of the 64 discarded
  right-product bits;
* the signed 72-bit Mreg range is six zero high bits; and
* endpoint visibility is a six-member residue set modulo 512.

The remaining arithmetic is exactly H1410's operation-specific-width graph.
The primary variable is its 67-bit chopped square.  Every SAT square is tested
for an exact external 64-bit preimage by integer square-root bounds, which is
complete because the first-square map is injective on the normalized binade.
No x87 instruction is executed and no emulator default is changed.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
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


COMPARATOR_LOW = 0xAAAAAAAAAAAAAAAB
COMPARATOR_HIGH = 0xAAAAFFFFFFFFFFFF
RIGHT_PRODUCT_LOW72 = (3 << 64) | COMPARATOR_LOW
RIGHT_PRODUCT_HIGH72 = (3 << 64) | COMPARATOR_HIGH
ENDPOINT_RESIDUES = (0x000, 0x100, 0x001, 0x101, 0x081, 0x180)
SIDE_BOUNDARY = 0xB504F333F9DE6800


def bv(value: int, width: int) -> z3.BitVecNumRef:
    return z3.BitVecVal(value & ((1 << width) - 1), width)


def as_int(value: z3.ExprRef, model: z3.ModelRef) -> int:
    evaluated = model.eval(value, model_completion=True)
    if z3.is_bool(evaluated):
        return int(z3.is_true(evaluated))
    return evaluated.as_long()


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def standalone_query(solver: z3.Solver) -> bytes:
    """Serialize with the exact QF_BV logic made explicit for other solvers."""

    body = solver.to_smt2()
    if "(set-logic " not in body:
        body = "(set-logic QF_BV)\n" + body
    return body.encode()


def write_new(path: Path, content: bytes) -> None:
    if path.exists():
        raise SystemExit(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as target:
        target.write(content)


def prove_comparator_interval() -> dict[str, str]:
    rd64 = z3.BitVec("h1463_lemma_rd64", 64)
    rd = z3.ZeroExt(2, rd64)
    triple = bv(3, 66) * rd
    mask = bv((1 << 48) - 1, 66)
    merged = triple - (triple & mask)
    plain = triple - ((bv(2, 66) * rd) & mask) - (rd & mask)
    threshold1 = bv(1 << 64, 66)
    threshold2 = bv(1 << 65, 66)
    original = z3.And(
        z3.UGE(merged, threshold1),
        z3.UGE(merged, threshold2),
        z3.UGE(plain, threshold1),
        z3.ULT(plain, threshold2),
    )
    reduced = z3.And(
        z3.UGE(rd64, bv(COMPARATOR_LOW, 64)),
        z3.ULE(rd64, bv(COMPARATOR_HIGH, 64)),
    )
    solver = z3.SolverFor("QF_BV")
    solver.add(original != reduced)
    result = solver.check()
    if result != z3.unsat:
        raise AssertionError(f"comparator interval lemma failed: {result}")
    return {
        "result": "UNSAT",
        "meaning": "no counterexample to comparator split iff right-discard interval",
    }


def prove_endpoint_residues() -> dict[str, str]:
    base = z3.BitVec("h1463_lemma_base", 76)
    original = h1410.endpoint_residue(base)
    low9 = z3.Extract(8, 0, base)
    reduced = z3.Or(*(low9 == bv(item, 9)
                      for item in ENDPOINT_RESIDUES))
    solver = z3.SolverFor("QF_BV")
    solver.add(
        z3.UGE(base, bv(1 << 66, 76)),
        z3.ULT(base, bv(1 << 67, 76)),
        original != reduced,
    )
    result = solver.check()
    if result != z3.unsat:
        raise AssertionError(f"endpoint residue lemma failed: {result}")
    return {
        "result": "UNSAT",
        "meaning": "no counterexample to four-mode visibility iff six residues modulo 512",
    }


def prove_mreg_range() -> dict[str, str]:
    mreg = z3.BitVec("h1463_lemma_mreg", 72)
    original = z3.And(mreg >= bv(0, 72), mreg < bv(1 << 66, 72))
    reduced = z3.Extract(71, 66, mreg) == bv(0, 6)
    solver = z3.SolverFor("QF_BV")
    solver.add(original != reduced)
    result = solver.check()
    if result != z3.unsat:
        raise AssertionError(f"Mreg range lemma failed: {result}")
    return {
        "result": "UNSAT",
        "meaning": "no counterexample to signed Mreg range iff high six bits are zero",
    }


def prove_terminal_fusion() -> dict[str, str]:
    """Prove the zero-discard/base-residue reduction for this fixed path."""

    left = z3.BitVec("h1463_lemma_left", 67)
    right = z3.BitVec("h1463_lemma_right", 67)
    source = z3.ZeroExt(9, left) << 8
    umag = source + bv(3, 76) - z3.ZeroExt(9, right)
    base = z3.LShR(umag, 8)
    original = z3.And(
        z3.UGT(source + bv(3, 76), z3.ZeroExt(9, right)),
        z3.Extract(7, 0, umag) == bv(0, 8),
        z3.Or(*(z3.Extract(8, 0, base) == bv(item, 9)
                for item in ENDPOINT_RESIDUES)),
    )
    reduced_base = left - z3.LShR(right, 8)
    reduced = z3.And(
        z3.Extract(7, 0, right) == bv(3, 8),
        z3.UGT(source + bv(3, 76), z3.ZeroExt(9, right)),
        z3.Or(*(z3.Extract(8, 0, reduced_base) == bv(item, 9)
                for item in ENDPOINT_RESIDUES)),
    )
    solver = z3.SolverFor("QF_BV")
    solver.add(original != reduced)
    result = solver.check()
    if result != z3.unsat:
        raise AssertionError(f"terminal fusion lemma failed: {result}")
    return {
        "result": "UNSAT",
        "meaning": (
            "no counterexample to zero terminal discard plus base residue "
            "iff right low byte is three plus reduced left/right residue"
        ),
    }


def exact_path_consequent(graph: h1410.NarrowGraph) -> z3.BoolRef:
    tracker = "h1410.exact_materialization_path"
    matches = []
    for assertion in graph.solver.assertions():
        if (z3.is_implies(assertion)
                and str(assertion.arg(0)) == tracker):
            matches.append(assertion.arg(1))
    if len(matches) != 1:
        raise AssertionError(
            f"expected one {tracker} implication, found {len(matches)}"
        )
    return matches[0]


def external_preimage(square_sig: int) -> int | None:
    """Return the unique exact first-square preimage, if one exists."""

    lower_square = square_sig << 61
    upper_square = ((square_sig + 1) << 61) - 1
    lower = math.isqrt(lower_square)
    if lower * lower < lower_square:
        lower += 1
    upper = math.isqrt(upper_square)
    if lower > upper:
        return None
    if lower != upper:
        raise AssertionError("first-square map unexpectedly has two preimages")
    if not (1 << 63) <= lower < (1 << 64):
        return None
    if lower < SIDE_BOUNDARY:
        return None
    if (lower * lower) >> 61 != square_sig:
        raise AssertionError("integer square-root preimage check failed")
    return lower


def build_modular_solver() -> tuple[h1410.NarrowGraph, z3.Solver]:
    graph = h1410.build_graph(primary_kind="square")
    solver = z3.SolverFor("QF_BV")
    solver.add(exact_path_consequent(graph))

    right_shift = int(graph.values["right_shift"])
    if right_shift != 64:
        raise AssertionError(f"unexpected right shift {right_shift}")
    right_product = graph.values["right_product"]
    if not isinstance(right_product, z3.BitVecRef):
        raise AssertionError("right product is not symbolic")
    right_discard = z3.Extract(63, 0, right_product)

    right_sig = graph.values["right_sig"]
    left_sig = graph.values["left_sig"]
    if not isinstance(right_sig, z3.BitVecRef):
        raise AssertionError("right significand is not symbolic")
    if not isinstance(left_sig, z3.BitVecRef):
        raise AssertionError("left significand is not symbolic")
    right_product_low72 = z3.Extract(71, 0, right_product)
    reduced_base = left_sig - z3.LShR(right_sig, 8)

    umag = graph.values["umag"]
    mreg = graph.values["Mreg"]
    active = graph.values["active"]
    if not isinstance(umag, z3.BitVecRef):
        raise AssertionError("terminal magnitude is not symbolic")
    if not isinstance(mreg, z3.BitVecRef):
        raise AssertionError("Mreg is not symbolic")
    if not isinstance(active, z3.BoolRef):
        raise AssertionError("active gate is not symbolic")
    k = int(graph.values["k"])
    base = z3.LShR(umag, k)
    base_low9 = z3.Extract(8, 0, reduced_base)

    solver.add(
        active,
        z3.UGE(right_product_low72, bv(RIGHT_PRODUCT_LOW72, 72)),
        z3.ULE(right_product_low72, bv(RIGHT_PRODUCT_HIGH72, 72)),
        z3.Extract(71, 66, mreg) == bv(0, 6),
        z3.Or(*(base_low9 == bv(item, 9)
                for item in ENDPOINT_RESIDUES)),
    )
    graph.values["h1463_right_discard"] = right_discard
    graph.values["h1463_right_product_low72"] = right_product_low72
    graph.values["h1463_base"] = base
    graph.values["h1463_base_low9"] = base_low9
    return graph, solver


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--query-output", required=True, type=Path)
    parser.add_argument("--timeout-ms", type=int, default=60_000)
    parser.add_argument("--max-models", type=int, default=64)
    parser.add_argument("--residue", type=lambda value: int(value, 0))
    args = parser.parse_args()
    if args.residue is not None and args.residue not in ENDPOINT_RESIDUES:
        raise SystemExit(
            "--residue must be one of "
            + ", ".join(f"0x{item:03x}" for item in ENDPOINT_RESIDUES)
        )

    lemmas = {
        "comparator_interval": prove_comparator_interval(),
        "endpoint_residues": prove_endpoint_residues(),
        "mreg_range": prove_mreg_range(),
        "terminal_fusion": prove_terminal_fusion(),
    }
    graph, solver = build_modular_solver()
    solver.set(timeout=args.timeout_ms)

    template = h1410.h1404.concrete_forward(h1410.TEMPLATE_SIG)
    template_square = int(template["square_sig"])
    solver.push()
    solver.add(graph.primary == bv(template_square, 67))
    known_result = solver.check()
    if known_result != z3.sat:
        raise AssertionError(f"known d0d0 square is {known_result}")
    known_model = solver.model()
    if as_int(graph.values["h1463_base_low9"], known_model) \
            not in ENDPOINT_RESIDUES:
        raise AssertionError("known witness misses reduced endpoint residue")
    h1410.verify_values(graph, known_model, template)
    solver.pop()

    solver.add(graph.primary != bv(template_square, 67))
    if args.residue is not None:
        solver.add(
            graph.values["h1463_base_low9"] == bv(args.residue, 9)
        )
    query = standalone_query(solver)
    write_new(args.query_output, query)

    rejected_squares: list[dict[str, str]] = []
    witness: dict[str, Any] | None = None
    result = z3.unknown
    reason = "model limit reached"
    for _ in range(args.max_models):
        result = solver.check()
        if result == z3.unknown:
            reason = solver.reason_unknown()
            break
        if result == z3.unsat:
            reason = ""
            break
        model = solver.model()
        square_sig = as_int(graph.primary, model)
        external = external_preimage(square_sig)
        if external is None:
            rejected_squares.append({
                "square_sig": f"{square_sig:017x}",
                "reason": "no_exact_external_first_square_preimage",
            })
            solver.add(graph.primary != bv(square_sig, 67))
            continue

        concrete = h1410.h1404.concrete_forward(external)
        h1410.verify_values(graph, model, concrete)
        if concrete["square_sig"] != square_sig:
            raise AssertionError("external replay changed square")
        if not any(concrete[f"current_{mode}"]
                   != concrete[f"candidate_{mode}"]
                   for mode in h1410.MODES):
            raise AssertionError("external replay is not endpoint-visible")
        witness = {
            "operand": h1410.h1404.operand_text(0x3FFC, external),
            "square_sig": f"{square_sig:017x}",
            "right_discard": (
                f"{as_int(graph.values['h1463_right_discard'], model):016x}"
            ),
            "right_product_low72": (
                f"{as_int(graph.values['h1463_right_product_low72'], model):018x}"
            ),
            "base_low9": f"{as_int(graph.values['h1463_base_low9'], model):03x}",
            "python_replay": "exact",
            "changed_modes": [
                mode for mode in h1410.MODES
                if concrete[f"current_{mode}"]
                != concrete[f"candidate_{mode}"]
            ],
        }
        reason = ""
        break

    if witness is not None:
        status = "SAT_EXTERNAL_WITNESS"
    elif result == z3.unsat:
        status = "UNSAT_SQUARE_SUPERSET"
    elif result == z3.unknown:
        status = "UNKNOWN"
    else:
        status = "MODEL_LIMIT_WITHOUT_EXTERNAL_PREIMAGE"

    report = {
        "query": "r1382_modular_square_second_witness",
        "status": status,
        "solver": f"z3 {z3.get_version_string()}",
        "timeout_ms_per_check": args.timeout_ms,
        "maximum_models": args.max_models,
        "selected_endpoint_residue": (
            None if args.residue is None else f"{args.residue:03x}"
        ),
        "solver_result_at_stop": str(result).upper(),
        "reason": reason,
        "known_witness": h1410.TEMPLATE,
        "known_square_sig": f"{template_square:017x}",
        "known_witness_result": str(known_result).upper(),
        "known_python_replay": "exact",
        "proved_reductions": lemmas,
        "comparator_interval": [
            f"{COMPARATOR_LOW:016x}", f"{COMPARATOR_HIGH:016x}"
        ],
        "endpoint_residues_mod512": [
            f"{item:03x}" for item in ENDPOINT_RESIDUES
        ],
        "rejected_square_models": rejected_squares,
        "external_witness": witness,
        "query_artifact": str(args.query_output),
        "query_bytes": len(query),
        "query_sha256": sha256_bytes(query),
        "scope": (
            "all 67-bit chopped-square values in d0d0's exact complete "
            "materialization path, excluding d0d0's square; every SAT "
            "square is checked for an exact positive normal 3ffc external "
            "preimage on the side-one domain"
        ),
        "hardware_execution": "none",
        "emulator_change": "none",
    }
    write_new(
        args.output,
        (json.dumps(report, indent=2, sort_keys=True) + "\n").encode(),
    )
    print(json.dumps({
        "output": str(args.output),
        "query_output": str(args.query_output),
        "status": status,
        "rejected_square_models": len(rejected_squares),
        "external_witness": None if witness is None else witness["operand"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
