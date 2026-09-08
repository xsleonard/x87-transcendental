#!/usr/bin/env python3
"""Audit the exact preimage sign/quadrant classes omitted from H1570.

Only fixed sign symmetries are used.  Negative result projection swaps RD
and RU; RN and RZ are unchanged.  Signed-zero residual metadata is checked
explicitly.  Every other exposed arithmetic diagnostic must be identical.
This is a transfer construction, not a carry selector or a hardware run.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from h1569_algebraic_preimage_families import MODES, replay, sha256_file, sha256_text


def project_mode(mode: str, negative: bool) -> str:
    return {"rn": "rn", "rd": "ru", "ru": "rd", "rz": "rz"}[mode] if negative else mode


def project_value(value: str, negative: bool) -> str:
    se, sig = value.split(":")
    return f"{int(se, 16) ^ (0x8000 if negative else 0):04x}:{sig}"


def canonical_trace(trace: list[str], residual_negative: bool, output_negative: bool) -> list[str]:
    """Verify the predicted sign fields, then map them to the direct anchor.

    No numeric word, diagnostic stage, rounding flag, or branch field is
    dropped.  The only additional normalization beyond H1569 is a fixed
    replacement of five sign metadata fields and the two RC2 sign bits.
    """
    result = []
    for line in trace:
        prefix = line.split()[0]
        if prefix == "DI_RC2":
            for field in ("r", "c"):
                match = re.search(rf"\b{field}=([01]):", line)
                assert match and int(match[1]) == int(residual_negative), line
                line = re.sub(rf"\b{field}=[01]:", f"{field}=0:", line)
        if prefix in ("DI_RED", "DI_POLY"):
            for field, expected in (("i0", output_negative), ("rsn", residual_negative)):
                match = re.search(rf"\b{field}=([01])\b", line)
                assert match and int(match[1]) == int(expected), line
                line = re.sub(rf"\b{field}=[01]\b", f"{field}=0", line)
        if prefix == "DI_FIN":
            match = re.search(r"\bneg=([01])\b", line)
            assert match and int(match[1]) == int(output_negative), line
            line = re.sub(r"\bneg=[01]\b", "neg=0", line)
        result.append(line)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--models", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    source_path = args.root / "tmp/ledger33/current/h1569_algebraic_preimage_families.json"
    source = json.loads(source_path.read_text())
    models = {n: (args.models / n).resolve() for n in ("baseline", "carry0", "carry1")}
    assert {n: sha256_file(p) for n, p in models.items()} == source["sha256"]["models"]
    assert sha256_file(args.root / "src/fsincos_skylake.c") == source["sha256"]["source"]
    families = []
    for family in source["families"]:
        if not family["preimage_count"] or family["positive_same_residual_cosine_candidates"]:
            continue
        anchor = family["anchor"]
        direct = {mode: replay(models["baseline"], anchor, "fcos", mode, True) for mode in MODES}
        for mode in MODES:
            assert direct[mode][1] == canonical_trace(direct[mode][1], False, False)
        anchor_mode = family["mode"]
        direct_endpoints = {n: replay(p, anchor, "fcos", anchor_mode)[0] for n, p in models.items()}
        candidates = []
        for preimage in family["all_preimages"]:
            quotient = preimage["quotient"]
            instruction = "fsin" if quotient & 1 else "fcos"
            negative = bool((quotient >> 1) & 1)
            residual_negative = preimage["residual_side"] < 0
            equal = {}
            for mode in MODES:
                value, trace = replay(models["baseline"], preimage["operand"], instruction,
                                      project_mode(mode, negative), True)
                equal[mode] = (project_value(value, negative) == direct[mode][0]
                               and canonical_trace(trace, residual_negative, negative) == direct[mode][1])
            capture_mode = project_mode(anchor_mode, negative)
            endpoints = {n: replay(p, preimage["operand"], instruction, capture_mode)[0]
                         for n, p in models.items()}
            endpoint_equal = all(project_value(endpoints[n], negative) == direct_endpoints[n] for n in models)
            candidates.append({"operand": preimage["operand"], "quotient": quotient,
                               "instruction": instruction, "mode": capture_mode,
                               "residual_side": preimage["residual_side"],
                               "output_negative": negative,
                               "trace_and_endpoint_equal_all_modes": all(equal.values()),
                               "mode_equalities": equal, "forced_endpoints_equal": endpoint_equal,
                               "outputs": endpoints,
                               "transfer_prediction": project_value(family["hardware_anchor"], negative)})
        families.append({"anchor": anchor, "source": family["source"], "case_id": family["case_id"],
                         "anchor_mode": anchor_mode, "anchor_hardware": family["hardware_anchor"],
                         "anchor_baseline_exact": family["baseline_anchor_exact"],
                         "direct_trace_sha256": sha256_text("\n".join(direct[anchor_mode][1])),
                         "candidates": candidates})
    candidates = [c for f in families for c in f["candidates"]]
    counts = {"anchor_families": len(families), "candidates": len(candidates),
              "trace_mismatches": sum(not c["trace_and_endpoint_equal_all_modes"] for c in candidates),
              "forced_endpoint_mismatches": sum(not c["forced_endpoints_equal"] for c in candidates),
              "negative_projection_candidates": sum(c["output_negative"] for c in candidates),
              "negative_residual_candidates": sum(c["residual_side"] < 0 for c in candidates)}
    report = {"experiment": "h1572_signed_preimage_projection", "capture_state": "SOFTWARE_ONLY_NOT_FROZEN",
              "hardware_execution": "none", "new_hardware_labels": "none", "selector_claim": "none",
              "counts": counts, "families": families,
              "canonical_sign_fields": ["DI_RC2.r.sign", "DI_RC2.c.sign", "DI_RED.i0", "DI_RED.rsn",
                                        "DI_POLY.i0", "DI_POLY.rsn", "DI_FIN.neg"],
              "mode_projection": "negative_cosine_swaps_RD_RU_only",
              "sha256": {"source_report": sha256_file(source_path), "source": source["sha256"]["source"],
                         "models": source["sha256"]["models"], "script": sha256_file(Path(__file__))}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps(counts, sort_keys=True))


if __name__ == "__main__":
    main()
