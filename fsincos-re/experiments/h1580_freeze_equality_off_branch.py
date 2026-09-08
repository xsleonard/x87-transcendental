#!/usr/bin/env python3
"""Freeze the eleven new equality OFF-branch falsifiers, not an on-branch test."""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from h1570_freeze_exact_preimage_transfer import collision_signatures, digest


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True,type=Path)
    p.add_argument("--private-ledger-dir",required=True,type=Path)
    p.add_argument("--output-dir",required=True,type=Path)
    args=p.parse_args()
    if args.output_dir.exists():raise SystemExit("refusing existing kit")
    assert args.private_ledger_dir.is_dir()
    sources=[args.root/"tmp/ledger33/current"/n for n in ("h1577_equality_bank","h1579_equality_bank")]
    candidates=[]
    for directory,number in zip(sources,(1,10)):
        report=json.loads((directory/"bank.json").read_text())
        assert report["capture_state"]=="SOFTWARE_ONLY_NOT_FROZEN"
        assert report["counts"]["actual_equality_candidates"]==number
        assert report["counts"]["gate_counts"]=={"0":number}
        for c in report["candidates"]:
            assert c["prediction"]=="inclusive" and c["r1263_gate"]==0 and c["final_kill"]==0
            c=dict(c,bank=directory.name)
            candidates.append(c)
    assert len({c["operand"] for c in candidates})==len(candidates)==11
    signatures={c["operand"].split()[1] for c in candidates}
    allowed={f.resolve() for d in sources for f in d.iterdir() if f.is_file()}
    public=collision_signatures(signatures,args.root,allowed)
    private=collision_signatures(signatures,args.private_ledger_dir,set())
    if public or private:raise RuntimeError("selected evidence collides; no manifest frozen")
    rows=[]
    for c in sorted(candidates,key=lambda c:c["operand"]):
        mode=min(c["modes"],key=lambda m:("rn","rd","ru").index(m["mode"]))
        assert mode["baseline"]==mode["inclusive"]!=mode["strict"]
        rows.append({"case_id":f"E{len(rows)+1:03d}","capture_state":"FROZEN_UNOPENED",
                     "instruction":"fcos","precision_control":"pc64","mode":mode["mode"],
                     "operand":c["operand"],"baseline":mode["baseline"],"strict":mode["strict"],
                     "inclusive":mode["inclusive"],"s4":c["s4"],"rsh":c["rsh"],
                     "theta":c["theta"],"low3":c["low3"],"branch":c["branch"],
                     "held_carry":c["held_carry"],"final_kill":c["final_kill"],"r1263_gate":0,
                     "scope":"off_branch_false_negative_test_only","source_bank":c["bank"]})
    args.output_dir.mkdir(parents=True)
    manifest=args.output_dir/"manifest.tsv"
    with manifest.open("x",newline="") as target:
        w=csv.DictWriter(target,fieldnames=list(rows[0]),delimiter="\t");w.writeheader();w.writerows(rows)
    inputs=args.output_dir/"inputs";inputs.mkdir()
    lanes={}
    for mode in ("rn","rd","ru"):
        selected=[r for r in rows if r["mode"]==mode]
        if not selected:continue
        name="fcos_"+mode;path=inputs/(name+".txt")
        with path.open("x") as target:target.write("".join(r["operand"]+"\n" for r in selected))
        lanes[name]={"mode":mode,"instruction":"fcos","rows":len(selected),"sha256":digest(path)}
    template=args.root/"transfer-tests/h1573/run_capture.sh"
    prior=json.loads((template.parent/"FREEZE.json").read_text())
    assert digest(template)==prior["sha256"]["runner"]
    lines=template.read_text().splitlines()
    stop=next(i for i,s in enumerate(lines) if s.startswith('"$BIN" '))
    lines=[s.replace("H1573","H1580") for s in lines[:stop]]
    for name,lane in lanes.items():
        lines.append(f'"$BIN" {lane["mode"]} pc64 cos --status < inputs/{name}.txt > hardware-output/{name}.txt')
    lines += ["sha256sum hardware-output/fcos_*.txt > hardware-output/outputs.sha256",
              'echo "H1580_CAPTURE_COMPLETE tuples=11 repeats=0"']
    runner=args.output_dir/"run_capture.sh"
    with runner.open("x") as target:target.write("\n".join(lines)+"\n")
    freeze={"experiment":"h1580_equality_off_branch","capture_state":"FROZEN_UNOPENED",
            "unique_capture_tuples":11,"one_observation_maximum_per_tuple":True,
            "hardware_execution":"none","new_hardware_labels":"none","lanes":lanes,
            "claim_boundary":"only_R1263_off_branch_is_exercised_no_enabled_branch_validation",
            "selection_rule":"all_eleven_source_bank_candidates_one_nonredundant_mode_each",
            "r1263_gate_counts":{"0":11},"s4_counts":dict(Counter(str(r["s4"]) for r in rows)),
            "freshness":{"selected_repository_collision_count":0,"selected_private_collision_count":0,
                         "private_files_examined":sum(f.is_file() for f in args.private_ledger_dir.rglob("*")),
                         "private_identity_published":False},
            "sha256":{"source_banks":{d.name:digest(d/"bank.json") for d in sources},
                       "manifest":digest(manifest),"runner":digest(runner),"freezer":digest(Path(__file__)),
                       "runner_template":digest(template)}}
    path=args.output_dir/"FREEZE.json"
    with path.open("x") as target:json.dump(freeze,target,indent=2,sort_keys=True);target.write("\n")
    with (args.output_dir/"CHECKSUMS.sha256").open("x") as target:
        for f in [path,manifest,runner,*sorted(inputs.iterdir())]:target.write(f"{digest(f)}  {f.relative_to(args.output_dir)}\n")
    print(json.dumps({k:freeze[k] for k in ("unique_capture_tuples","freshness","r1263_gate_counts","s4_counts")},sort_keys=True))


if __name__=="__main__":main()
