#!/usr/bin/env python3
"""Independently rescore preserved H1619 output/C1 streams against raw captures.

No producer/parser/arithmetic imports and no model execution. This verifies
source/artifact hashes, input order, row alignment and every reported output
and C1 match. It is a scoring verifier, not a silicon-correctness proof.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
from pathlib import Path


PREPARED_SHA = "5dac6bd6c624ab05a87ddebede9fa5be271591c06832ebfa60fd1f0a7c21ff1f"


def sha(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def indicators(stream):
    for block in iter(lambda: stream.read(65536), b""):
        yield from block


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    assert not args.output.exists()
    assert sha(args.audit / "prepared.json") == PREPARED_SHA
    prepared = json.loads((args.audit / "prepared.json").read_text())
    result = json.loads((args.audit / "report.json").read_text())
    assert result["sha256"]["prepared"] == PREPARED_SHA
    assert result["sha256"]["evidence"] == prepared["sha256"]["evidence"]
    for relative, expected in result["sha256"]["evidence"].items():
        assert sha(args.root / relative) == expected, relative
    rows = output_misses = c1_misses = 0
    banks = []
    for bank in result["banks"]:
        directory = args.audit / bank["bank"]
        assert json.loads((directory / "report.json").read_text()) == bank
        for name, expected in bank["artifacts"].items():
            assert sha(directory / name) == expected, (bank["bank"], name)
        lane_reports = {}
        for mode in ("rn", "rd", "ru"):
            count = bad_output = bad_c1 = 0
            previous = ""
            with (directory / "inputs.txt").open() as inputs, \
                    (args.root / "stageA" / f"{bank['bank']}_{mode}_status.txt").open() as hardware, \
                    gzip.open(directory / f"{mode}_candidate.stdout.gz", "rt") as predictions, \
                    gzip.open(directory / f"{mode}_candidate.c1.gz", "rb") as predicted_c1:
                for operand, actual, prediction, bit in itertools.zip_longest(inputs, hardware, predictions, indicators(predicted_c1)):
                    assert all(x is not None for x in (operand, actual, prediction, bit)), (bank["bank"], mode, count)
                    assert len(operand) == 22 and operand.startswith("3ffc ") and operand > previous
                    assert (1 << 63) <= int(operand[5:21], 16) < (1 << 64)
                    previous = operand
                    assert len(actual) == 33 and actual.startswith("OK 3ffe ") and actual[24:28] == " SW "
                    assert len(prediction) == 25 and prediction.startswith("OK 3ffe ")
                    assert bit in (48, 49)
                    bad_output += prediction != actual[:24] + "\n"
                    bad_c1 += bit - 48 != ((int(actual[28:32], 16) >> 9) & 1)
                    count += 1
            expected = bank["mode_reports"][mode]["counts"]
            assert count == bank["input_reconstruction"]["unique_bank_operands"] == expected["raw_mode_row_appearances"]
            assert count == expected["candidate_hook_hits"]
            assert bad_output == expected["candidate_output_misses"] and bad_c1 == expected["candidate_C1_misses"]
            rows += count
            output_misses += bad_output
            c1_misses += bad_c1
            lane_reports[mode] = {"rows": count, "output_misses": bad_output, "C1_misses": bad_c1}
            print(bank["bank"], mode, lane_reports[mode], flush=True)
        banks.append({"bank": bank["bank"], "lanes": lane_reports})
    assert rows == result["counts"]["raw_mode_row_appearances"]
    assert output_misses == result["counts"]["candidate_output_misses"]
    assert c1_misses == result["counts"]["candidate_C1_misses"]
    report = {"experiment": "h1619_verify_raw_streams", "verification_status": "PASS",
              "rows": rows, "output_misses": output_misses, "C1_misses": c1_misses, "banks": banks,
              "claim_boundary": "Independent exhaustive artifact scoring and alignment verification; no new arithmetic or hardware proof. Bank totals are appearances, not cross-bank unique tuples.",
              "sha256": {"script": sha(Path(__file__)), "audit_report": sha(args.audit / "report.json"), "prepared": PREPARED_SHA}}
    with args.output.open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps({"status": "PASS", "rows": rows, "output_misses": output_misses, "C1_misses": c1_misses}))


if __name__ == "__main__":
    main()
