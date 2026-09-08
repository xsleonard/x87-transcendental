"""Offline saved-hardware replay through the public library client.

Recorded observations and independent rational references are separate from
implementation parity. No hardware or network access is performed.
"""
from collections import Counter
from fractions import Fraction
from functools import lru_cache
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

TESTS = Path(__file__).resolve().parents[1]
DATA = TESTS / 'data'
sys.path.insert(0, str(TESTS / 'reference'))
import sibling_reference
import log_reference


def sibling_constants():
    def value(v):
        scale = v['scale']
        return (-1 if v['sign'] else 1) * int(v['significand'],16) * (
            Fraction(1 << scale) if scale >= 0 else Fraction(1, 1 << -scale))
    raw=json.loads((DATA/'sibling-constants.json').read_text())['constants']
    return {k:value(v) if k=='F2_LN2' else
            {int(b):tuple(value(x) for x in pair) for b,pair in v.items()} if k=='TABLE'
            else [value(x) for x in v] for k,v in raw.items()}


def atan_reference():
    rom={}
    with (DATA/'pentium-rom/rom-constants.tsv').open() as stream:
        for row in csv.DictReader(stream,delimiter='\t'):
            i=int(row['row'])
            if i in (19,20) or 114<=i<=123 or 125<=i<=156:
                e=int(row['exp'],16)-0xffff-66
                n=int(row['sig68'],16)*(-1 if int(row['sign']) else 1)
                rom[i]=Fraction(n<<e) if e>=0 else Fraction(n,1<<-e)
    path=TESTS/'reference/fpatan.md'
    blocks=re.findall(r'^```python\n(.*?)^```',path.read_text(),re.M|re.S)
    assert len(blocks)==5 and len(rom)==44
    namespace={'ROM':rom}
    exec(compile('\n'.join(blocks),str(path),'exec'),namespace)
    namespace['finite_angle']=lru_cache(maxsize=8192)(namespace['finite_angle'])
    return namespace


def cases():
    rows=[]
    const=sibling_constants()
    atan=atan_reference()
    reference_counts=Counter()
    for row in json.loads((DATA/'smoke-witnesses.json').read_text())['rows']:
        op,rc,pc=row['instruction'],row['rc'],row['pc']
        f=row['input'].split(); expected=row['expected'].split()
        if op=='fpatan':
            y=f[3:5];x=f[5:7]
            want=(int(expected[1],16),int(expected[2],16))
            c1=int(expected[3]);flags=int(expected[4],16)
            observed=atan['fpatan'](atan['Raw80'](*map(lambda v:int(v,16),y)),
                atan['Raw80'](*map(lambda v:int(v,16),x)),rc.upper(),pc)
            assert observed==(want,c1,flags,int(expected[5],16))
            rows.append((op,rc,pc,x,y,want,None,c1,None,flags))
            reference_counts['fpatan']+=1
        else:
            x=f;y=[];range_return=expected[0]=='C2'
            want=None if range_return else tuple(int(v,16) for v in expected[1:3])
            push=tuple(int(v,16) for v in expected[3:5]) if len(expected)==5 else None
            c1=row['C1'];c2=row['C2']
            if op in ('f2xm1','fptan'):
                observed=sibling_reference.evaluate(op.upper(),int(x[0],16),int(x[1],16),rc,const)
                assert observed==(want,push,c1,c2) if not range_return else observed[3]==1
                reference_counts[op]+=1
            rows.append((op,rc,pc,x,y,want,push,c1,c2,None))
    for row in json.loads((DATA/'f2xm1-regressions.json').read_text())['cases']:
        f=row['hardware'].split();rc=f[1];pc=int(f[2]);x=f[3:5]
        want=tuple(int(v,16) for v in f[-2:]);c1=(int(f[7],16)>>9)&1
        observed=sibling_reference.evaluate('F2XM1',int(x[0],16),int(x[1],16),rc,const)
        assert observed[0]==want and observed[2]==c1
        rows.append(('f2xm1',rc,pc,x,[],want,None,c1,None,None))
        reference_counts['f2xm1-storage']+=1
    raw=(DATA/'log-witnesses.txt').read_bytes()
    manifest=json.loads((DATA/'log-witnesses.json').read_text())
    assert hashlib.sha256(raw).hexdigest()==manifest['sha256']
    assert len(raw.splitlines())==manifest['rows']
    for line in raw.decode().splitlines():
        f=line.split();op,rc,pc=f[1],f[2],int(f[3]);y=f[4:6];x=f[6:8]
        sw=int(f[10],16);want=tuple(int(v,16) for v in f[-2:])
        assert log_reference.predict_full(' '.join(f[:8]))==(*want,(sw>>9)&1,sw&63)
        rows.append((op,rc,pc,x,y,want,None,(sw>>9)&1,None,sw&63))
        reference_counts[op]+=1
    # Historical paired inputs that separate the two polynomial schedules.
    pairs=[('rd','c060000000d78237','bf3ed1ea9755cbd7','fb7ee49efb569156',0),
        ('ru','c060000000d78237','bf3ed1ea9755cbd8','fb7ee49efb569157',1),
        ('rd','b400000004ea29f8','b3130fc9731657e8','fc0e1abb7dd28ccd',0),
        ('rn','e79000000c3e46e7','e5980e1fae54d858','f97b7761040745d2',0),
        ('rd','e79000000c3e46e7','e5980e1fae54d857','f97b7761040745d2',0),
        ('ru','e79000000c3e46e7','e5980e1fae54d858','f97b7761040745d3',1)]
    for rc,x,s,c,c1 in pairs:
        rows.append(('fsincos',rc,64,['3ffc',x],[],(0x3ffc,int(s,16)),(0x3ffe,int(c,16)),c1,0,None))
    return rows,reference_counts


