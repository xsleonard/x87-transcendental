#!/usr/bin/env python3
"""Independently rescore H1624 and extend the incumbent's observed frontier.

No candidate, freezer, scorer or prior arithmetic/parser modules are imported.
A separate Fraction implementation evaluates the complete fixed graph.
Only existing capture files are read; the eight replays below are software.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from collections import Counter
from fractions import Fraction
from pathlib import Path


LOCKS = {
    "src/fsincos_skylake.c": "0339a7d6161c29164232fadd46053a538b7163d5d4449889e3600e9245026f2b",
    "transfer-tests/h1624/FREEZE.json": "8683d8b34c7b7c7089081cc6fcf3dd90a484c2b61942d679a507ea41c5bc7d4d",
    "tmp/ledger33/current/h1625_fixed_candidate_score/report.json": "ef2624cdbcb0fbf277d306ef21becc510e043e19b78a4e29e4eadf4aeccf39bf",
    "tmp/ledger33/current/h1621_cached_frontier_extension/report.json": "19b344095df1edb7e26b73c061571323a2e3b1d1f8fb3e19ba5c64b77da71688",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dyadic(n: int, exponent: int) -> Fraction:
    return Fraction(n << exponent) if exponent >= 0 else Fraction(n, 1 << -exponent)


def exponent(value: Fraction) -> int:
    assert value > 0 and value.denominator & (value.denominator - 1) == 0
    return value.numerator.bit_length() - value.denominator.bit_length()


def rounding(value: Fraction, bits: int, mode: str) -> tuple[Fraction, bool]:
    assert mode in ("chop", "rn", "ru")
    if not value:
        return value, False
    unit = dyadic(1, exponent(abs(value)) - bits + 1)
    scaled = abs(value) / unit
    q, r = divmod(scaled.numerator, scaled.denominator)
    increment = (mode == "ru" and r != 0) or (mode == "rn" and (
        r * 2 > scaled.denominator or (r * 2 == scaled.denominator and q % 2 != 0)))
    return (-1 if value < 0 else 1) * (q + increment) * unit, increment


def fixed_graph(operand: str) -> Fraction:
    se, word = operand.split(); assert se == "3ffc" and len(word) == 16
    x = dyadic(int(word, 16), -66)
    assert Fraction(1, 8) <= x < Fraction(1, 4)
    constants = {1: dyadic(-0x7FFFFFFFFFFFFFFFE, -68), 2: dyadic(0x55555555555554277, -71),
                 3: dyadic(-0x5B05B05B05A18A1BA, -76), 4: dyadic(0x680680675B559F2CF, -82),
                 5: dyadic(-0x49F93AF61F5349300, -88), 6: dyadic(0x47A4F2483514C1AF8, -95)}
    chop67 = lambda v: rounding(v, 67, "chop")[0]
    rn64 = lambda v: rounding(v, 64, "rn")[0]
    square = chop67(x * x)
    fourth = chop67(square * rounding(square, 64, "chop")[0])
    negative = rn64(constants[1] + chop67(fourth * rn64(constants[3] + chop67(fourth * constants[5]))))
    positive = rn64(constants[2] + chop67(fourth * rn64(constants[4] + chop67(fourth * constants[6]))))
    correction = chop67(chop67(square * negative) + chop67(fourth * positive))
    return 1 + correction


def terminal(prevalue: Fraction, mode: str) -> tuple[str, int]:
    value, c1 = rounding(prevalue, 64, mode if mode in ("rn", "ru") else "chop")
    top = exponent(value)
    significand = value / dyadic(1, top - 63)
    assert significand.denominator == 1 and 1 << 63 <= significand < 1 << 64
    return f"{top+16383:04x}:{int(significand):016x}", int(c1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output_dir.resolve()
    assert not output.exists()
    for relative, expected in LOCKS.items():
        assert digest(root / relative) == expected, relative
    kit = root / "transfer-tests/h1624"
    frozen = json.loads((kit / "FREEZE.json").read_text())
    opened = json.loads((kit / "OPENED.json").read_text())
    assert opened["capture_state"] == "OPENED_ONCE" and opened["repeats"] == 0
    for line in (kit / "CHECKSUMS.sha256").read_text().splitlines():
        h, name = line.split(None, 1); relative = Path(name.strip())
        assert not relative.is_absolute() and ".." not in relative.parts and digest(kit / relative) == h
    with (kit / "manifest.tsv").open(newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    raw = kit / "hardware-output"
    assert (raw / "complete-utc.txt").is_file()
    assert (raw / "binary.sha256").read_text().split()[0] == frozen["hardware_target"]["capture_binary_sha256"]
    raw_hashes = {}
    for line in (raw / "outputs.sha256").read_text().splitlines():
        expected, name = line.split()
        assert name.startswith("hardware-output/") and ".." not in Path(name).parts
        assert digest(kit / name) == expected
        raw_hashes[Path(name).name] = expected
    assert set(raw_hashes) == {"fcos_" + mode + ".txt" for mode in ("rn", "rd", "ru", "rz")}
    prevalues = {r["operand"]: fixed_graph(r["operand"]) for r in rows}
    assert len(prevalues) == 417
    actual, counts, fresh_misses = {}, Counter(), []
    for mode in ("rn", "rd", "ru", "rz"):
        selected = [r for r in rows if r["mode"] == mode]
        assert (kit / "inputs" / ("fcos_" + mode + ".txt")).read_text().splitlines() == [r["operand"] for r in selected]
        lines = (raw / ("fcos_" + mode + ".txt")).read_text().splitlines()
        assert len(lines) == len(selected) == 417
        for index, (row, line) in enumerate(zip(selected, lines), 1):
            match = re.fullmatch(r"OK ([0-9a-f]{4}) ([0-9a-f]{16}) SW ([0-9a-f]{4})", line)
            assert match
            se, sig, sw = match.groups(); value = se + ":" + sig
            predicted, c1 = terminal(prevalues[row["operand"]], mode)
            assert predicted == row["candidate"] == value
            assert c1 == int(row["candidate_C1"]) == (int(sw, 16) // 512) % 2
            identity = (row["instruction"], mode, row["operand"])
            assert identity not in actual
            actual[identity] = {"baseline": row["baseline"], "hardware": value,
                                "hardware_status": sw, "case_id": row["case_id"], "raw_line": index,
                                "raw_file": "transfer-tests/h1624/hardware-output/fcos_" + mode + ".txt"}
            counts["observed"] += 1; counts["candidate_output_exact"] += 1; counts["candidate_C1_exact"] += 1
            counts["baseline_output_exact"] += row["baseline"] == value
            counts["models_disagree"] += row["baseline"] != row["candidate"]
            if row["baseline"] != value:
                fresh_misses.append(dict(row, hardware=value, hardware_status=sw, raw_line=index))
    score = json.loads((root / "tmp/ledger33/current/h1625_fixed_candidate_score/report.json").read_text())
    assert dict(counts) == score["counts"] and opened["counts"] == dict(counts)
    assert len(fresh_misses) == 3 and len({r["operand"] for r in fresh_misses}) == 2
    prior = json.loads((root / "tmp/ledger33/current/h1621_cached_frontier_extension/report.json").read_text())
    identity = lambda row: (row["instruction"], row["mode"], row["operand"])
    union = {identity(r): {"baseline": r["output"], "provenance": "H1621 authenticated old frontier"}
             for r in prior["build_checks"]["baseline_O2"]["outputs"]}
    for row in prior["build_checks"]["candidate_O2"]["outputs"]:
        union[identity(row)]["hardware"] = row["output"]
    assert len(union) == 78
    for row in fresh_misses:
        key = identity(row); assert key not in union
        assert key[2] not in {k[2] for k in union}
        # Both RD and RZ on the first fresh input are separate new tuples.
        # Operand freshness is checked against the OLD union, below.
    old_operands = {k[2] for k in union}
    assert not old_operands.intersection({r["operand"] for r in fresh_misses})
    for row in fresh_misses:
        union[identity(row)] = dict(actual[identity(row)], provenance="H1624 one-shot capture")
    direct = [k for k in union if k[0] == "fcos" and k[2].startswith("3ffc ")]
    assert len(union) == 81 and len({k[2] for k in union}) == 79
    assert len(direct) == 50 and len({k[2] for k in direct}) == 48
    checked = {}
    for label, old_check in prior["build_checks"].items():
        folder = "h1621_cached_frontier_extension" if label in ("baseline_O0", "baseline_O3", "baseline_ubsan") else "h1618_isolated_cosine_transfer"
        binary = root / "tmp/ledger33/current" / folder / label
        assert digest(binary) == old_check["binary_sha256"]
        outputs = []
        for instruction, mode in sorted({k[:2] for k in union}):
            keys = sorted(k for k in union if k[:2] == (instruction, mode))
            result = subprocess.run([str(binary), "--batch", "--" + instruction + "-standalone", "--rc=" + mode],
                                    input="".join(k[2] + "\n" for k in keys), text=True, capture_output=True, check=True)
            assert not result.stderr and len(result.stdout.splitlines()) == len(keys)
            for key, line in zip(keys, result.stdout.splitlines()):
                match = re.fullmatch(r"OK ([0-9a-f]{4}) ([0-9a-f]{16})", line); assert match
                value = ":".join(match.groups())
                expected = union[key]["baseline" if label.startswith("baseline") else "hardware"]
                assert value == expected
                outputs.append({"instruction": key[0], "mode": key[1], "operand": key[2], "output": value})
        checked[label] = {"rows": 81, "expected_matches": 81, "binary_sha256": digest(binary), "outputs": outputs}
    assert len(checked) == 8 and all(r["baseline"] != r["hardware"] for r in union.values())
    report = {"experiment": "h1626_verify_fresh_frontier", "status": "PASS",
              "independent_full_graph_operands": len(prevalues), "independent_output_C1_checks": 1668,
              "independent_scoring_counts": dict(counts), "new_misses": fresh_misses,
              "external_failing_rows": 81, "external_operands": 79,
              "positive_direct_failing_rows": 50, "positive_direct_operands": 48,
              "build_checks": checked, "hardware_execution": "none; reads H1624 captures only",
              "canonical_source_unchanged": True, "candidate_changed": False, "paper_change": "none",
              "claim_boundary": "Independent fresh-bank verification and observed lower-bound incumbent frontier, not a complete miss census or global candidate proof. Eight compiler replays are software, not repeat hardware.",
              "sha256": {"script": digest(Path(__file__)), "evidence": LOCKS, "raw_outputs": raw_hashes,
                         "opened": digest(kit / "OPENED.json"), "manifest": digest(kit / "manifest.tsv")}}
    output.mkdir(parents=True)
    with (output / "report.json").open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True); target.write("\n")
    print(json.dumps({key: report[key] for key in ("status", "independent_full_graph_operands", "independent_output_C1_checks",
                     "external_failing_rows", "external_operands", "positive_direct_failing_rows", "positive_direct_operands")}, sort_keys=True))


if __name__ == "__main__":
    main()
