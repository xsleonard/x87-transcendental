#!/usr/bin/env python3
"""Replay retained R84/R85 hardware-line records and the current frontier.

The historical miss extracts are weaker provenance than full indexed raw
streams; identify them as such. Deduplicate matching tuples and retain absent
status as unknown. R86-off is a software counterfactual, never new hardware.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path

import h1630_shared_polynomial_audit as candidate


CURRENT = "tmp/ledger33/current/"
PARENT = CURRENT + "h1630_shared_polynomial_audit/"
FRONTIER = CURRENT + "h1626_fresh_frontier_verification/report.json"
LOCKS = {
    PARENT + "report.json": "5dc548a52e2d46749548011b2e4c2fa8ce919d2a7ab618fc4f4c2746fa54bd79",
    FRONTIER: "e4e0bae20a5a24e067a887c49784ec3d83ebc64031ab9f897e63d94d67075a80",
    "experiments/h1630_shared_polynomial_audit.py": "706a7ed6a2556cb8aa03ca9c7842ece37d70f99f0cbe01479eb9e76e58828834",
    "experiments/r84_misses.tsv": "e49222bd5499a26f02ab82cb4c59c094e15e33868a57cda6951e4fa15263c876",
    "experiments/r85_rz_misses.tsv": "9334edbdde46f061b594393606df2406076bf60cf32dccb973c6de3e53c9bff3",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output_dir.resolve()
    assert not output.exists()
    evidence = dict(LOCKS)
    for name, expected in evidence.items():
        assert candidate.records.digest(root / name) == expected, name
    parent = json.loads((root / PARENT / "report.json").read_text())
    for name, expected in parent["sha256"]["evidence"].items():
        assert candidate.records.digest(root / name) == expected
        evidence[name] = expected
    legacy, source_rows = {}, 0
    for relative in ("experiments/r84_misses.tsv", "experiments/r85_rz_misses.tsv"):
        for number, line in enumerate((root / relative).read_text().splitlines(), 1):
            fields = line.split("\t"); assert len(fields) == 8
            corpus, insn, mode, index, se, sig, hardware_line, old_model_line = fields
            assert insn in ("sin", "cos") and mode in ("rn", "rd", "ru", "rz")
            words = hardware_line.split()
            assert words[0] == "OK" and len(words) in (3, 5)
            if len(words) == 5:
                value, status = candidate.records.parse_output(hardware_line, True)
            else:
                value, status = candidate.records.parse_output(hardware_line), None
            key = "f" + insn, mode, se + " " + sig
            row = {"instruction": key[0], "mode": mode, "operand": key[2], "hardware": value,
                   "hardware_C1": (status >> 9) & 1 if status is not None else None,
                   "hardware_status": f"{status:04x}" if status is not None else None,
                   "sources": [], "provenance": "retained historical hardware-line extract; original corpus stream not reauthenticated here"}
            if key in legacy:
                assert legacy[key]["hardware"] == value and legacy[key]["hardware_C1"] == row["hardware_C1"]
            else:
                legacy[key] = row
            legacy[key]["sources"].append({"file": relative, "line": number, "corpus": corpus, "original_index": int(index)})
            source_rows += 1
    assert source_rows == 56 and len(legacy) == 53 and len({k[2] for k in legacy}) == 47
    prior = json.loads((root / FRONTIER).read_text())
    key = lambda row: (row["instruction"], row["mode"], row["operand"])
    current = {key(r): {"instruction": r["instruction"], "mode": r["mode"], "operand": r["operand"],
                       "hardware": r["output"], "hardware_C1": None, "hardware_status": None,
                       "provenance": "H1626 authenticated frontier; status not re-imported"}
               for r in prior["build_checks"]["candidate_O2"]["outputs"]}
    assert len(current) == 81
    overlap = legacy.keys() & current.keys()
    assert all(legacy[k]["hardware"] == current[k]["hardware"] for k in overlap)
    output.mkdir(parents=True)
    source = (root / "src/fsincos_skylake.c").read_text()
    ablated = output / "baseline_R86_off"
    build = subprocess.run(["cc", "-O2", "-std=c11", "-DG_ROUND84=0", "-DG_ROUND86=0", "-I", str(root / "src"),
                            "-x", "c", "-", "-lm", "-o", str(ablated)], input=source, text=True, capture_output=True, check=True)
    assert not build.stderr
    binaries = {"baseline_O2": root / CURRENT / "h1618_isolated_cosine_transfer/baseline_O2", "baseline_R86_off": ablated}
    old = json.loads((binaries["baseline_O2"].parent / "report.json").read_text())
    assert candidate.records.digest(binaries["baseline_O2"]) == old["builds"]["baseline_O2"]["binary_sha256"]
    for label in ("candidate_O0", "candidate_O2", "candidate_O3", "candidate_ubsan", "disabled_O2"):
        binary = root / PARENT / label
        assert candidate.records.digest(binary) == parent["sha256"]["binaries"][label]
        binaries[label] = binary
    results = {}
    for name, bank in (("legacy", legacy), ("frontier", current)):
        builds = {}
        for label, binary in binaries.items():
            scored, counts = [], Counter()
            for instruction, mode in sorted({k[:2] for k in bank}):
                keys = sorted(k for k in bank if k[:2] == (instruction, mode))
                values, metadata, _, _ = candidate.run(binary, instruction, mode, [k[2] for k in keys])
                for i, (identity, value) in enumerate(zip(keys, values)):
                    row, meta = bank[identity], metadata.get(i)
                    lane = "cosine" if meta and meta["cosine"] else "sine" if meta else "fallback"
                    known_c1 = row["hardware_C1"]
                    c1_exact = meta["C1"] == known_c1 if meta is not None and known_c1 is not None else None
                    detail = dict(row, output=value, output_exact=value == row["hardware"], lane=lane, metadata=meta, C1_exact=c1_exact)
                    counts["rows"] += 1; counts["output_exact"] += value == row["hardware"]
                    counts[lane + "_rows"] += 1
                    counts["known_hit_C1"] += c1_exact is not None
                    counts["C1_misses"] += c1_exact is False
                    if meta:
                        ivalue, ic1, _ = candidate.independent(meta, mode)
                        assert ivalue == value and ic1 == meta["C1"]
                        detail.update(independent_output=ivalue, independent_C1=ic1)
                    scored.append(detail)
            builds[label] = {"counts": dict(counts), "rows": scored}
        for label in ("candidate_O0", "candidate_O3", "candidate_ubsan"):
            assert builds[label] == builds["candidate_O2"]
        assert [r["output"] for r in builds["disabled_O2"]["rows"]] == [r["output"] for r in builds["baseline_O2"]["rows"]]
        by_key = {label: {key(r): r for r in build["rows"]} for label, build in builds.items()}
        ablation_changes = []
        for identity, row in by_key["candidate_O2"].items():
            base, without = by_key["baseline_O2"][identity], by_key["baseline_R86_off"][identity]
            if base["output"] != without["output"]:
                assert row["lane"] == "sine"
                ablation_changes.append({"instruction": identity[0], "mode": identity[1], "operand": identity[2],
                                         "hardware": row["hardware"], "baseline": base["output"], "R86_off": without["output"],
                                         "shared": row["output"], "shared_exact": row["output_exact"]})
        results[name] = {"builds": builds, "R86_ablation_changes": ablation_changes}
        print(name, {label: build["counts"] for label, build in builds.items()}, "R86 changes", len(ablation_changes), flush=True)
    result = {"experiment": "h1632_legacy_and_frontier_transfer", "results": results,
              "legacy_source_rows": 56, "legacy_unique_tuples": 53, "legacy_operands": 47, "frontier_overlap_tuples": len(overlap),
              "status": "PASS_RETAINED_RECORDS_AND_FRONTIER" if all(r["builds"]["candidate_O2"]["counts"]["output_exact"] == r["builds"]["candidate_O2"]["counts"]["rows"] and not r["builds"]["candidate_O2"]["counts"]["C1_misses"] for r in results.values()) else "CANDIDATE_FALSIFIED",
              "hardware_execution": "none", "canonical_default_or_paper_change": "none", "private_ledger_access": "none",
              "claim_boundary": "Legacy extracts preserve observed result lines but are not full original streams; H1626 frontier is inherited authenticated evidence. Software ablation is not a hardware intervention or a new capture. Missing C1 stays unknown.",
              "sha256": {"script": candidate.records.digest(Path(__file__)), "evidence": evidence,
                         "binaries": {name: candidate.records.digest(path) for name,path in binaries.items()}}}
    candidate.records.save(output / "report.json", result)
    print(result["status"], flush=True)


if __name__ == "__main__":
    main()