def check_results(rows, results):
    assert len(results)==len(rows)
    checked=Counter()
    for i,(row,line) in enumerate(zip(rows,results)):
        op,rc,pc,x,y,want,push,c1,c2,flags=row
        f=line.split();assert len(f)==13 and f[0]==str(i),(row,line)
        assert f[1]=='0',(row,line)
        if want is None:
            assert f[2]=='1' and f[3]=='0' and f[12]=='0',(row,line)
        else:
            assert f[2]=='0' and int(f[3])&1,(row,line)
            assert tuple(int(v,16) for v in f[4:6])==want,(row,line)
            if push is not None:
                assert int(f[3])&2 and tuple(int(v,16) for v in f[6:8])==push,(row,line)
        cc,known,raised,raised_known=map(lambda v:int(v,16),f[8:12])
        # Required metadata comes from the case contract, never from the
        # implementation's own availability claims. C1 on range return and
        # F2XM1's C2 are outside the defined condition-code contract.
        required=(0x200 if c1 is not None and want is not None else 0)
        required|=0x400 if c2 is not None and op!='f2xm1' else 0
        assert known&required==required,('missing condition metadata',row,line)
        if required&0x200:
            assert (cc>>9)&1==c1,(row,line);checked['C1']+=1
        if required&0x400:
            assert (cc>>10)&1==c2,(row,line);checked['C2']+=1
        if flags is not None:
            assert raised_known==63 and raised==flags,(row,line);checked['exceptions']+=1
        checked[op]+=1
    return checked


def main():
    rows,references=cases()
    inputs=[' '.join([str(i),op,rc,str(pc),*x,*y])
            for i,(op,rc,pc,x,y,*_) in enumerate(rows)]
    proc=subprocess.run([str(Path(sys.argv[1]).resolve())],input='\n'.join(inputs)+'\n',
        text=True,capture_output=True,check=True)
    checked=check_results(rows,proc.stdout.splitlines())
    print(json.dumps(dict(status='PASS',rows=len(rows),checked=checked,
        independent_reference_checks=references,hardware_executed=False),sort_keys=True))


if __name__=='__main__':main()
