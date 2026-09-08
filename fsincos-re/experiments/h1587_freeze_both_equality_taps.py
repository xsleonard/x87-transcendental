#!/usr/bin/env python3
"""Freeze a bounded two-tap, two-branch challenge; reject every prior tuple."""
from __future__ import annotations
import argparse
import csv
import json
from collections import Counter,defaultdict
from pathlib import Path
from h1570_freeze_exact_preimage_transfer import collision_signatures,digest


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True,type=Path)
    p.add_argument("--private-ledger-dir",required=True,type=Path)
    p.add_argument("--output-dir",required=True,type=Path)
    a=p.parse_args()
    if a.output_dir.exists():raise SystemExit("refusing an existing campaign directory")
    assert a.private_ledger_dir.is_dir()
    current=a.root/"tmp/ledger33/current"
    banks=[current/n for n in ("h1584_equality_control_bank","h1584_equality_control_bank_r8192","h1586_stream_control_plateaus")]
    source=banks[-1]/"bank.json";bank=json.loads(source.read_text())
    assert bank["capture_state"]=="SOFTWARE_ONLY_NOT_FROZEN"
    assert digest(a.root/"src/fsincos_skylake.c")==bank["sha256"]["source"]
    candidates=bank["candidates"]
    assert len(candidates)==bank["counts"]["actual_equality_candidates"]
    for c in candidates:
        assert int(c["trace"]["rd3"],16)==1<<(c["rsh"]+c["tap"]-1)
        assert int(c["trace"]["tc_rf_sig"],16)==int(c["scanner_row"]["positive_proxy"],16)
        assert int(c["trace"][f"b{c['tap']}"])==1-c["r1263_gate"]
    assert len({r["operand"] for r in candidates})==len(candidates)
    sigs={r["operand"].split()[1] for r in candidates}
    allowed={f.resolve() for d in banks for f in d.rglob("*") if f.is_file()}
    public=collision_signatures(sigs,a.root,allowed)
    private=collision_signatures(sigs,a.private_ledger_dir,set())
    buckets=defaultdict(list)
    for c in candidates:
        if c["operand"].split()[1] not in public|private:buckets[c["tap"],c["r1263_gate"]].append(c)
    chosen=[]
    for key in sorted(buckets):chosen.extend(sorted(buckets[key],key=lambda c:c["operand"])[:8])
    if not chosen:raise RuntimeError("no fresh candidate; no manifest frozen")
    rows=[]
    for c in sorted(chosen,key=lambda c:c["operand"]):
        mode=min(c["modes"],key=lambda m:("rn","rd","ru").index(m["mode"]))
        assert c["prediction"]==("strict" if c["r1263_gate"] else "inclusive")
        assert mode["baseline"]==mode[c["prediction"]] and mode["strict"]!=mode["inclusive"]
        rows.append({"case_id":f"Q{len(rows)+1:03d}","capture_state":"FROZEN_UNOPENED","instruction":"fcos",
                     "precision_control":"pc64","mode":mode["mode"],"operand":c["operand"],
                     "baseline":mode["baseline"],"strict":mode["strict"],"inclusive":mode["inclusive"],
                     "prediction":c["prediction"],"tap":c["tap"],"r1263_gate":c["r1263_gate"],
                     "held_carry":c["held_carry"],"final_kill":c["final_kill"],"s4":c["s4"],"rsh":c["rsh"],
                     "theta":c["theta"],"low3":c["low3"],"branch":c["branch"],
                     "anchor":c["scanner_row"]["anchor"],"plateau_offset":c["scanner_row"]["plateau_offset"]})
    a.output_dir.mkdir(parents=True);manifest=a.output_dir/"manifest.tsv"
    with manifest.open("x",newline="") as out:
        w=csv.DictWriter(out,fieldnames=list(rows[0]),delimiter="\t");w.writeheader();w.writerows(rows)
    inputs=a.output_dir/"inputs";inputs.mkdir();lanes={}
    for mode in ("rn","rd","ru"):
        subset=[r for r in rows if r["mode"]==mode]
        if not subset:continue
        name="fcos_"+mode;path=inputs/(name+".txt")
        with path.open("x") as out:out.write("".join(r["operand"]+"\n" for r in subset))
        lanes[name]={"instruction":"fcos","mode":mode,"rows":len(subset),"sha256":digest(path)}
    template=a.root/"transfer-tests/h1580/run_capture.sh"
    old=json.loads((template.parent/"FREEZE.json").read_text());assert digest(template)==old["sha256"]["runner"]
    lines=template.read_text().splitlines();stop=next(i for i,l in enumerate(lines) if l.startswith('"$BIN" '))
    lines=[l.replace("H1580","H1587") for l in lines[:stop]]
    for name,lane in lanes.items():
        lines.append(f'"$BIN" {lane["mode"]} pc64 cos --status < inputs/{name}.txt > hardware-output/{name}.txt')
    lines.extend(["sha256sum hardware-output/fcos_*.txt > hardware-output/outputs.sha256",
                  f'echo "H1587_CAPTURE_COMPLETE tuples={len(rows)} repeats=0"'])
    runner=a.output_dir/"run_capture.sh"
    with runner.open("x") as out:out.write("\n".join(lines)+"\n")
    freeze={"experiment":"h1587_both_equality_taps","capture_state":"FROZEN_UNOPENED",
            "hardware_execution":"none","new_hardware_labels":"none","one_observation_maximum_per_tuple":True,
            "unique_capture_tuples":len(rows),"lanes":lanes,
            "selection_rule":"first_eight_fresh_operands_sorted_per_tap_gate_cell_one_mode_RN_RD_RU_priority",
            "tap_gate_counts":dict(Counter(f"b{r['tap']}/gate{r['r1263_gate']}" for r in rows)),
            "fresh_candidates_before_cell_cap":sum(map(len,buckets.values())),
            "source_rejected_proxy_rows_not_eligible":bank["counts"]["rejected"],
            "claim_boundary":"bounded_two_threshold_equality_challenge_not_selector_proof",
            "freshness":{"rejected_repository_significands":len(public),"rejected_private_significands":len(private),
                         "selected_repository_collision_count":0,"selected_private_collision_count":0,
                         "private_files_examined":sum(f.is_file() for f in a.private_ledger_dir.rglob("*")),
                         "private_identity_published":False},
            "sha256":{"source_bank":digest(source),"manifest":digest(manifest),"runner":digest(runner),
                       "source":bank["sha256"]["source"],"freezer":digest(Path(__file__)),"template":digest(template)}}
    frozen=a.output_dir/"FREEZE.json"
    with frozen.open("x") as out:json.dump(freeze,out,indent=2,sort_keys=True);out.write("\n")
    with (a.output_dir/"CHECKSUMS.sha256").open("x") as out:
        for f in (frozen,manifest,runner,*sorted(inputs.iterdir())):out.write(f"{digest(f)}  {f.relative_to(a.output_dir)}\n")
    print(json.dumps({k:freeze[k] for k in ("unique_capture_tuples","tap_gate_counts","freshness")},sort_keys=True))


if __name__=="__main__":main()
