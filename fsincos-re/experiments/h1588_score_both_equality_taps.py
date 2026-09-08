#!/usr/bin/env python3
"""Score the fixed two-threshold challenge, keeping branch coverage explicit."""
from __future__ import annotations
import argparse
import csv
import json
from collections import Counter,defaultdict
from pathlib import Path
from h1474_score_r1382_lattice import parse_hardware_line
from h1570_freeze_exact_preimage_transfer import digest


def classify(row: dict,value: str) -> tuple[str,str]:
    assert row["prediction"] in ("strict","inclusive")
    assert row["baseline"]==row[row["prediction"]] and row["strict"]!=row["inclusive"]
    endpoint="strict" if value==row["strict"] else "inclusive" if value==row["inclusive"] else "other"
    return endpoint,"EXACT" if value==row["baseline"] else "MISS"


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--kit",required=True,type=Path)
    p.add_argument("--output-prefix",required=True,type=Path)
    p.add_argument("--mark-opened",action="store_true")
    a=p.parse_args()
    for prediction in ("strict","inclusive"):
        row={"strict":"0","inclusive":"1","prediction":prediction,"baseline":"0" if prediction=="strict" else "1"}
        for value in ("0","1","2"):
            endpoint,verdict=classify(row,value)
            assert endpoint=={"0":"strict","1":"inclusive","2":"other"}[value]
            assert (verdict=="EXACT")== (value==row["baseline"])
    score=a.output_prefix.with_name(a.output_prefix.name+"_score.tsv")
    report_path=a.output_prefix.with_name(a.output_prefix.name+"_report.json");opened=a.kit/"OPENED.json"
    if score.exists() or report_path.exists() or (a.mark_opened and opened.exists()):
        raise SystemExit("refusing to overwrite evidence")
    for line in (a.kit/"CHECKSUMS.sha256").read_text().splitlines():
        h,n=line.split(None,1);rel=Path(n.strip())
        assert not rel.is_absolute() and ".." not in rel.parts and digest(a.kit/rel)==h
    frozen=a.kit/"FREEZE.json";freeze=json.loads(frozen.read_text())
    assert freeze["experiment"]=="h1587_both_equality_taps" and freeze["capture_state"]=="FROZEN_UNOPENED"
    assert freeze["one_observation_maximum_per_tuple"] is True
    manifest=a.kit/"manifest.tsv";assert digest(manifest)==freeze["sha256"]["manifest"]
    rows=list(csv.DictReader(manifest.open(),delimiter="\t"));n=len(rows)
    assert n==freeze["unique_capture_tuples"] and 0<n<=32
    assert len({r["case_id"] for r in rows})==len({(r["mode"],r["operand"]) for r in rows})==n
    raw=a.kit/"hardware-output"
    hashes={Path(name.strip()).name:h for h,name in (l.split(None,1) for l in (raw/"outputs.sha256").read_text().splitlines())}
    assert set(hashes)=={name+".txt" for name in freeze["lanes"]}
    assert (raw/"binary.sha256").read_text().split()[0]=="9eef49556c7da32c270b1f1c29f777bfffbba7eb85a68ddb512e8e7e1a192af1"
    observed={}
    for name,lane in freeze["lanes"].items():
        selected=[r for r in rows if (r["instruction"],r["mode"])==(lane["instruction"],lane["mode"])]
        inputs=a.kit/"inputs"/(name+".txt");assert digest(inputs)==lane["sha256"]
        assert inputs.read_text().splitlines()==[r["operand"] for r in selected]
        path=raw/(name+".txt");lines=path.read_text().splitlines()
        assert len(lines)==len(selected)==lane["rows"] and digest(path)==hashes[path.name]
        for i,(r,line) in enumerate(zip(selected,lines),1):observed[r["case_id"]]=parse_hardware_line(line,path,i)
    assert set(observed)=={r["case_id"] for r in rows}
    counts=Counter();cells=defaultdict(Counter);scored=[]
    for r in rows:
        assert r["instruction"]=="fcos" and r["precision_control"]=="pc64" and r["capture_state"]=="FROZEN_UNOPENED"
        assert r["tap"] in ("1","2") and r["r1263_gate"] in ("0","1")
        assert r["prediction"]==("strict" if r["r1263_gate"]=="1" else "inclusive")
        value,status=observed[r["case_id"]];endpoint,verdict=classify(r,value)
        counts["baseline."+verdict]+=1;counts["endpoint."+endpoint]+=1
        cell=f"b{r['tap']}/gate{r['r1263_gate']}"
        cells[cell]["observed"]+=1;cells[cell]["baseline."+verdict]+=1;cells[cell]["endpoint."+endpoint]+=1
        scored.append(dict(r,hardware=value,hardware_status=status,endpoint=endpoint,baseline_verdict=verdict))
    assert {k:v["observed"] for k,v in cells.items()}==freeze["tap_gate_counts"]
    score.parent.mkdir(parents=True,exist_ok=True)
    with score.open("x",newline="") as out:
        w=csv.DictWriter(out,fieldnames=list(scored[0]),delimiter="\t");w.writeheader();w.writerows(scored)
    report={"experiment":"h1588_score_both_equality_taps","observed_rows":n,"repeats":0,
            "counts":dict(sorted(counts.items())),"cells":{k:dict(v) for k,v in sorted(cells.items())},
            "verdict":"CURRENT_RULE_SURVIVES_FINITE_BANK" if counts["baseline.EXACT"]==n else "CURRENT_RULE_FALSIFIED",
            "claim_boundary":"bounded_branch_coverage_not_global_selector_or_physical_cause_proof",
            "sha256":{"freeze":digest(frozen),"manifest":digest(manifest),"score":digest(score),
                       "scorer":digest(Path(__file__)),"raw_captures":hashes}}
    with report_path.open("x") as out:json.dump(report,out,indent=2,sort_keys=True);out.write("\n")
    if a.mark_opened:
        record={"experiment":freeze["experiment"],"capture_state":"OPENED_ONCE","unique_capture_tuples":n,"repeats":0,
                "hardware":"skylake_xeon_vm_oracle","paper_change":"none","emulator_change":"none",
                "counts":report["counts"],"cells":report["cells"],"verdict":report["verdict"],"freshness":freeze["freshness"],
                "sha256":dict(report["sha256"],report=digest(report_path),
                              capture_metadata={f.name:digest(f) for f in raw.iterdir() if f.name not in hashes})}
        with opened.open("x") as out:json.dump(record,out,indent=2,sort_keys=True);out.write("\n")
    print(json.dumps({k:report[k] for k in ("observed_rows","counts","cells","verdict")},sort_keys=True))


if __name__=="__main__":main()
