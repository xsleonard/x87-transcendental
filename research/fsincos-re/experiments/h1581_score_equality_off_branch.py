#!/usr/bin/env python3
"""Score H1580 without confusing an off-branch challenge with gate validation."""
from __future__ import annotations
import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from h1474_score_r1382_lattice import parse_hardware_line
from h1570_freeze_exact_preimage_transfer import digest


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--kit",required=True,type=Path)
    p.add_argument("--output-prefix",required=True,type=Path)
    p.add_argument("--mark-opened",action="store_true")
    a=p.parse_args()
    score=a.output_prefix.with_name(a.output_prefix.name+"_score.tsv")
    report_path=a.output_prefix.with_name(a.output_prefix.name+"_report.json")
    opened=a.kit/"OPENED.json"
    if score.exists() or report_path.exists() or (a.mark_opened and opened.exists()):
        raise SystemExit("refusing to overwrite evidence")
    for line in (a.kit/"CHECKSUMS.sha256").read_text().splitlines():
        h,n=line.split(None,1);rel=Path(n.strip())
        assert not rel.is_absolute() and ".." not in rel.parts
        assert digest(a.kit/rel)==h
    freeze=json.loads((a.kit/"FREEZE.json").read_text())
    assert freeze["experiment"]=="h1580_equality_off_branch"
    assert freeze["capture_state"]=="FROZEN_UNOPENED" and freeze["one_observation_maximum_per_tuple"] is True
    manifest=a.kit/"manifest.tsv"
    assert digest(manifest)==freeze["sha256"]["manifest"]
    rows=list(csv.DictReader(manifest.open(),delimiter="\t"))
    assert len(rows)==freeze["unique_capture_tuples"]==11
    assert len({r["case_id"] for r in rows})==11
    assert len({(r["instruction"],r["mode"],r["operand"]) for r in rows})==11
    raw=a.kit/"hardware-output"
    hashes={Path(n.strip()).name:h for h,n in (l.split(None,1) for l in (raw/"outputs.sha256").read_text().splitlines())}
    assert set(hashes)=={name+".txt" for name in freeze["lanes"]}
    assert (raw/"binary.sha256").read_text().split()[0]=="9eef49556c7da32c270b1f1c29f777bfffbba7eb85a68ddb512e8e7e1a192af1"
    observed={}
    for name,lane in freeze["lanes"].items():
        selected=[r for r in rows if r["mode"]==lane["mode"]]
        inputs=a.kit/"inputs"/(name+".txt")
        assert digest(inputs)==lane["sha256"]
        assert inputs.read_text().splitlines()==[r["operand"] for r in selected]
        path=raw/(name+".txt");lines=path.read_text().splitlines()
        assert len(lines)==len(selected)==lane["rows"] and digest(path)==hashes[path.name]
        for i,(r,line) in enumerate(zip(selected,lines),1):observed[r["case_id"]]=parse_hardware_line(line,path,i)
    assert set(observed)=={r["case_id"] for r in rows}
    counts=Counter();scored=[]
    for r in rows:
        assert r["r1263_gate"]=="0" and r["capture_state"]=="FROZEN_UNOPENED"
        assert r["instruction"]=="fcos" and r["precision_control"]=="pc64"
        assert r["baseline"]==r["inclusive"]!=r["strict"]
        value,status=observed[r["case_id"]]
        endpoint="inclusive" if value==r["inclusive"] else "strict" if value==r["strict"] else "other"
        verdict="EXACT" if value==r["baseline"] else "MISS"
        counts["endpoint."+endpoint]+=1;counts["baseline."+verdict]+=1
        scored.append(dict(r,hardware=value,hardware_status=status,endpoint=endpoint,baseline_verdict=verdict))
    score.parent.mkdir(parents=True,exist_ok=True)
    with score.open("x",newline="") as target:
        w=csv.DictWriter(target,fieldnames=list(scored[0]),delimiter="\t");w.writeheader();w.writerows(scored)
    report={"experiment":"h1581_score_equality_off_branch","observed_rows":11,"repeats":0,
            "counts":dict(sorted(counts.items())),"enabled_branch_observations":0,
            "verdict":("OFF_BRANCH_SURVIVES_FINITE_BANK" if counts["baseline.EXACT"]==11 else
                       "OFF_BRANCH_OTHER_ENDPOINT_FOUND" if counts["endpoint.other"] else "OFF_BRANCH_FALSE_NEGATIVE_FOUND"),
            "claim_boundary":"not_enabled_branch_or_global_R1263_validation",
            "sha256":{"freeze":digest(a.kit/"FREEZE.json"),"manifest":digest(manifest),"score":digest(score),
                       "scorer":digest(Path(__file__)),"raw_captures":hashes}}
    with report_path.open("x") as target:json.dump(report,target,indent=2,sort_keys=True);target.write("\n")
    if a.mark_opened:
        record={"experiment":freeze["experiment"],"capture_state":"OPENED_ONCE","unique_capture_tuples":11,
                "repeats":0,"hardware":"skylake_xeon_vm_oracle","paper_change":"none","emulator_change":"none",
                "counts":report["counts"],"verdict":report["verdict"],"enabled_branch_observations":0,
                "freshness":freeze["freshness"],
                "sha256":dict(report["sha256"],report=digest(report_path),
                              capture_metadata={f.name:digest(f) for f in raw.iterdir() if f.name not in hashes})}
        with opened.open("x") as target:json.dump(record,target,indent=2,sort_keys=True);target.write("\n")
    print(json.dumps({k:report[k] for k in ("observed_rows","counts","verdict","enabled_branch_observations")},sort_keys=True))


if __name__=="__main__":main()
