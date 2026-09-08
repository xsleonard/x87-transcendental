#!/usr/bin/env python3
"""Replay exact neighborhoods of both equality taps; do not open hardware labels."""
from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
from collections import Counter
from pathlib import Path

from h1400_causal_stage_localization import digest, run
from h1210_stagea_residual_reframe import parse_dump, run as dump_run
from h1400_p5_representation_audit import tree_variants
from h1479_r1475_topology_isomorphism import trace_tree
from h1564_shared_tree_automorphism_wall import CASES


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True,type=Path)
    p.add_argument("--scanner",required=True,type=Path)
    p.add_argument("--baseline",required=True,type=Path)
    p.add_argument("--radius",type=int,default=1024)
    p.add_argument("--output-dir",required=True,type=Path)
    a=p.parse_args()
    if a.output_dir.exists():raise SystemExit("refusing existing output directory")
    prior_path=a.root/"tmp/ledger33/current/h1577_equality_bank/bank.json"
    prior=json.loads(prior_path.read_text())
    source=a.root/"src/fsincos_skylake.c"
    assert digest(source)==prior["sha256"]["source"]
    assert digest(a.baseline)==prior["sha256"]["models"]["baseline"]
    check=subprocess.run([str(a.scanner.resolve()),"--selftest"],capture_output=True,text=True,check=True)
    assert check.stdout=="SELFTEST: ok\n" and not check.stderr
    a.output_dir.mkdir(parents=True)
    scan=subprocess.run([str(a.scanner.resolve()),str(a.radius)],capture_output=True,text=True,check=True)
    raw_path=a.output_dir/"raw_proxy_preimages.tsv"
    with raw_path.open("x") as out:out.write(scan.stdout)
    with (a.output_dir/"scanner_summary.txt").open("x") as out:out.write(scan.stderr)
    raw=list(csv.DictReader(io.StringIO(scan.stdout),delimiter="\t"))
    unique={}
    for r in raw:
        sig=int(r["operand"].split()[1],16);square=sig*sig>>61
        f=int(r["fourth"],16);rf=int(r["positive_proxy"],16);shift=int(r["rsh"]);tap=int(r["tap"])
        assert (square*square).bit_length()-67==int(r["s4"])==67
        assert square*square>>67==f
        product=f*rf;assert product.bit_length()-67==shift
        rd=product%(1<<shift);assert rd==int(r["rdisc_proxy"],16)
        b=1<<(shift-16);target=1<<(shift+tap-1)
        assert target in (3*rd-(3*rd%b),3*rd-(2*rd%b)-(rd%b))
        key=(r["operand"],r["tap"])
        assert key not in unique,"overlapping input neighborhoods require explicit reconciliation"
        unique[key]=r
    print(f"validated exact proxy rows={len(raw)}",flush=True)
    old=prior_path.parent
    models={"baseline":a.baseline.resolve(),"tap1":(old/"strict").resolve(),"tap2":(old/"inclusive").resolve(),
            "tap4":(a.output_dir/"tap4").resolve()}
    assert digest(models["tap1"])==prior["sha256"]["models"]["strict"]
    assert digest(models["tap2"])==prior["sha256"]["models"]["inclusive"]
    subprocess.run(["cc","-O2","-std=c11","-DG_ROUND84=0","-DG_R99TAPS=4",str(source.resolve()),
                    "-lm","-o",str(models["tap4"])],capture_output=True,text=True,check=True)
    operands=sorted({r["operand"] for r in raw})
    outputs={n:{} for n in models}
    for name,model in models.items():
        for mode in ("rn","rd","ru"):
            for index in range(0,len(operands),10000):
                outputs[name].update(run(model,mode,operands[index:index+10000]))
        print(f"model {name} complete",flush=True)
    visible=[]
    for r in raw:
        strict,inclusive=("tap1","tap2") if r["tap"]=="1" else ("tap2","tap4")
        if any(outputs[strict][mode,r["operand"]]!=outputs[inclusive][mode,r["operand"]] for mode in ("rn","rd","ru")):
            visible.append(r)
    visops=sorted({r["operand"] for r in visible})
    _,stderr=dump_run(models["baseline"],"rn",visops,dump=True)
    traces={r["op"]:r for r in parse_dump(stderr,visops)}
    config=next(c for n,_,c in tree_variants() if n=="patent")
    candidates=[];rejects=Counter()
    for r in visible:
        op=r["operand"];t=traces[op];tap=int(r["tap"])
        if "rd3" not in t or int(t["rd3"],16)!=1<<(int(t["rsh"])+tap-1):
            rejects["not_current_equality"]+=1;continue
        if int(t["tc_rf_sig"],16)!=int(r["positive_proxy"],16):
            rejects["current_positive_proxy_mismatch"]+=1;continue
        if t["side"]!="1":rejects["not_side1"]+=1;continue
        nodes,_,final=trace_tree(t,config);shift=int(t["rsh"])
        held=nodes["l2_2"][1]>>(shift+4)&1
        kill=1^((final[0]|final[1])>>(shift+15)&1);gate=held&kill
        assert int(t[f"b{tap}"])==1-gate
        assert int(t["b2" if tap==1 else "b1"])==(0 if tap==1 else 1)
        strict,inclusive=("tap1","tap2") if tap==1 else ("tap2","tap4")
        modes=[]
        for mode in ("rn","rd","ru"):
            key=mode,op
            assert outputs["baseline"][key]==outputs[strict if gate else inclusive][key]
            if outputs[strict][key]!=outputs[inclusive][key]:
                modes.append({"mode":mode,"baseline":outputs["baseline"][key],
                              "strict":outputs[strict][key],"inclusive":outputs[inclusive][key]})
        candidates.append({"operand":op,"tap":tap,"s4":int(t["s4"]),"rsh":shift,
                           "theta":int(t["theta"]),"low3":int(t["low3"]),"branch":t["branch"],
                           "held_carry":held,"final_kill":kill,"r1263_gate":gate,
                           "prediction":"strict" if gate else "inclusive","modes":modes,
                           "scanner_row":r,"trace":{k:t[k] for k in ("rd3","tc_f4_sig","tc_rf_sig","b1","b2")}})
    anchors=[]
    for case in CASES:
        if case["consumer"]!="R1263":continue
        matches=[c for c in candidates if c["operand"]==case["operand"]]
        assert len(matches)==1 and matches[0]["r1263_gate"]==1,case["name"]
        match=next(m for m in matches[0]["modes"] if m["mode"]==case["mode"])
        assert match["baseline"]==match["strict"]==case["hardware"]
        anchors.append({"name":case["name"],"operand":case["operand"],"cached_control_reproduced":True})
    counts={"raw_preimages":len(raw),"unique_operands":len(operands),"endpoint_visible_operands":len(visops),
            "actual_equality_candidates":len(candidates),"rejected":dict(rejects),
            "tap_gate_counts":dict(Counter(f"b{c['tap']}/gate{c['r1263_gate']}" for c in candidates)),
            "cached_defining_controls":len(anchors)}
    report={"experiment":"h1584_equality_control_bank","capture_state":"SOFTWARE_ONLY_NOT_FROZEN",
            "hardware_execution":"none","new_hardware_labels":"none","selector_claim":"none",
            "plateau_radius":a.radius,"counts":counts,"candidates":candidates,"old_anchors":anchors,
            "claim_boundary":"bounded_exact_coefficient_plateau_neighborhood_not_global_equality_domain",
            "sha256":{"source":digest(source),"script":digest(Path(__file__)),"scanner":digest(a.scanner),
                       "scanner_source":digest(a.root/"experiments/h1583_equality_control_plateaus.c"),
                       "scanner_dependency":digest(a.root/"experiments/h1469_r1382_targeted_wrap.c"),
                       "h491_dependency":digest(a.root/"experiments/h491_scan3.c"),"raw":digest(raw_path),
                       "models":{n:digest(p) for n,p in models.items()},"h1577_bank":digest(prior_path)}}
    with (a.output_dir/"bank.json").open("x") as out:json.dump(report,out,indent=2,sort_keys=True);out.write("\n")
    print(json.dumps(counts,sort_keys=True),flush=True)


if __name__=="__main__":main()
