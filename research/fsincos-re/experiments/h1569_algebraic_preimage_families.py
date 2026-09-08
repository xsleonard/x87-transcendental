#!/usr/bin/env python3
"""Enumerate exact M66 reduction preimages algebraically, without an SMT bound.

This solves the external-input representability problem, NOT the R59 carry
selector.  Only existing hardware observations provide anchor truth.  Fresh
preimages are software-only transfer discriminators until separately frozen
and observed once.  No emulator defaults or paper artifacts are changed.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

from h1411_exact_preimage_discriminators import (
    M66, MODES, add_carry_mask, sha256_file, sha256_text, subtract_borrow_mask,
)


def ceildiv(n: int, d: int) -> int:
    return -((-n) // d)


def preimages(residual: int, bits: int = 64, m: int = M66) -> list[dict]:
    """All positive normal preimages, 3 <= external shift <= bits+1.

    X = sig*2^t = 2*q*m + side*r.  Odd r is impossible by parity.
    For even r, q is one residue class modulo 2^(t-1), since m is
    odd.  Normalization gives an interval shorter than that modulus,
    so there is at most one q for each t and residual sign.  The
    64-bit instance exhausts positive finite normal inputs below 2^63.
    """
    assert (1 << (bits - 1)) <= residual < (1 << bits)
    assert m & 1 and m > (1 << bits)
    if residual & 1:
        return []
    result = []
    for side in (-1, 1):
        for t in range(3, bits + 2):
            modulus = 1 << (t - 1)
            q0 = (-side * (residual // 2) * pow(m, -1, modulus)) % modulus
            lo = max(1, ceildiv((1 << (bits - 1 + t)) - side * residual, 2 * m))
            hi = ((1 << (bits + t)) - 1 - side * residual) // (2 * m)
            assert hi - lo < modulus
            q = q0 + max(0, ceildiv(lo - q0, modulus)) * modulus
            if q > hi:
                continue
            x = 2 * q * m + side * residual
            sig, remainder = divmod(x, 1 << t)
            assert remainder == 0 and (1 << (bits - 1)) <= sig < (1 << bits)
            assert (x + m) // (2 * m) == q
            result.append({"shift": t, "quotient": q, "residual_side": side,
                           "significand": sig})
    return sorted(result, key=lambda row: (row["quotient"], row["residual_side"]))


def toy_exhaustion() -> dict:
    """Independently brute-force every external encoding at four toy widths."""
    encodings = 0
    cases = 0
    for bits in range(3, 7):
        m = 3 * (1 << bits) + 1
        brute = {r: set() for r in range(1 << (bits - 1), 1 << bits)}
        for t in range(3, bits + 2):
            for sig in range(1 << (bits - 1), 1 << bits):
                encodings += 1
                x = sig << t
                q = (x + m) // (2 * m)
                r = x - 2 * q * m
                if q and abs(r) in brute:
                    brute[abs(r)].add((t, sig, q, 1 if r > 0 else -1))
        for r, expected in brute.items():
            actual = {(v["shift"], v["significand"], v["quotient"],
                       v["residual_side"]) for v in preimages(r, bits, m)}
            assert actual == expected, (bits, r, actual, expected)
            cases += 1
    return {"result": "exact", "widths": [3, 4, 5, 6],
            "residual_cases": cases, "external_encodings": encodings}


def replay(model: Path, op: str, instruction: str, mode: str,
           dump: bool = False) -> tuple[str, list[str]]:
    command = [str(model), "--batch", f"--rc={mode}", f"--{instruction}-standalone"]
    if dump:
        command.append("--dump-internals")
    proc = subprocess.run(command, input=op + "\n", text=True,
                          capture_output=True, check=True)
    outputs = proc.stdout.strip().splitlines()
    if len(outputs) != 1 or not outputs[0].startswith("OK "):
        raise RuntimeError(f"unexpected architectural output for {op}: {outputs}")
    # DI_IN intentionally identifies the different external input.  The ra
    # token in DI_FIN is an ASLR-dependent address, not an arithmetic wire.
    # No other diagnostic prefix or field is removed from the comparison.
    trace = [re.sub(r" ra=\S+", "", line) for line in proc.stderr.splitlines()
             if line.startswith("DI_") and not line.startswith("DI_IN ")]
    if dump:
        prefixes = {line.split()[0] for line in trace}
        assert {"DI_RC2", "DI_POLY", "DI_R59", "DI_BR", "DI_FIN"} <= prefixes
    return ":".join(outputs[0][3:].split()), trace


def reducer_history(residual: int, row: dict) -> dict:
    """Actual equation X - 2*q*M66 = r, not the inverse construction A+r."""
    assert row["residual_side"] == 1
    width = 130
    x = row["significand"] << row["shift"]
    a = 2 * row["quotient"] * M66
    borrow, difference = subtract_borrow_mask(x, a, width)
    carry, total = add_carry_mask(x, ((1 << width) - 1) ^ a, width, 1)
    assert difference == residual and total % (1 << width) == residual
    assert (borrow ^ carry) == (1 << (width + 1)) - 1
    return {"equation": "X - 2*q*M66 = R", "width": width,
            "borrow_entering_columns_hex": hex(borrow),
            "complement_add_carry_entering_columns_hex": hex(carry),
            "borrow64": (borrow >> 64) & 1, "carry64": (carry >> 64) & 1,
            "claim_boundary": "mathematical_ripple_history_not_a_recovered_silicon_wire"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--models", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    source_path = args.root / "tmp/ledger33/current/h1568_expanded_causal_frontier.json"
    source = json.loads(source_path.read_text())
    models = {name: (args.models / name).resolve() for name in ("baseline", "carry0", "carry1")}
    assert {name: sha256_file(model) for name, model in models.items()} == {
        name: source["sha256"]["models"][name] for name in models}
    assert sha256_file(args.root / "src/fsincos_skylake.c") == source["sha256"]["source"]
    anchors = {}
    for row in sorted(source["rows"], key=lambda r: (MODES.index(r["mode"]), r["operand"])):
        anchors.setdefault(row["operand"], row)

    old_path = args.root / "tmp/ledger33/current/h1404_exact_external_preimages.json"
    old = json.loads(old_path.read_text())
    old_checks = []
    for row in old["rows"]:
        choices = preimages(int(row["anchor"].split()[1], 16))
        status = "SAT" if choices else "UNSAT"
        assert status == row["result"]
        if status == "SAT":
            assert any(f"{0x3ffc + c['shift']:04x} {c['significand']:016x}" == row["operand"]
                       and c["quotient"] == row["quotient"]
                       and c["residual_side"] == row["residual_side"] for c in choices)
        old_checks.append({"anchor": row["anchor"], "result": status,
                           "exact_preimage_count": len(choices)})

    families = []
    for anchor, observed in anchors.items():
        residual = int(anchor.split()[1], 16)
        assert anchor.startswith("3ffc ")
        choices = preimages(residual)
        direct = {mode: replay(models["baseline"], anchor, "fcos", mode, True)
                  for mode in MODES}
        mode = observed["mode"]
        direct_endpoints = {name: replay(model, anchor, "fcos", mode)[0]
                            for name, model in models.items()}
        assert direct_endpoints == {name: observed["outputs"][name] for name in models}
        compatible = []
        for choice in choices:
            choice["operand"] = f"{0x3ffc + choice['shift']:04x} {choice['significand']:016x}"
            if choice["residual_side"] != 1 or choice["quotient"] % 4 not in (0, 1):
                continue
            instruction = "fsin" if choice["quotient"] & 1 else "fcos"
            external = {rc: replay(models["baseline"], choice["operand"], instruction, rc, True)
                        for rc in MODES}
            equal = {rc: external[rc] == direct[rc] for rc in MODES}
            endpoints = {name: replay(model, choice["operand"], instruction, mode)[0]
                         for name, model in models.items()}
            compatible.append({"operand": choice["operand"], "instruction": instruction,
                               "quotient": choice["quotient"], "shift": choice["shift"],
                               "residual_side": 1, "trace_and_endpoint_equal": equal,
                               "forced_endpoints_equal": endpoints == direct_endpoints,
                               "outputs": endpoints,
                               "reduction_history": reducer_history(residual, choice)})
        families.append({"anchor": anchor, "source": observed["source"],
                         "case_id": observed["case_id"], "mode": mode,
                         "hardware_anchor": observed["hardware"],
                         "baseline_anchor_exact": observed["baseline_exact"],
                         "anchor_carries": observed["allowed_carries"],
                         "preimage_count": len(choices), "all_preimages": choices,
                         "direct_trace": {rc: direct[rc][1] for rc in MODES},
                         "direct_trace_sha256": {rc: sha256_text("\n".join(direct[rc][1]))
                                                 for rc in MODES},
                         "positive_same_residual_cosine_candidates": compatible})
    candidates = [c for f in families for c in f["positive_same_residual_cosine_candidates"]]
    counts = {"anchors": len(families),
              "anchors_with_exact_preimages": sum(bool(f["preimage_count"]) for f in families),
              "exact_preimages": sum(f["preimage_count"] for f in families),
              "positive_cosine_candidates": len(candidates),
              "anchors_with_positive_cosine_candidates": sum(bool(f["positive_same_residual_cosine_candidates"])
                                                             for f in families),
              "candidate_trace_mismatches": sum(not all(c["trace_and_endpoint_equal"].values()) for c in candidates),
              "candidate_forced_endpoint_mismatches": sum(not c["forced_endpoints_equal"] for c in candidates)}
    report = {"experiment": "h1569_algebraic_preimage_families", "hardware_execution": "none",
              "new_hardware_labels": "none", "capture_state": "SOFTWARE_ONLY_NOT_FROZEN",
              "scope": "positive_normal_external_inputs_below_2^63_exact_M66_residual_3ffc",
              "selector_claim": "none", "counts": counts, "toy_exhaustion": toy_exhaustion(),
              "h1404_reconciliation": old_checks,
              "h1404_status_counts": dict(Counter(r["result"] for r in old_checks)),
              "trace_exclusions": ["DI_IN external input identity", "DI_FIN ra ASLR address token"],
              "families": families,
              "sha256": {"h1568": sha256_file(source_path), "h1404": sha256_file(old_path),
                         "source": source["sha256"]["source"], "script": sha256_file(Path(__file__)),
                         "models": {name: sha256_file(path) for name, path in models.items()}}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps({"counts": counts, "h1404_status_counts": report["h1404_status_counts"],
                      "toy_exhaustion": report["toy_exhaustion"]}, sort_keys=True))


if __name__ == "__main__":
    main()
