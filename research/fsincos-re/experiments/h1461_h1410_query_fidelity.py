#!/usr/bin/env python3
"""Repair and audit the standalone serialization of the H1410 query.

H1410 uses ``Solver.assert_and_track`` for its two large conjunctions.  Z3
checks tracked assertions under their tracking literals, but ``to_smt2``
serializes only the implications and does not serialize the check-time
assumptions.  Consequently the original H1410 Python result describes the
intended graph, while its standalone SMT-LIB file is underconstrained.

This analysis-only program rebuilds the same width-minimal external-input
graph, explicitly asserts both tracking literals, proves that the known d0d0
witness remains SAT, excludes it, and writes a self-contained QF_BV query.
It neither executes x87 hardware nor changes emulator defaults.  Existing
H1410 artifacts are inspected by digest and are never overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
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


EXPECTED_ORIGINAL_QUERY_SHA256 = (
    "18a583a2b92e736e5afe89f07d26cd2e0a903b4722908f75abac8be95c713c46"
)
TRACKERS = (
    "h1410.exact_materialization_path",
    "h1410.endpoint_visible",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def write_new(path: Path, content: bytes) -> None:
    if path.exists():
        raise SystemExit(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as target:
        target.write(content)


def assertion_present(query: str, tracker: str) -> bool:
    return re.search(
        rf"\(assert\s+{re.escape(tracker)}\s*\)", query
    ) is not None


def add_logic(query: str) -> str:
    if "(set-logic " in query:
        return query
    return query.replace(
        "(set-info :status unknown)",
        "(set-logic QF_BV)\n(set-info :status unknown)",
        1,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--original-query", required=True, type=Path)
    parser.add_argument("--h1409-query", required=True, type=Path)
    parser.add_argument("--query-output", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout-ms", type=int, default=60_000)
    args = parser.parse_args()

    original_digest = sha256(args.original_query)
    if original_digest != EXPECTED_ORIGINAL_QUERY_SHA256:
        raise SystemExit(
            "unexpected original H1410 query digest: " + original_digest
        )
    original_text = args.original_query.read_text()
    original_tracker_assertions = {
        tracker: assertion_present(original_text, tracker)
        for tracker in TRACKERS
    }
    if any(original_tracker_assertions.values()):
        raise AssertionError("original H1410 query unexpectedly asserts a tracker")
    for tracker in TRACKERS:
        if f"(=> {tracker} " not in original_text:
            raise AssertionError(f"original query omitted implication for {tracker}")

    h1409_text = args.h1409_query.read_text()
    h1409_trackers = (
        "separator_fixed.exact_materialization_path",
        "r1382.endpoint_visible_in_fixed_path",
    )
    h1409_tracker_assertions = {
        tracker: assertion_present(h1409_text, tracker)
        for tracker in h1409_trackers
    }
    if not all(h1409_tracker_assertions.values()):
        raise AssertionError("H1409 does not contain its documented tracker fix")

    graph = h1410.build_graph(primary_kind="external")
    for tracker in TRACKERS:
        graph.solver.add(z3.Bool(tracker))
    graph.solver.set(timeout=args.timeout_ms)

    graph.solver.push()
    graph.solver.add(graph.primary == z3.BitVecVal(h1410.TEMPLATE_SIG, 64))
    known_result = graph.solver.check()
    if known_result != z3.sat:
        raise AssertionError(f"known d0d0 witness is {known_result}")
    known = h1410.concrete_replay(graph, graph.solver.model())
    graph.solver.pop()

    graph.solver.add(graph.primary != z3.BitVecVal(h1410.TEMPLATE_SIG, 64))
    query_text = add_logic(graph.solver.to_smt2())
    for tracker in TRACKERS:
        if not assertion_present(query_text, tracker):
            raise AssertionError(f"corrected query omitted {tracker}")
    query = query_text.encode()
    write_new(args.query_output, query)

    result = graph.solver.check()
    report: dict[str, Any] = {
        "query": "h1410_width_minimal_external_second_witness_fidelity_repair",
        "solver": f"z3 {z3.get_version_string()}",
        "timeout_ms": args.timeout_ms,
        "result": str(result).upper(),
        "reason": graph.solver.reason_unknown() if result == z3.unknown else "",
        "known_witness": h1410.TEMPLATE,
        "known_witness_result": str(known_result).upper(),
        "known_python_replay": "exact",
        "known_square_sig": f"{known['square_sig']:017x}",
        "original_h1410_query": str(args.original_query),
        "original_h1410_query_sha256": original_digest,
        "original_h1410_tracker_assertions": original_tracker_assertions,
        "original_h1410_standalone_status": "UNDERCONSTRAINED_NOT_FAITHFUL",
        "original_h1410_python_checkpoint_status": (
            "INTENDED_TRACKED_QUERY_UNKNOWN_REMAINS_VALID"
        ),
        "h1409_query": str(args.h1409_query),
        "h1409_query_sha256": sha256(args.h1409_query),
        "h1409_tracker_assertions": h1409_tracker_assertions,
        "corrected_query": str(args.query_output),
        "corrected_query_bytes": len(query),
        "corrected_query_sha256": sha256_bytes(query),
        "corrected_tracker_assertions": {
            tracker: assertion_present(query_text, tracker)
            for tracker in TRACKERS
        },
        "scope": (
            "all positive normal 3ffc external inputs in d0d0's exact "
            "complete materialization path, excluding d0d0; R1272 gate "
            "relaxed to its enabling value"
        ),
        "hardware_execution": "none",
        "emulator_change": "none",
    }
    if result == z3.sat:
        model = graph.solver.model()
        concrete = h1410.concrete_replay(graph, model)
        report.update({
            "operand": h1410.h1404.operand_text(0x3FFC, concrete["m"]),
            "python_replay": "exact",
            "status_boundary": (
                "SAT requires exact-tree and C replay before use as a witness"
            ),
        })
    elif result == z3.unsat:
        report["unsat_core"] = sorted(
            str(item) for item in graph.solver.unsat_core()
        )

    write_new(
        args.output,
        (json.dumps(report, indent=2, sort_keys=True) + "\n").encode(),
    )
    print(json.dumps({
        "output": str(args.output),
        "query_output": str(args.query_output),
        "result": report["result"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
