#!/usr/bin/env python3
"""Scale the fixed equality challenge with bounded-memory software replay.

Preserves every raw generated preimage in gzip, validates its exact integer
equations, and independently checks all emitted endpoint differences against
the separately compiled constant-tap models.  No hardware labels are opened.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import subprocess
from collections import Counter
from pathlib import Path

from h1400_causal_stage_localization import digest, run
from h1210_stagea_residual_reframe import parse_dump, run as dump_run
from h1400_p5_representation_audit import tree_variants
from h1479_r1475_topology_isomorphism import trace_tree


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--scanner", required=True, type=Path)
    parser.add_argument("--filter", required=True, type=Path)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--max-externals", type=int, default=500000)
    parser.add_argument("--seed", default="0xb7e151628aed2a6b")
    args = parser.parse_args()
    if args.output_dir.exists():
        raise SystemExit(f"refusing to overwrite {args.output_dir}")
    old_dir = args.root / "tmp/ledger33/current/h1577_equality_bank"
    old = json.loads((old_dir / "bank.json").read_text())
    assert digest(args.scanner) == old["sha256"]["scanner"]
    assert digest(args.baseline) == old["sha256"]["models"]["baseline"]
    assert digest(args.root / "src/fsincos_skylake.c") == old["sha256"]["source"]
    models = {"baseline": args.baseline.resolve(), "strict": (old_dir / "strict").resolve(),
              "inclusive": (old_dir / "inclusive").resolve()}
    assert {n: digest(p) for n,p in models.items()} == old["sha256"]["models"]
    assert digest(old_dir / "raw_proxy_preimages.tsv") == old["sha256"]["raw"]
    with (old_dir / "raw_proxy_preimages.tsv").open("rb") as input_file:
        check = subprocess.run([str(args.filter.resolve())], stdin=input_file,
                               capture_output=True, check=True, text=True)
    expected = {(c["operand"], m["mode"], m["strict"], m["inclusive"])
                for c in old["candidates"] for m in c["modes"]}
    actual = {tuple(line.split("\t")) for line in check.stdout.splitlines()}
    assert old["counts"]["rejected"] == {} and actual == expected
    assert check.stderr.strip() == f"input_rows=50000 visible_mode_rows={len(expected)}"
    args.output_dir.mkdir(parents=True)
    with (args.output_dir / "filter_parity_check.txt").open("x") as target:
        target.write(check.stdout + check.stderr)
    print("streaming filter matches the independent 50,000-row constant-tap replay", flush=True)
    command = [str(args.scanner.resolve()), "1000000", args.seed, str(args.max_externals)]
    raw_hash = hashlib.sha256()
    count = 0
    archived = args.output_dir / "raw_proxy_preimages.tsv.gz"
    visible_path = args.output_dir / "visible_endpoints.tsv"
    with archived.open("xb") as raw_file, gzip.GzipFile(fileobj=raw_file, mode="wb", mtime=0) as compressed, \
            visible_path.open("xb") as output_file:
        scan = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        filtered = subprocess.Popen([str(args.filter.resolve())], stdin=subprocess.PIPE,
                                    stdout=output_file, stderr=subprocess.PIPE)
        assert scan.stdout is not None and filtered.stdin is not None
        columns = None
        for line in scan.stdout:
            raw_hash.update(line)
            compressed.write(line)
            filtered.stdin.write(line)
            fields = line.decode().rstrip("\n").split("\t")
            if columns is None:
                columns = fields
                continue
            row = dict(zip(columns,fields))
            sig = int(row["operand"].split()[1],16)
            square = sig*sig>>61
            fourth = int(row["fourth"],16)
            shift = int(row["rsh"])
            product = fourth*int(row["positive_proxy"],16)
            assert square*square>>int(row["s4"]) == fourth
            assert (square*square).bit_length()-67 == int(row["s4"])
            assert product.bit_length()-67 == shift
            r = product% (1<<shift)
            assert r == int(row["rdisc_proxy"],16)
            block=1<<(shift-16)
            assert 3*r-(2*r%block)-(r%block) == 3*r-(3*r%block) == 1<<shift
            count += 1
            if count%100000==0:
                print(f"exact proxy preimages checked: {count}", flush=True)
        filtered.stdin.close()
        scanner_stderr = scan.stderr.read().decode() if scan.stderr is not None else ""
        filter_stderr = filtered.stderr.read().decode() if filtered.stderr is not None else ""
        assert scan.wait()==filtered.wait()==0
    with (args.output_dir / "run_summary.txt").open("x") as target:
        target.write(scanner_stderr+filter_stderr)
    visible = [tuple(line.split("\t")) for line in visible_path.read_text().splitlines()]
    assert len(set(visible)) == len(visible), "duplicate software rows require explicit reconciliation"
    selected_ops = {r[0] for r in visible}
    originals = {}
    with gzip.open(archived,"rt") as data:
        for row in csv.DictReader(data,delimiter="\t"):
            if row["operand"] in selected_ops:
                originals[row["operand"]] = row
    operands = sorted(selected_ops)
    outputs = {n: {} for n in models}
    for n,p in models.items():
        for mode in ("rn","rd","ru"):
            outputs[n].update(run(p,mode,operands))
    for op,mode,strict,inclusive in visible:
        assert outputs["strict"][mode,op] == strict
        assert outputs["inclusive"][mode,op] == inclusive
    _, stderr = dump_run(models["baseline"],"rn",operands,dump=True)
    traces = {r["op"]: r for r in parse_dump(stderr,operands)}
    config = next(c for n,_,c in tree_variants() if n=="patent")
    candidates, rejected = [], Counter()
    for operand in operands:
        row=traces[operand]
        if "rd3" not in row or int(row["rd3"],16) != 1<<int(row["rsh"]):
            rejected["not_actual_b1_equality"]+=1
            continue
        if int(row["side"])!=1 or int(row["b2"])!=0:
            rejected["wrong_side_or_b2"]+=1
            continue
        if int(row["tc_rf_sig"],16)!=int(originals[operand]["positive_proxy"],16):
            rejected["positive_proxy_mismatch"]+=1
            continue
        nodes,_,final=trace_tree(row,config)
        shift=int(row["rsh"])
        held=(nodes["l2_2"][1]>>(shift+4))&1
        kill=1^(((final[0]|final[1])>>(shift+15))&1)
        gate=held&kill
        assert int(row["b1"])==1-gate
        prediction="strict" if gate else "inclusive"
        mode_rows=[]
        for mode in ("rn","rd","ru"):
            key=mode,operand
            assert outputs["baseline"][key]==outputs[prediction][key]
            if outputs["strict"][key]!=outputs["inclusive"][key]:
                mode_rows.append({"mode":mode,**{n:out[key] for n,out in outputs.items()}})
        candidates.append({"operand":operand,"s4":int(row["s4"]),"rsh":shift,
                           "theta":int(row["theta"]),"low3":int(row["low3"]),"branch":row["branch"],
                           "held_carry":held,"final_kill":kill,"r1263_gate":gate,
                           "prediction":prediction,"modes":mode_rows,"scanner_row":originals[operand],
                           "trace":{k:row[k] for k in ("rd3","tc_f4_sig","tc_rf_sig","b1","b2")}})
    counts={"raw_preimages":count,"visible_mode_rows":len(visible),"visible_operands":len(operands),
            "actual_equality_candidates":len(candidates),"rejected":dict(rejected),
            "gate_counts":dict(Counter(str(c["r1263_gate"]) for c in candidates)),
            "s4_gate_counts":dict(Counter(f"{c['s4']}/{c['r1263_gate']}" for c in candidates))}
    report={"experiment":"h1579_stream_equality_bank","capture_state":"SOFTWARE_ONLY_NOT_FROZEN",
            "hardware_execution":"none","new_hardware_labels":"none","selector_claim":"none",
            "generator_arguments":command[1:],"counts":counts,"candidates":candidates,
            "claim_boundary":"sampled_exact_proxy_preimages_with_current_source_and_independent_tree_replay",
            "sha256":{"source":old["sha256"]["source"],"models":old["sha256"]["models"],
                       "script":digest(Path(__file__)),"scanner":digest(args.scanner),"filter":digest(args.filter),
                       "filter_source":digest(args.root/"experiments/h1578_stream_equality_endpoints.c"),
                       "raw_uncompressed":raw_hash.hexdigest(),"raw_gzip":digest(archived),
                       "visible_endpoints":digest(visible_path),"run_summary":digest(args.output_dir/"run_summary.txt"),
                       "filter_parity_check":digest(args.output_dir/"filter_parity_check.txt"),
                       "h1577_bank":digest(old_dir/"bank.json")}}
    with (args.output_dir/"bank.json").open("x") as target:
        json.dump(report,target,indent=2,sort_keys=True)
        target.write("\n")
    print(json.dumps(counts,sort_keys=True),flush=True)


if __name__=="__main__":
    main()
