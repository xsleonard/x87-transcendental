#!/usr/bin/env python3
"""Isolated C implementation/transfer audit of the fixed H1617 candidate.

The canonical source stays unchanged. A hash-locked source string receives
one include and one default-off hook in memory and is compiled from stdin.
This is an experiment build, not a promotion. Only already-opened captures
are read; no remote host, hardware instruction or private ledger is used.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import random
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

import h1617_asymmetric_width_reduction as reference
from h1582_equality_frontier_reconciliation import checked_score


spec, V = reference.spec, reference.V
PARENT = "tmp/ledger33/current/h1616_independent_asymmetric_direct_audit"
LOCKS = {
    "src/fsincos_skylake.c": "0339a7d6161c29164232fadd46053a538b7163d5d4449889e3600e9245026f2b",
    PARENT+"/report.json": "51f70688d18c6fcc0aa524b9cbf8da9f631f5ea4a86079d7397173b1fd77e3c4",
    "tmp/ledger33/current/h1617_asymmetric_width_reduction/report.json":
        "38f763ecb098758c47475efaa1cd0877a0f4fe67a3c6f52d1a4498ed2d5cb6fa",
    "experiments/h1617_asymmetric_width_reduction.py":
        "179c24db05a6ca8935d7b5b86658ffd518de1a5ac43b0f6f13c92d7c72e7a97d",
}
ANCHOR = """static sf_t fsin_operation_class_polynomial(
    wv_t magnitude, int residual_sign, int64_t signed_n, sf_rc_t rc,
    int retain_cosine_product, int cos_gate_eligible)
{"""
HOOK = """
    /* H1618 isolated audit only; the original reduction/phase dispatch is
     * unchanged. Do not combine this graph with the legacy terminal selector. */
    if (G_H1618_ASYMMETRIC_COSINE
        && ((unsigned)signed_n & 1u) && h1618_cosine_scope(magnitude))
        return h1618_cosine(magnitude, ((unsigned)signed_n >> 1) & 1u, rc);
"""
CONFIGS = {
    "baseline_O2": (False, 0, ("-O2",)),
    "disabled_O2": (True, 0, ("-O2",)),
    "candidate_O0": (True, 1, ("-O0",)),
    "candidate_O2": (True, 1, ("-O2",)),
    "candidate_O3": (True, 1, ("-O3",)),
    "candidate_ubsan": (True, 1, ("-O2", "-fsanitize=undefined", "-fno-sanitize-recover=undefined")),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assembled_source(root: Path) -> tuple[str, str]:
    source = (root/"src/fsincos_skylake.c").read_text()
    assert digest(root/"src/fsincos_skylake.c") == LOCKS["src/fsincos_skylake.c"]
    assert source.count(ANCHOR) == 1
    changed = source.replace(ANCHOR, '#include "h1618_asymmetric_cosine.h"\n\n'+ANCHOR+HOOK)
    assert changed.replace('#include "h1618_asymmetric_cosine.h"\n\n'+ANCHOR+HOOK, ANCHOR) == source
    return source, changed


def save_gzip(path: Path, text: str) -> None:
    with path.open("xb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as stream:
        stream.write(text.encode())


def run_batch(binary: Path, instruction: str, mode: str, operands: list[str], trace: bool = False) -> tuple[list[str], dict[str, dict], str]:
    command = [str(binary), "--batch", "--"+instruction+"-standalone", "--rc="+mode]
    if trace:
        command.append("--dump-internals")
    result = subprocess.run(command, input="".join(op+"\n" for op in operands), text=True,
                            capture_output=True, check=True)
    lines = result.stdout.splitlines()
    assert len(lines) == len(operands)
    words = []
    for line in lines:
        if line == "C2":
            words.append(line)
        else:
            parts = line.lower().split()
            assert len(parts) == 3 and parts[0] == "ok", line
            words.append(parts[1]+":"+parts[2])
    assert "runtime error:" not in result.stderr and "UndefinedBehaviorSanitizer" not in result.stderr
    if not trace:
        assert not result.stderr, result.stderr[:1024]
        return words, {}, result.stdout
    current, traces, selected = None, {}, []
    for line in result.stderr.splitlines():
        if line.startswith("DI_IN "):
            current = " ".join(line.split()[1:])
            assert current in operands
        elif line.startswith("DI_H1618 "):
            assert current is not None and current not in traces
            traces[current] = dict(word.split("=", 1) for word in line.split()[1:])
            selected.extend(("DI_IN "+current, line))
    # Only the deterministic candidate diagnostic is retained; unrelated
    # legacy dumps (including ASLR return addresses) are not called raw traces.
    return words, traces, "\n".join(selected)+("\n" if selected else "")


def trace_value(value: str) -> V:
    sign, exponent, significand = value.split(":")
    return V((-1 if int(sign) else 1)*int(significand, 16), int(exponent))


def independent_signed_output(correction: V, neg: bool, mode: str) -> tuple[str, int, int]:
    magnitude = spec.exact_add(V(1, 0), correction)
    policy = {"rn": 1, "rz": 0, "rd": 3 if neg else 0, "ru": 0 if neg else 3}[mode]
    rounded = reference.rounding(magnitude, 64, policy)
    assert rounded.n > 0 and rounded.n.bit_length() == 64
    exponent = rounded.e+63+16383
    output = f"{exponent | (0x8000 if neg else 0):04x}:{rounded.n:016x}"
    magnitude_increment = int(rounded.fraction() > magnitude.fraction())
    numerical_increment = int((-1 if neg else 1)*rounded.fraction() > (-1 if neg else 1)*magnitude.fraction())
    return output, magnitude_increment, numerical_increment


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output_dir.resolve()
    assert not output.exists(), "refusing existing output directory"
    evidence = dict(LOCKS)
    for relative, expected in evidence.items():
        assert digest(root/relative) == expected, relative
    parent = json.loads((root/PARENT/"report.json").read_text())
    for relative, expected in parent["sha256"]["evidence"].items():
        assert digest(root/relative) == expected, relative
        assert evidence.get(relative, expected) == expected
        evidence[relative] = expected
    raw_relative = PARENT+"/independent_direct_replay.jsonl.gz"
    assert digest(root/raw_relative) == parent["sha256"]["independent_replay"]
    evidence[raw_relative] = parent["sha256"]["independent_replay"]
    truth, direct_stages, direct_c1 = {}, {}, {}
    with gzip.open(root/raw_relative, "rt") as stream:
        for line in stream:
            row = json.loads(line)
            direct_stages[row["operand"]] = row["stages"]
            for observed in row["observations"]:
                key = "fcos", observed["mode"], row["operand"]
                assert key not in truth
                truth[key] = observed["hardware"]
                if observed["known_C1"] is not None:
                    direct_c1[key] = observed["known_C1"]
    assert len(truth) == 150351 and len(direct_stages) == 37823 and len(direct_c1) == 27
    aliases = []
    for campaign, stem in (("h1570", "h1571_exact_preimage_transfer"), ("h1573", "h1574_signed_preimage_transfer")):
        aliases.extend(dict(row, campaign=campaign) for row in checked_score(root, campaign, stem, evidence))
    assert len(aliases) == 52
    for row in aliases:
        key = row["instruction"], row["mode"], row["operand"]
        assert key not in truth
        truth[key] = row["hardware"]
    original, candidate = assembled_source(root)
    header_relative = "experiments/h1618_asymmetric_cosine.h"
    evidence[header_relative] = digest(root/header_relative)
    output.mkdir(parents=True)
    compiler = subprocess.run(["cc", "--version"], text=True, capture_output=True, check=True).stdout
    with (output/"compiler.txt").open("x") as stream:
        stream.write(compiler)
    builds, values, artifacts = {}, {}, {}
    grouped = defaultdict(list)
    for instruction, mode, operand in sorted(truth):
        grouped[instruction, mode].append(operand)
    for name, (transformed, enabled, flags) in CONFIGS.items():
        binary = output/name
        command = ["cc", *flags, "-std=c11", "-DG_ROUND84=0", f"-DG_H1618_ASYMMETRIC_COSINE={enabled}",
                   "-I", str(root/"src"), "-I", str(root/"experiments"), "-x", "c", "-", "-lm", "-o", str(binary)]
        proc = subprocess.run(command, input=candidate if transformed else original, text=True, capture_output=True, check=True)
        assert not proc.stderr, proc.stderr
        selftest = subprocess.run([str(binary), "--selftest"], text=True, capture_output=True, check=True)
        assert selftest.stdout == "SELFTEST: ok\n" and not selftest.stderr
        observed_outputs = {}
        for (instruction, mode), operands in sorted(grouped.items()):
            outputs, _, stdout = run_batch(binary, instruction, mode, operands)
            path = output/f"{name}_{instruction}_{mode}.stdout.gz"
            save_gzip(path, stdout)
            artifacts[path.name] = digest(path)
            observed_outputs.update({(instruction, mode, operand): value for operand, value in zip(operands, outputs)})
        misses = [{"instruction": key[0], "mode": key[1], "operand": key[2], "hardware": truth[key], "predicted": value}
                  for key, value in sorted(observed_outputs.items()) if value != truth[key]]
        canonical = "".join(" ".join(key)+" "+value+"\n" for key, value in sorted(observed_outputs.items()))
        values[name] = observed_outputs
        builds[name] = {"flags": list(flags), "candidate_enabled": bool(enabled), "rows": len(observed_outputs),
                        "output_misses": len(misses), "misses": misses, "binary_sha256": digest(binary),
                        "ordered_output_sha256": hashlib.sha256(canonical.encode()).hexdigest(), "selftest": "PASS"}
        print(name, "rows", len(observed_outputs), "misses", len(misses), flush=True)
    assert values["disabled_O2"] == values["baseline_O2"]
    assert all(values[name] == values["candidate_O2"] for name in CONFIGS if name.startswith("candidate"))

    stage_checks = direct_endpoint_checks = direct_C1_checks = 0
    positive_operands = sorted(direct_stages)
    outputs, traces, selected = run_batch(output/"candidate_O2", "fcos", "rn", positive_operands, True)
    assert set(traces) == set(positive_operands), "a direct success must not come from fallback"
    trace_path = output/"candidate_direct_selected_trace.gz"
    save_gzip(trace_path, selected)
    artifacts[trace_path.name] = digest(trace_path)
    for operand, actual in zip(positive_operands, outputs):
        trace = traces[operand]
        assert trace["neg"] == "0" and trace_value(trace["magnitude"]).fraction() == spec.decode_external(operand).fraction()
        for stage, expected in direct_stages[operand].items():
            assert trace_value(trace[stage]).fraction() == reference.verified.independent.from_record(expected).fraction()
            stage_checks += 1
        correction = trace_value(trace["correction"])
        assert independent_signed_output(correction, False, "rn")[0] == actual
        direct_endpoint_checks += 1
        for mode in spec.MODES:
            key = "fcos", mode, operand
            if key in direct_c1:
                assert independent_signed_output(correction, False, mode)[1] == direct_c1[key]
                direct_C1_checks += 1
    alias_details, alias_counts = [], Counter()
    alias_groups = defaultdict(list)
    for row in aliases:
        alias_groups[row["instruction"], row["mode"]].append(row)
    for (instruction, mode), rows in sorted(alias_groups.items()):
        operands = [row["operand"] for row in rows]
        outputs, traces, selected = run_batch(output/"candidate_O2", instruction, mode, operands, True)
        path = output/f"aliases_{instruction}_{mode}_selected_trace.gz"
        save_gzip(path, selected)
        artifacts[path.name] = digest(path)
        for row, actual in zip(rows, outputs):
            key = instruction, mode, row["operand"]
            assert values["baseline_O2"][key] == row["baseline"]
            hit = row["operand"] in traces
            detail = {"campaign": row["campaign"], "case_id": row["case_id"], "instruction": instruction,
                      "mode": mode, "operand": row["operand"], "anchor": row["anchor"], "hardware": row["hardware"],
                      "baseline": values["baseline_O2"][key], "candidate": actual, "candidate_hook_hit": hit,
                      "hardware_status": row["hardware_status"]}
            alias_counts["observed_rows"] += 1
            alias_counts["candidate_hits"] += hit
            alias_counts["output_exact"] += actual == row["hardware"]
            alias_counts["baseline_misses"] += values["baseline_O2"][key] != row["hardware"]
            if hit:
                trace = traces[row["operand"]]
                anchor = spec.decode_external(row["anchor"])
                anchor = V(abs(anchor.n), anchor.e)
                assert trace_value(trace["magnitude"]).fraction() == anchor.fraction()
                expected_stages = reference.simplified_graph(row["anchor"])
                for name, expected in expected_stages.items():
                    assert trace_value(trace[name]).fraction() == expected.fraction()
                    stage_checks += 1
                neg = bool(int(trace["neg"]))
                expected, magnitude_C1, numerical_C1 = independent_signed_output(expected_stages["correction"], neg, mode)
                assert expected == actual
                known_C1 = (int(row["hardware_status"], 16) >> 9) & 1
                detail.update(output_negative=neg, independent_output=expected, known_C1=known_C1,
                              ordinary_magnitude_increment=magnitude_C1, ordinary_numerical_increment=numerical_C1,
                              magnitude_C1_matches=known_C1 == magnitude_C1, numerical_C1_matches=known_C1 == numerical_C1)
                alias_counts["magnitude_C1_matches"] += known_C1 == magnitude_C1
                alias_counts["numerical_C1_matches"] += known_C1 == numerical_C1
            alias_details.append(detail)
    assert alias_counts["candidate_hits"] == 52, "do not claim transfer from a fallback success"

    # Guard/fallback parity is software-only. These are not hardware labels.
    rng = random.Random(0x1618)
    software_ops = {f"{se:04x} {rng.randrange(1 << 63, 1 << 64):016x}"
                    for se in (0x3ffb, 0x3ffc, 0x3ffd, 0x3fff, 0x4001, 0x4020, 0xbffb, 0xbffc, 0xbffd, 0xc001)
                    for _ in range(32)}
    software_ops.update(("0000 0000000000000000", "8000 0000000000000000", "7fff 8000000000000000",
                         "ffff 8000000000000000", "7fff c000000000000001", "3fff 0000000000000001",
                         "403e 8000000000000000", "0000 8000000000000000", "0000 0000000000000001"))
    software_ops = sorted(software_ops)
    soft = Counter()
    for instruction in ("fsin", "fcos"):
        for mode in spec.MODES:
            baseline, _, _ = run_batch(output/"baseline_O2", instruction, mode, software_ops)
            candidate_outputs, traces, _ = run_batch(output/"candidate_ubsan", instruction, mode, software_ops, True)
            for operand, previous, new in zip(software_ops, baseline, candidate_outputs):
                soft["rows"] += 1
                if operand not in traces:
                    assert previous == new
                    soft["outside_hook_equal"] += 1
                else:
                    soft["hook_hits_not_hardware_observations"] += 1
    result = {"experiment": "h1618_isolated_cosine_transfer", "candidate_status": "CACHED_OUTPUT_PASS_NOT_CLOSURE"
              if not builds["candidate_O2"]["misses"] else "FALSIFIED_ON_CACHED_OUTPUTS",
        "canonical_source_unchanged": digest(root/"src/fsincos_skylake.c") == LOCKS["src/fsincos_skylake.c"],
        "hardware_execution": "none", "private_ledger_access": "none", "selector_promotion": "none",
        "direct_observed_rows": 150351, "alias_observed_rows": len(aliases), "unique_observed_rows": len(truth),
        "builds": builds, "disabled_hook_matches_baseline": True, "candidate_builds_identical": True,
        "C_independent_stage_equalities": stage_checks, "direct_RN_software_endpoint_equalities": direct_endpoint_checks,
        "direct_known_C1_checks": direct_C1_checks, "aliases": alias_details, "alias_counts": dict(alias_counts),
        "software_guard_checks": dict(soft),
        "source_transformation": {"anchor": ANCHOR, "inserted_hook": HOOK, "included_header": header_relative,
            "source_sha256_before": hashlib.sha256(original.encode()).hexdigest(),
            "source_sha256_after_in_memory": hashlib.sha256(candidate.encode()).hexdigest(), "compiled_from_stdin_no_canonical_edit": True},
        "claim_boundary": "Only cosine polynomial branches with exponent -3 and numerical input precision<=64 use the candidate. The rest is incumbent fallback, not validation of new arithmetic there. Cached transfers are not fresh validation. Ordinary C1 indicators are compared to observations, not a full status implementation.",
        "sha256": {"script": digest(Path(__file__)), "compiler": digest(output/"compiler.txt"), "evidence": evidence, "artifacts": artifacts}}
    with (output/"report.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": result["candidate_status"], "alias_counts": result["alias_counts"],
                      "C_stage_checks": stage_checks, "software_guard_checks": dict(soft)}, sort_keys=True))


if __name__ == "__main__":
    main()
