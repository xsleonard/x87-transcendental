#!/usr/bin/env python3
"""Isolated fixed table arithmetic, port-width certificate and retained replay.

No hardware/private history/default change. H1630 polynomial stays fixed.
The second RN64-destination multiply is explicit, not double rounding.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from contextlib import ExitStack
from pathlib import Path
import h1630_shared_polynomial_audit as poly

records, integer = poly.records, poly.integer
PARENT = 'tmp/ledger33/current/h1630_shared_polynomial_audit/'
LOCKS = {
    **poly.LOCKS,
    'experiments/h1630_shared_polynomial.h': '5c279565bf3ab5b1a02d92a24fb2e40dc3b12ab23498522768118890cf5c5310',
    'experiments/h1630_shared_polynomial_audit.py': '706a7ed6a2556cb8aa03ca9c7842ece37d70f99f0cbe01479eb9e76e58828834',
    PARENT + 'report.json': '5dc548a52e2d46749548011b2e4c2fa8ce919d2a7ab618fc4f4c2746fa54bd79',
}
ANCHOR = '''static sf_t fsin_operation_class_table(
    wv_t residual, int residual_sign, int64_t signed_n, sf_rc_t rc)
{'''


def source_string(root):
    source = poly.source_string(root)
    assert source.count(ANCHOR) == 1
    return source.replace(ANCHOR, '#include "h1633_shared_table.h"\n\n' + ANCHOR + '''
    /* H1633 isolated numerical table program; existing dispatcher retained. */
    if (G_H1633_TABLE) return h1633_table(residual, residual_sign, signed_n, rc);
''')


def load_constants(root):
    text = (root / 'src/p5_rom_constants.h').read_text()
    coefficients, table = {}, {}
    def value(sign, exponent, hi, lo):
        return (-1 if int(sign) else 1) * ((int(hi,16)<<64)|int(lo,16)), int(exponent)
    for kind, index, sign, e, hi, lo in re.findall(r'P5([SC])4_(\d) = \{ ([01]), (-?\d+), .*?0x([0-9a-f]+)ull<<64\)\|0x([0-9a-f]+)ull', text):
        coefficients.setdefault(kind,{})[int(index)] = value(sign,e,hi,lo)
    n,e = coefficients['S'][4]; coefficients['S'][4] = n-(1<<60),e
    row_pattern = r'\{ (\d+), \{ ([01]), (-?\d+), .*?0x([0-9a-f]+)ull<<64\)\|0x([0-9a-f]+)ull \}, \{ ([01]), (-?\d+), .*?0x([0-9a-f]+)ull<<64\)\|0x([0-9a-f]+)ull \} \}'
    for b,*fields in re.findall(row_pattern,text):
        table[int(b)] = value(*fields[:4]), value(*fields[4:])
    assert len(table)==8 and all(len(c)==4 for c in coefficients.values())
    assert integer.width(coefficients['S'][4][0]) <=64 and integer.width(coefficients['C'][4][0])<=64
    return coefficients, table


def M(a,b,bits=67,mode='chop'):
    x,y = integer.quantize(a,67)[0], integer.quantize(b,64)[0]
    assert integer.equal(a,x) and integer.equal(b,y), ('nonidentity table port',a,b)
    return integer.quantize((x[0]*y[0],x[1]+y[1]),bits,mode)[0]


def independent(meta, mode, coefficients, table):
    r = poly.decode(meta['magnitude'])
    a = integer.add(r,(-meta['b'],-6))
    assert integer.width(a[0]) <= 61
    a=integer.quantize(a,67)[0]; square=M(a,a)
    def horner(c):
        v=c[4]
        for i in (3,2,1): v=integer.rnadd(M(square,v),c[i])
        return v
    p,q=horner(coefficients['S']),horner(coefficients['C'])
    psq=M(square,p); stail=M(psq,a); sstate=integer.rnadd(a,stail)
    ctail=M(square,q,64,'rn')
    tsin,tcos=table[meta['b']]
    first=M(tsin if meta['cosine'] else tcos,sstate)
    if meta['cosine']: first=(-first[0],first[1])
    second=M(tcos if meta['cosine'] else tsin,ctail)
    correction=integer.quantize(integer.add(first,second),67)[0]
    pre=integer.add(tcos if meta['cosine'] else tsin,correction)
    rounding='rn' if mode=='rn' else 'away' if (mode=='rd' and meta['negative']) or (mode=='ru' and not meta['negative']) else 'chop'
    (sig,e),c1=integer.quantize(pre,64,rounding)
    assert sig>0
    se=e+63+16383+(0x8000 if meta['negative'] else 0)
    stages=dict(a=a,sq=square,p=p,q=q,psq=psq,stail=stail,sstate=sstate,ctail=ctail,first=first,second=second,correction=correction)
    return f'{se:04x}:{sig:016x}',c1,stages


def run(binary,instruction,mode,operands,trace=False):
    command=[str(binary),'--batch','--'+instruction+'-standalone','--rc='+mode]
    if trace: command.append('--dump-internals')
    proc=subprocess.run(command,input=''.join(op+'\n' for op in operands),text=True,capture_output=True,check=True)
    values=[records.parse_output(line) for line in proc.stdout.splitlines()]
    assert len(values)==len(operands)
    metadata,stages,current={}, {}, None
    for line in proc.stderr.splitlines():
        words=line.split()
        if words[0] in ('HTABLE','HPOLY'):
            lane='table' if words[0]=='HTABLE' else 'polynomial'
            fields=('cosine','top','b','precision','residual_sign','negative','C1') if lane=='table' else ('cosine','top','precision','residual_sign','negative','C1')
            assert len(words)==len(fields)+3
            index=int(words[1]); assert 0<=index<len(operands) and index not in metadata
            metadata[index]=dict(zip(fields,map(int,words[2:-1])),lane=lane,magnitude=words[-1])
            current=index
        elif words[0] in ('HTSTAGE','HSTAGE'):
            assert trace and current is not None and current not in stages
            stages[current]={k:poly.decode(v) for k,v in (w.split('=',1) for w in words[1:])}
        else:
            assert trace and (line.startswith('DI_') or line.startswith('SINE_STATE ')),line[:1024]
    return values,metadata,stages,proc.stdout


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--output-dir',required=True,type=Path)
    args=parser.parse_args(); root,output=args.root.resolve(),args.output_dir.resolve()
    assert not output.exists()
    evidence=dict(LOCKS)
    for name,expected in evidence.items(): assert records.digest(root/name)==expected,name
    parent=json.loads((root/PARENT/'report.json').read_text())
    for name,expected in parent['sha256']['evidence'].items():
        assert records.digest(root/name)==expected,name
        evidence[name]=expected
    assert records.digest(root/PARENT/'prepared.json')==parent['sha256']['prepared']
    inventories=json.loads((root/PARENT/'prepared.json').read_text())['inventories']
    constants,table=load_constants(root)
    source=source_string(root)
    evidence['experiments/h1633_shared_table.h']=records.digest(root/'experiments/h1633_shared_table.h')
    output.mkdir(parents=True)
    records.save(output/'prepared.json',dict(state='SOFTWARE_ONLY_FIXED_TABLE',inventories=inventories,
        source_sha256=hashlib.sha256(source.encode()).hexdigest(),sha256=dict(evidence=evidence,script=records.digest(Path(__file__)))))
    binaries={}
    for label,(enabled,flags) in poly.CONFIGS.items():
        binary=output/label
        proc=subprocess.run(['cc',*flags,'-std=c11','-DG_ROUND84=0','-DG_H1630_POLYNOMIAL=1',
            '-DG_H1633_TABLE='+str(enabled),'-I',str(root/'src'),'-I',str(root/'experiments'),'-x','c','-','-lm','-o',str(binary)],
            input=source,text=True,capture_output=True,check=True)
        assert not proc.stderr
        test=subprocess.run([str(binary),'--selftest'],text=True,capture_output=True,check=True)
        assert test.stdout=='SELFTEST: ok\n' and not test.stderr
        binaries[label]=binary
    baseline=root/PARENT/'candidate_O2'
    assert records.digest(baseline)==parent['sha256']['binaries']['candidate_O2']
    # Every reachable table boundary/center and adjacent representable direct
    # operands, both signs; tiny/poly/out-of-range fallbacks and high-q inputs.
    operands=set()
    for k in (16,18,20,22,24,26,28,30,32,36,40,44,48,52):
        e=k.bit_length()-1-6; sig=k<<(63-(k.bit_length()-1))
        for d in (-1,0,1):
            n=sig+d; ee=e
            if n<1<<63: n<<=1; ee-=1
            for sign in (0,0x8000): operands.add(f'{sign+ee+16383:04x} {n:016x}')
    for sign in (0,0x8000):
        for e in (-69,-33,-32,-3,-1,0,7,31,62,63):
            for sig in (0x8000000000000001,0xc90fdaa22168c233,0xc90fdaa22168c234,0xffffffffffffffff):
                operands.add(f'{sign+e+16383:04x} {sig:016x}')
    operands=sorted(operands); checks=stage_checks=0
    for insn in ('fsin','fcos'):
        for mode in ('rn','rd','ru','rz'):
            base,_,_,_=run(baseline,insn,mode,operands)
            disabled,_,_,_=run(binaries['disabled_O2'],insn,mode,operands)
            assert disabled==base
            reference=None
            for label in ('candidate_O0','candidate_O2','candidate_O3','candidate_ubsan'):
                values,metadata,stages,_=run(binaries[label],insn,mode,operands,True)
                assert len(stages)==len(metadata) and values==base
                if reference is None: reference=values,metadata,stages
                assert (values,metadata,stages)==reference
                for i,meta in metadata.items():
                    expected,c1,expected_stages=independent(meta,mode,constants,table) if meta['lane']=='table' else poly.independent(meta,mode)
                    assert values[i]==expected and meta['C1']==c1
                    assert stages[i].keys()==expected_stages.keys()
                    assert all(integer.equal(v,stages[i][k]) for k,v in expected_stages.items())
                    stage_checks+=len(stages[i])
                checks+=len(values)
    records.save(output/'preflight.json',dict(operands=operands,row_checks=checks,stage_equalities=stage_checks,hardware_observations=0))
    print('PREFLIGHT PASS',checks,stage_checks,flush=True)
    totals,reports=Counter(),[]
    for inventory in inventories:
        directory=output/inventory['tag']; directory.mkdir()
        inputs=(root/inventory['inputs']).read_text().splitlines(); counts=Counter(); samples=[]; sampled=set()
        with ExitStack() as stack:
            failures=records.zipped(stack,directory/'changes_or_misses.jsonl.gz')
            for mode,capture in inventory['captures'].items():
                actual=(root/capture).read_text().splitlines(); assert len(actual)==len(inputs)
                out=records.zipped(stack,directory/(mode+'_candidate.stdout.gz'))
                metaout=records.zipped(stack,directory/(mode+'_metadata.jsonl.gz'))
                for start in range(0,len(inputs),8192):
                    batch=inputs[start:start+8192]
                    base,_,_,_=run(baseline,inventory['instruction'],mode,batch)
                    values,metadata,_,stdout=run(binaries['candidate_O2'],inventory['instruction'],mode,batch)
                    out.write(stdout.encode())
                    for i,meta in sorted(metadata.items()): metaout.write((json.dumps(dict(index=start+i,**meta),sort_keys=True)+'\n').encode())
                    for i,value in enumerate(values):
                        hardware,sw=records.parse_output(actual[start+i],True); meta=metadata.get(i)
                        lane=meta['lane'] if meta else 'fallback'
                        badc1=meta is not None and meta['C1'] != (sw>>9)&1
                        delta=dict(observed=1,output_changes=int(value!=base[i]))
                        delta.update({lane+'_rows':1,lane+'_output_misses':int(value!=hardware),lane+'_C1_misses':int(badc1)})
                        counts.update(delta); totals.update(delta)
                        detail=dict(index=start+i,operand=batch[i],instruction=inventory['instruction'],mode=mode,hardware=hardware,hardware_status=f'{sw:04x}',output=value,baseline=base[i],metadata=meta)
                        interesting=value!=hardware or badc1 or value!=base[i]
                        if interesting: failures.write((json.dumps(detail,sort_keys=True)+'\n').encode())
                        cell=(mode,lane,meta.get('b'),meta['negative'],meta['precision']) if meta else None
                        if meta and (interesting or cell not in sampled):
                            expected,c1,_=independent(meta,mode,constants,table) if lane=='table' else poly.independent(meta,mode)
                            assert expected==value and c1==meta['C1']
                            samples.append(dict(detail,independent_output=expected,independent_C1=c1)); sampled.add(cell)
                print(inventory['tag'],mode,dict(counts),flush=True)
        records.save(directory/'independent_checks.json',samples)
        report=dict(bank=inventory['tag'],counts=dict(counts),complete=True,independent_checks=len(samples),sha256={p.name:records.digest(p) for p in sorted(directory.iterdir())})
        records.save(directory/'report.json',report); reports.append(report)
        if any(counts[lane+s] for lane in ('table','polynomial') for s in ('_output_misses','_C1_misses')): break
    for name,expected in evidence.items(): assert records.digest(root/name)==expected
    result=dict(experiment='h1633_shared_table_audit',status='CANDIDATE_FALSIFIED' if any(totals[l+s] for l in ('table','polynomial') for s in ('_output_misses','_C1_misses')) else 'PASS_LISTED_RETAINED_BANKS_ONLY',
        counts=dict(totals),banks=reports,remaining_banks=[b['tag'] for b in inventories[len(reports):]],preflight_checks=checks,preflight_stage_equalities=stage_checks,
        hardware_execution='none',private_ledger_access='none',canonical_default_or_paper_change='none',
        claim_boundary='Fixed numerical table rewrite, all input cuts are identities with explicit width-compatible operand orientation; not physical port recovery. RN64 multiply is distinct from CHOP67. Polynomial unchanged, other fallback status unscored. Finite retained rows, not a universal hardware proof.',
        sha256=dict(script=records.digest(Path(__file__)),prepared=records.digest(output/'prepared.json'),evidence=evidence,binaries={k:records.digest(v) for k,v in binaries.items()}))
    records.save(output/'report.json',result)
    print(result['status'],dict(totals),flush=True)


if __name__=='__main__': main()
