#!/usr/bin/env python3
"""Freeze software predictions before challenging masked architectural state.

No hardware or private-history access. Each operand gets only one prestate;
even the old, narrower instruction/RC/PC/operand tuples remain unique. The
full initial state is recorded additionally, not used to permit recaptures.
"""
from __future__ import annotations
import argparse
import json
import random
from collections import Counter
from dataclasses import asdict
from pathlib import Path
import h1639_remaining_scope_proposals as numerical
import h1645_masked_status_model as status
from h1640_remaining_scope_freshness import save

MODEL_DIR=numerical.MODELS
LOCKS={**numerical.LOCKS,
    'experiments/h1645_masked_status_model.py':'d00bbf0adf069be0e2553712c45df96eb1e457dfe74b8403e27b61f69eda0fc5',
    'capture-kit/x87_masked_transition_capture.c':'c718ded47f49a8a4d84532eb2d7eab9ec811bd52940806b97b56659ed961fddd',
    'capture-kit/x87_state_capture.c':'1b2df713deeb44576169c7f75e86a1365f92b6315da284280e8c76437588980b',
}
RC={'rn':0,'rd':0x400,'ru':0x800,'rz':0xc00}
PC={24:0,53:0x200,64:0x300}


def cc_bits(n): return ((n&1)<<8)|((n&2)<<8)|((n&4)<<8)|((n&8)<<11)


def proposals():
    rng=random.Random(0x1648)
    profiles=[dict(profile=f'C{n:02d}',cc=cc_bits(n),flags=0,depth=1+n%8) for n in range(16)]
    profiles += [dict(profile=f'F{n:02d}',cc=0x4700,flags=f,depth=1+n) for n,f in enumerate((1,2,4,8,16,32,0x41,0x7f))]
    rows=[]
    for profile in profiles:
        p=rng.getrandbits(63)|1; low=p&((1<<62)-1)
        assert low
        normal=(1<<63)|p
        empty_sig=(1<<63)|rng.getrandbits(63)|1
        specs=[('denormal',0,p,0),('pseudo_denormal',0,normal,0),('equivalent_normal',1,normal,0),
            ('quiet_nan',0x7fff,(3<<62)|low,0),('signaling_nan',0x7fff,(1<<63)|low,0),
            ('unnormal',0x3fff,p&((1<<63)-1),0),('pseudo_nan',0x7fff,p&((1<<63)-1),0),
            ('tiny_bypass',16383-69,normal,0),('tiny_sticky',16383-50,normal,0),
            ('polynomial',0x3ffc,normal,0),('table',0x3ffd,normal,0),
            ('reduced',0x400a,normal,0),('out_of_range',0x403e,normal,0),('empty_stack',0x3ffc,empty_sig,1)]
        for kind,e,sig,empty in specs:
            for sign in (0,0x8000):
                rows.append(dict(profile,operand=f'{e|sign:04x} {sig:016x}',kind=kind,empty=empty,
                    equivalence_pair=f'{profile["profile"]}/{sign>>15}' if kind in ('pseudo_denormal','equivalent_normal') else None))
    assert len(rows)==len({r['operand'] for r in rows})==672
    return rows


def numerical_predictions(root,rows):
    digest=numerical.candidate.table.records.digest
    report=json.loads((root/MODEL_DIR/'report.json').read_text())
    numerical.independent.initialize_proof(root)
    operands=[r['operand'] for r in rows]; answer={}
    for insn in ('fsin','fcos'):
        for mode in RC:
            reference=None
            for label in ('candidate_O0','candidate_O2','candidate_O3','candidate_ubsan'):
                binary=root/MODEL_DIR/label
                assert digest(binary)==report['sha256']['binaries'][label]
                values,metadata,_=numerical.candidate.run(binary,insn,mode,operands)
                if reference is None: reference=values,metadata
                assert reference==(values,metadata)
            values,metadata=reference
            for i,(op,value) in enumerate(zip(operands,values)):
                meta=metadata.get(i); small=numerical.candidate.spec.evaluate(op,insn,mode)
                if meta and meta['lane'] in ('polynomial','table'):
                    expected,c1,_,_=numerical.independent.verify_hit(op,insn,mode,meta)
                    assert expected==value and c1==meta['C1']
                else:
                    numerical.candidate.check_spec(op,insn,mode,value,meta)
                    assert small['output']==value
                    c1=small['C1']
                answer[(insn,mode,op)]=dict(numerical_output=value,numerical_C1=c1,metadata=meta)
    return answer


