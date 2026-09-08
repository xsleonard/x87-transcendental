#!/usr/bin/env python3
"""Challenge the fixed wider cosine graph with the old lower-binade walls.

H1135/H1160 deliberately target R1158's difficult boundary cells. Authenticate
their raw positional captures, not merely historical model scores. Retain
unknown C1 as unknown. No new hardware, fitting, promotion or paper change.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from contextlib import ExitStack
from pathlib import Path

import h1627_wider_cosine_transfer_v2 as wider


CURRENT = "tmp/ledger33/current/"
PARENT = CURRENT + "h1627_wider_cosine_transfer_v2/report.json"
LOCKS = {
    PARENT: "4481d624bc46037674ef0c60313c5f2f171ba5f87d65eaa368a42292655db962",
    "experiments/h1627_wider_cosine_transfer_v2.py": "5e8350946774fca72520464c186c319371e26cd8b5f67cb48bb67eeab3d321e5",
    CURRENT + "h1207_lower_recurrence_cache_audit.txt": "d72b2e1b9ceb1fea2ac153a73cc054c44e12927e8314a54ab6eafd8319752ae0",
    CURRENT + "h1136_3ffb_blind_score.tsv": "7d31f41bafb04368372651ff066d0e5a23a1ac4e1104d966370d225a3249e127",
    CURRENT + "h1161_3ffb_boundary_score.tsv": "08041537ec4552804cf7d967760cd4dc393f049f171f35eb1d0345cfab861740",
}


def table(path):
    with path.open(newline="") as source:
        return list(csv.DictReader(source, delimiter="\t"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output_dir.resolve()
    assert not output.exists()
    evidence = dict(LOCKS)
    for name, expected in evidence.items():
        assert wider.digest(root / name) == expected, name
    parent = json.loads((root / PARENT).read_text())
    for relative, expected in parent["sha256"]["evidence"].items():
        assert wider.digest(root / relative) == expected, relative
        evidence[relative] = expected
    binaries = {v: root / CURRENT / "h1627_wider_cosine_transfer_v2" / v for v in wider.VARIANTS}
    for variant, path in binaries.items():
        assert wider.digest(path) == parent["sha256"]["binary"][variant]
    baseline = root / CURRENT / "h1618_isolated_cosine_transfer/baseline_O2"
    old_model = json.loads((baseline.parent / "report.json").read_text())
    assert wider.digest(baseline) == old_model["builds"]["baseline_O2"]["binary_sha256"]
    inventories, truth = [], {}
    for tag, prefix, scored, count in (
        ("h1160", "h1160_3ffb_boundary", "h1161_3ffb_boundary_score.tsv", 2151),
        ("h1135", "h1135_3ffb_blind", "h1136_3ffb_blind_score.tsv", 51229),
    ):
        manifest = CURRENT + prefix + "_manifest.tsv"
        frozen, cached = table(root / manifest), table(root / CURRENT / scored)
        assert len(frozen) == len(cached) == count
        evidence[manifest] = wider.digest(root / manifest)
        labels = {(r["mode"], r["op"]): r["hw"] for r in cached}
        assert len(labels) == count
        lanes = {}
        for mode in wider.MODES:
            selected = [r for r in frozen if r["mode"] == mode]
            inputs, raw = CURRENT + prefix + "_" + mode + "_ops.txt", CURRENT + tag + "_hw_cos_" + mode + ".raw"
            operands = (root / inputs).read_text().splitlines()
            actual = (root / raw).read_text().splitlines()
            assert operands == [r["op"] for r in selected] and len(actual) == len(selected)
            values = [wider.parse_output(line) for line in actual]
            for operand, value in zip(operands, values):
                assert value == labels[mode, operand]
                assert truth.setdefault((mode, operand), value) == value
            for name in (inputs, raw):
                evidence[name] = wider.digest(root / name)
            lanes[mode] = {"inputs": inputs, "raw": raw, "rows": len(values)}
        inventories.append({"tag": tag, "manifest": manifest, "rows": count, "lanes": lanes})
    output.mkdir(parents=True)
    wider.save(output / "prepared.json", {"state": "AUTHENTICATED_CACHED_LABELS_FIXED_GRAPH", "inventories": inventories,
                                          "sha256": {"script": wider.digest(Path(__file__)), "evidence": evidence}})
    reports, total = [], {v: Counter() for v in wider.VARIANTS}
    for bank in inventories:
        directory = output / bank["tag"]; directory.mkdir()
        counts, failures = {v: Counter() for v in wider.VARIANTS}, {v: [] for v in wider.VARIANTS}
        with ExitStack() as stack:
            full = {v: wider.zipped(stack, directory / (v + "_replay.jsonl.gz")) for v in wider.VARIANTS}
            for mode, lane in bank["lanes"].items():
                operands = (root / lane["inputs"]).read_text().splitlines()
                hardware = [wider.parse_output(line) for line in (root / lane["raw"]).read_text().splitlines()]
                base, _, _, _ = wider.run(baseline, "fcos", mode, operands, False)
                for variant, binary in binaries.items():
                    values, metadata, _, _ = wider.run(binary, "fcos", mode, operands, True)
                    assert len(metadata) == len(operands)
                    for index, (operand, value, observed) in enumerate(zip(operands, values, hardware)):
                        meta = metadata[index]
                        assert operand.startswith("3ffb ") and meta["top"] == -4 and meta["precision"] <= 64 and not meta["old_scope"]
                        independent_value, c1 = wider.independent(meta, mode, variant == "all_ports")
                        assert value == independent_value and meta["C1"] == c1
                        row = {"operand": operand, "mode": mode, "raw_ordinal": index,
                               "hardware": observed, "baseline": base[index], "candidate": value,
                               "candidate_output_exact": value == observed, "baseline_output_exact": base[index] == observed,
                               "metadata": meta, "hardware_C1": None, "independent_output": independent_value,
                               "independent_C1": c1}
                        full[variant].write((json.dumps(row, sort_keys=True) + "\n").encode())
                        metrics = {"observed": 1, "candidate_output_exact": int(value == observed),
                                   "candidate_output_misses": int(value != observed), "baseline_output_exact": int(base[index] == observed),
                                   "baseline_output_misses": int(base[index] != observed), "output_changes": int(value != base[index]),
                                   "independent_output_checks": 1, "known_hardware_C1": 0}
                        counts[variant].update(metrics); total[variant].update(metrics)
                        if value != observed:
                            failures[variant].append(row)
                print(bank["tag"], mode, {v: dict(c) for v, c in counts.items()}, flush=True)
        wider.save(directory / "failures.json", failures)
        report = {"bank": bank["tag"], "complete": True, "counts": {v: dict(c) for v, c in counts.items()},
                  "sha256": {p.name: wider.digest(p) for p in sorted(directory.iterdir())}}
        wider.save(directory / "report.json", report); reports.append(report)
    for relative, expected in evidence.items():
        assert wider.digest(root / relative) == expected
    result = {"experiment": "h1628_targeted_lower_transfer", "banks": reports,
              "counts": {v: dict(c) for v, c in total.items()}, "unique_actual_mode_operand_rows": len(truth),
              "unique_operands": len({operand for mode, operand in truth}),
              "status": {v: "LOWER_EXTENSION_FALSIFIED" if c["candidate_output_misses"] else "PASS_TARGETED_LOWER_CACHED_WALLS" for v, c in total.items()},
              "hardware_execution": "none", "private_ledger_access": "none", "candidate_changed": False,
              "canonical_default_or_paper_change": "none",
              "claim_boundary": "Actual lower-binade captures; no imputed C1, RZ or aliases. Test of fixed arithmetic against a hard targeted wall, not a global silicon proof or new hardware validation.",
              "sha256": {"script": wider.digest(Path(__file__)), "prepared": wider.digest(output / "prepared.json"), "evidence": evidence}}
    wider.save(output / "report.json", result)
    print(json.dumps({key: result[key] for key in ("status", "counts", "unique_actual_mode_operand_rows", "unique_operands")}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
