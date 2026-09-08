#!/usr/bin/env python3
"""Audit the fixed H1618 graph on complete, already-recorded stage-A banks.

Only software executes. All raw sources are hashed before scoring. The
historical sorted-unique tie-input reconstruction is checked strictly, and
only actual RN/RD/RU streams are scored. Counts across banks are appearances,
not assertions of distinct observations or fresh validation. Stop after a
complete falsifying bank, preserving its full outputs and all misses.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
import os
import random
import subprocess
from collections import Counter
from contextlib import ExitStack
from pathlib import Path

import h1618_isolated_cosine_transfer as candidate


BANKS = {"comb": 531422, "comb3": 1275000, "comb4": 1812250,
         "comb5": 274594, "comb6": 1694649, "comb7": 1947982,
         "comb8": 4645447, "comb9": 6616333}
MODES = ("rn", "rd", "ru")
PARENT = "tmp/ledger33/current/h1618_isolated_cosine_transfer"
LOCKS = {
    PARENT + "/report.json": "b184f29cb7534c6e667f1780b6fdca6a7bb0e52d368e5891700391ff54910112",
    "experiments/h1618_isolated_cosine_transfer.py": "bb321f62daa8d06168bbd3ee6e872f25afe370fe51f14676c63a574141cb4d19",
    "experiments/h1618_asymmetric_cosine.h": "df5a4b9114c0a754a68274d29c1252257c449af34f68769c6e5f83b85584c6cf",
    "experiments/h1204_cached_comb_r1200_score.py": "3aa560cac578a8d7d6487c85238fe18e1184ce2ae8b902a3a7a0833eef5ea174",
    "tmp/ledger33/current/h1377_x67y64_attached_stageA_score.txt": "289639149535db1a99d8ef3dad3cc4c7e8d05bde6b9dbfff28ff7c42c8d92ada",
}
AUDIT_INCLUDE = r'''
#include <assert.h>
/* H1619 observes only the candidate's final round. Return exactly the
 * original result; the diagnostic is not an architectural status model. */
static sf_t h1619_observe_final(u256 before, int32_t scale, int neg, sf_rc_t rc)
{
    sf_t result = acc_round64_rc(before, scale, neg, rc);
    assert(!(before.hi >> 127));
    assert(result.cls == SF_FIN && result.sig);
    assert(result.exp - 63 >= scale && result.exp - 63 - scale < 128);
    u256 stored_magnitude = {0, 0};
    acc_add_product(&stored_magnitude, 0, result.sig, 1, result.exp - 63, scale);
    int increment = stored_magnitude.hi > before.hi
        || (stored_magnitude.hi == before.hi && stored_magnitude.lo > before.lo);
    fputc('0' + increment, stderr);
    return result;
}
#define acc_round64_rc h1619_observe_final
#include "h1618_asymmetric_cosine.h"
#undef acc_round64_rc
'''


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def json_save(path: Path, value) -> None:
    with path.open("x") as target:
        json.dump(value, target, indent=2, sort_keys=True)
        target.write("\n")


def zipped(stack: ExitStack, path: Path):
    raw = stack.enter_context(path.open("xb"))
    return stack.enter_context(gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0))


def run(binary: Path, mode: str, operands: list[str], observe: bool):
    proc = subprocess.run([str(binary), "--batch", "--fcos-standalone", "--rc=" + mode],
                          input="".join(op + "\n" for op in operands), text=True,
                          capture_output=True, check=True)
    lines = proc.stdout.splitlines()
    assert len(lines) == len(operands)
    outputs = []
    for line in lines:
        words = line.split()
        assert len(words) == 3 and words[0] == "OK" and words[1] == "3ffe", line
        outputs.append(words[1] + ":" + words[2])
    if observe:
        # One diagnostic per row proves every row used the candidate, rather
        # than an incumbent fallback path. Other diagnostics are fatal.
        assert len(proc.stderr) == len(operands) and set(proc.stderr) <= {"0", "1"}
    else:
        assert not proc.stderr
    return outputs, proc.stderr, proc.stdout


def reconstruct(source: Path, output: Path, expected: int) -> tuple[Path, dict]:
    raw, ordered = output / "unsorted_inputs.txt", output / "inputs.txt"
    tie_rows = 0
    with source.open() as stream, raw.open("x") as target:
        for line in stream:
            fields = line.split()
            if not fields:
                continue
            word = fields[0].lower()
            assert len(word) == 16 and (1 << 63) <= int(word, 16) < (1 << 64)
            target.write("3ffc " + word + "\n")
            tie_rows += 1
    environment = dict(os.environ, LC_ALL="C")
    with ordered.open("x") as target:
        subprocess.run(["sort", "-u", str(raw)], stdout=target, env=environment, check=True)
    count, previous = 0, ""
    with ordered.open() as stream:
        for line in stream:
            assert line > previous and line.startswith("3ffc ") and len(line) == 22
            previous, count = line, count + 1
    assert count == expected, (source, count, expected)
    return ordered, {"tie_rows": tie_rows, "unique_bank_operands": count,
                     "input_sha256": digest(ordered), "raw_derived_input_sha256": digest(raw),
                     "domain": "positive normal direct FCOS, external64, exponent -3"}


def independent(operand: str, mode: str):
    correction = candidate.reference.simplified_graph(operand)["correction"]
    return candidate.independent_signed_output(correction, False, mode)[:2]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--banks", nargs="+", choices=list(BANKS), default=list(BANKS))
    parser.add_argument("--batch-size", type=int, default=32768)
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output_dir.resolve()
    assert not output.exists() and args.batch_size > 0 and len(set(args.banks)) == len(args.banks)
    evidence = dict(LOCKS)
    for name, expected in evidence.items():
        assert digest(root / name) == expected, name
    parent = json.loads((root / PARENT / "report.json").read_text())
    for name, expected in parent["sha256"]["evidence"].items():
        assert digest(root / name) == expected, name
        assert evidence.get(name, expected) == expected
        evidence[name] = expected
    for name in ("baseline_O2", "candidate_O2"):
        assert digest(root / PARENT / name) == parent["builds"][name]["binary_sha256"]
    # Read-only historical capture scripts are provenance, never commands to run.
    for filename in ("run_scan5.sh", "run_scan6.sh", "run_scan7.sh", "run_scan8.sh", "run_scan9.sh", "run_scan10.sh"):
        relative = "stageA/" + filename
        evidence[relative] = digest(root / relative)
    for bank in args.banks:
        for filename in (f"ties_{bank}.txt", *(f"{bank}_{mode}_status.txt" for mode in MODES)):
            relative = "stageA/" + filename
            evidence[relative] = digest(root / relative)
    original, source = candidate.assembled_source(root)
    include = '#include "h1618_asymmetric_cosine.h"'
    assert source.count(include) == 1
    source = source.replace(include, AUDIT_INCLUDE)
    output.mkdir(parents=True)
    source_hash = hashlib.sha256(source.encode()).hexdigest()
    json_save(output / "prepared.json", {"state": "SOFTWARE_AUDIT_PREPARED_NOT_COMPLETE", "banks": args.banks,
              "hardware_execution": "none", "private_ledger_access": "none", "source_sha256": source_hash,
              "sha256": {"script": digest(Path(__file__)), "evidence": evidence}})
    binary = output / "candidate_observed"
    command = ["cc", "-O2", "-std=c11", "-DG_ROUND84=0", "-DG_H1618_ASYMMETRIC_COSINE=1",
               "-I", str(root / "src"), "-I", str(root / "experiments"), "-x", "c", "-", "-lm", "-o", str(binary)]
    build = subprocess.run(command, input=source, text=True, capture_output=True, check=True)
    assert not build.stderr
    test = subprocess.run([str(binary), "--selftest"], capture_output=True, text=True, check=True)
    assert test.stdout == "SELFTEST: ok\n" and set(test.stderr) <= {"0", "1"}
    rng = random.Random(0x1619)
    preflight = sorted({"3ffc 8000000000000000", "3ffc ffffffffffffffff"}
                       | {f"3ffc {rng.randrange(1 << 63, 1 << 64):016x}" for _ in range(128)})
    for mode in candidate.spec.MODES:
        observed, indicators, _ = run(binary, mode, preflight, True)
        plain, _, _ = run(root / PARENT / "candidate_O2", mode, preflight, False)
        assert observed == plain
        for operand, endpoint, indicator in zip(preflight, observed, indicators):
            assert (endpoint, int(indicator)) == independent(operand, mode)
    reports, total = [], Counter()
    for bank in args.banks:
        directory = output / bank
        directory.mkdir()
        inputs, reconstruction = reconstruct(root / "stageA" / f"ties_{bank}.txt", directory, BANKS[bank])
        print(bank, "reconstructed", BANKS[bank], flush=True)
        counts, mode_reports, independent_replays = Counter(), {}, []
        stride = max(1, BANKS[bank] // 1024)
        with ExitStack() as stack:
            changes = zipped(stack, directory / "changes.jsonl.gz")
            misses = zipped(stack, directory / "misses.jsonl.gz")
            for mode in MODES:
                mode_counts, ordered_baseline = Counter(), hashlib.sha256()
                with ExitStack() as lane:
                    capture = lane.enter_context((root / "stageA" / f"{bank}_{mode}_status.txt").open())
                    stream = lane.enter_context(inputs.open())
                    stored_outputs = zipped(lane, directory / f"{mode}_candidate.stdout.gz")
                    stored_c1 = zipped(lane, directory / f"{mode}_candidate.c1.gz")
                    offset = 0
                    while operands := [line.strip() for line in itertools.islice(stream, args.batch_size)]:
                        baseline, _, baseline_raw = run(root / PARENT / "baseline_O2", mode, operands, False)
                        values, indicators, raw = run(binary, mode, operands, True)
                        ordered_baseline.update(baseline_raw.encode())
                        stored_outputs.write(raw.encode())
                        stored_c1.write(indicators.encode())
                        for index, (operand, old, new, indicator) in enumerate(zip(operands, baseline, values, indicators), offset):
                            fields = capture.readline().split()
                            assert len(fields) == 5 and fields[0] == "OK" and fields[3] == "SW", (bank, mode, index)
                            hardware = fields[1].lower() + ":" + fields[2].lower()
                            sw = int(fields[4], 16)
                            assert 0 <= sw <= 0xffff and fields[1].lower() == "3ffe"
                            known_c1, predicted_c1 = (sw >> 9) & 1, int(indicator)
                            bad_output, bad_c1 = new != hardware, predicted_c1 != known_c1
                            classification = "unchanged" if old == new else "fix" if not bad_output else "regression" if old == hardware else "changed_both_wrong"
                            for counter in (counts, mode_counts, total):
                                counter["raw_mode_row_appearances"] += 1
                                counter["candidate_hook_hits"] += 1
                                counter["baseline_output_misses"] += old != hardware
                                counter["candidate_output_misses"] += bad_output
                                counter["candidate_C1_misses"] += bad_c1
                                counter["classification_" + classification] += 1
                            detail = {"corpus": bank, "index": index, "instruction": "fcos", "mode": mode,
                                      "operand": operand, "hardware": hardware, "hardware_status": fields[4].lower(),
                                      "baseline": old, "candidate": new, "candidate_C1": predicted_c1,
                                      "known_C1": known_c1, "classification": classification,
                                      "output_miss": bad_output, "C1_miss": bad_c1}
                            if old != new:
                                changes.write((json.dumps(detail, sort_keys=True) + "\n").encode())
                            if bad_output or bad_c1:
                                misses.write((json.dumps(detail, sort_keys=True) + "\n").encode())
                            # Uniform index samples are fixed independently of labels.
                            # Additionally independently verify the first 256 miss rows.
                            if index % stride == 0 or index == BANKS[bank] - 1 or ((bad_output or bad_c1) and len(independent_replays) < 256):
                                independent_output, independent_c1 = independent(operand, mode)
                                assert (new, predicted_c1) == (independent_output, independent_c1)
                                independent_replays.append(dict(detail, independent_output=independent_output,
                                                                independent_C1=independent_c1))
                        offset += len(operands)
                        if offset % (args.batch_size * 8) == 0:
                            print(bank, mode, offset, dict(mode_counts), flush=True)
                    assert offset == BANKS[bank] and not capture.readline()
                mode_reports[mode] = {"counts": dict(mode_counts), "baseline_stdout_sha256": ordered_baseline.hexdigest()}
                print(bank, mode, "COMPLETE", dict(mode_counts), flush=True)
        json_save(directory / "independent_replays.json", independent_replays)
        artifacts = {p.name: digest(p) for p in sorted(directory.iterdir()) if p.is_file()}
        bank_report = {"bank": bank, "complete": True, "input_reconstruction": reconstruction,
                       "counts": dict(counts), "mode_reports": mode_reports,
                       "independent_sample_checks": len(independent_replays), "artifacts": artifacts}
        json_save(directory / "report.json", bank_report)
        reports.append(bank_report)
        if counts["candidate_output_misses"] or counts["candidate_C1_misses"]:
            print("STOP_AFTER_COMPLETE_FALSIFYING_BANK", bank, flush=True)
            break
    for relative, expected in evidence.items():
        assert digest(root / relative) == expected, "source changed during audit: " + relative
    assert digest(root / "src/fsincos_skylake.c") == candidate.LOCKS["src/fsincos_skylake.c"]
    result = {"experiment": "h1619_raw_stagea_candidate_audit", "counts": dict(total),
              "status": "FALSIFIED_ON_RAW_OUTPUTS" if total["candidate_output_misses"] else
                        "OUTPUT_PASS_C1_FALSIFIED" if total["candidate_C1_misses"] else "CACHED_RAW_PASS_NOT_CLOSURE",
              "requested_banks": args.banks, "completed_banks": [r["bank"] for r in reports], "banks": reports,
              "preflight_independent_output_C1_checks": len(preflight) * len(candidate.spec.MODES),
              "hardware_execution": "none", "private_ledger_access": "none", "canonical_source_unchanged": True,
              "selector_promotion": "none", "audit_include": AUDIT_INCLUDE,
              "claim_boundary": "Bank totals are raw row appearances, not deduplicated across banks. Actual RN/RD/RU only; no RZ imputation. All rows hit the exact fixed candidate. C1 magnitude increment is an observed arithmetic indicator, not complete architectural status. Historical near-tie selection, inherited Skylake attribution, not fresh or unbiased validation.",
              "sha256": {"script": digest(Path(__file__)), "binary": digest(binary), "in_memory_source": source_hash,
                         "prepared": digest(output / "prepared.json"), "evidence": evidence}}
    json_save(output / "report.json", result)
    print(json.dumps({"status": result["status"], "counts": dict(total), "completed": result["completed_banks"]}, sort_keys=True))


if __name__ == "__main__":
    main()
