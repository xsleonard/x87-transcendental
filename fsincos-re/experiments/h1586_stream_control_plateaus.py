#!/usr/bin/env python3
"""Bounded-memory extension of the fixed, exact H1584 neighborhood audit."""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

from h1400_causal_stage_localization import digest, run
from h1210_stagea_residual_reframe import parse_dump, run as dump_run
from h1400_p5_representation_audit import tree_variants
from h1479_r1475_topology_isomorphism import trace_tree


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True,type=Path)
    p.add_argument("--scanner",required=True,type=Path)
    p.add_argument("--filter",required=True,type=Path)
    p.add_argument("--baseline",required=True,type=Path)
    p.add_argument("--radius",type=int,default=65536)
    p.add_argument("--output-dir",required=True,type=Path)
    a=p.parse_args()
    if a.output_dir.exists():raise SystemExit("refusing existing output directory")
    old_dir=a.root/"tmp/ledger33/current/h1584_equality_control_bank_r8192"
    old=json.loads((old_dir/"bank.json").read_text())
    assert digest(a.scanner)==old["sha256"]["scanner"]
    assert digest(a.root/"src/fsincos_skylake.c")==old["sha256"]["source"]
    models={"baseline":a.baseline.resolve(),
            "tap1":(a.root/"tmp/ledger33/current/h1577_equality_bank/strict").resolve(),
            "tap2":(a.root/"tmp/ledger33/current/h1577_equality_bank/inclusive").resolve(),
            "tap4":(old_dir/"tap4").resolve()}
    assert {n:digest(v) for n,v in models.items()}==old["sha256"]["models"]
    assert digest(old_dir/"raw_proxy_preimages.tsv")==old["sha256"]["raw"]
    with (old_dir/"raw_proxy_preimages.tsv").open("rb") as inp:
        check=subprocess.run([str(a.filter.resolve())],stdin=inp,capture_output=True,text=True,check=True)
    expected={(c["operand"],str(c["tap"]),m["mode"],m["strict"],m["inclusive"])
              for c in old["candidates"] for m in c["modes"]}
    actual={tuple(line.split("\t")) for line in check.stdout.splitlines()}
    assert actual==expected and not old["counts"]["rejected"]
    assert check.stderr.strip()==f"input_rows=106095 visible_mode_rows={len(expected)}"
    a.output_dir.mkdir(parents=True)
    with (a.output_dir/"filter_parity.txt").open("x") as out:out.write(check.stdout+check.stderr)
    print("Independent filter parity passed on all 106,095 prior rows",flush=True)
    raw_path=a.output_dir/"raw_proxy_preimages.tsv.gz";visible_path=a.output_dir/"visible.tsv"
    raw_hash=hashlib.sha256();count=0
    with raw_path.open("xb") as archived,gzip.GzipFile(fileobj=archived,mode="wb",mtime=0) as compressed,visible_path.open("xb") as vis:
        scan=subprocess.Popen([str(a.scanner.resolve()),str(a.radius)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        filtered=subprocess.Popen([str(a.filter.resolve())],stdin=subprocess.PIPE,stdout=vis,stderr=subprocess.PIPE)
        assert scan.stdout is not None and filtered.stdin is not None
        header=None
        for line in scan.stdout:
            raw_hash.update(line);compressed.write(line);filtered.stdin.write(line)
            fields=line.decode().rstrip("\n").split("\t")
            if header is None:header=fields;continue
            r=dict(zip(header,fields));sig=int(r["operand"].split()[1],16);q=sig*sig>>61
            f=int(r["fourth"],16);rf=int(r["positive_proxy"],16);shift=int(r["rsh"]);tap=int(r["tap"])
            assert (q*q).bit_length()-67==int(r["s4"])==67 and q*q>>67==f
            product=f*rf;assert product.bit_length()-67==shift
            rd=product%(1<<shift);assert rd==int(r["rdisc_proxy"],16)
            b=1<<(shift-16);target=1<<(shift+tap-1)
            assert target in (3*rd-3*rd%b,3*rd-2*rd%b-rd%b)
            count+=1
            if count%100000==0:print(f"exact preimages checked: {count}",flush=True)
        filtered.stdin.close()
        scan_log=scan.stderr.read().decode() if scan.stderr else ""
        filter_log=filtered.stderr.read().decode() if filtered.stderr else ""
        assert scan.wait()==filtered.wait()==0
    with (a.output_dir/"run_summary.txt").open("x") as out:out.write(scan_log+filter_log)
    visible=[tuple(l.split("\t")) for l in visible_path.read_text().splitlines()]
    assert len(visible)==len(set(visible))
    operands=sorted({r[0] for r in visible});originals={}
    with gzip.open(raw_path,"rt") as inp:
        for row in csv.DictReader(inp,delimiter="\t"):
            if row["operand"] in operands:
                key=(row["operand"],row["tap"]);assert key not in originals
                originals[key]=row
    outputs={n:{} for n in models}
    for n,model in models.items():
        for mode in ("rn","rd","ru"):outputs[n].update(run(model,mode,operands))
    for op,tap,mode,strict,inclusive in visible:
        sn,inm=("tap1","tap2") if tap=="1" else ("tap2","tap4")
        assert outputs[sn][mode,op]==strict and outputs[inm][mode,op]==inclusive
    _,stderr=dump_run(models["baseline"],"rn",operands,dump=True)
    traces={r["op"]:r for r in parse_dump(stderr,operands)}
    config=next(c for n,_,c in tree_variants() if n=="patent")
    candidates=[];rejects=Counter()
    for (op,tap_text),r in sorted(originals.items()):
        tap=int(tap_text);t=traces[op]
        if "rd3" not in t or int(t["rd3"],16)!=1<<(int(t["rsh"])+tap-1):
            rejects["not_current_equality"]+=1;continue
        if int(t["tc_rf_sig"],16)!=int(r["positive_proxy"],16):
            rejects["current_positive_proxy_mismatch"]+=1;continue
        if t["side"]!="1":rejects["not_side1"]+=1;continue
        nodes,_,final=trace_tree(t,config);shift=int(t["rsh"])
        held=nodes["l2_2"][1]>>(shift+4)&1;kill=1^((final[0]|final[1])>>(shift+15)&1);gate=held&kill
        assert int(t[f"b{tap}"])==1-gate
        assert int(t["b2" if tap==1 else "b1"])==(0 if tap==1 else 1)
        sn,inm=("tap1","tap2") if tap==1 else ("tap2","tap4");modes=[]
        for mode in ("rn","rd","ru"):
            key=mode,op;assert outputs["baseline"][key]==outputs[sn if gate else inm][key]
            if outputs[sn][key]!=outputs[inm][key]:
                modes.append({"mode":mode,"baseline":outputs["baseline"][key],"strict":outputs[sn][key],"inclusive":outputs[inm][key]})
        candidates.append({"operand":op,"tap":tap,"s4":int(t["s4"]),"rsh":shift,
                           "theta":int(t["theta"]),"low3":int(t["low3"]),"branch":t["branch"],
                           "held_carry":held,"final_kill":kill,"r1263_gate":gate,
                           "prediction":"strict" if gate else "inclusive","modes":modes,"scanner_row":r,
                           "trace":{k:t[k] for k in ("rd3","tc_f4_sig","tc_rf_sig","b1","b2")}})
    prior_map={(c["operand"],c["tap"]):c for c in old["candidates"]}
    for c in candidates:
        if (c["operand"],c["tap"]) in prior_map:assert c==prior_map[c["operand"],c["tap"]]
    assert set(prior_map)<={(c["operand"],c["tap"]) for c in candidates}
    counts={"raw_preimages":count,"visible_mode_rows":len(visible),"actual_equality_candidates":len(candidates),
            "rejected":dict(rejects),"tap_gate_counts":dict(Counter(f"b{c['tap']}/gate{c['r1263_gate']}" for c in candidates)),
            "prior_candidates_reproduced":len(prior_map)}
    report={"experiment":"h1586_stream_control_plateaus","capture_state":"SOFTWARE_ONLY_NOT_FROZEN",
            "hardware_execution":"none","new_hardware_labels":"none","selector_claim":"none",
            "plateau_radius":a.radius,"counts":counts,"candidates":candidates,
            "claim_boundary":"bounded_exact_neighborhood_of_four_known_controls_not_global_domain",
            "sha256":{"source":old["sha256"]["source"],"script":digest(Path(__file__)),"scanner":digest(a.scanner),
                       "scanner_source":old["sha256"]["scanner_source"],"filter":digest(a.filter),
                       "filter_source":digest(a.root/"experiments/h1585_stream_both_equality_taps.c"),
                       "raw_uncompressed":raw_hash.hexdigest(),"raw_gzip":digest(raw_path),"visible":digest(visible_path),
                       "models":old["sha256"]["models"],"h1584_bank":digest(old_dir/"bank.json")}}
    with (a.output_dir/"bank.json").open("x") as out:json.dump(report,out,indent=2,sort_keys=True);out.write("\n")
    print(json.dumps(counts,sort_keys=True),flush=True)


if __name__=="__main__":main()
