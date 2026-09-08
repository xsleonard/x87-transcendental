#!/usr/bin/env python3
"""Post-capture compiler/independent replay; never execute hardware again."""
import argparse
import json
from collections import Counter
from pathlib import Path
import h1710_verify_paired_program as independent
from h1709_paired_retained_census import digest, save


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True,type=Path);p.add_argument('--output-dir',required=True,type=Path)
    a=p.parse_args();root=a.root.resolve();out=a.output_dir.resolve();assert not out.exists()
    kit=root/'transfer-tests/h1712'; opened=json.loads((kit/'OPENED.json').read_text())
    assert opened['status']=='OPENED_ONCE_DO_NOT_RERUN'
    assert digest(kit/'FREEZE.json')==opened['sha256']['freeze']
    assert digest(kit/'hardware-output/state-output.txt')==opened['sha256']['raw']
    freeze=json.loads((kit/'FREEZE.json').read_text())
    assert digest(kit/'manifest.json')==freeze['sha256']['manifest']
    entries=json.loads((kit/'manifest.json').read_text());by_operand={}
    for row in entries:
        previous=by_operand.setdefault(row['operand'],row['predictions'])
        assert previous==row['predictions']
    ops=sorted(by_operand);assert len(ops)==1150
    independent.constants(root);cache={};counts=Counter()
    path=root/'tmp/ledger33/current/h1710_independent_paired_program'
    old=json.loads((path/'report.json').read_text())
    for name,sha in old['sha256']['independent_modules'].items():assert digest(root/name)==sha,name
    for policy in ('baseline','last','all'):
        for config in ('O0','O2','O3','ubsan'):
            binary=path/(policy+'_'+config);assert digest(binary)==old['sha256']['binaries'][binary.name]
            for mode in ('rn','rd','ru','rz'):
                values,metas=independent.run(binary,mode,ops,True)
                for i,op in enumerate(ops):
                    value,meta=independent.expected(op,mode,policy,cache)
                    assert (values[i],metas.get(i))==(value,meta)
                    frozen=by_operand[op][policy][mode]
                    assert frozen['outputs']==(list(value) if value else None)
                    assert frozen['path']==(meta[0] if meta else 'range')
                    assert frozen['C1']==(meta[3] if meta and meta[1] else None)
                    counts['instruction_rows']+=1
                    counts['lane_outputs']+=2 if value else 0
                    counts['per_lane_C1']+=2 if meta and meta[1] else 0
            print(policy,config,'frozen/independent replay pass',flush=True)
    out.mkdir(parents=True)
    save(out/'report.json',dict(experiment='h1712_verify_opened_paired',status='PASS_FROZEN_COMPILER_REPLAY',
        counts=dict(counts),hardware_execution='none_replay_only',candidate_changed=False,
        sha256=dict(script=digest(Path(__file__)),freeze=digest(kit/'FREEZE.json'),opened=digest(kit/'OPENED.json'),
            independent_report=digest(path/'report.json'),verifier=digest(Path(independent.__file__)))))
    print(dict(counts),flush=True)


if __name__=='__main__':main()
