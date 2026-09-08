#!/usr/bin/env python3
"""Verify signed-payload scaling repair, without new hardware execution."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import subprocess
from collections import defaultdict
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    a = p.parse_args()
    if a.output_dir.exists():
        raise SystemExit("refusing existing output directory")
    cur = a.root / "tmp/ledger33/current"
    before = cur / "h1598_source_before.c"
    after = cur / "h1598_source_candidate.c"
    old_audit_path = cur / "h1590_signed_threshold_ub_audit/report.json"
    broad_path = cur / "h1597_broad_encoding_ub_audit/report.json"
    old = json.loads(old_audit_path.read_text())
    broad = json.loads(broad_path.read_text())
    assert digest(before) == old["sha256"]["source_after"] == broad["sha256"]["source"]
    expected = before.read_text().replace("    if (payload)\n        S += (__int128)payload << dp;",
        "    /* A payload can be negative. Scale it without a signed negative shift. */\n"
        "    if (payload)\n        S += (__int128)payload * ((__int128)1 << dp);")
    for variable, shift in (("payload", "dl75 - 8"), ("payload_pre_gate", "dl96 - 8"), ("payload", "dl96 - 8")):
        expected = expected.replace(f"((__int128){variable} << ({shift}))",
                                    f"(__int128){variable} * ((__int128)1 << ({shift}))")
    assert after.read_text() == expected, "source differs beyond five payload scales and comment"
    inputs_path = cur / "h1597_broad_encoding_ub_audit/software_inputs.txt"
    assert digest(inputs_path) == broad["sha256"]["inputs"]
    software = inputs_path.read_text().splitlines()
    cached: dict[tuple[str,str], set[str]] = defaultdict(set)
    evidence = {}
    for name in ("h1575_current_rule_ablation.json", "h1582_equality_frontier_reconciliation.json", "h1589_equality_gate_collision_audit.json"):
        path = cur / name
        assert digest(path) == old["sha256"]["evidence"][str(path.relative_to(a.root))]
        data = json.loads(path.read_text())
        for r in data["rows" if name.startswith("h1575") else "new_rows"]:
            cached["fcos",r["mode"]].add(r["operand"])
        evidence[str(path.relative_to(a.root))] = digest(path)
    for name in ("h1571_exact_preimage_transfer_score.tsv", "h1574_signed_preimage_transfer_score.tsv", "h1107_controls_allmodes.tsv"):
        path = cur / name
        assert digest(path) == old["sha256"]["evidence"][str(path.relative_to(a.root))]
        with path.open() as inp:
            for r in csv.DictReader(inp, delimiter="\t"):
                if "insn" in r:
                    assert r["insn"] == "cos"
                    insn, op = "fcos", r["op"]
                else:
                    insn, op = r["instruction"], r["operand"]
                cached[insn,r["mode"]].add(op)
        evidence[str(path.relative_to(a.root))] = digest(path)
    cached_count = sum(map(len,cached.values()))
    assert cached_count == 149898
    jobs = {f"software_{i}_{m}": (i,m,software) for i in ("fcos","fsin") for m in ("rn","rd","ru","rz")}
    jobs.update({f"cached_{i}_{m}": (i,m,sorted(ops)) for (i,m),ops in cached.items()})
    a.output_dir.mkdir(parents=True)
    models = a.output_dir / "models"
    models.mkdir()
    configs = {"O0":["-O0"],"O2":["-O2"],"O3":["-O3"],"ubsan":["-O2","-fsanitize=undefined"]}
    baseline = {}
    reports = {}
    for version, source in (("before",before),("after",after)):
        for config, flags in configs.items():
            name = f"{version}_{config}"
            model = (models/name).resolve()
            subprocess.run(["cc",*flags,"-std=c11","-DG_ROUND84=0","-I",str((a.root/"src").resolve()),
                            str(source.resolve()),"-lm","-o",str(model)],check=True,capture_output=True)
            report = {"binary_sha256":digest(model),"jobs":{}}
            for key,(insn,mode,ops) in sorted(jobs.items()):
                proc = subprocess.run([str(model),"--batch",f"--{insn}-standalone",f"--rc={mode}"],
                    input="".join(op+"\n" for op in ops),text=True,capture_output=True,check=True,timeout=120)
                lines = proc.stdout.splitlines()
                assert len(lines) == len(ops)
                if name == "before_O0":
                    baseline[key] = lines
                changes = [{"row":j,"operand":ops[j],"before":original,"after":new}
                           for j,(original,new) in enumerate(zip(baseline[key],lines)) if original != new]
                artifacts = {}
                for suffix,content in (("stdout",proc.stdout),("stderr",proc.stderr)):
                    path = a.output_dir / f"{name}_{key}.{suffix}"
                    with path.open("x") as out:
                        out.write(content)
                    artifacts[path.name] = digest(path)
                if key.startswith("cached_"):
                    old_path = cur / "h1590_signed_threshold_ub_audit" / f"after_O2_{insn}_{mode}.stdout"
                    assert digest(old_path) == old["versions"]["after_O2"]["artifacts"][old_path.name]
                    assert baseline[key] == old_path.read_text().splitlines()
                report["jobs"][key] = {"rows":len(ops),"changes":changes,"artifacts":artifacts,
                    "runtime_diagnostics":[line for line in proc.stderr.splitlines() if "runtime error:" in line]}
            reports[name] = report
            print(name,"changes",sum(len(j["changes"]) for j in report["jobs"].values()),
                  "diagnostics",sum(len(j["runtime_diagnostics"]) for j in report["jobs"].values()),flush=True)
    # Locate a software-only witness by diagnostic-driven bisection. These are
    # emulator invocations, never hardware recaptures or new ground-truth labels.
    witness = software
    model = (models/"before_ubsan").resolve()
    def diagnostic(ops: list[str], trace: bool=False) -> subprocess.CompletedProcess:
        command = [str(model),"--batch","--fcos-standalone","--rc=rn"]
        if trace:
            command.append("--dump-r59-compact")
        return subprocess.run(command,input="".join(op+"\n" for op in ops),text=True,capture_output=True,check=True)
    assert "left shift of negative" in diagnostic(witness).stderr
    while len(witness)>1:
        mid = len(witness)//2
        first = witness[:mid]
        witness = first if "left shift of negative" in diagnostic(first).stderr else witness[mid:]
    proc = diagnostic(witness,True)
    assert "left shift of negative" in proc.stderr
    with (a.output_dir/"witness_trace.txt").open("x") as out:
        out.write(proc.stderr+"\nOUTPUT\n"+proc.stdout)
    report = {"experiment":"h1598_signed_payload_ub_audit","hardware_execution":"none",
              "source_change":"five_signed_payload_scales_and_explanatory_comment_only_no_selector_or_default_change",
              "cached_legs":cached_count,"software_encodings":len(software),"software_legs":len(software)*8,
              "counts_overlap_between_banks_not_deduplicated":True,"witness":witness[0],
              "all_outputs_unchanged":not any(j["changes"] for r in reports.values() for j in r["jobs"].values()),
              "after_ubsan_clean":not any(j["runtime_diagnostics"] for j in reports["after_ubsan"]["jobs"].values()),
              "runs":reports,"claim_boundary":"finite_software_parity_and_defined_signed_scaling_not_silicon_solution",
              "sha256":{"source_before":digest(before),"source_after":digest(after),"script":digest(Path(__file__)),
                         "h1590":digest(old_audit_path),"h1597":digest(broad_path),"evidence":evidence,
                         "witness_trace":digest(a.output_dir/"witness_trace.txt")}}
    with (a.output_dir/"report.json").open("x") as out:
        json.dump(report,out,indent=2,sort_keys=True)
        out.write("\n")


if __name__ == "__main__":
    main()
