#!/usr/bin/env python3
"""Prepare fixed-prediction remaining-scope proposals, not a capture manifest.

Exact table-center preimages are enumerated algebraically across every valid
reduction exponent. Other bounded proposals challenge control, tiny, range,
and special-encoding paths. Freshness is deliberately unresolved here.
No hardware/private-history/default/paper action.
"""
from __future__ import annotations
import argparse
import json
import random
from collections import Counter
from pathlib import Path
import h1638_tiny_c_transfer as candidate
import h1636_retained_rz_pc_transfer as independent

MODELS='tmp/ledger33/current/h1638_tiny_c_transfer/'
LOCKS={
    **candidate.LOCKS,
    MODELS+'report.json':'db6c8cbc1e0e2c9acdb54da5e1e381407a6b8c5f6f62cc7b1c52c4d90f8510e0',
    'experiments/h1638_tiny_closed_form.h':'910cbb03c7310ad86b77bce4ae64fd611d96374c794df0048922b7dc2f199227',
    'experiments/h1638_tiny_c_transfer.py':'db99dc020ab7372af7f8018a11c4e81a7c73afd227c4dccbbcc080d3b38a4fd1',
    'experiments/h1636_retained_rz_pc_transfer.py':'9d44c92b5c6267752da7bab906e160ae82bb1eda338f93c86c8e7732adb45707',
}
M=candidate.spec.M66


