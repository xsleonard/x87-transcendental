#!/usr/bin/env python3
"""Synthetic guard/scorer tests and default-CLI parity; no native capture."""
import collections
import gzip
import json
import subprocess
import sys
from pathlib import Path
from h1725_full_campaign import ROOT,BASE,PINS,save,suite,INSNS,MODES
from h1725_run_full import predict,score
sys.path.insert(0,str(ROOT/'corpus-suite'))
from h1725_remote_capture import reserve,CASES


def main():
    import tempfile
    out=Path(tempfile.mkdtemp(prefix='preflight-',dir=BASE))
    for name,sha in PINS.items():assert suite.digest(ROOT/name)==sha
    predictor=BASE/'predictor'
    bits=bytearray(32)
    reserve(bits,[0,7,8,17,255]);assert bits[0]==129 and bits[1]==1 and bits[2]==2 and bits[31]==128
    guard_checks=0
    for indices in ([7],[8,19],[19,19],[-1],[CASES]):
        before=bytes(bits)
        try:reserve(bits,indices)
        except ValueError:pass
        else:raise AssertionError('invalid reservation accepted')
        assert bytes(bits)==before;guard_checks+=1
    ops=['3ffc e79000000c3e46e7','bffc e79000000c3e46e7','3ffc d0d000000cc0b3f8',
        '3ffd 9000000000000001','3ffe c90fdaa22168c235','403d ffffffffffffffff',
        '0000 0000000000000000','8000 0000000000000000','0000 0000000000000001',
        '0000 8000000000000000','7fff 8000000000000000','7fff 8000000000000001',
        '7fff c000000000000123','3fff 0000000000000001','403e 8000000000000000',
        '3fba ffffffffffffffff','3fde ffffffffffffffff','3fdf 8000000000000000']
    records=[(i,*map(lambda s:int(s,16),op.split()),4095) for i,op in enumerate(ops)]
    bank=out/'predictions';bank.mkdir();pred=predict(bank,records,predictor)
    # Check exact entry results through the ordinary CLI, with no algorithm
    # selection flag. Only instruction and architectural rounding are inputs.
    for insn in INSNS:
        for mode in MODES:
            cmd=[str(ROOT/'src/fsincos_skylake'),'--batch','--rc='+mode]
            if insn!='fsincos':cmd.append('--'+insn+'-standalone')
            actual=subprocess.run(cmd,input='\n'.join(ops)+'\n',text=True,capture_output=True,check=True)
            assert not actual.stderr
            assert actual.stdout.splitlines()==[pred[suite.case_id(insn,mode,64,op)]['value'] for op in ops]
    rows=[]
    for case,v in pred.items():
        insn,mode,pc,op=suite.decode_case(case);w=v['value'].split();c2=w[0]=='C2'
        sw=(7 if c2 or insn!='fsincos' else 6)<<11
        if c2:sw|=0x400
        elif v['known']:sw|=v['c1']<<9
        sin=cos='-'
        if not c2:
            if insn!='fcos':sin=w[1]+':'+w[2]
            if insn=='fcos':cos=w[1]+':'+w[2]
            elif insn=='fsincos':cos=w[3]+':'+w[4]
        d=dict(CASE=case,INSN=insn,MODE=mode,PC='pc64',IN=op.replace(' ',':'),
            CW=f'{suite.expected_cw(mode,pc):04x}',B_SW='3800',A_SW=f'{sw:04x}',SIN=sin,COS=cos,
            PRESERVED=op.replace(' ',':') if c2 else '-')
        rows.append(d)
    known=next(i for i,r in enumerate(rows) if pred[r['CASE']]['known'] and r['SIN']!='-')
    negative_checks=0
    for name in ('baseline','value','C1','CW','case','top','truncated','extra'):
        job=out/name;job.mkdir()
        data=[dict(r) for r in rows]
        if name=='value':
            se,sig=data[known]['SIN'].split(':');data[known]['SIN']=se+':'+f'{int(sig,16)^1:016x}'
        elif name=='C1':data[known]['A_SW']=f'{int(data[known]["A_SW"],16)^0x200:04x}'
        elif name=='CW':data[known]['CW']='0000'
        elif name=='case':data[known]['CASE']='wrong'
        elif name=='top':data[known]['B_SW']='0000'
        elif name=='truncated':data=data[:-1]
        elif name=='extra':data.append(data[-1])
        with gzip.open(job/'inputs.txt.gz','xt') as f:f.write(''.join(suite.capture_line(r['CASE'])+'\n' for r in rows))
        with gzip.open(job/'outputs.txt.gz','xt') as f:f.write(''.join(' '.join(k+'='+v for k,v in r.items())+'\n' for r in data))
        with gzip.open(job/'predictions.json.gz','xt') as f:json.dump(pred,f)
        save(job/'cpu.json',dict(identity_kind='SYNTHETIC_NO_HARDWARE'))
        save(job/'COMPLETE.json',dict(status='SYNTHETIC_NO_HARDWARE'))
        try:counts,misses=score(job,pred)
        except (ValueError,AssertionError,StopIteration):
            assert name not in ('baseline','value','C1');negative_checks+=1
        else:
            if name=='baseline':assert misses==0 and counts['rows']==len(pred)
            else:assert misses>0;negative_checks+=1
    assert negative_checks==7
    save(BASE/'PREFLIGHT.json',dict(status='PASS',hardware_execution='none',
        ordinary_default_CLI_cases=len(pred),reservation_negative_checks=guard_checks,
        synthetic_scorer_negative_checks=negative_checks,predictor_sha256=suite.digest(predictor),
        source_pins=PINS,files={name:suite.digest(ROOT/'experiments'/name) for name in
            ('h1725_remote_capture.py','h1725_run_full.py','h1725_preflight.py','h1725_select_full.py')}))
    print('PREFLIGHT PASS:',len(pred),'default CLI cases;',guard_checks,'reservation controls;',negative_checks,'scorer mutations. No hardware executed.')


if __name__=='__main__':main()
