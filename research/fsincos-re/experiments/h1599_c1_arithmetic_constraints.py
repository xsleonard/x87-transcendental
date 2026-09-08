#!/usr/bin/env python3
"""Refine cached output inverses with C1 under an explicit final-add contract.

No hardware runs. H1580/H1587 are rejoined to their immutable raw captures.
The additional f410 check uses one already observed H1412 init_load case and
records the complete older status audit context without inventing other modes.
Only H1595 output-matching masks are replayed; no full-graph search is rerun.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction as F
from pathlib import Path

import h1595_coupled_faithful_reachability as graph


Value = graph.Value
spec = graph.spec
GRAPH_SHA = "ace7b0f79cbf50728f082800882df36bda5ffddd7327de9624214e4da7bac47a"
REPORT_SHA = "d1c4a18f462a24b2282a2e15eb6e0ac374e34f124b0bf3cd0a24663d98669f2f"
CAPTURE_SHA = "aededbaea438dbd1526aca4926530b655d6c9a1ad0f0bac82ad58fcbe3d824d1"
OPENED_SHA = {
    "h1580": "3c59e0d0407049acd996d6f2bc4b81315396f74383a8ad04738165015ebe6822",
    "h1587": "effe9d43bc8042a726a8ed703fe3063caf7d3e9c85ff572588689d9b1edfcdbe",
}
SCORES = {"h1580": "h1581_equality_off_branch_score.tsv", "h1587": "h1588_both_equality_taps_score.tsv"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def power(exponent: int) -> F:
    return F(1 << exponent) if exponent >= 0 else F(1, 1 << -exponent)


@dataclass(frozen=True)
class Interval:
    lo: F
    hi: F
    lc: bool
    hc: bool

    def contains(self, value: F) -> bool:
        return (value > self.lo or self.lc and value == self.lo) and (value < self.hi or self.hc and value == self.hi)

    def grid(self, exponent: int) -> tuple[int, int]:
        lo, hi = self.lo / power(exponent), self.hi / power(exponent)
        floor = lambda x: x.numerator // x.denominator
        ceil = lambda x: -floor(-x)
        return (ceil(lo) if self.lc else floor(lo)+1, floor(hi) if self.hc else ceil(hi)-1)

    def record(self) -> dict:
        return {"lower": str(self.lo), "upper": str(self.hi), "lower_closed": self.lc, "upper_closed": self.hc}


def inverse(output: Value, mode: str, c1: int | None = None) -> Interval:
    """c > 0, y = round64_RC(1-c) > 0, no output binade boundary."""
    assert output.n > 1 << 63 and output.n < (1 << 64)-1
    y, ulp = output.fraction(), power(output.e)
    center = 1-y
    if mode == "rn":
        base = Interval(center-ulp/2, center+ulp/2, output.n % 2 == 0, output.n % 2 == 0)
    elif mode == "ru":
        base = Interval(center, center+ulp, True, False)
    else:
        assert mode in ("rd", "rz")
        base = Interval(center-ulp, center, False, True)
    if c1 is None:
        return base
    assert c1 in (0, 1)
    # Rounded magnitude exceeds positive prevalue iff c > 1-y.
    if c1:
        return Interval(max(base.lo, center), base.hi,
                        base.lc if base.lo > center else False, base.hc)
    return Interval(base.lo, min(base.hi, center), base.lc,
                    base.hc if base.hi <= center else True)


def c1_for(output: Value, signed_correction: Value) -> int:
    before = spec.exact_add(Value(1, 0), signed_correction)
    assert before.n > 0 and output.n > 0
    return int(spec.exact_add(output, Value(-before.n, before.e)).n > 0)


def selftest() -> dict:
    comparisons = 0
    for odd in (0, 1):
        output = Value((1 << 63)+16+odd, -64)
        center = 1-output.fraction()
        for mode in spec.MODES:
            for offset in range(-32, 33):
                correction = center+offset*power(-68)
                numerator = correction.numerator
                signed = Value(-numerator, -(correction.denominator.bit_length()-1))
                actual = spec.add(Value(1, 0), signed, 64, mode)
                output_matches = actual.fraction() == output.fraction()
                assert inverse(output, mode).contains(correction) == output_matches
                for c1 in (0, 1):
                    assert inverse(output, mode, c1).contains(correction) == (output_matches and c1_for(output, signed) == c1)
                    comparisons += 1
    assert inverse(Value((1 << 63)+16, -64), "ru", 0).lo == inverse(Value((1 << 63)+16, -64), "ru", 0).hi
    return {"status": "PASS", "interval_membership_comparisons": comparisons,
            "includes_even_odd_ties_exact_points_and_impossible_directed_C1": True}


def checked_path(root: Path, relative: str, expected: str, evidence: dict) -> Path:
    path = root/relative
    assert digest(path) == expected, relative
    evidence[relative] = expected
    return path


def capture_rows(root: Path, campaign: str, evidence: dict) -> list[dict]:
    relative = f"transfer-tests/{campaign}"
    kit = root/relative
    opened = json.loads(checked_path(root, relative+"/OPENED.json", OPENED_SHA[campaign], evidence).read_text())
    assert opened["capture_state"] == "OPENED_ONCE" and opened["repeats"] == 0
    frozen = json.loads(checked_path(root, relative+"/FREEZE.json", opened["sha256"]["freeze"], evidence).read_text())
    assert frozen["capture_state"] == "FROZEN_UNOPENED" and frozen["one_observation_maximum_per_tuple"]
    manifest = checked_path(root, relative+"/manifest.tsv", opened["sha256"]["manifest"], evidence)
    rows = list(csv.DictReader(manifest.open(), delimiter="\t"))
    assert len(rows) == frozen["unique_capture_tuples"] == opened["unique_capture_tuples"]
    scored = list(csv.DictReader(checked_path(root, "tmp/ledger33/current/"+SCORES[campaign], opened["sha256"]["score"], evidence).open(), delimiter="\t"))
    score_by_id = {r["case_id"]: r for r in scored}
    assert len(score_by_id) == len(rows)
    for name, expected in opened["sha256"]["capture_metadata"].items():
        checked_path(root, relative+"/hardware-output/"+name, expected, evidence)
    observed = []
    for name, lane in frozen["lanes"].items():
        selected = [r for r in rows if r["mode"] == lane["mode"] and r["instruction"] == lane["instruction"]]
        inputs = checked_path(root, relative+"/inputs/"+name+".txt", lane["sha256"], evidence)
        assert inputs.read_text().splitlines() == [r["operand"] for r in selected]
        raw = checked_path(root, relative+"/hardware-output/"+name+".txt", opened["sha256"]["raw_captures"][name+".txt"], evidence)
        lines = raw.read_text().splitlines()
        assert len(lines) == len(selected) == lane["rows"]
        for row, line in zip(selected, lines):
            tokens = line.lower().split()
            assert len(tokens) == 5 and tokens[0] == "ok" and tokens[3] == "sw"
            value, sw = ":".join(tokens[1:3]), int(tokens[4], 16)
            score = score_by_id[row["case_id"]]
            assert (score["operand"], score["mode"], score["hardware"], int(score["hardware_status"], 16)) == (row["operand"], row["mode"], value, sw)
            assert row["instruction"] == "fcos" and row["precision_control"] == "pc64"
            observed.append({"source": campaign, "case_id": row["case_id"], "operand": row["operand"],
                             "mode": row["mode"], "hardware": value, "hardware_status": f"{sw:04x}", "c1": (sw >> 9)&1})
    assert len(observed) == len(rows)
    return observed


def f410_context(root: Path, evidence: dict) -> tuple[dict, dict]:
    status_report = checked_path(root, "tmp/ledger33/current/h1423_cached_status_observability.txt",
        "d4cd5b221b10268a9692e121c3067ef021effc5bee687c48d33ef06462b89f21", evidence)
    hashes = dict(line.split("\t", 1) for line in status_report.read_text().splitlines()[:6])
    found = []
    for campaign, filename in (("h1406", "h1406_input_history_hardware.txt"),
        ("h1410", "h1410_producer_class_hardware.txt"), ("h1412", "h1412_prelude_transitions_hardware.txt")):
        raw = checked_path(root, "tmp/ledger33/current/"+filename, hashes[campaign+"_sha256"], evidence)
        for line in raw.read_text().splitlines():
            fields = dict(token.lower().split("=", 1) for token in line.split())
            if fields["operand"] == "3ffc:f4100000059862dd":
                found.append(dict(fields, campaign=campaign))
    assert len(found) == 23
    assert {(r["mode"], r["result"], r["after_sw"]) for r in found} == {("ru", "3ffe:f8c35790ef2cf9b8", "3820")}
    selected = [r for r in found if r["campaign"] == "h1412" and r["case"] == "d0092"]
    assert len(selected) == 1 and selected[0]["variant"] == "init_load"
    row = {"source": "h1378", "status_source": "h1412/D0092/init_load", "case_id": "D0092",
           "operand": "3ffc f4100000059862dd", "mode": "ru", "hardware": selected[0]["result"],
           "hardware_status": "3820", "c1": 0}
    return row, {"context_observations": found, "observed_modes": ["ru"],
                 "RN_RD_RZ_C1": "NOT_OBSERVED_IN_THESE_RAW_FILES",
                 "new_hardware_observations": 0,
                 "singleton_output_inverse_compatibility": "C1=0 is compatible; no contrary nonzero C1 found"}


def replay_correction(operand: str, payload: Value, mask: int) -> Value:
    """Replay a known successful mask without materializing full debug records."""
    state = graph.initial(operand)
    for index, node in enumerate(graph.NODES):
        exact = graph.operation(state, node, payload)
        ordinary = spec.quantize(exact, node[4], node[5])
        if mask & (1 << index):
            choices = [v for v in graph.neighbors(exact, node[4]) if graph.key(v) != graph.key(ordinary)]
            assert len(choices) == 1
            state[node[0]] = choices[0]
        else:
            state[node[0]] = ordinary
    return state["correction"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    checks = selftest()
    if args.selftest:
        print(json.dumps(checks, sort_keys=True))
        return
    if args.output_dir is None:
        parser.error("--output-dir required")
    output_dir, root = args.output_dir, args.root
    if output_dir.exists():
        raise SystemExit(f"refusing existing output {output_dir}")
    evidence = {}
    checked_path(root, "experiments/h1595_coupled_faithful_reachability.py", GRAPH_SHA, evidence)
    graph_path = checked_path(root, "tmp/ledger33/current/h1595_coupled_faithful_reachability_v2/report.json", REPORT_SHA, evidence)
    report = json.loads(graph_path.read_text())
    checked_path(root, "experiments/h1592_independent_integer_spec.py", report["sha256"]["evidence"]["experiments/h1592_independent_integer_spec.py"], evidence)
    checked_path(root, "tmp/ledger33/current/h1598_source_before.c", report["sha256"]["source"], evidence)
    checked_path(root, "capture-kit/x87_capture.c", CAPTURE_SHA, evidence)
    rows = capture_rows(root, "h1580", evidence)+capture_rows(root, "h1587", evidence)
    assert len(rows) == 26 and len({(r["mode"],r["operand"]) for r in rows}) == 26
    extra, extra_context = f410_context(root, evidence)
    rows.append(extra)
    graph_rows = {(r["source"], r["mode"], r["operand"]): r for r in report["rows"]}
    output_dir.mkdir(parents=True)
    counts = Counter()
    details = []
    raw_path = output_dir/"successful_output_paths_c1.tsv.gz"
    with raw_path.open("xb") as raw_file, gzip.GzipFile(fileobj=raw_file, mode="wb", filename="", mtime=0) as raw:
        raw.write(b"source\tmode\toperand\tpayload\tmask\tcorrection_signed_sig_hex\tcorrection_e2\tpredicted_c1\tobserved_c1\tstatus_matches\n")
        for row in rows:
            original = graph_rows[row["source"], row["mode"], row["operand"]]
            assert original["hardware"] == row["hardware"]
            sw = int(row["hardware_status"], 16)
            assert (sw & ~(0x3800|0x0200|0x0020)) == 0 and (sw&0x3800) == 0x3800 and sw&0x20
            y = spec.decode_external(row["hardware"].replace(":", " "))
            ordinary_inverse, refined = inverse(y, row["mode"]), inverse(y, row["mode"], row["c1"])
            variants = {}
            for name, variant in original["variants"].items():
                payload = graph.unpack(variant["payload_signed_dyadic"])
                successful = variant["families"]["all_graph"]["successful_masks"]
                kept, rejected, c_hist = [], [], Counter()
                for mask in successful:
                    correction = replay_correction(row["operand"], payload, mask)
                    assert correction.n < 0
                    endpoint = spec.encode_external(spec.add(Value(1, 0), correction, 64, row["mode"]))
                    assert endpoint == row["hardware"]
                    c1 = c1_for(y, correction)
                    positive = -correction.fraction()
                    assert ordinary_inverse.contains(positive)
                    assert refined.contains(positive) == (c1 == row["c1"])
                    (kept if c1 == row["c1"] else rejected).append(mask)
                    c_hist[f"{correction.n:x}@{correction.e}/C1={c1}"] += 1
                    raw.write((f"{row['source']}\t{row['mode']}\t{row['operand']}\t{name}\t{mask}\t{correction.n:x}\t{correction.e}\t{c1}\t{row['c1']}\t{int(c1==row['c1'])}\n").encode())
                probe_masks = sorted({successful[0], successful[-1]} | ({kept[0]} if kept else set()) | ({rejected[0]} if rejected else set()))
                for mask in probe_masks:
                    expected = graph.unpack(graph.replay_mask(row["operand"],row["mode"],payload,mask)["steps"][-1]["chosen_output"])
                    assert graph.key(replay_correction(row["operand"],payload,mask)) == graph.key(expected)
                families = {family: graph.summarize_masks(kept, allowed) for family, allowed in graph.FAMILIES.items()}
                variants[name] = {"output_matching_paths": len(successful), "output_and_C1_matching_paths": len(kept),
                    "C1_rejected_paths": len(rejected), "correction_histogram": dict(sorted(c_hist.items())),
                    "families_after_C1": families,
                    "families_before_C1": {family: {k:v for k,v in summary.items() if k != "successful_masks"} for family,summary in variant["families"].items()},
                    "replay_mask_checks": len(probe_masks)}
                prefix = ("f410_extra" if row is extra else "primary26")+"."+name
                counts[prefix+".output_matching_paths"] += len(successful)
                counts[prefix+".C1_rejected_paths"] += len(rejected)
                counts[prefix+".output_and_C1_matching_paths"] += len(kept)
                counts[prefix+".rows_with_rejections"] += bool(rejected)
                counts[prefix+".rows_still_reachable"] += bool(kept)
            details.append(dict(row, correction_inverse=ordinary_inverse.record(), correction_inverse_with_C1=refined.record(), variants=variants))
            print(row["source"], row["mode"], row["operand"], {name:(v["output_matching_paths"],v["output_and_C1_matching_paths"]) for name,v in variants.items()}, flush=True)
    result = {"experiment": "h1599_c1_arithmetic_constraints", "status": "CONDITIONAL_FINAL_ROUNDING_CONSTRAINT_NOT_SELECTOR",
        "hardware_execution": "none", "new_hardware_observations": 0, "unobserved_modes_inferred": False,
        "primary_observations": 26, "additional_cached_f410_mode_rows": 1, "selftest": checks,
        "C1_contract": "For positive y=round64_RC(1-c), C1=int(y>1-c)=int(c>1-y); not a claim about correctly rounded mathematical cosine.",
        "PE_contract": "Instruction-level PE may reflect earlier internal inexactness; it is not used to exclude exact final-add prevalues.",
        "graph_contract": report["claim_boundary"], "summary": dict(sorted(counts.items())), "rows": details,
        "f410_cached_status_context": extra_context,
        "primary_sources": [{"url":"https://www.intel.com/content/dam/www/public/us/en/documents/manuals/64-ia-32-architectures-software-developer-vol-2a-manual.pdf","location":"FCOS, Vol. 2A pp. 3-331--3-332"},
            {"url":"https://cdrdv2-public.intel.com/843827/253665-sdm-vol-1-dec-24.pdf","location":"Vol. 1 Section 8.5.6, p. 8-31"}],
        "sha256": {"script": digest(Path(__file__)), "evidence": evidence, "raw_path_results": digest(raw_path)}}
    with (output_dir/"report.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True); out.write("\n")
    print(json.dumps(result["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