def ceildiv(a,b): return -(-a//b)


def exact_centers():
    rows=[]; counts=Counter()
    for b in (18,22,26,30,36,44):
        for residual_sign in (0,1):
            d=(-1 if residual_sign else 1)*(b<<59)
            assert 2*abs(d)<M
            for e in range(-1,63):
                k=e+2; modulus=1<<k
                # A=N*M+D must be an external64-bit significand times2^k.
                residue=(-d*pow(M,-1,modulus))%modulus
                low=ceildiv(((1<<63)<<k)-d,M)
                high=(((1<<64)-1)<<k)-d
                high//=M
                first=residue+ceildiv(max(0,low)-residue,modulus)*modulus
                assert high-low<modulus
                if first>high: continue
                n=first; a=n*M+d; assert a%modulus==0
                sig=a>>k; assert 1<<63<=sig<1<<64
                if e==-1 and sig<0xc90fdaa22168c234: continue
                q,rem=divmod(a,M); q+=int(rem*2>M)
                assert q==n and n>0 and a-n*M==d
                rows.append(dict(b=b,residual_sign=residual_sign,input_top=e,
                    positive_operand=f'{e+16383:04x} {sig:016x}',quotient=str(n),reduced_integer=str(d)))
                counts[str(b)]+=1
    return rows,dict(counts)


def proposals():
    inputs={}
    def add(se,sig,kind,origin):
        assert 0<=se<1<<16 and 0<=sig<1<<64
        key=f'{se:04x} {sig:016x}'
        inputs.setdefault(key,{'kinds':set(),'origins':[]})['kinds'].add(kind)
        inputs[key]['origins'].append(origin)
    centers,center_counts=exact_centers()
    for b in (18,22,26,30,36,44):
        width=b.bit_length(); e=width-1-6; sig=b<<(64-width)
        for sign in (0,0x8000): add(sign|e+16383,sig,'direct_table_center',dict(b=b))
    for row in centers:
        se,sig=(int(w,16) for w in row['positive_operand'].split())
        for sign in (0,0x8000): add(se|sign,sig,'exact_table_center_preimage',row)
    rng=random.Random(0x1639)
    # All cases are proposed before hardware. No selection by unseen labels.
    # Interior lane edges receive random x87-ulp offsets inside and outside
    # the old double-classifier sliver, not just familiar literal endpoints.
    for numerator in (16,20,24,28,32,40,48):
        width=numerator.bit_length(); e=width-1-6; base=numerator<<(64-width)
        offsets={-1,0,1}
        offsets.update(-rng.randrange(2,2049) for _ in range(4))
        offsets.update(rng.randrange(2049,1<<20) for _ in range(3))
        for d in sorted(offsets):
            sig=base+d; top=e
            if sig<1<<63: sig<<=1; top-=1
            for sign in (0,0x8000): add(sign|top+16383,sig,'table_lane_boundary',dict(edge_numerator=numerator,offset=d))
    for e in (-70,-69,-68,-67,-34,-33,-32,-31):
        for _ in range(4):
            sig=(1<<63)|rng.getrandbits(63)
            for sign in (0,0x8000): add(sign|e+16383,sig,'tiny_dispatch_boundary',dict(top=e))
    for e in (62,63,64):
        for _ in range(4):
            sig=(1<<63)|rng.getrandbits(63)
            for sign in (0,0x8000): add(sign|e+16383,sig,'range_boundary',dict(top=e))
    for _ in range(8):
        p=rng.getrandbits(62)|1
        for sign in (0,0x8000):
            add(sign,p,'denormal',{})
            add(sign,(1<<63)|p,'pseudo_denormal',{})
            add(sign|0x7fff,(1<<63)|p,'signaling_nan',{})
            add(sign|0x7fff,(3<<62)|p,'quiet_nan',{})
            add(sign|0x7fff,p,'invalid_special_encoding',{})
            add(sign|0x3fff,p,'unnormal',{})
    for sign in (0,0x8000):
        add(sign,0,'zero',{})
        add(sign|0x7fff,1<<63,'infinity',{})
        add(sign|0x7fff,0,'invalid_zero_payload',{})
    return [dict(operand=op,kinds=sorted(v['kinds']),origins=v['origins']) for op,v in sorted(inputs.items())],centers,center_counts


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--output-dir',required=True,type=Path)
    args=parser.parse_args(); root,output=args.root.resolve(),args.output_dir.resolve(); assert not output.exists()
    digest=candidate.table.records.digest; evidence=dict(LOCKS)
    for name,expected in evidence.items(): assert digest(root/name)==expected,name
    report=json.loads((root/MODELS/'report.json').read_text())
    for name,expected in report['sha256']['evidence'].items():
        assert digest(root/name)==expected,name
        evidence[name]=expected
    rows,centers,center_counts=proposals(); operands=[r['operand'] for r in rows]
    independent.initialize_proof(root)
    binaries={label:root/MODELS/label for label in ('candidate_O0','candidate_O2','candidate_O3','candidate_ubsan')}
    for label,binary in binaries.items(): assert digest(binary)==report['sha256']['binaries'][label]
    predictions=[]
    for insn in ('fsin','fcos'):
        for mode in ('rn','rd','ru','rz'):
            reference=None
            for label,binary in binaries.items():
                values,metadata,_=candidate.run(binary,insn,mode,operands)
                if reference is None: reference=values,metadata
                assert (values,metadata)==reference
            values,metadata=reference
            for i,(row,value) in enumerate(zip(rows,values)):
                meta=metadata.get(i); small=candidate.spec.evaluate(row['operand'],insn,mode)
                if meta and meta['lane'] in ('table','polynomial'):
                    expected,c1,_,center=independent.verify_hit(row['operand'],insn,mode,meta)
                    assert expected==value and c1==meta['C1']
                else:
                    candidate.check_spec(row['operand'],insn,mode,value,meta)
                    assert small['output']==value
                    c1=small['C1']; center=False
                if 'direct_table_center' in row['kinds'] or 'exact_table_center_preimage' in row['kinds']:
                    assert meta is not None and meta['lane']=='table' and center
                predictions.append(dict(instruction=insn,mode=mode,operand=row['operand'],kinds=row['kinds'],
                    output=value,C1=c1,exception_flags=small['exception_flags'],metadata=meta,exact_center=center))
    output.mkdir(parents=True)
    result=dict(experiment='h1639_remaining_scope_proposals',capture_state='SOFTWARE_ONLY_NOT_FROZEN',candidate_changed=False,
        operands=rows,predictions=predictions,unique_operands=len(rows),instruction_mode_predictions=len(predictions),
        proposed_precision_controls=[24,53,64],proposed_full_tuples=len(predictions)*3,
        operand_kind_memberships=dict(Counter(k for r in rows for k in r['kinds'])),
        exact_center_reduced_preimages=centers,center_preimage_counts_positive_external=center_counts,
        center_enumeration_scope='All valid external reduction exponents -1..62 and both residual signs; one congruence class modulo2^(e+2), bounded by the complete normalized64 significand interval. Negative external inputs are signed mirrors. Not proof of silicon reduction.',
        prediction_limits='Numerical model predicts PC independence; these proposals are not captured evidence. Special C1/exception fields without a prior explicit rule stay null, not silently predicted zero. Normal finite exception mask0x20 is a declared hypothesis; no full SW/stack/unmasked prediction.',
        freshness='NOT AUDITED: includes known/reused operands, software witnesses and new proposals. Must pass local public/private history before freeze; no tuple authorized for execution by this file alone.',
        hardware_execution='none',private_ledger_access='none',manifest_frozen=False,canonical_default_or_paper_change='none',
        sha256=dict(script=digest(Path(__file__)),evidence=evidence,binaries={k:digest(v) for k,v in binaries.items()}))
    candidate.table.records.save(output/'bank.json',result)
    print(json.dumps({k:result[k] for k in ('unique_operands','instruction_mode_predictions','proposed_full_tuples','operand_kind_memberships','center_preimage_counts_positive_external')},sort_keys=True),flush=True)


if __name__=='__main__': main()
