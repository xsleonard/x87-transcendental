#!/usr/bin/env python3
"""Independent fixed X67/Y64 direct-cosine replay on the wider cached bank.

The production graph is written explicitly here and uses H1604's separate
integer quantizer, not the H1614 port/graph/rounding functions. Signed-dyadic
addition/multiplication and literal coefficients are shared H1592 primitives.
The H1615 module is used only to authenticate/load old observations. No
argument reduction, fresh validation, physical micro-op recovery or default
change is claimed.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

import h1604_fixed_policy_core_certificate as independent
import h1596_rounding_mode_feasibility as observations
import h1615_asymmetric_port_regression_gate as provenance


spec, V = independent.arithmetic, independent.Value
PARENT = "tmp/ledger33/current/h1615_asymmetric_port_regression_gate"
LOCKS = {
    PARENT+"/report.json": "dcc1f291289c1423f5b4426f21dccd1b741251a217ac3d1a1db8f9c5860275b7",
    "experiments/h1615_asymmetric_port_regression_gate.py":
        "7b2d53b5ca3bc2888ba0d79b384209ccd596ceafdcd781f5399f833667a81e95",
    "experiments/h1604_fixed_policy_core_certificate.py":
        "0d24e387cf10a6b218fa45f7bca53c5c0b0dc7ba7cebab8c293e6410fabb5463",
    "experiments/h1596_rounding_mode_feasibility.py":
        "186b8812f938ef2f890fe1cb9768e303c7d60d7eab07f83213f788a95bba4ade",
    "tmp/ledger33/current/h1363_x67_y64_replacement_blind_score.txt":
        "5ca23b41f8991a1c72517e6462ee9d6337476db56935641d29d204c30c589933",
}


def digest(path: Path) -> str:
    return observations.digest(path)


def product(a: V, b: V) -> V:
    x = independent.internal_round(a, 67, 0)
    y = independent.internal_round(b, 64, 0)
    return independent.internal_round(spec.exact_mul(x, y), 67, 0)


def rn_add(a: V, b: V) -> V:
    return independent.internal_round(spec.exact_add(a, b), 64, 1)


def fixed_graph(operand: str) -> dict[str, V]:
    x = spec.decode_external(operand)
    assert x.n > 0 and x.e+x.n.bit_length()-1 == -3
    c = spec.COEFFICIENTS
    square = product(x, x)
    fourth = product(square, square)
    negative_mul1 = product(fourth, c[5])
    negative_add1 = rn_add(c[3], negative_mul1)
    negative_mul2 = product(fourth, negative_add1)
    negative_factor = rn_add(c[1], negative_mul2)
    positive_mul1 = product(fourth, c[6])
    positive_add1 = rn_add(c[4], positive_mul1)
    positive_mul2 = product(fourth, positive_add1)
    positive_factor = rn_add(c[2], positive_mul2)
    left = product(square, negative_factor)
    right = product(fourth, positive_factor)
    correction = independent.internal_round(spec.exact_add(left, right), 67, 0)
    return {"square": square, "fourth": fourth, "negative_mul1": negative_mul1,
            "negative_add1": negative_add1, "negative_mul2": negative_mul2,
            "negative_factor": negative_factor, "positive_mul1": positive_mul1,
            "positive_add1": positive_add1, "positive_mul2": positive_mul2,
            "positive_factor": positive_factor, "left": left, "right": right,
            "correction": correction}


def final_output(correction: V, mode: str) -> tuple[str, int, V]:
    prevalue = spec.exact_add(V(1, 0), correction)
    assert 0 < prevalue.fraction() < 1
    value = independent.internal_round(prevalue, 64, {"rn": 1, "rd": 0, "ru": 3, "rz": 0}[mode])
    assert value.n > 0 and value.n.bit_length() == 64
    exponent = value.e+63+16383
    assert 0 < exponent < 0x7fff
    encoded = f"{exponent:04x}:{value.n:016x}"
    c1 = int(value.fraction() > prevalue.fraction())
    return encoded, c1, prevalue


def load_h1363(root: Path, evidence: dict) -> list[dict]:
    score = root/"tmp/ledger33/current/h1363_x67_y64_replacement_blind_score.txt"
    pins = dict(line.split("\t", 1) for line in score.read_text().splitlines() if "\t" in line)
    assert pins["hardware_policy"] == "one_capture_per_mode_operand_pair"
    relative = "tmp/ledger33/current/h1363_x67_y64_replacement_blind_score_labels.tsv"
    assert digest(root/relative) == pins["labels_sha256"]
    evidence[relative] = pins["labels_sha256"]
    captured = {}
    for mode in ("rn", "rd", "ru"):
        stem = "tmp/ledger33/current/h1362_x67_y64_replacement_blind/"+mode
        for suffix, key in (("_inputs.txt", "inputs_sha256."), ("_hardware.txt", "hardware_sha256.")):
            assert digest(root/(stem+suffix)) == pins[key+mode]
            evidence[stem+suffix] = pins[key+mode]
        inputs = (root/(stem+"_inputs.txt")).read_text().splitlines()
        outputs = (root/(stem+"_hardware.txt")).read_text().splitlines()
        assert len(inputs) == len(outputs)
        for operand, line in zip(inputs, outputs):
            fields = line.lower().split()
            assert len(fields) == 3 and fields[0] == "ok"
            key = operand.lower(), mode
            assert key not in captured
            captured[key] = fields[1]+":"+fields[2]
    rows = []
    with (root/relative).open() as source:
        for line, row in enumerate(csv.DictReader(source, delimiter="\t"), 2):
            key = row["op"].lower(), row["mode"]
            assert captured[key] == row["hardware"].lower()
            rows.append({"operand": key[0], "mode": key[1], "hardware": captured[key],
                         "instruction": "fcos", "sources": [f"h1363:line{line}"]})
    assert len(rows) == len(captured) == 28 and len({row["operand"] for row in rows}) == 20
    return rows


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
    for filename, key in (("witness_regression_replays.jsonl.gz", "witness_replays"), ("policy_certificate.json", "policy_certificate")):
        assert digest(root/PARENT/filename) == parent["sha256"][key]
        evidence[PARENT+"/"+filename] = parent["sha256"][key]
    assert parent["status"] == "SAT_CACHED_BANK_ONLY_REQUIRES_WIDER_VALIDATION"
    assert parent["final_cached_bank_witness"] == ["chop", "chop", "chop", "rn", "chop", "rn", "chop", "rn", "chop", "rn", "chop", "chop", "chop"]
    banks, source_evidence = observations.load(root)
    evidence.update(source_evidence)
    old = provenance.load_old(root, evidence)
    groups = {"named_direct": banks["named"], "historical_h1091": banks["history"], "H1603_controls": banks["controls"],
        "old_highq": [{"operand": row["operand"], "instruction": "fcos", "mode": obs["mode"], "hardware": obs["hardware"],
                       "sources": [obs["source"]+":"+str(obs["source_line_one_based"])]}
                      for row in old for obs in row["authenticated_observations"]], "h1363_previous_blind": load_h1363(root, evidence)}
    truth, memberships = {}, defaultdict(set)
    for name, rows in groups.items():
        for row in rows:
            assert row["instruction"] == "fcos"
            key = row["operand"], row["mode"]
            assert truth.setdefault(key, row["hardware"]) == row["hardware"]
            memberships[key].add(name)
    earlier_outputs = {}
    with gzip.open(root/PARENT/"witness_regression_replays.jsonl.gz", "rt") as stream:
        for line in stream:
            row = json.loads(line)
            assert row["round"] == 0 and not row["mismatched_modes"]
            for mode, value in row["outputs"].items():
                key = row["operand"], mode
                assert earlier_outputs.setdefault(key, value) == value
    named_replays = parent["target_vector_checks"]["natural_original_output_policies"]["replays"]
    for operand, record in named_replays.items():
        earlier_outputs.update({(operand, mode): value for mode, value in record["observed_mode_outputs"].items()})
    facts = json.loads((root/provenance.fixed.REPORT).read_text())
    c1_constraints = {(row["operand"], obs["mode"]): obs["c1"] for row in facts["rows"] for obs in row["actual_C1_constraints"]}
    assert len(c1_constraints) == 27
    tests = independent.selftest()
    output.mkdir(parents=True)
    trace_path = output/"independent_direct_replay.jsonl.gz"
    results, stage_checks, output_checks = defaultdict(Counter), 0, 0
    c1_checks, misses = 0, []
    by_operand = defaultdict(list)
    for key in sorted(truth):
        by_operand[key[0]].append(key[1])
    with trace_path.open("xb") as raw_file, gzip.GzipFile(fileobj=raw_file, mode="wb", filename="", mtime=0) as raw:
        for operand, modes in sorted(by_operand.items()):
            stages = fixed_graph(operand)
            if operand in named_replays:
                for previous in named_replays[operand]["stages"]:
                    assert stages[previous["node"]].fraction() == independent.from_record(previous["selected_result"]).fraction()
                    stage_checks += 1
            rows = []
            for mode in modes:
                key = operand, mode
                predicted, c1, prevalue = final_output(stages["correction"], mode)
                if key in earlier_outputs:
                    assert predicted == earlier_outputs[key]
                    output_checks += 1
                ok = predicted == truth[key]
                c1_ok = key not in c1_constraints or c1 == c1_constraints[key]
                if key in c1_constraints:
                    c1_checks += 1
                for name in memberships[key]:
                    results[name]["mode_rows"] += 1
                    results[name]["output_misses"] += not ok
                    results[name]["known_C1_misses"] += not c1_ok
                record = {"mode": mode, "hardware": truth[key], "predicted": predicted,
                          "known_C1": c1_constraints.get(key), "predicted_ordinary_C1": c1,
                          "prevalue": str(prevalue.fraction()), "sources": sorted(memberships[key])}
                rows.append(record)
                if not ok or not c1_ok:
                    misses.append({"operand": operand, **record})
            raw.write((json.dumps({"operand": operand, "stages": {name: value.record() for name, value in stages.items()},
                                  "observations": rows}, separators=(",", ":"))+"\n").encode())
    assert output_checks == len(earlier_outputs) == 150198
    assert c1_checks == 27 and stage_checks == 36*13
    result = {"experiment": "h1616_independent_asymmetric_direct_audit",
        "status": "PASS_CACHED_DIRECT_ONLY_NOT_CLOSURE" if not misses else "FALSIFIED_FIXED_GRAPH",
        "unique_observed_rows": len(truth), "unique_observed_operands": len(by_operand),
        "source_results": {name: dict(counts) for name, counts in sorted(results.items())},
        "output_misses": len(misses), "misses": misses, "known_C1_checks": c1_checks,
        "H1615_independent_output_agreements": output_checks, "H1615_independent_stage_agreements": stage_checks,
        "selftest": tests, "hardware_execution": "none", "selector_promotion": "none",
        "aliases_not_evaluated": len(banks["aliases"]),
        "independence_boundary": "Independent explicit graph, H1604 quantizer and final positive RC/encoding; H1592 exact dyadics and coefficients shared. H1615 imported only for observation loading; its arithmetic functions are not used for production predictions.",
        "claim_boundary": "positive normal direct FCOS inputs in [1/8,1/4) only; cached historical data, not fresh validation; no reduction/FSIN transfer, other domains, complete status behavior or recovered chip control proved",
        "sha256": {"script": digest(Path(__file__)), "evidence": evidence, "independent_replay": digest(trace_path)}}
    with (output/"report.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({key: result[key] for key in ("status", "unique_observed_rows", "unique_observed_operands", "output_misses", "known_C1_checks")}, sort_keys=True))


if __name__ == "__main__":
    main()
