#!/usr/bin/env python3
"""Replay the first exact external SAT witness for H1410's relaxed tree gate.

H1410 deliberately fixes the R1272 merge gate to its enabling value while
solving the rest of d0d0's exact arithmetic schedule.  H1470's modular-lattice
search found an external operand satisfying that relaxed graph.  This script
checks it directly in the original H1410 graph, verifies every pre-tree
arithmetic value against the independent concrete replay, and then restores
the exact product-tree gate.  The real gate rejects the endpoint change.

No x87 instruction is executed and no emulator behavior is changed.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

try:
    import z3
except ImportError as error:  # pragma: no cover
    raise SystemExit("z3-solver 4.15.3.0 is required") from error


HERE = Path(__file__).resolve().parent
H1410_PATH = HERE / "h1410_width_reduced_r1382.py"
SPEC = importlib.util.spec_from_file_location("h1410_h1473", H1410_PATH)
if SPEC is None or SPEC.loader is None:  # pragma: no cover
    raise SystemExit(f"cannot load {H1410_PATH}")
h1410 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = h1410
SPEC.loader.exec_module(h1410)


OPERAND = 0xD0001749ED75344D
EXPECTED_SQUARE = 0x548012EC11FE6980B
EXPECTED_FOURTH = 0x6F9131F7651BFF7BA
ARITHMETIC_NAMES = (
    "square_sig",
    "fourth_sig",
    "negative_sig",
    "positive_sig",
    "left_sig",
    "right_sig",
    "active",
    "low3",
    "dist",
    "payload",
    "S",
    "B",
    "umag",
    "k",
    "disc",
    "ce",
    "s4",
    "side",
    "t4",
    "sqlow",
    "Mreg",
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def symbolic_value(value: Any, model: z3.ModelRef) -> int:
    if isinstance(value, int):
        return value
    return h1410.as_int(value, model)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout-ms", type=int, default=30_000)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    graph = h1410.build_graph(primary_kind="external")
    graph.solver.set(timeout=args.timeout_ms)
    graph.solver.add(graph.primary == h1410.bv(OPERAND, 64))
    result = graph.solver.check()
    if result != z3.sat:
        raise AssertionError(
            f"targeted H1410 relaxed-gate witness is {result}: "
            f"{graph.solver.reason_unknown()}"
        )
    model = graph.solver.model()
    concrete = h1410.h1404.concrete_forward(OPERAND)
    arithmetic_mismatches = {}
    for name in ARITHMETIC_NAMES:
        got = symbolic_value(graph.values[name], model)
        expected = int(concrete[name])
        if got != expected:
            arithmetic_mismatches[name] = [got, expected]
    if arithmetic_mismatches:
        raise AssertionError(
            f"relaxed/concrete arithmetic mismatch: {arithmetic_mismatches}"
        )
    if concrete["square_sig"] != EXPECTED_SQUARE \
            or concrete["fourth_sig"] != EXPECTED_FOURTH:
        raise AssertionError("exact external inversion changed the recovered path")

    relaxed_changed = [
        mode for mode in h1410.MODES
        if symbolic_value(graph.values[f"current_{mode}"], model)
        != symbolic_value(graph.values[f"candidate_{mode}"], model)
    ]
    exact_tree_changed = [
        mode for mode in h1410.MODES
        if concrete[f"current_{mode}"] != concrete[f"candidate_{mode}"]
    ]
    if relaxed_changed != ["rd", "rz"]:
        raise AssertionError(f"unexpected relaxed response: {relaxed_changed}")
    if concrete["merge_gate"] != 0 or exact_tree_changed:
        raise AssertionError(
            f"exact tree failed to reject witness: gate={concrete['merge_gate']} "
            f"modes={exact_tree_changed}"
        )

    report = {
        "experiment": "h1473_r1382_relaxed_gate_witness",
        "status": "SAT_RELAXED_GATE_REJECTED_BY_EXACT_TREE",
        "operand": f"3ffc:{OPERAND:016x}",
        "square_sig": f"{EXPECTED_SQUARE:017x}",
        "fourth_sig": f"{EXPECTED_FOURTH:017x}",
        "solver": f"z3 {z3.get_version_string()}",
        "timeout_ms": args.timeout_ms,
        "relaxed_h1410": {
            "result": "SAT",
            "merge_gate": symbolic_value(graph.values["merge_gate"], model),
            "changed_modes": relaxed_changed,
            "current_rd3": f"{symbolic_value(graph.values['current_rd3'], model):x}",
            "candidate_rd3": f"{symbolic_value(graph.values['candidate_rd3'], model):x}",
            "current_retained": (
                f"{symbolic_value(graph.values['current_retained'], model):x}"
            ),
            "candidate_retained": (
                f"{symbolic_value(graph.values['candidate_retained'], model):x}"
            ),
        },
        "exact_tree_replay": {
            "arithmetic_values_checked": len(ARITHMETIC_NAMES),
            "arithmetic_mismatches": 0,
            "merge_gate": int(concrete["merge_gate"]),
            "changed_modes": exact_tree_changed,
            "current_rd3": f"{concrete['current_rd3']:x}",
            "candidate_rd3": f"{concrete['candidate_rd3']:x}",
            "current_retained": f"{concrete['current_retained']:x}",
            "candidate_retained": f"{concrete['candidate_retained']:x}",
        },
        "bounded_conclusion": (
            "The formerly UNKNOWN H1410 relaxed-gate second-preimage query "
            "is SAT. Its first recovered exact external assignment is not a "
            "physical R1382 endpoint separator because the independently "
            "reconstructed R1272 tree gate is zero."
        ),
        "hardware_execution": "none",
        "hardware_labels": "none",
        "emulator_change": "none",
        "paper_change": "none",
        "sha256": {
            "h1410_source": digest(H1410_PATH),
            "h1404_replay": digest(HERE / "h1404_exact_preimage_smt.py"),
            "h1470_search": digest(
                HERE / "h1470_r1382_constant_positive_lattice.c"
            ),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps({
        "output": str(args.output),
        "status": report["status"],
        "operand": report["operand"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
