#!/usr/bin/env python3
"""Reconcile the three H1620 cached baseline misses with the H1618 frontier.

Re-read the exact original input/status rows, independently evaluate the
fixed arithmetic, and check the expanded frontier across compiler builds.
This changes knowledge of the incumbent, not emulator defaults. No capture.
"""
from __future__ import annotations

import argparse
import gzip
import json
import subprocess
from pathlib import Path

import h1618_isolated_cosine_transfer as candidate


PARENT = "tmp/ledger33/current/h1618_isolated_cosine_transfer"
WIDER = "tmp/ledger33/current/h1620_heterogeneous_candidate_audit_v2"
LOCKS = {PARENT + "/report.json": "b184f29cb7534c6e667f1780b6fdca6a7bb0e52d368e5891700391ff54910112",
         WIDER + "/report.json": "7ea431b36610cd0c8b82cbe8edd6b3ec3b0df3abdfc55dc8038c56e568096b60"}
RAW = {"h110-sweep": ("capture-kit/inputs/sweep_inputs.txt", "capture-kit-captures/skylake-fsin-h110/sweep_fcos_ru_status.txt"),
       "h363": ("capture-kit/inputs/constraint_fcos_terminal_neighbors_h363.txt", "capture-kit-captures/skylake-fcos-h363/fcos_ru_status.txt")}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output_dir.resolve()
    assert not output.exists()
    evidence = dict(LOCKS)
    for relative, expected in evidence.items():
        assert candidate.digest(root / relative) == expected
    previous = json.loads((root / PARENT / "report.json").read_text())
    wider = json.loads((root / WIDER / "report.json").read_text())
    for report in (previous, wider):
        for relative, expected in report["sha256"]["evidence"].items():
            assert candidate.digest(root / relative) == expected
            evidence[relative] = expected
    key = lambda row: (row["instruction"], row["mode"], row["operand"])
    old = {key(r): dict(r, baseline=r["predicted"]) for r in previous["builds"]["baseline_O2"]["misses"]}
    assert len(old) == 75
    added, replays = [], []
    for bank in wider["banks"]:
        relative = WIDER + "/" + bank["bank"] + "/changes.jsonl.gz"
        assert candidate.digest(root / relative) == bank["sha256"]["changes.jsonl.gz"]
        evidence[relative] = bank["sha256"]["changes.jsonl.gz"]
        with gzip.open(root / relative, "rt") as stream:
            for line in stream:
                row = json.loads(line)
                assert row["candidate_hook_hit"] and row["candidate"] == row["hardware"] != row["baseline"]
                assert key(row) not in old and row["mode"] == "ru"
                input_path, capture_path = RAW[row["bank"]]
                assert (root / input_path).read_text().splitlines()[row["index"]].lower() == row["operand"]
                raw = (root / capture_path).read_text().splitlines()[row["index"]].lower().split()
                assert len(raw) == 5 and raw[0] == "ok" and raw[3] == "sw"
                assert raw[1] + ":" + raw[2] == row["hardware"] and int(raw[4], 16) == row["hardware_status"]
                se, sig = row["operand"].split()
                assert int(se, 16) & 0x7fff == 0x3ffc
                anchor = "3ffc " + sig
                stages = candidate.reference.simplified_graph(anchor)
                value, c1, _ = candidate.independent_signed_output(stages["correction"], False, row["mode"])
                assert value == row["hardware"] and c1 == (int(raw[4], 16) >> 9) & 1
                added.append(row)
                replays.append(dict(row, positive_cosine_anchor=anchor, independent_output=value,
                                    independent_C1=c1, independent_stages={name: v.record() for name, v in stages.items()}))
    assert len(added) == 3 and len({key(r) for r in added}) == 3
    union = dict(old)
    union.update({key(r): r for r in added})
    assert len(union) == 78 and len({k[2] for k in union}) == 77
    direct = [k for k in union if k[0] == "fcos" and k[2].startswith("3ffc ")]
    assert len(direct) == 47 and len({k[2] for k in direct}) == 46
    output.mkdir(parents=True)
    source = (root / "src/fsincos_skylake.c").read_text()
    assert candidate.digest(root / "src/fsincos_skylake.c") == candidate.LOCKS["src/fsincos_skylake.c"]
    builds = {"baseline_O2": root / PARENT / "baseline_O2"}
    for label, flags in (("baseline_O0", ["-O0"]), ("baseline_O3", ["-O3"]),
                         ("baseline_ubsan", ["-O2", "-fsanitize=undefined", "-fno-sanitize-recover=undefined"])):
        binary = output / label
        result = subprocess.run(["cc", *flags, "-std=c11", "-DG_ROUND84=0", "-I", str(root / "src"),
                                 "-x", "c", "-", "-lm", "-o", str(binary)], input=source, text=True, capture_output=True, check=True)
        assert not result.stderr
        test = subprocess.run([str(binary), "--selftest"], text=True, capture_output=True, check=True)
        assert test.stdout == "SELFTEST: ok\n" and not test.stderr
        builds[label] = binary
    for name in previous["builds"]:
        if name.startswith("candidate"):
            binary = root / PARENT / name
            assert candidate.digest(binary) == previous["builds"][name]["binary_sha256"]
            builds[name] = binary
    checked = {}
    groups = sorted({(instruction, mode) for instruction, mode, _ in union})
    for label, binary in builds.items():
        rows = []
        for instruction, mode in groups:
            keys = sorted(k for k in union if k[:2] == (instruction, mode))
            values, _, _ = candidate.run_batch(binary, instruction, mode, [k[2] for k in keys])
            for identity, value in zip(keys, values):
                expected = union[identity]["baseline"] if label.startswith("baseline") else union[identity]["hardware"]
                assert value == expected, (label, identity, value, expected)
                rows.append({"instruction": instruction, "mode": mode, "operand": identity[2], "output": value})
        checked[label] = {"rows": len(rows), "expected_matches": len(rows), "binary_sha256": candidate.digest(binary), "outputs": rows}
    report = {"experiment": "h1621_cached_frontier_extension", "status": "THREE_ADDITIONAL_CACHED_BASELINE_MISSES_FIXED_BY_CANDIDATE",
              "old_external_failing_rows": 75, "old_external_operands": 74,
              "external_failing_rows": 78, "external_operands": 77,
              "positive_direct_failing_rows": 47, "positive_direct_operands": 46,
              "additional_rows": replays, "build_checks": checked,
              "claim_boundary": "Three more cached external baseline misses beyond the H1618 bank; two positive residuals and one negative-input even-cosine alias. Not a new hardware campaign or a complete global miss census. The isolated fixed candidate repairs every reconciled row but is not promoted.",
              "hardware_execution": "none", "private_ledger_access": "none", "canonical_source_unchanged": True,
              "sha256": {"script": candidate.digest(Path(__file__)), "evidence": evidence}}
    with (output / "report.json").open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps({"status": report["status"], "external_rows": 78, "external_operands": 77,
                      "direct_rows": 47, "direct_operands": 46, "builds": len(builds)}, sort_keys=True))


if __name__ == "__main__":
    main()
