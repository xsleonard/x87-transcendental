#!/usr/bin/env python3
"""Build and audit a fixed shared-operator polynomial without promotion.

Compile from a hash-locked source string. The canonical file and H1618
artifacts remain untouched. Both polynomial lanes are identified per row;
all other paths retain the incumbent and are explicitly counted as fallback.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from contextlib import ExitStack
from pathlib import Path

import h1618_isolated_cosine_transfer as original
import h1627_wider_cosine_transfer_v2 as records
import h1629_polynomial_domain_certificate as integer


CURRENT = "tmp/ledger33/current/"
WIDER = CURRENT + "h1627_wider_cosine_transfer_v2/"
LOCKS = {
    "src/fsincos_skylake.c": "0339a7d6161c29164232fadd46053a538b7163d5d4449889e3600e9245026f2b",
    "src/p5_rom_constants.h": "2189e0063c913ee4004e09c8b80cb17afb16c95715ea579854e152088bbfce97",
    "src/ia64_sf.h": "a5e9d085f2607cbc43fecbadcce3cebf57620fb07d9509627ce2d27164d7758d",
    WIDER + "report.json": "4481d624bc46037674ef0c60313c5f2f171ba5f87d65eaa368a42292655db962",
    "experiments/h1627_wider_cosine_transfer_v2.py": "5e8350946774fca72520464c186c319371e26cd8b5f67cb48bb67eeab3d321e5",
    "experiments/h1629_polynomial_domain_certificate.py": "72291e774bd4301dfcdea4095d9d01641797701cf6c90b7bb567f150ba5dca1f",
}
SINE = {1: (-0x55555555555555555, -69), 2: (0x44444444444443E35, -73),
        3: (-0x6806806806773C774, -79), 4: (0x5C778E94F50956D70, -85),
        5: (-0x6B991122EFA0532F0, -92), 6: (0x58303F02614D5E4D8, -99)}
CONFIGS = {"disabled_O2": (0, ("-O2",)), "candidate_O0": (1, ("-O0",)),
           "candidate_O2": (1, ("-O2",)), "candidate_O3": (1, ("-O3",)),
           "candidate_ubsan": (1, ("-O2", "-fsanitize=undefined", "-fno-sanitize-recover=undefined"))}
HOOK = """
    /* H1630 analysis build only: both explicit polynomial schedules share
     * numerical operators, not a fitted selector or common terminal rule. */
    if (G_H1630_POLYNOMIAL)
        return h1630_polynomial(magnitude, residual_sign, signed_n, rc);
