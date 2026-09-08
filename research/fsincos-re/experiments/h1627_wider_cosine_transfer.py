#!/usr/bin/env python3
"""Test two fixed wider-domain cosine extensions on retained H110 captures.

H1617 equates the simplified and all-port graphs only for <=64-bit inputs.
Keep both hypotheses explicit outside that bound. No canonical/default or
hardware action. Stop after a complete bank if both extensions are falsified.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from contextlib import ExitStack
from pathlib import Path

import h1618_isolated_cosine_transfer as candidate
import h1626_verify_fresh_frontier as rational


PARENT = "tmp/ledger33/current/h1620_heterogeneous_candidate_audit_v2/report.json"
LOCKS = {
    PARENT: "7ea431b36610cd0c8b82cbe8edd6b3ec3b0df3abdfc55dc8038c56e568096b60",
    "experiments/h1618_asymmetric_cosine.h": "df5a4b9114c0a754a68274d29c1252257c449af34f68769c6e5f83b85584c6cf",
    "experiments/h1618_isolated_cosine_transfer.py": "bb321f62daa8d06168bbd3ee6e872f25afe370fe51f14676c63a574141cb4d19",
    "experiments/h1626_verify_fresh_frontier.py": "27439bf1165f107509e574f1d6f8680f1978899a18ab47fe2f6475ab4435fd8e",
}
MODES = ("rn", "rd", "ru")
VARIANTS = ("simplified", "all_ports")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value) -> None:
    with path.open("x") as target:
        json.dump(value, target, indent=2, sort_keys=True); target.write("\n")


def zipped(stack, path):
    raw = stack.enter_context(path.open("xb"))
    return stack.enter_context(gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0))


def independent(meta: dict, mode: str, ports: bool):
    sign, exponent, word = meta["magnitude"].split(":")
    assert sign == "0"
    x = rational.dyadic(int(word, 16), int(exponent))
    constants = {1: rational.dyadic(-0x7FFFFFFFFFFFFFFFE, -68), 2: rational.dyadic(0x55555555555554277, -71),
                 3: rational.dyadic(-0x5B05B05B05A18A1BA, -76), 4: rational.dyadic(0x680680675B559F2CF, -82),
                 5: rational.dyadic(-0x49F93AF61F5349300, -88), 6: rational.dyadic(0x47A4F2483514C1AF8, -95)}
    chop = lambda value, bits: rational.rounding(value, bits, "chop")[0]
    rn64 = lambda value: rational.rounding(value, 64, "rn")[0]
    def product(a, b):
        return chop((chop(a, 67) * chop(b, 64)) if ports else a * b, 67)
    square = product(x, x)
    fourth = product(square, chop(square, 64))
    negative = rn64(constants[1] + product(fourth, rn64(constants[3] + product(fourth, constants[5]))))
    positive = rn64(constants[2] + product(fourth, rn64(constants[4] + product(fourth, constants[6]))))
    prevalue = 1 + chop(product(square, negative) + product(fourth, positive), 67)
    # Architectural directed modes reverse their magnitude direction for
    # negative cosine outputs. C1 remains the magnitude-increment indicator.
    magnitude_mode = {"rn": "rn", "rd": "ru", "ru": "rd", "rz": "rz"}[mode] if meta["negative"] else mode
    encoded, c1 = rational.terminal(prevalue, magnitude_mode)
    se, sig = encoded.split(":")
    if meta["negative"]:
        encoded = f"{int(se,16)|0x8000:04x}:" + sig
    return encoded, c1


def parse_output(line: str, status=False):
    if status:
        match = re.fullmatch(r"(OK ([0-9a-f]{4}) ([0-9a-f]{16})|C2) SW ([0-9a-f]{4})", line.lower().replace("ok", "OK").replace("c2", "C2"))
        assert match, line
        sw = int(match[4], 16)
        if match[1] == "C2":
            assert sw & 0x400
            return "C2", sw
        return ("C2" if sw & 0x400 else match[2] + ":" + match[3]), sw
    if line == "C2":
        return "C2"
    words = line.lower().split()
    assert len(words) == 3 and words[0] == "ok"
    return words[1] + ":" + words[2]


def run(binary: Path, instruction: str, mode: str, operands: list[str], observe: bool):
    proc = subprocess.run([str(binary), "--batch", "--" + instruction + "-standalone", "--rc=" + mode],
                          input="".join(op + "\n" for op in operands), text=True, capture_output=True, check=True)
    values = [parse_output(line) for line in proc.stdout.splitlines()]
    assert len(values) == len(operands)
    metadata = {}
    for line in proc.stderr.splitlines():
        assert observe, proc.stderr[:512]
        words = line.split(); assert len(words) == 7, line
        index, top, width, old_scope, neg, c1 = map(int, words[:6])
        assert 0 <= index < len(values) and index not in metadata
        assert old_scope in (0, 1) and neg in (0, 1) and c1 in (0, 1)
        metadata[index] = {"top": top, "precision": width, "old_scope": old_scope,
                           "negative": neg, "C1": c1, "magnitude": words[6]}
    return values, metadata, proc.stdout, proc.stderr


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output_dir.resolve()
    assert not output.exists()
    evidence = dict(LOCKS)
    for name, expected in evidence.items():
        assert digest(root / name) == expected, name
    parent = json.loads((root / PARENT).read_text())
    evidence["src/fsincos_skylake.c"] = candidate.LOCKS["src/fsincos_skylake.c"]
    assert digest(root / "src/fsincos_skylake.c") == evidence["src/fsincos_skylake.c"]
    # The historical runner documents that both instructions consume the
    # same positional input stream. H1620 independently pins its FCOS side.
    for name in ("capture-kit/run_standalone_prebuilt.sh", "capture-kit/README.md", "experiments/h1627_wider_cosine_observer.h"):
        evidence[name] = digest(root / name)
    inventories = []
    for tag, input_name, count in (("sweep", "sweep_inputs.txt", 50038), ("dense", "dense_qn.txt", 240000)):
        input_path = "capture-kit/inputs/" + input_name
        assert digest(root / input_path) == parent["sha256"]["evidence"][input_path]
        evidence[input_path] = digest(root / input_path)
        for instruction in ("fcos", "fsin"):
            captures = {mode: f"capture-kit-captures/skylake-fsin-h110/{tag}_{instruction}_{mode}_status.txt" for mode in MODES}
            for mode, relative in captures.items():
                evidence[relative] = digest(root / relative)
                if instruction == "fcos":
                    assert evidence[relative] == parent["sha256"]["evidence"][relative]
                # These second repository copies are not extra observations;
                # exact equality authenticates the historical stream alias.
                alias = f"capture-kit-captures/skylake-perinsn-20260807/{tag}_{instruction}_{mode}.txt"
                assert digest(root / alias) == evidence[relative]
                evidence[alias] = digest(root / alias)
            inventories.append({"tag": tag + "_" + instruction, "instruction": instruction,
                                "inputs": input_path, "count": count, "captures": captures})
    models = root / "tmp/ledger33/current/h1618_isolated_cosine_transfer"
    old = json.loads((models / "report.json").read_text())
    baseline = models / "baseline_O2"
    assert digest(baseline) == old["builds"]["baseline_O2"]["binary_sha256"]
    original, source = candidate.assembled_source(root)
    include, anchor = '#include "h1618_asymmetric_cosine.h"', '    while (scanf("%x %llx", &se, &sig) == 2) {'
    assert source.count(include) == source.count(anchor) == 1
    source = source.replace(include, '#include "h1627_wider_cosine_observer.h"').replace(anchor, anchor + "\n        ++h1627_row;")
    output.mkdir(parents=True)
    prepared = {"state": "SOFTWARE_ONLY_PREPARED_NO_NEW_LABELS", "hypotheses": list(VARIANTS),
                "claim_boundary": "All cosine-polynomial dispatches, without H1618's binade/precision guard; no table, tiny or sine-polynomial transfer credit. Fixed hypotheses, not physical-control claims.",
                "inventories": inventories, "evidence": evidence, "script_sha256": digest(Path(__file__)),
                "source_sha256": hashlib.sha256(source.encode()).hexdigest()}
    save(output / "prepared.json", prepared)
    binaries = {}
    for variant in VARIANTS:
        binary = output / variant
        build = subprocess.run(["cc", "-O2", "-std=c11", "-DG_ROUND84=0", "-DG_H1618_ASYMMETRIC_COSINE=1",
                                "-DH1627_ALL_PORTS=" + str(int(variant == "all_ports")), "-I", str(root / "src"),
                                "-I", str(root / "experiments"), "-x", "c", "-", "-lm", "-o", str(binary)],
                               input=source, text=True, capture_output=True, check=True)
        assert not build.stderr
        test = subprocess.run([str(binary), "--selftest"], text=True, capture_output=True, check=True)
        assert test.stdout == "SELFTEST: ok\n" and not test.stderr
        binaries[variant] = binary
    totals, reports = {variant: Counter() for variant in VARIANTS}, []
    for bank in inventories:
        operands = (root / bank["inputs"]).read_text().lower().splitlines()
        assert len(operands) == bank["count"]
        directory = output / bank["tag"]; directory.mkdir()
        counts = {variant: Counter() for variant in VARIANTS}
        cells = {variant: defaultdict(Counter) for variant in VARIANTS}
        independent_checks, sampled = [], set()
        with ExitStack() as stack:
            differences = zipped(stack, directory / "changes_or_misses.jsonl.gz")
            for mode, capture in bank["captures"].items():
                actual = (root / capture).read_text().splitlines(); assert len(actual) == len(operands)
                streams = {variant: (zipped(stack, directory / (variant + "_" + mode + ".stdout.gz")),
                                     zipped(stack, directory / (variant + "_" + mode + ".metadata.gz"))) for variant in VARIANTS}
                for start in range(0, len(operands), 8192):
                    batch = operands[start:start + 8192]
                    base, _, _, _ = run(baseline, bank["instruction"], mode, batch, False)
                    computed = {}
                    for variant, binary in binaries.items():
                        values, metadata, stdout, _ = run(binary, bank["instruction"], mode, batch, True)
                        streams[variant][0].write(stdout.encode())
                        for i, meta in sorted(metadata.items()):
                            streams[variant][1].write((json.dumps(dict(index=start+i, **meta), sort_keys=True) + "\n").encode())
                        computed[variant] = values, metadata
                    assert set(computed["simplified"][1]) == set(computed["all_ports"][1])
                    for i, operand in enumerate(batch):
                        hardware, sw = parse_output(actual[start+i], True)
                        for variant, (values, metadata) in computed.items():
                            new, meta = values[i], metadata.get(i)
                            hit = meta is not None
                            prefix = "old_scope" if hit and meta["old_scope"] else "extended" if hit else "fallback"
                            assert hit or new == base[i]
                            if hit and meta["precision"] <= 64:
                                assert computed["simplified"][0][i] == computed["all_ports"][0][i]
                                assert computed["simplified"][1][i] == computed["all_ports"][1][i]
                            wrong_c1 = hit and meta["C1"] != ((sw >> 9) & 1)
                            metrics = {"observed": 1, prefix + "_rows": 1,
                                       prefix + "_output_misses": int(new != hardware), prefix + "_C1_misses": int(wrong_c1),
                                       "baseline_output_misses": int(base[i] != hardware), "output_changes": int(new != base[i])}
                            cell = f"{prefix}/e{meta['top']}/p{meta['precision']}/neg{meta['negative']}" if hit else "fallback"
                            for counter in (counts[variant], totals[variant], cells[variant][cell]):
                                counter.update(metrics)
                            detail = {"bank": bank["tag"], "index": start+i, "instruction": bank["instruction"], "mode": mode,
                                      "operand": operand, "variant": variant, "hardware": hardware, "hardware_status": f"{sw:04x}",
                                      "baseline": base[i], "candidate": new, "metadata": meta, "scope": prefix}
                            differs = computed["simplified"][0][i] != computed["all_ports"][0][i]
                            interesting = new != hardware or wrong_c1 or new != base[i] or differs
                            if interesting:
                                differences.write((json.dumps(detail, sort_keys=True) + "\n").encode())
                            sample_key = variant, mode, cell
                            if hit and (interesting or sample_key not in sampled):
                                predicted, c1 = independent(meta, mode, variant == "all_ports")
                                assert predicted == new and c1 == meta["C1"], (detail, predicted, c1)
                                independent_checks.append(dict(detail, independent_output=predicted, independent_C1=c1))
                                sampled.add(sample_key)
                print(bank["tag"], mode, {variant: dict(value) for variant, value in counts.items()}, flush=True)
        save(directory / "independent_checks.json", independent_checks)
        report = {"bank": bank["tag"], "complete": True, "counts": {v: dict(c) for v, c in counts.items()},
                  "cells": {v: {k: dict(c) for k, c in sorted(group.items())} for v, group in cells.items()},
                  "independent_checks": len(independent_checks), "sha256": {p.name: digest(p) for p in sorted(directory.iterdir())}}
        save(directory / "report.json", report); reports.append(report)
        if all(totals[v]["extended_output_misses"] or totals[v]["extended_C1_misses"] for v in VARIANTS):
            break
    for relative, expected in evidence.items():
        assert digest(root / relative) == expected, relative
    result = {"experiment": "h1627_wider_cosine_transfer", "complete_banks": reports,
              "remaining_banks_unscored": [b["tag"] for b in inventories[len(reports):]],
              "counts": {v: dict(c) for v, c in totals.items()}, "hardware_execution": "none",
              "private_ledger_access": "none", "canonical_or_default_change": "none", "paper_change": "none",
              "status": {v: "WIDER_EXTENSION_FALSIFIED" if c["extended_output_misses"] or c["extended_C1_misses"] else "SURVIVES_LISTED_CACHED_BANKS_ONLY" for v, c in totals.items()},
              "claim_boundary": prepared["claim_boundary"] + " Counts are bank/RC appearances; C1 only, not full status. Original guarded candidate is separate from wider extensions. Missing further banks are not passes.",
              "sha256": {"script": digest(Path(__file__)), "prepared": digest(output / "prepared.json"),
                         "binary": {v: digest(p) for v, p in binaries.items()}, "evidence": evidence}}
    save(output / "report.json", result)
    print(json.dumps({"status": result["status"], "counts": result["counts"], "remaining": result["remaining_banks_unscored"]}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
