#!/usr/bin/env python3
"""Replay opened captures with the actual promoted binary and import review data.

Read-only with respect to hardware and sealed evidence. A new normalized
observation dataset preserves original outputs and historical CPU metadata.
"""
import argparse
import csv
import gzip
import hashlib
import json
import sys
from collections import Counter,defaultdict
from fractions import Fraction
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'corpus-suite'))
import suite
import h1714_rounding_challenge as oracle


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path)
    p.add_argument('--output-dir',required=True,type=Path);a=p.parse_args();root=a.root.resolve();out=a.output_dir.resolve()
    out.mkdir(parents=True,exist_ok=False);binary=root/'src/fsincos_skylake';reports={}
    for name in ('h1712-h1714-skylake','h1715-skylake'):
        groups=defaultdict(list)
        for row in suite.observations(root/'corpus-suite/references'/name):
            insn,mode,pc,op=suite.decode_case(row['case_id']);groups[insn,mode].append((op,row))
        counts=Counter()
        for (insn,mode),rows in groups.items():
            ops=sorted({op for op,row in rows});values=oracle.c_predictions(binary,insn,mode,ops);pred=dict(zip(ops,values))
            for op,row in rows:
                got=pred[op];want=None if row['C2']=='1' else [row[lane] for lane in ('sin','cos') if row[lane]!='-']
                assert got['outputs']==want,(name,insn,mode,op,got,want)
                counts['tuples']+=1;counts['lanes']+=len(want or [])
                if got['C1'] is not None:assert got['C1']==int(row['C1']);counts['known_C1']+=1
        reports[name]=dict(counts);print(name,dict(counts),'PASS',flush=True)
    review=root/'transfer-tests/review-20260905';raw=review/'bank/state-output.txt.gz'
    h=hashlib.sha256()
    with gzip.open(raw,'rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    assert h.hexdigest() in (review/'bank/CHECKSUMS.sha256').read_text()
    inputs=(review/'bank/inputs.txt').read_text().splitlines();ops=(review/'bank/operands.txt').read_text().splitlines()
    lookup={};counts=Counter()
    for insn in oracle.INSTRUCTIONS:
        for mode in oracle.MODES:
            values=oracle.c_predictions(binary,insn,mode,ops)
            for i,value in enumerate(values):lookup[f'{insn}-{mode}-{i:05d}']=value
    target=root/'corpus-suite/references/review-20260905-skylake';target.mkdir(parents=True,exist_ok=False)
    db=suite.create_observation_db(target)
    with gzip.open(raw,'rt') as f:
        for line in inputs:
            case,insn,mode,pc,masks,depth,prior,se,sig=line.split();assert (masks,depth,prior)==('3f','1','clear')
            words=next(f).split();d=dict(w.split('=',1) for w in words);assert len(d)==len(words)==31
            assert (d['CASE'],d['INSN'],d['MODE'],d['PC'],d['DEPTH'],d['PRIOR'],d['MASKS'])==(case,insn,mode,pc,depth,prior,masks)
            sw=int(d['A_SW'],16);c2=bool(sw&0x400);op=se+' '+sig;got=lookup[case]
            numeric=dict(CASE=case,INSN=insn,MODE=mode,PC=pc,IN=d['B_R0'],CW=d['A_CW'],B_SW=d['B_SW'],A_SW=d['A_SW'],
                SIN='-' if c2 or insn=='fcos' else d['A_R1' if insn=='fsincos' else 'A_R0'],
                COS='-' if c2 or insn=='fsin' else d['A_R0'],PRESERVED=d['A_R0'] if c2 else '-')
            result=suite.validate_numeric(numeric,insn,mode,int(pc[2:]),op,case)
            assert d['A_CW']==d['B_CW']
            assert (d['A_TOP'],d['A_FTW'])==(('6','c0') if insn=='fsincos' and not c2 else ('7','80'))
            want=None if c2 else [numeric[lane] for lane in ('SIN','COS') if numeric[lane]!='-']
            assert got['outputs']==want,(case,got,want)
            if got['C1'] is not None:assert got['C1']==((sw>>9)&1);counts['known_C1']+=1
            counts['tuples']+=1;counts['lanes']+=len(want or []);counts['C2']+=c2
            db.execute('INSERT INTO observations VALUES(?,?,?,?,?,?)',result)
        assert not f.readline()
    db.commit();reported={}
    for line in (review/'bank/cpu-summary.txt').read_text().splitlines():
        if ':' in line:k,v=line.split(':',1);reported[k.strip()]=v.strip()
    metadata=dict(identity_kind='historical_reported_FMS',reported=reported,raw_cpuid=None,
        limits='Original review retained CPU summary, not raw CPUID or verified affinity. Do not synthesize them.')
    suite.finish_observations(target,db,metadata,dict(source='independent_review_saved_capture',
        raw_decompressed_sha256=h.hexdigest(),inputs_sha256=suite.digest(review/'bank/inputs.txt'),
        original_checksums_sha256=suite.digest(review/'bank/CHECKSUMS.sha256'),hardware_executions=0,observations_reused=True))
    db.close();reports['review-20260905']=dict(counts);print('review',dict(counts),'PASS',flush=True)
    # Independent exact-rational derivation of the already-observed separator.
    v=oracle.independent;v.constants(root);op='3ffc e79000000c3e46e7';r=v.integer.decode_external(op).fraction()
    midpoint=Fraction(int('e5980e1fae54d857',16)*2+1,1<<67)
    offsets={policy:str((v.polynomial(r,policy)[0]-midpoint)*(1<<66)) for policy in ('last','all')}
    assert offsets==dict(last='-5/1024',all='5/512')
    expected,meta=v.expected(op,'rn','all',{});values,_=v.run(binary,'rn',[op])
    assert values==[expected] and expected==('3ffc:e5980e1fae54d858','3ffe:f97b7761040745d2')
    suite.save(out/'report.json',dict(status='PASS_OPENED_REPLAY',reports=reports,separator=dict(operand=op,midpoint_offsets_ulps=offsets,expected_RN=expected),
        hardware_executions=0,private_access=False,sha256=dict(binary=suite.digest(binary),paired=suite.digest(root/'src/general/paired.h'),script=suite.digest(Path(__file__)))))


if __name__=='__main__':main()
