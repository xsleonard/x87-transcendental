"""Public NaN, signed-zero and exception-mask contracts, without host FP.

The tables specify operand selection and writeback independently of the
implementation. Every row is exercised under all 64 masks and all four RCs.
"""
from collections import Counter
import subprocess
import sys

OPS=('fsin','fcos','fsincos','fptan','f2xm1','fpatan','fyl2x','fyl2xp1')
TRIG=set(OPS[:4]);PAIRED={'fsincos','fptan'};BINARY=set(OPS[5:])
ZERO='0000 0000000000000000';NEGZERO='8000 0000000000000000'
ONE='3fff 8000000000000000';HALF='3ffe 8000000000000000'
QNAN='ffff c000000000000123';SNAN='7fff 8000000000000456'
QUIETED='7fff c000000000000456';UNSUPPORTED='4321 0000000000000123'
INDEFINITE='ffff c000000000000000';DENORMAL='0000 0000000000000001'


def main():
    vectors=[]
    for op in OPS:
        for label,x,want,flags in [('quiet',QNAN,QNAN,0),('signaling',SNAN,QUIETED,1),
                                    ('unsupported',UNSUPPORTED,INDEFINITE,1)]:
            vectors.append((op,label,x,HALF,want,want if op in PAIRED else None,flags))
        if op in BINARY:
            for label,x,y,want,flags in [
                ('quiet-y',HALF,QNAN,QNAN,0),('signaling-y',HALF,SNAN,QUIETED,1),
                ('quiet-before-signaling',SNAN,QNAN,QNAN,1),
                ('signaling-before-quiet',QNAN,SNAN,QNAN,1),
                ('unsupported-before-nan',QNAN,UNSUPPORTED,INDEFINITE,1),
                ('nan-suppresses-denormal',DENORMAL,QNAN,QNAN,0),
                ('equal-payload-positive-sign','ffff c000000000000123',
                    '7fff c000000000000123','7fff c000000000000123',0),
                ('larger-payload','7fff c000000000000999',QNAN,
                    '7fff c000000000000999',0)]:
                vectors.append((op,label,x,y,want,None,flags))
    for op in OPS[:5]:
        for zero in (ZERO,NEGZERO):
            want=ONE if op=='fcos' else zero
            vectors.append((op,'signed-zero',zero,ZERO,want,ONE if op in PAIRED else None,0))
    # An unmasked operand invalid suppresses replacement and the paired push or
    # binary pop. A quiet NaN still commits, even with every exception unmasked.
    requests=[];expected=[]
    for vector in vectors:
        op,label,x,y,want,push,flags=vector
        for rc in ('rn','rd','ru','rz'):
            for masks in range(64):
                ident=len(requests)
                requests.append(f'{ident} {op} {rc} 64 {masks:02x} {x} {y}')
                expected.append((vector,masks))
    run=subprocess.run([sys.argv[1]],input='\n'.join(requests)+'\n',text=True,capture_output=True,check=True)
    output=run.stdout.splitlines();assert len(output)==len(expected)
    counts=Counter()
    for index,((vector,masks),line) in enumerate(zip(expected,output)):
        op,label,x,y,want,push,flags=vector
        f=line.split();context=(op,label,masks,line)
        assert len(f)==14 and f[0]==str(index) and f[1]=='0',context
        assert int(f[10],16)==flags and int(f[11],16)==63,context
        cc_mask=0x600 if op in TRIG else 0x200
        assert int(f[9],16)==cc_mask and int(f[8],16)==0,context
        early=bool(flags and not masks&1)
        assert int(f[13],16)==int(early) and int(f[2])==(2 if early else 0),context
        if early:
            assert f[3]=='0' and f[12]=='0',context
        else:
            assert ' '.join(f[4:6])==want,context
            assert int(f[3])==(3 if push else 1),context
            assert int(f[12])==(2 if push else 3 if op in BINARY else 1),context
            if push:assert ' '.join(f[6:8])==push,context
        counts[op]+=1
    print('PASS',len(expected),'special-value mask/rounding cases',dict(counts))


if __name__=='__main__':main()
