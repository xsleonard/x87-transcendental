#!/usr/bin/env python3
"""Reconcile H1587 and prove collisions in the specified equality-gate inputs."""
from __future__ import annotations
import argparse
import json
from collections import Counter,defaultdict
from pathlib import Path
from h1400_causal_stage_localization import digest,run
from h1210_stagea_residual_reframe import parse_dump,run as dump_run
from h1400_p5_representation_audit import tree_variants
from h1479_r1475_topology_isomorphism import trace_tree
from h1582_equality_frontier_reconciliation import checked_score,census
from h1569_algebraic_preimage_families import replay


PROFILE=("mode","tap","s4","rsh","theta","low3","branch","held_carry","final_kill")


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True,type=Path)
    p.add_argument("--carry-models",required=True,type=Path)
    p.add_argument("--ablation-models",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    if a.output.exists():raise SystemExit("refusing existing report")
    current=a.root/"tmp/ledger33/current"
    previous_path=current/"h1582_equality_frontier_reconciliation.json"
    previous=json.loads(previous_path.read_text());evidence=dict(previous["sha256"]["evidence"])
    assert digest(a.root/"src/fsincos_skylake.c")==previous["sha256"]["source"]
    for path,h in evidence.items():assert digest(a.root/path)==h
    evidence[str(previous_path.relative_to(a.root))]=digest(previous_path)
    models={n:(a.carry_models/n).resolve() for n in previous["sha256"]["carry_models"]}
    ablations={n:(a.ablation_models/n).resolve() for n in previous["sha256"]["ablation_models"]}
    assert {n:digest(v) for n,v in models.items()}==previous["sha256"]["carry_models"]
    assert {n:digest(v) for n,v in ablations.items()}==previous["sha256"]["ablation_models"]
    rows=checked_score(a.root,"h1587","h1588_both_equality_taps",evidence)
    bank_path=current/"h1586_stream_control_plateaus/bank.json"
    frozen=json.loads((a.root/"transfer-tests/h1587/FREEZE.json").read_text())
    assert digest(bank_path)==frozen["sha256"]["source_bank"]
    evidence[str(bank_path.relative_to(a.root))]=digest(bank_path)
    grouped={mode:[r["operand"] for r in rows if r["mode"]==mode] for mode in ("rn","rd","ru")}
    outputs={n:{k:v for m,ops in grouped.items() for k,v in run(model,m,ops).items()} for n,model in models.items()}
    ablated={n:{k:v for m,ops in grouped.items() for k,v in run(model,m,ops).items()} for n,model in ablations.items()}
    traces={}
    for mode,ops in grouped.items():
        _,err=dump_run(models["baseline"],mode,ops,dump=True)
        traces.update({(mode,r["op"]):r for r in parse_dump(err,ops)})
    config=next(c for n,_,c in tree_variants() if n=="patent")
    new=[];profiles=defaultdict(list)
    for r in rows:
        key=r["mode"],r["operand"];t=traces[key]
        for field in ("s4","rsh","theta","low3","branch"):assert t[field]==r[field]
        shift=int(t["rsh"]);tap=int(r["tap"])
        assert int(t["rd3"],16)==1<<(shift+tap-1)
        nodes,_,final=trace_tree(t,config)
        held=nodes["l2_2"][1]>>(shift+4)&1;kill=1^((final[0]|final[1])>>(shift+15)&1)
        assert (held,kill)==(int(r["held_carry"]),int(r["final_kill"]))
        assert r["baseline"]==outputs["baseline"][key] and r["endpoint"] in ("strict","inclusive")
        item=dict(r,source="h1587",baseline_exact=r["baseline"]==r["hardware"],
                  allowed_carries=[c for c in (0,1) if outputs[f"carry{c}"][key]==r["hardware"]],
                  outputs={n:v[key] for n,v in outputs.items()},ablation_outputs={n:v[key] for n,v in ablated.items()})
        new.append(item);profiles[tuple(r[f] for f in PROFILE)].append(item)
    collisions=[]
    for key,members in profiles.items():
        if len({r["endpoint"] for r in members})>1:
            collisions.append({"profile":dict(zip(PROFILE,key)),"rows":[{f:r[f] for f in
                               ("case_id","mode","operand","hardware","strict","inclusive","endpoint")} for r in members]})
    frontier=json.loads((current/"h1568_expanded_causal_frontier.json").read_text())
    direct=[dict(r,instruction="fcos") for r in frontier["rows"]]+previous["new_rows"]
    assert census(direct)==previous["distinct_direct_residual_bank"]
    direct+=new;union=list(direct)
    for campaign,stem in (("h1570","h1571_exact_preimage_transfer"),("h1573","h1574_signed_preimage_transfer")):
        for r in checked_score(a.root,campaign,stem,evidence):
            for name in ("baseline","carry0","carry1"):
                assert replay(models[name],r["operand"],r["instruction"],r["mode"])[0]==r[name]
            union.append(dict(r,source=campaign,baseline_exact=r["baseline"]==r["hardware"],
                              allowed_carries=[c for c in (0,1) if r[f"carry{c}"]==r["hardware"]]))
    fixed=json.loads((current/"h1575_current_rule_ablation.json").read_text())["rows"]+previous["new_rows"]+new
    counts={n:dict(Counter("exact" if r["ablation_outputs"][n]==r["hardware"] else "miss" for r in fixed)) for n in ablations}
    report={"experiment":"h1589_equality_gate_collision_audit","hardware_execution":"none_cached_only","selector_claim":"none",
            "new_observations":census(new),"distinct_direct_residual_bank":census(direct),
            "external_union_including_aliases":census(union),"fixed_ablation_bank_rows":len(fixed),"fixed_ablation_counts":counts,
            "profile_fields":PROFILE,"contradictory_profile_groups":collisions,
            "profile_function_status":"IMPOSSIBLE_ON_OBSERVED_BANK" if collisions else "NOT_FALSIFIED",
            "claim_boundary":"only_functions_of_listed_profile_fields_excluded_not_full_datapath_or_arbitrary_FSM",
            "new_rows":new,"sha256":{"script":digest(Path(__file__)),"source":previous["sha256"]["source"],
                                      "evidence":evidence,"models":previous["sha256"]["carry_models"],
                                      "ablation_models":previous["sha256"]["ablation_models"]}}
    with a.output.open("x") as out:json.dump(report,out,indent=2,sort_keys=True);out.write("\n")
    print(json.dumps({k:report[k] for k in ("new_observations","distinct_direct_residual_bank","external_union_including_aliases",
                                          "fixed_ablation_counts","profile_function_status")},sort_keys=True))
    print(f"contradictory_profile_groups={len(collisions)}")


if __name__=="__main__":main()
