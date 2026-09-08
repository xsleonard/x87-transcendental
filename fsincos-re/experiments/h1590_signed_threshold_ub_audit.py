#!/usr/bin/env python3
"""Audit the defined signed-threshold scaling repair without new x87 execution.

Compare three optimization levels and UBSan before/after the exact source
edit, using old cached controls plus every explicitly reconciled direct and
alias observation. Source snapshots and raw program outputs are hash-locked.
This tests compiler arithmetic, not a new R59 selector.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import subprocess
from collections import Counter,defaultdict
from pathlib import Path
from h1570_freeze_exact_preimage_transfer import digest
from h1582_equality_frontier_reconciliation import checked_score


CONFIGS={"O0":["-O0"],"O2":["-O2"],"O3":["-O3"],"ubsan":["-O2","-fsanitize=undefined"]}
BEFORE_SHA="8fe40b8c852918f9cbe57a91b678861aa5e847f6c07106db1a18175a22314f39"


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True,type=Path)
    p.add_argument("--build-dir",required=True,type=Path)
    p.add_argument("--output-dir",required=True,type=Path)
    a=p.parse_args()
    if a.build_dir.exists() or a.output_dir.exists():raise SystemExit("refusing existing build/evidence directory")
    current=a.root/"tmp/ledger33/current"
    before=current/"h1590_source_before.c";after=a.root/"src/fsincos_skylake.c"
    assert digest(before)==BEFORE_SHA
    expected=before.read_text().replace("        int tfire = Mreg < ((__int128)u0 << 66);",
        "        /* Scale signed thresholds by multiplication: shifting a negative\n"
        "         * u0 is undefined in C.  Every int times 2^66 fits in __int128. */\n"
        "        int tfire = Mreg < (__int128)u0 * ((__int128)1 << 66);")
    expected=expected.replace("Mreg < ((__int128)uu << 66)","Mreg < (__int128)uu * ((__int128)1 << 66)")
    expected=expected.replace("Mreg >= ((__int128)uu << 66)","Mreg >= (__int128)uu * ((__int128)1 << 66)")
    assert after.read_text()==expected,"source changed outside the three signed-scaling sites"
    prior_path=current/"h1589_equality_gate_collision_audit.json";prior=json.loads(prior_path.read_text())
    evidence=dict(prior["sha256"]["evidence"])
    for path,h in evidence.items():assert digest(a.root/path)==h
    evidence[str(prior_path.relative_to(a.root))]=digest(prior_path)
    truth={};known_baseline={};sources=Counter()
    def add(instruction,mode,op,hardware,source,baseline=None):
        key=instruction,mode,op.lower()
        assert truth.setdefault(key,hardware.lower())==hardware.lower(),("conflicting cached truth",key)
        sources[source]+=1
        if baseline is not None:assert known_baseline.setdefault(key,baseline)==baseline
    for name in ("h1575_current_rule_ablation.json","h1582_equality_frontier_reconciliation.json","h1589_equality_gate_collision_audit.json"):
        path=current/name;d=json.loads(path.read_text())
        evidence[str(path.relative_to(a.root))]=digest(path)
        for r in d["rows" if name.startswith("h1575") else "new_rows"]:
            add("fcos",r["mode"],r["operand"],r["hardware"],name,r["outputs"]["baseline"])
    for campaign,stem in (("h1570","h1571_exact_preimage_transfer"),("h1573","h1574_signed_preimage_transfer")):
        for r in checked_score(a.root,campaign,stem,evidence):
            add(r["instruction"],r["mode"],r["operand"],r["hardware"],campaign,r["baseline"])
    assert len(known_baseline)==134
    controls=current/"h1107_controls_allmodes.tsv"
    with controls.open() as inp:
        for r in csv.DictReader(inp,delimiter="\t"):
            if r["insn"].lower()=="cos":add("fcos",r["mode"],r["op"],r["hw"],controls.name)
    evidence[str(controls.relative_to(a.root))]=digest(controls)
    grouped=defaultdict(list)
    for insn,mode,op in sorted(truth):grouped[insn,mode].append(op)
    a.build_dir.mkdir(parents=True);a.output_dir.mkdir(parents=True)
    compiler=subprocess.run(["cc","--version"],capture_output=True,text=True,check=True).stdout
    with (a.output_dir/"compiler.txt").open("x") as out:out.write(compiler)
    baseline=None;results={}
    for version,source in (("before",before),("after",after)):
        for label,flags in CONFIGS.items():
            name=version+"_"+label;binary=(a.build_dir/name).resolve()
            command=["cc",*flags,"-std=c11","-DG_ROUND84=0","-I",str((a.root/"src").resolve()),
                     str(source.resolve()),"-lm","-o",str(binary)]
            subprocess.run(command,capture_output=True,text=True,check=True)
            values={};artifacts={};diagnostics=[]
            for (insn,mode),ops in grouped.items():
                proc=subprocess.run([str(binary),"--batch","--rc="+mode,"--"+insn+"-standalone"],
                                    input="".join(op+"\n" for op in ops),capture_output=True,text=True,check=True)
                lines=proc.stdout.splitlines();assert len(lines)==len(ops)
                for op,line in zip(ops,lines):
                    fields=line.split();assert len(fields)==3 and fields[0]=="OK"
                    values[insn,mode,op]=fields[1].lower()+":"+fields[2].lower()
                for suffix,content in (("stdout",proc.stdout),("stderr",proc.stderr)):
                    path=a.output_dir/f"{name}_{insn}_{mode}.{suffix}"
                    with path.open("x") as out:out.write(content)
                    artifacts[path.name]=digest(path)
                diagnostics.extend(l for l in proc.stderr.splitlines() if "runtime error:" in l)
            assert all(values[key]==v for key,v in known_baseline.items()),name
            if baseline is None:baseline=values
            differences=[{"instruction":k[0],"mode":k[1],"operand":k[2],"before":baseline[k],"candidate":v}
                         for k,v in values.items() if baseline[k]!=v]
            counts=dict(Counter("exact" if v==truth[k] else "miss" for k,v in values.items()))
            canonical="".join(" ".join(k)+" "+values[k]+"\n" for k in sorted(values))
            results[name]={"flags":flags,"rows":len(values),"hardware_counts":counts,"changes":differences,
                           "runtime_diagnostics":diagnostics,"binary_sha256":digest(binary),"artifacts":artifacts,
                           "ordered_output_sha256":hashlib.sha256(canonical.encode()).hexdigest()}
            print(name,"rows",len(values),"changes",len(differences),"diagnostics",len(diagnostics),counts,flush=True)
    # A 32-bit signed threshold times 2^66 has magnitude at most 2^97,
    # strictly inside the signed-128 range. Test extreme and interior values
    # against their explicitly signed 128-bit bit-vector interpretation.
    for u in (-(1<<31),-(1<<31)+1,-65536,-3,-2,-1,0,1,2,3,65536,(1<<31)-1):
        product=u*(1<<66);bits=((u%(1<<128))<<66)% (1<<128)
        signed=bits-(1<<128) if bits>>(127) else bits
        assert product==signed and -(1<<127)<=product<(1<<127)
    report={"experiment":"h1590_signed_threshold_ub_audit","hardware_execution":"none_cached_only",
            "selector_change":"none","known_frontier_and_defining_rows":134,"unique_cached_rows":len(truth),
            "input_source_rows":dict(sources),"versions":results,
            "all_compiler_outputs_equal":len({r["ordered_output_sha256"] for r in results.values()})==1,
            "after_ubsan_clean":not results["after_ubsan"]["runtime_diagnostics"],
            "claim_boundary":"defined_scaling_and_finite_compiler_parity_not_global_UB_freedom_or_x87_closure",
            "scaling_argument":"signed_int32_times_2pow66_fits_signed_int128_exactly_no_negative_shift",
            "sha256":{"source_before":digest(before),"source_after":digest(after),"script":digest(Path(__file__)),
                       "compiler":digest(a.output_dir/"compiler.txt"),"evidence":evidence}}
    with (a.output_dir/"report.json").open("x") as out:json.dump(report,out,indent=2,sort_keys=True);out.write("\n")


if __name__=="__main__":main()
