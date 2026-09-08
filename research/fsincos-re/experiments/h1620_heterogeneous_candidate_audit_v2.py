#!/usr/bin/env python3
"""Score H1618 on authenticated older dense, targeted and sweep captures.

Use H1509/H1510/H1511 only for capture inventories and immutable hashes,
never their model outputs as hardware truth. Score every actual cached row,
with separate candidate-hook and incumbent-fallback accounting. No hardware,
private ledger, fresh label, source/default change or PDF update.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from contextlib import ExitStack
from pathlib import Path

import h1619_raw_stagea_candidate_audit as prior
from h1510_existing_targeted_pair_audit import SUITES
from h1511_remaining_fcos_cache_audit import CASES


candidate, digest, save, zipped = prior.candidate, prior.digest, prior.json_save, prior.zipped
LOCKS = {
    "experiments/h1619_raw_stagea_candidate_audit.py": "f7dd40373eeabc81df682387b92597ebed86fd3c65ba16cb0e59e1e8e0479f82",
    "experiments/h1510_existing_targeted_pair_audit.py": "401a51badf03f9bcc73cd56aa1e6fbd3b3289f986783bf7605c0284cfe708ec4",
    "experiments/h1511_remaining_fcos_cache_audit.py": "244b39cb52ca79ffc4f8414fa3c4664faa2701f39a3cb9d8c4813235e334a16a",
    "tmp/ledger33/current/h1509_existing_dense_pair_audit.json": "0bfe819369fe908f03f0e6a3936679885f8c01e543de57c2bcc5ff5bcab0e3cb",
    "tmp/ledger33/current/h1510_existing_targeted_pair_audit.json": "c0841bcceae0a02c61871e35cd0de3fb76dae14055e33b109cf1d4c3c22fb143",
    "tmp/ledger33/current/h1511_remaining_fcos_cache_audit.json": "8a2ca48492e5de79c02a8d7483b8a2c64592cee94b8214923756a352029d0285",
}
ROW_ANCHOR = '    while (scanf("%x %llx", &se, &sig) == 2) {'
INCLUDE = "static unsigned long long h1620_row;\n" + prior.AUDIT_INCLUDE.replace(
    "fputc('0' + increment, stderr);",
    'fprintf(stderr, "%llu %d\\n", h1620_row - 1, increment);')


def run(binary: Path, mode: str, operands: list[str], observed: bool):
    process = subprocess.run([str(binary), "--batch", "--fcos-standalone", "--rc=" + mode],
                             input="".join(op + "\n" for op in operands),
                             text=True, capture_output=True, check=True)
    values = []
    for line in process.stdout.splitlines():
        parts = line.lower().split()
        if parts == ["c2"]:
            values.append("C2")
        else:
            assert len(parts) == 3 and parts[0] == "ok", line
            values.append(parts[1] + ":" + parts[2])
    assert len(values) == len(operands)
    indicators = {}
    for line in process.stderr.splitlines():
        assert observed, process.stderr[:1024]
        parts = line.split()
        assert len(parts) == 2 and parts[1] in ("0", "1"), line
        index = int(parts[0])
        assert 0 <= index < len(operands) and index not in indicators
        indicators[index] = int(parts[1])
    return values, indicators, process.stdout, process.stderr


def raw_hardware(line: str):
    parts = line.lower().split()
    # H1620 v2: the actual sweep stream has a distinct C2 status-only row.
    if len(parts) == 3 and parts[0] == "c2":
        assert parts[1] == "sw", line
        status = int(parts[2], 16)
        assert 0 <= status <= 0xffff and status & 0x400, line
        return "C2", status
    assert len(parts) in (3, 5) and parts[0] == "ok", line
    se, sig = int(parts[1], 16), int(parts[2], 16)
    assert 0 <= se <= 0xffff and 0 <= sig < (1 << 64)
    status = None
    if len(parts) == 5:
        assert parts[3] == "sw"
        status = int(parts[4], 16)
        assert 0 <= status <= 0xffff
    return ("C2" if status is not None and status & 0x400 else f"{se:04x}:{sig:016x}"), status


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output_dir.resolve()
    assert not output.exists()
    evidence = {**prior.LOCKS, **LOCKS}
    for relative, expected in evidence.items():
        assert digest(root / relative) == expected, relative
    parent = json.loads((root / prior.PARENT / "report.json").read_text())
    for relative, expected in parent["sha256"]["evidence"].items():
        assert digest(root / relative) == expected, relative
        evidence[relative] = expected
    for name in ("baseline_O2", "candidate_O2"):
        assert digest(root / prior.PARENT / name) == parent["builds"][name]["binary_sha256"]
    dense = json.loads((root / "tmp/ledger33/current/h1509_existing_dense_pair_audit.json").read_text())
    targeted = json.loads((root / "tmp/ledger33/current/h1510_existing_targeted_pair_audit.json").read_text())
    remainder = json.loads((root / "tmp/ledger33/current/h1511_remaining_fcos_cache_audit.json").read_text())
    inventories = [("h110-dense", "capture-kit/inputs/dense_qn.txt",
                    {mode: f"capture-kit-captures/skylake-fsin-h110/dense_fcos_{mode}_status.txt" for mode in prior.MODES},
                    240000, dense["sha256"]["inputs"], dense["sha256"]["captures"])]
    for tag, inputs, captures, count in SUITES:
        inventories.append((tag, inputs, {mode: captures + f"/fcos_{mode}_status.txt" for mode in prior.MODES},
                            count, targeted["sha256"]["inputs"][tag], targeted["sha256"]["captures"][tag]))
    for tag, inputs, captures, count in CASES:
        inventories.append((tag, inputs, captures, count, remainder["sha256"]["inputs"][tag], remainder["sha256"]["captures"][tag]))
    for _, inputs, captures, _, input_hash, capture_hashes in inventories:
        assert digest(root / inputs) == input_hash, inputs
        evidence[inputs] = input_hash
        for mode, relative in captures.items():
            assert digest(root / relative) == capture_hashes[mode], relative
            evidence[relative] = capture_hashes[mode]
    original, source = candidate.assembled_source(root)
    include = '#include "h1618_asymmetric_cosine.h"'
    assert source.count(include) == source.count(ROW_ANCHOR) == 1
    source = source.replace(include, INCLUDE).replace(ROW_ANCHOR, ROW_ANCHOR + "\n        h1620_row++;")
    output.mkdir(parents=True)
    save(output / "prepared.json", {"state": "SOFTWARE_AUDIT_PREPARED_NOT_COMPLETE", "evidence": evidence,
                                   "script_sha256": digest(Path(__file__)), "in_memory_source_sha256": hashlib.sha256(source.encode()).hexdigest()})
    binary = output / "candidate_indexed"
    build = subprocess.run(["cc", "-O2", "-std=c11", "-DG_ROUND84=0", "-DG_H1618_ASYMMETRIC_COSINE=1",
                            "-I", str(root / "src"), "-I", str(root / "experiments"), "-x", "c", "-", "-lm", "-o", str(binary)],
                           input=source, text=True, capture_output=True, check=True)
    assert not build.stderr
    test = subprocess.run([str(binary), "--selftest"], capture_output=True, text=True, check=True)
    assert test.stdout == "SELFTEST: ok\n"
    reports, totals = [], Counter()
    for tag, inputs, captures, count, _, _ in inventories:
        operands = (root / inputs).read_text().lower().splitlines()
        assert len(operands) == count and all(len(op.split()) == 2 for op in operands)
        directory = output / tag
        directory.mkdir()
        counts, modes, verified = Counter(), {}, []
        with ExitStack() as stack:
            misses = zipped(stack, directory / "misses.jsonl.gz")
            changes = zipped(stack, directory / "changes.jsonl.gz")
            for mode, capture_path in captures.items():
                actual_lines = (root / capture_path).read_text().splitlines()
                assert len(actual_lines) == count
                mode_counts, examples = Counter(), []
                with ExitStack() as lane:
                    outputs_file = zipped(lane, directory / f"{mode}_candidate.stdout.gz")
                    hits_file = zipped(lane, directory / f"{mode}_hook_indicators.gz")
                    for start in range(0, count, 16384):
                        batch = operands[start:start + 16384]
                        baseline, _, _, _ = run(root / prior.PARENT / "baseline_O2", mode, batch, False)
                        values, indicators, raw, _ = run(binary, mode, batch, True)
                        outputs_file.write(raw.encode())
                        hits_file.write("".join(f"{start + index} {indicator}\n" for index, indicator in sorted(indicators.items())).encode())
                        for i, (operand, old, new) in enumerate(zip(batch, baseline, values)):
                            hardware, status = raw_hardware(actual_lines[start + i])
                            hit = i in indicators
                            assert hit or old == new, (tag, mode, start + i, "fallback changed")
                            known_c1 = (status >> 9) & 1 if status is not None else None
                            bad_c1 = hit and known_c1 is not None and indicators[i] != known_c1
                            prefix = "candidate" if hit else "fallback"
                            for counter in (counts, mode_counts, totals):
                                counter["raw_mode_row_appearances"] += 1
                                counter[prefix + "_rows"] += 1
                                counter[prefix + "_output_misses"] += new != hardware
                                counter["baseline_output_misses"] += old != hardware
                                if hit:
                                    counter["candidate_known_C1"] += known_c1 is not None
                                    counter["candidate_C1_misses"] += bad_c1
                                counter["output_changes"] += old != new
                            detail = {"bank": tag, "index": start + i, "instruction": "fcos", "mode": mode,
                                      "operand": operand, "hardware": hardware, "hardware_status": status,
                                      "baseline": old, "candidate": new, "candidate_hook_hit": hit,
                                      "known_C1": known_c1, "candidate_C1": indicators.get(i)}
                            if new != hardware or bad_c1:
                                misses.write((json.dumps(detail, sort_keys=True) + "\n").encode())
                            if old != new:
                                changes.write((json.dumps(detail, sort_keys=True) + "\n").encode())
                            if hit and len(examples) < 128:
                                examples.append(detail)
                    if examples:
                        selected = [r["operand"] for r in examples]
                        plain, traces, _ = candidate.run_batch(root / prior.PARENT / "candidate_O2", "fcos", mode, selected, True)
                        assert set(traces) == set(selected)
                        for detail, plain_result in zip(examples, plain):
                            trace = traces[detail["operand"]]
                            magnitude = candidate.trace_value(trace["magnitude"])
                            value = candidate.reference.rounding(magnitude, 64, 0)
                            assert value.fraction() == magnitude.fraction()
                            anchor = f"{value.e + 63 + 16383:04x} {value.n:016x}"
                            correction = candidate.reference.simplified_graph(anchor)["correction"]
                            endpoint, c1, _ = candidate.independent_signed_output(correction, bool(int(trace["neg"])), mode)
                            assert endpoint == plain_result == detail["candidate"] and c1 == detail["candidate_C1"]
                            verified.append(dict(detail, independent_anchor=anchor, independent_output=endpoint, independent_C1=c1))
                modes[mode] = dict(mode_counts)
                print(tag, mode, dict(mode_counts), flush=True)
        save(directory / "independent_checks.json", verified)
        report = {"bank": tag, "complete": True, "counts": dict(counts), "modes": modes,
                  "independent_checks": len(verified), "sha256": {p.name: digest(p) for p in sorted(directory.iterdir()) if p.is_file()}}
        save(directory / "report.json", report)
        reports.append(report)
    for relative, expected in evidence.items():
        assert digest(root / relative) == expected, "changed source: " + relative
    assert digest(root / "src/fsincos_skylake.c") == candidate.LOCKS["src/fsincos_skylake.c"]
    result = {"experiment": "h1620_heterogeneous_candidate_audit_v2", "counts": dict(totals), "banks": reports,
              "status": "CANDIDATE_FALSIFIED" if totals["candidate_output_misses"] or totals["candidate_C1_misses"] else "CACHED_CANDIDATE_DOMAIN_PASS_NOT_CLOSURE",
              "canonical_source_unchanged": True, "hardware_execution": "none", "private_ledger_access": "none", "selector_promotion": "none",
              "claim_boundary": "All listed actual raw FCOS rows scored; only indexed hook hits validate candidate arithmetic. Fallback exactness does not extend the candidate domain. C1 is an arithmetic indicator, not full status. Counts are bank/mode appearances, not cross-bank unique tuples. Missing status stays unknown; no mode is inferred.",
              "source_instrumentation": {"audit_include": INCLUDE, "batch_anchor": ROW_ANCHOR},
              "sha256": {"script": digest(Path(__file__)), "binary": digest(binary), "evidence": evidence,
                         "in_memory_source": hashlib.sha256(source.encode()).hexdigest(), "prepared": digest(output / "prepared.json")}}
    save(output / "report.json", result)
    print(json.dumps({"status": result["status"], "counts": dict(totals)}, sort_keys=True))


if __name__ == "__main__":
    main()
