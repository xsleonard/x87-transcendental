#!/usr/bin/env python3
"""Build and independently verify a software-only challenge for fixed H1618.

Keep the candidate unchanged. Scan known-frontier neighborhoods, domain
edges, fixed-seed domain-wide samples and two old label-free proxy streams.
These are not yet fresh audited hardware tuples and no manifest is frozen.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import random
import subprocess
from collections import Counter
from pathlib import Path

import h1618_isolated_cosine_transfer as candidate


LOCKS = {
    "src/fsincos_skylake.c": "0339a7d6161c29164232fadd46053a538b7163d5d4449889e3600e9245026f2b",
    "experiments/h1618_asymmetric_cosine.h": "df5a4b9114c0a754a68274d29c1252257c449af34f68769c6e5f83b85584c6cf",
    "experiments/h1618_isolated_cosine_transfer.py": "bb321f62daa8d06168bbd3ee6e872f25afe370fe51f14676c63a574141cb4d19",
    "tmp/ledger33/current/h1621_cached_frontier_extension/report.json": "19b344095df1edb7e26b73c061571323a2e3b1d1f8fb3e19ba5c64b77da71688",
    "tmp/ledger33/current/h1579_equality_bank/bank.json": "db6e5a24a3fc653ee904982ca697211a2b2340eced01426d6280fb534b06c489",
    "tmp/ledger33/current/h1586_stream_control_plateaus/bank.json": "386db4b2d903aa0f13f70ea8cfefd8a1ddd0a601d9c215b3942600c60af5a75b",
}
OBSERVER = '''
static u256 h1622_pre;
static int h1622_scale, h1622_neg, h1622_final_calls;
static sf_t h1622_observe_final(u256 before, int32_t scale, int neg, sf_rc_t rc)
{
    h1622_pre = before; h1622_scale = scale; h1622_neg = neg; ++h1622_final_calls;
    return acc_round64_rc(before, scale, neg, rc);
}
#define acc_round64_rc h1622_observe_final
#include "h1618_asymmetric_cosine.h"
#undef acc_round64_rc
'''


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output_dir.resolve()
    assert not output.exists()
    evidence = dict(LOCKS)
    for name, expected in evidence.items():
        assert digest(root / name) == expected, name
    frontier = json.loads((root / "tmp/ledger33/current/h1621_cached_frontier_extension/report.json").read_text())
    anchors = sorted({int(r["operand"].split()[1], 16) for r in frontier["build_checks"]["baseline_O2"]["outputs"]
                      if r["instruction"] == "fcos" and r["operand"].startswith("3ffc ")})
    assert len(anchors) == 46
    sources = []
    for origin, bank in ((3, "h1579_equality_bank"), (4, "h1586_stream_control_plateaus")):
        directory = root / "tmp/ledger33/current" / bank
        report = json.loads((directory / "bank.json").read_text())
        assert report["capture_state"] == "SOFTWARE_ONLY_NOT_FROZEN" and report["new_hardware_labels"] == "none"
        path = directory / "raw_proxy_preimages.tsv.gz"
        assert digest(path) == report["sha256"]["raw_gzip"]
        evidence[str(path.relative_to(root))] = digest(path)
        sources.append((origin, path, report))
    evidence["experiments/h1622_fixed_candidate_scanner_v2.c"] = digest(root / "experiments/h1622_fixed_candidate_scanner_v2.c")
    output.mkdir(parents=True)
    seen, origins = set(), Counter()
    inputs = output / "scan_inputs.txt"
    with inputs.open("x") as target:
        def emit(sig, origin, ordinal):
            if not (1 << 63) <= sig < (1 << 64) or sig in seen:
                return
            seen.add(sig)
            origins[origin] += 1
            target.write(f"3ffc {sig:016x} {origin} {ordinal}\n")
        for anchor_index, anchor in enumerate(anchors):
            for delta in range(-4096, 4097):
                emit(anchor + delta, 0, anchor_index * 8193 + delta + 4096)
        for i in range(256):
            emit((1 << 63) + i, 1, 2 * i)
            emit((1 << 64) - 1 - i, 1, 2 * i + 1)
        rng = random.Random(0x1622C06764)
        for i in range(131072):
            emit(rng.randrange(1 << 63, 1 << 64), 2, i)
        for origin, path, report in sources:
            raw_hash, count = hashlib.sha256(), 0
            with gzip.open(path, "rb") as stream:
                header = stream.readline(); raw_hash.update(header)
                names = header.decode().rstrip("\n").split("\t")
                for i, line in enumerate(stream):
                    raw_hash.update(line)
                    row = dict(zip(names, line.decode().rstrip("\n").split("\t")))
                    se, word = row["operand"].split()
                    assert se == "3ffc"
                    emit(int(word, 16), origin, i); count += 1
            assert raw_hash.hexdigest() == report["sha256"]["raw_uncompressed"]
            assert count == report["counts"]["raw_preimages"]
    original, source = candidate.assembled_source(root)
    include = '#include "h1618_asymmetric_cosine.h"'
    assert source.count(include) == 1
    prefix = 'static int h1622_enabled;\n#define G_H1618_ASYMMETRIC_COSINE h1622_enabled\n#define main h1622_original_main\n'
    source = prefix + source.replace(include, OBSERVER) + '\n#undef main\n' + (root / "experiments/h1622_fixed_candidate_scanner_v2.c").read_text()
    binary = output / "scanner"
    proc = subprocess.run(["cc", "-O2", "-std=c11", "-DG_ROUND84=0", "-I", str(root / "src"),
                           "-I", str(root / "experiments"), "-x", "c", "-", "-lm", "-o", str(binary)],
                          input=source, text=True, capture_output=True, check=True)
    assert not proc.stderr, proc.stderr
    prepared = {"state": "SOFTWARE_SCAN_PREPARED_NOT_FROZEN", "unique_scan_inputs": len(seen),
                "origin_counts": dict(origins), "seed": "0x1622c06764", "radius": 4096,
                "selection": "all model separators; at most four uniform-sample agreement controls per fourth-cut/square-low3/final-edge cell; every4096th uniform sample; first16 domain-edge ordinals",
                "sha256": {"script": digest(Path(__file__)), "inputs": digest(inputs), "binary": digest(binary),
                           "in_memory_source": hashlib.sha256(source.encode()).hexdigest(), "evidence": evidence}}
    with (output / "prepared.json").open("x") as target:
        json.dump(prepared, target, indent=2, sort_keys=True); target.write("\n")
    events = output / "events.tsv"
    print(json.dumps({"prepared_inputs": len(seen), "origins": dict(origins)}, sort_keys=True), flush=True)
    with inputs.open("rb") as stream, events.open("xb") as target, (output / "scanner.stderr").open("xb") as errors:
        subprocess.run([str(binary)], stdin=stream, stdout=target, stderr=errors, check=True)
    rows = list(csv.DictReader(events.open(), delimiter="\t"))
    assert len({r["operand"] for r in rows}) == len(rows)
    operands = [r["operand"] for r in rows]
    models = root / "tmp/ledger33/current/h1618_isolated_cosine_transfer"
    parent = json.loads((models / "report.json").read_text())
    for name in ("baseline_O2", "candidate_O0", "candidate_O2", "candidate_O3", "candidate_ubsan"):
        assert digest(models / name) == parent["builds"][name]["binary_sha256"]
        for mode in candidate.spec.MODES:
            values, _, _ = candidate.run_batch(models / name, "fcos", mode, operands)
            for row, value in zip(rows, values):
                assert row[("baseline_" if name.startswith("baseline") else "candidate_") + mode] == value
    checked = []
    for row in rows:
        stages = candidate.reference.simplified_graph(row["operand"])
        assert int(row["square_low3"]) == (stages["square"].n & 7)
        assert int(row["fourth_cut"]) == (stages["square"].n ** 2).bit_length() - 67
        raw_pre = int(row["pre_significand"], 16)
        assert int(row["final_shift"]) == raw_pre.bit_length() - 64
        assert int(row["final_remainder"]) == raw_pre % (1 << int(row["final_shift"]))
        pre = candidate.spec.exact_add(candidate.V(1, 0), stages["correction"])
        assert pre.fraction() == candidate.V(int(row["pre_significand"], 16), int(row["pre_scale"])).fraction()
        changed = 0
        for i, mode in enumerate(candidate.spec.MODES):
            value, c1, _ = candidate.independent_signed_output(stages["correction"], False, mode)
            assert value == row["candidate_" + mode] and str(c1) == row["C1_bits"][i]
            if value != row["baseline_" + mode]: changed |= 1 << i
        assert changed == int(row["changed_mask"])
        checked.append(dict(row, independently_verified=True))
    result = {"experiment": "h1622_fixed_candidate_challenge_bank_v2", "capture_state": "SOFTWARE_ONLY_NOT_FROZEN",
              "hardware_execution": "none", "private_ledger_access": "none", "candidate_changed": False,
              "unique_scan_inputs": len(seen), "events": checked, "event_counts": dict(Counter(r["kind"] for r in rows)),
              "origin_counts": dict(origins), "independent_mode_checks": 4 * len(rows),
              "claim_boundary": "Proposals only: repository/private freshness audit and prediction freeze are still required. Old proxy streams are reused label-free software inputs; their capture subsets are not assumed fresh.",
              "sha256": {"prepared": digest(output / "prepared.json"), "events": digest(events), "scanner_log": digest(output / "scanner.stderr"), "evidence": evidence}}
    with (output / "bank.json").open("x") as target:
        json.dump(result, target, indent=2, sort_keys=True); target.write("\n")
    assert digest(root / "src/fsincos_skylake.c") == LOCKS["src/fsincos_skylake.c"]
    print(json.dumps({"inputs": len(seen), "events": result["event_counts"], "independent_mode_checks": result["independent_mode_checks"]}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