"""


def source_string(root):
    source = (root / "src/fsincos_skylake.c").read_text()
    assert records.digest(root / "src/fsincos_skylake.c") == LOCKS["src/fsincos_skylake.c"]
    anchor = original.ANCHOR
    batch = '    while (scanf("%x %llx", &se, &sig) == 2) {'
    assert source.count(anchor) == source.count(batch) == 1
    source = source.replace(anchor, '#include "h1630_shared_polynomial.h"\n\n' + anchor + HOOK)
    return source.replace(batch, batch + "\n        ++h1630_row;")


def decode(value):
    sign, exponent, word = value.split(":")
    return (-1 if int(sign) else 1) * int(word, 16), int(exponent)


def independent(meta, mode):
    x = decode(meta["magnitude"])
    assert x[0] > 0
    c = integer.C if meta["cosine"] else SINE
    square = integer.mul(x, x)
    fourth = integer.mul(square, integer.quantize(square, 64)[0])
    negative = integer.rnadd(c[1], integer.mul(fourth, integer.rnadd(c[3], integer.mul(fourth, c[5]))))
    positive = integer.rnadd(c[2], integer.mul(fourth, integer.rnadd(c[4], integer.mul(fourth, c[6]))))
    left, right = integer.mul(square, negative), integer.mul(fourth, positive)
    combined = integer.quantize(integer.add(left, right), 67 if meta["cosine"] else 64,
                                "chop" if meta["cosine"] else "rn")[0]
    correction = combined if meta["cosine"] else integer.mul(x, combined)
    pre = integer.add((1, 0) if meta["cosine"] else x, correction)
    rounding = "rn" if mode == "rn" else "away" if (mode == "ru" and not meta["negative"]) or (mode == "rd" and meta["negative"]) else "chop"
    (sig, scale), c1 = integer.quantize(pre, 64, rounding)
    assert sig > 0 and sig.bit_length() == 64
    se = scale + 63 + 16383 + (0x8000 if meta["negative"] else 0)
    stages = {"sq": square, "f4": fourth, "n": negative, "p": positive,
              "left": left, "right": right, "combined": combined, "correction": correction}
    return f"{se:04x}:{sig:016x}", c1, stages


def run(binary, instruction, mode, operands, trace=False):
    command = [str(binary), "--batch", "--" + instruction + "-standalone", "--rc=" + mode]
    if trace:
        command.append("--dump-internals")
    proc = subprocess.run(command, input="".join(op + "\n" for op in operands), text=True, capture_output=True, check=True)
    values = [records.parse_output(line) for line in proc.stdout.splitlines()]
    assert len(values) == len(operands)
    metadata, stages, current = {}, {}, None
    for line in proc.stderr.splitlines():
        if line.startswith("HPOLY "):
            words = line.split(); assert len(words) == 9
            index, cosine, top, precision, residual_sign, neg, c1 = map(int, words[1:8])
            assert 0 <= index < len(operands) and index not in metadata
            assert all(x in (0, 1) for x in (cosine, residual_sign, neg, c1))
            metadata[index] = {"cosine": cosine, "top": top, "precision": precision,
                               "residual_sign": residual_sign, "negative": neg, "C1": c1, "magnitude": words[8]}
            current = index
        elif line.startswith("HSTAGE "):
            assert trace and current is not None and current not in stages
            stages[current] = {name: decode(value) for name, value in (w.split("=", 1) for w in line.split()[1:])}
        else:
            assert trace and (line.startswith("DI_") or line.startswith("SINE_STATE ")), line[:1024]
    return values, metadata, stages, proc.stdout


def inventories(root, evidence):
    prepared = json.loads((root / WIDER / "prepared.json").read_text())
    result = prepared["inventories"]
    # First run the compact targeted banks, including previous coefficient,
    # FMUL and sine-terminal discriminators, before the broad retained walls.
    targeted = []
    for number, name, count in ((130, "reduced_coefficient", 512), (140, "fmul", 5)):
        inputs = f"capture-kit/inputs/constraint_fsin_{name}_h{number}.txt"
        captures = {m: f"capture-kit-captures/skylake-fsin-h{number}/constraint_fsin_{name}_{m}_status.txt" for m in records.MODES}
        targeted.append({"tag": f"h{number}_fsin", "instruction": "fsin", "inputs": inputs, "count": count, "captures": captures})
    selected = {"h285", "h292", "h301", "h307", "h314", "h320", "h347"}
    # Explicit authenticated inventory avoids inferring filenames from ids.
    paths = (
        ("h285", "constraint_trig_sine_bias_h285.txt", 192),
        ("h292", "constraint_trig_sine_coordinates_h292.txt", 256),
        ("h301", "constraint_trig_sine_fraction_h301.txt", 32),
        ("h307", "constraint_trig_narrow_sine_fraction_h307.txt", 64),
        ("h314", "constraint_trig_narrow_sine_fraction2_h314.txt", 24),
        ("h320", "constraint_trig_narrow_sine_fraction3_h320.txt", 24),
        ("h347", "constraint_round49_residual_neighbors_h347.txt", 197044),
    )
    for tag, filename, count in paths:
        assert tag in selected
        directory = f"capture-kit-captures/skylake-trig-{tag}"
        checksums = root / directory / "SHA256SUMS"
        pins = {n: h for h, n in (line.split() for line in checksums.read_text().splitlines())}
        evidence[str(checksums.relative_to(root))] = records.digest(checksums)
        inputs = "capture-kit/inputs/" + filename
        assert records.digest(root / inputs) == records.digest(root / directory / "inputs.txt") == pins["inputs.txt"]
        evidence[directory + "/inputs.txt"] = pins["inputs.txt"]
        for instruction in ("fsin", "fcos"):
            captures = {m: directory + "/" + instruction + "_" + m + "_status.txt" for m in records.MODES}
            for m, name in captures.items():
                assert records.digest(root / name) == pins[Path(name).name]
            targeted.append({"tag": tag + "_" + instruction, "instruction": instruction, "inputs": inputs, "count": count, "captures": captures})
    result = targeted + result
    for bank in result:
        for name in (bank["inputs"], *bank["captures"].values()):
            h = records.digest(root / name)
            assert evidence.get(name, h) == h
            evidence[name] = h
        assert len((root / bank["inputs"]).read_text().splitlines()) == bank["count"]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output_dir.resolve()
    assert not output.exists()
    evidence = dict(LOCKS)
    for name, expected in evidence.items():
        assert records.digest(root / name) == expected, name
    prior = json.loads((root / WIDER / "report.json").read_text())
    for name, expected in prior["sha256"]["evidence"].items():
        assert records.digest(root / name) == expected
        evidence[name] = expected
    evidence["experiments/h1630_shared_polynomial.h"] = records.digest(root / "experiments/h1630_shared_polynomial.h")
    banks = inventories(root, evidence)
    source = source_string(root)
    # Verify native sine constants and the width assumptions independently of
    # their 67-bit hexadecimal containers before compiling or scoring.
    rom = (root / "src/p5_rom_constants.h").read_text()
    for index, (n, e) in SINE.items():
        match = re.search(rf"P5S6_{index} = \{{ ([01]), (-?\d+), .*?0x([0-9a-f]+)ull<<64\)\|0x([0-9a-f]+)ull", rom)
        assert match
        actual = ((int(match[3], 16) << 64) | int(match[4], 16)) * (-1 if int(match[1]) else 1)
        assert (actual, int(match[2])) == (n, e)
    assert integer.width(SINE[5][0]) == 63 and integer.width(SINE[6][0]) == 64
    output.mkdir(parents=True)
    records.save(output / "prepared.json", {"state": "SOFTWARE_ONLY_FIXED_SHARED_POLYNOMIAL", "inventories": banks,
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(), "sha256": {"script": records.digest(Path(__file__)), "evidence": evidence}})
    binaries = {}
    for label, (enabled, flags) in CONFIGS.items():
        binary = output / label
        proc = subprocess.run(["cc", *flags, "-std=c11", "-DG_ROUND84=0", "-DG_H1630_POLYNOMIAL=" + str(enabled),
                               "-I", str(root / "src"), "-I", str(root / "experiments"), "-x", "c", "-", "-lm", "-o", str(binary)],
                              input=source, text=True, capture_output=True, check=True)
        assert not proc.stderr
        test = subprocess.run([str(binary), "--selftest"], text=True, capture_output=True, check=True)
        assert test.stdout == "SELFTEST: ok\n" and not test.stderr
        binaries[label] = binary
    baseline = root / CURRENT / "h1618_isolated_cosine_transfer/baseline_O2"
    old = json.loads((baseline.parent / "report.json").read_text())
    assert records.digest(baseline) == old["builds"]["baseline_O2"]["binary_sha256"]
    preflight = []
    for top in (-33, -32, -31, -4, -3, -2):
        for sign in (0, 0x8000):
            for sig in (1 << 63, (1 << 63) + 1, 0x9000000000000001, 0xc90fdaa22168c234, (1 << 64)-1):
                preflight.append(f"{sign + top + 16383:04x} {sig:016x}")
    preflight.extend(("403d ffffffffffffffff", "c00d a123456789abcdef", "4018 c123456789abcdef", "c035 ad21ff1a7998c000"))
    preflight_checks, stages_checked = 0, 0
    for instruction in ("fsin", "fcos"):
        for mode in ("rn", "rd", "ru", "rz"):
            base, _, _, _ = run(baseline, instruction, mode, preflight)
            disabled, nohits, _, _ = run(binaries["disabled_O2"], instruction, mode, preflight)
            assert disabled == base and not nohits
            reference = None
            for label in ("candidate_O0", "candidate_O2", "candidate_O3", "candidate_ubsan"):
                values, metadata, stages, _ = run(binaries[label], instruction, mode, preflight, True)
                assert len(stages) == len(metadata)
                if reference is None:
                    reference = values, metadata, stages
                assert (values, metadata, stages) == reference
                for i, value in enumerate(values):
                    if i not in metadata:
                        assert value == base[i]
                    else:
                        independent_value, c1, expected_stages = independent(metadata[i], mode)
                        assert independent_value == value and c1 == metadata[i]["C1"]
                        assert set(expected_stages) == set(stages[i])
                        assert all(integer.equal(v, stages[i][k]) for k, v in expected_stages.items())
                        stages_checked += len(expected_stages)
                    preflight_checks += 1
    records.save(output / "preflight.json", {"software_only": True, "row_checks": preflight_checks, "stage_equalities": stages_checked,
                                           "operands": preflight, "hardware_observations": 0})
    print("Compiler and independent-stage preflight passed", preflight_checks, stages_checked, flush=True)
    totals, reports = Counter(), []
    for bank in banks:
        directory = output / bank["tag"]; directory.mkdir()
        operands = (root / bank["inputs"]).read_text().lower().splitlines()
        counts, cells, checks = Counter(), defaultdict(Counter), []
        sampled = set()
        with ExitStack() as stack:
            differences = records.zipped(stack, directory / "changes_or_misses.jsonl.gz")
            for mode, capture in bank["captures"].items():
                actual = (root / capture).read_text().splitlines(); assert len(actual) == len(operands)
                outputs = records.zipped(stack, directory / (mode + "_candidate.stdout.gz"))
                metadata_file = records.zipped(stack, directory / (mode + "_metadata.jsonl.gz"))
                for start in range(0, len(operands), 8192):
                    batch = operands[start:start+8192]
                    base, _, _, _ = run(baseline, bank["instruction"], mode, batch)
                    values, metadata, _, stdout = run(binaries["candidate_O2"], bank["instruction"], mode, batch)
                    outputs.write(stdout.encode())
                    for i, meta in sorted(metadata.items()):
                        metadata_file.write((json.dumps(dict(index=start+i, **meta), sort_keys=True)+"\n").encode())
                    for i, (operand, value) in enumerate(zip(batch, values)):
                        hardware, sw = records.parse_output(actual[start+i], True)
                        meta = metadata.get(i)
                        lane = "cosine" if meta and meta["cosine"] else "sine" if meta else "fallback"
                        bad_c1 = meta is not None and meta["C1"] != (sw >> 9) & 1
                        assert meta or value == base[i]
                        metrics = {"observed": 1, lane + "_rows": 1, lane + "_output_misses": int(value != hardware),
                                   lane + "_C1_misses": int(bad_c1), "baseline_output_misses": int(base[i] != hardware),
                                   "output_changes": int(value != base[i])}
                        cell = f"{lane}/e{meta['top']}/p{meta['precision']}/neg{meta['negative']}" if meta else "fallback"
                        for counter in (totals, counts, cells[cell]):
                            counter.update(metrics)
                        detail = {"bank": bank["tag"], "index": start+i, "instruction": bank["instruction"], "mode": mode,
                                  "operand": operand, "hardware": hardware, "hardware_status": f"{sw:04x}", "candidate": value,
                                  "baseline": base[i], "lane": lane, "metadata": meta}
                        interesting = value != hardware or bad_c1 or value != base[i]
                        if interesting:
                            differences.write((json.dumps(detail, sort_keys=True)+"\n").encode())
                        if meta and (interesting or (mode, cell) not in sampled):
                            ivalue, ic1, _ = independent(meta, mode)
                            assert ivalue == value and ic1 == meta["C1"]
                            checks.append(dict(detail, independent_output=ivalue, independent_C1=ic1))
                            sampled.add((mode, cell))
                print(bank["tag"], mode, dict(counts), flush=True)
        records.save(directory / "independent_checks.json", checks)
        report = {"bank": bank["tag"], "complete": True, "counts": dict(counts), "cells": {k: dict(v) for k, v in cells.items()},
                  "independent_checks": len(checks), "sha256": {p.name: records.digest(p) for p in sorted(directory.iterdir())}}
        records.save(directory / "report.json", report); reports.append(report)
        if counts["sine_output_misses"] or counts["sine_C1_misses"] or counts["cosine_output_misses"] or counts["cosine_C1_misses"]:
            break
    for name, expected in evidence.items():
        assert records.digest(root / name) == expected
    result = {"experiment": "h1630_shared_polynomial_audit", "counts": dict(totals), "banks": reports,
              "remaining_banks": [b["tag"] for b in banks[len(reports):]],
              "status": "SHARED_POLYNOMIAL_FALSIFIED" if any(totals[lane+suffix] for lane in ("sine", "cosine") for suffix in ("_output_misses", "_C1_misses")) else "PASS_LISTED_RETAINED_BANKS_ONLY",
              "preflight_checks": preflight_checks, "preflight_stage_equalities": stages_checked,
              "hardware_execution": "none", "canonical_default_or_paper_change": "none", "private_ledger_access": "none",
              "claim_boundary": "Both fixed polynomial schedules only. Fallback gives no new arithmetic/C1 coverage. Actual retained RN/RD/RU labels, not fresh hardware or global proof; software preflight RZ is not observed RZ.",
              "sha256": {"script": records.digest(Path(__file__)), "prepared": records.digest(output / "prepared.json"),
                         "preflight": records.digest(output / "preflight.json"), "binaries": {k: records.digest(v) for k,v in binaries.items()}, "evidence": evidence}}
    records.save(output / "report.json", result)
    print(json.dumps({key: result[key] for key in ("status", "counts", "remaining_banks")}, sort_keys=True))


if __name__ == "__main__":
    main()
