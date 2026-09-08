#!/usr/bin/env python3
"""Independently parse/recompute every already opened H1641 capture row.

Reuses the separate rational graph and integer tiny specification, not the
H1642 raw parser or score booleans. Unknown status is summarized as observation,
never converted to a retroactive prediction. No hardware/private-ledger action.
"""
from __future__ import annotations
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
import h1639_remaining_scope_proposals as proposals
from h1640_remaining_scope_freshness import save

KIT = 'transfer-tests/h1641'
SCORE = 'tmp/ledger33/current/h1642_score_remaining_scope'
LOCKS = {
    KIT+'/FREEZE.json':'066ac4f086d9132ba157195af02a3aaffaccb4f3e05c5337a4689b634f35f833',
    KIT+'/manifest.json':'453ecfe5ab81dc49c23cd045d85af341df3e8e6b2125cca6dd7c064568d06a84',
    SCORE+'/report.json':'8f19ff7e9a95df22824497abec43b765ee73d832296444bed9976b86b7092293',
}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--output-dir',required=True,type=Path)
    args=parser.parse_args(); root,output=args.root.resolve(),args.output_dir.resolve()
    assert not output.exists()
    digest=proposals.candidate.table.records.digest
    for name,sha in LOCKS.items(): assert digest(root/name)==sha,name
    freeze=json.loads((root/KIT/'FREEZE.json').read_text())
    report=json.loads((root/SCORE/'report.json').read_text())
    rows=json.loads((root/KIT/'manifest.json').read_text())
    for name,sha in freeze['sha256']['evidence'].items(): assert digest(root/name)==sha,name
    assert digest(root/SCORE/'score.json')==report['sha256']['score']
    scored={r['case_id']:r for r in json.loads((root/SCORE/'score.json').read_text())}
    model=json.loads((root/proposals.MODELS/'report.json').read_text())
    proposals.independent.initialize_proof(root)
    counts=Counter(); unpredicted=defaultdict(Counter); pc_groups=defaultdict(list); recomputed=[]
    for name,lane in sorted(freeze['lanes'].items()):
        selected=[r for r in rows if r['lane']==name]
        operands=[r['operand'] for r in selected]
        assert (root/KIT/'inputs'/f'{name}.txt').read_text().splitlines()==operands
        path=root/KIT/'hardware-output'/f'{name}.txt'
        assert digest(path)==report['sha256']['raw_outputs'][path.name]
        lines=path.read_text().splitlines()
        assert len(lines)==len(selected)==lane['rows']
        actual=[]
        for r,line in zip(selected,lines):
            fields=line.lower().split()
            assert fields[-2]=='sw' and len(fields[-1])==4
            sw=int(fields[-1],16)
            if fields[0]=='c2':
                assert len(fields)==3 and sw&0x400
                value='C2'
            else:
                assert fields[0]=='ok' and len(fields)==5 and not sw&0x400
                assert len(fields[1])==4 and len(fields[2])==16
                int(fields[1]+fields[2],16)
                value=fields[1]+':'+fields[2]
            # The OK format has five fields: the explicit arity check above
            # rejects arbitrary trailing output tokens.
            actual.append((value,sw))
        insn,mode=lane['instruction'],lane['mode']
        for label in ('candidate_O0','candidate_O2','candidate_O3','candidate_ubsan'):
            binary=root/proposals.MODELS/label
            assert digest(binary)==model['sha256']['binaries'][label]
            values,metadata,_=proposals.candidate.run(binary,insn,mode,operands)
            assert values==[v for v,_ in actual]
            assert [metadata.get(i) for i in range(len(operands))]==[r['metadata'] for r in selected]
            counts['compiler_output_checks']+=len(selected)
        for r,(value,sw) in zip(selected,actual):
            small=proposals.candidate.spec.evaluate(r['operand'],insn,mode)
            meta=r['metadata']
            if meta and meta['lane'] in ('polynomial','table'):
                expected,c1,_,center=proposals.independent.verify_hit(r['operand'],insn,mode,meta)
                assert center==r['exact_center']
                route=meta['lane']
            else:
                expected,c1=small['output'],small['C1']
                route=small['path']
            assert value==expected==r['output']
            assert c1==r['C1'] and small['exception_flags']==r['exception_flags']
            if c1 is not None:
                assert ((sw>>9)&1)==c1
                counts['C1_checks']+=1
            if small['exception_flags'] is not None:
                assert (sw&0x3f)==small['exception_flags']
                counts['exception_mask_checks']+=1
            if c1 is None or small['exception_flags'] is None:
                for kind in r['kinds']: unpredicted[kind+'/'+insn][f'{sw:04x}']+=1
            previous=scored[r['case_id']]
            assert (previous['hardware'],previous['hardware_SW'])==(value,f'{sw:04x}')
            counts['outputs']+=1; counts['route/'+route]+=1
            pc_groups[(insn,mode,r['operand'])].append((value,sw))
            recomputed.append(dict(case_id=r['case_id'],output=value,SW=f'{sw:04x}',route=route,C1_prediction=c1,
                exception_mask_prediction=small['exception_flags']))
    assert counts['outputs']==6432 and counts['C1_checks']==4512 and counts['exception_mask_checks']==3744
    assert len(pc_groups)==2144 and all(len(v)==3 and len(set(v))==1 for v in pc_groups.values())
    output.mkdir(parents=True)
    save(output/'recomputed.json',recomputed)
    result=dict(experiment='h1643_independent_remaining_scope',status='PASS_ALL_OPENED_ROWS',counts=dict(counts),
        independent_PC_groups=len(pc_groups),unpredicted_status_observations={k:dict(v) for k,v in unpredicted.items()},
        hardware_execution='none',private_ledger_access='none',candidate_or_paper_change='none',
        claim_boundary='Independent raw parsing, rational/integer recomputation and four-build software comparisons of existing H1641 labels. Not new hardware, a second independent silicon dataset or proof of universal semantics; unknown flags remain descriptive observations.',
        sha256=dict(script=digest(Path(__file__)),evidence=LOCKS,recomputed=digest(output/'recomputed.json')))
    save(output/'report.json',result)
    print(json.dumps(dict(status=result['status'],counts=result['counts'],independent_PC_groups=len(pc_groups)),sort_keys=True),flush=True)


if __name__=='__main__': main()