def predictions(root,rows):
    numbers=numerical_predictions(root,rows); answer=[]
    for insn in ('fsin','fcos'):
        for pc in PC:
            for mode in RC:
                for row in rows:
                    n=numbers[(insn,mode,row['operand'])]
                    top=(-row['depth'])&7
                    tag=((1<<row['depth'])-1)<<(8-row['depth'])
                    if row['empty']: tag&=~(1<<top)
                    sw=(top<<11)|row['cc']|row['flags']; cw=0x7f|PC[pc]|RC[mode]
                    se,sig=(int(w,16) for w in row['operand'].split())
                    result=status.masked(se,sig,insn,finite_output=n['numerical_output'],finite_C1=n['numerical_C1'],
                        before_status=sw,before_tag=tag,control_word=cw)
                    alternatives={}
                    for bit in (8,9,10,14):
                        if not result.status_known_mask&(1<<bit):
                            initial=(sw>>bit)&1
                            alternatives[str(bit)]=dict(clear=0,set=1,preserve=initial,invert=1-initial)
                    answer.append(dict(row,case_id=f'S{len(answer)+1:05d}',instruction=insn,mode=mode,pc=pc,
                        before_CW=cw,before_SW=sw,before_FTW=tag,expected=asdict(result),
                        numerical=n,unmodeled_bit_alternatives=alternatives,
                        deeper_register_relation='A_R1..A_R7 equal B_R1..B_R7, including empty-tag raw slots'))
    assert len(answer)==len({(r['instruction'],r['mode'],r['pc'],r['operand']) for r in answer})==16128
    # Equal-value pairs must agree on output/C1 and differ exactly in DE,
    # unless that bit was already set in the initial sticky exception mask.
    pairs={}
    for r in answer:
        if r['equivalence_pair']:
            key=(r['equivalence_pair'],r['instruction'],r['mode'],r['pc'])
            pairs.setdefault(key,{})[r['kind']]=r
    for pair in pairs.values():
        p,n=pair['pseudo_denormal']['expected'],pair['equivalent_normal']['expected']
        assert p['output']==n['output'] and p['C1']==n['C1']
        assert p['new_exception_flags']^n['new_exception_flags']==2
    assert len(pairs)==1152
    return answer


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True,type=Path); p.add_argument('--output-dir',required=True,type=Path)
    a=p.parse_args(); root,out=a.root.resolve(),a.output_dir.resolve(); assert not out.exists()
    digest=numerical.candidate.table.records.digest
    locks=dict(LOCKS)
    for name,sha in locks.items(): assert digest(root/name)==sha,name
    parent=json.loads((root/MODEL_DIR/'report.json').read_text())
    for name,sha in parent['sha256']['evidence'].items():
        assert digest(root/name)==sha,name
        locks[name]=sha
    rows=proposals(); predicted=predictions(root,rows)
    out.mkdir(parents=True)
    bank=dict(experiment='h1648_masked_state_proposals',capture_state='SOFTWARE_ONLY_NOT_FROZEN',
        operands=rows,predictions=predicted,unique_operands=len(rows),full_tuples=len(predicted),
        unique_significands=len({r['operand'].split()[1] for r in rows}),
        operand_kinds=dict(Counter(r['kind'] for r in rows)),profiles=24,equal_value_pairs=1152,
        prediction_scope='Frozen H1645 known bits, output, CW/TOP/tags/deeper-register relation. Unknown bits have explicit constant/preserve/invert discriminators, not successful predictions. No unmasked claim.',
        freshness='NOT AUDITED. Reject prior-visible significands before freeze; old instruction/RC/PC/operand identities remain unique even before recording prestate.',
        candidate_arithmetic_changed=False,status_model_changed=False,hardware_execution='none',private_ledger_access='none',manifest_frozen=False,
        sha256=dict(script=digest(Path(__file__)),evidence=locks,binaries=parent['sha256']['binaries']))
    save(out/'bank.json',bank)
    print(json.dumps({k:bank[k] for k in ('unique_operands','full_tuples','unique_significands','operand_kinds','equal_value_pairs')},sort_keys=True),flush=True)


if __name__=='__main__': main()
