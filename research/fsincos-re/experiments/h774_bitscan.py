#!/usr/bin/env python3
# h774: bit-position microscope — votes vs razor negatives, P(bit=1)
# at every position of mag/sq/f4/os2/es2/op3/ep3 sigs; flag >4-sigma.
import pickle, math
from fractions import Fraction
TWO = Fraction(2); HALF = Fraction(1,2)
def wv_val(w):
    v = Fraction(w[2])*TWO**w[1]
    return -v if w[0] else v
def pw(s):
    sg,e2,hx = s.split(':'); return (int(sg),int(e2),int(hx,16))
C = {1:(1,-69,(0x5<<64)|0x5555555555555555), 2:(0,-73,(0x4<<64)|0x4444444444443e35),
     3:(1,-79,(0x6<<64)|0x806806806773c774), 4:(0,-85,(0x5<<64)|0xc778e94f50956d70),
     5:(1,-92,(0x6<<64)|0xb991122efa0532f0), 6:(0,-99,(0x5<<64)|0x8303f02614d5e4d8)}
CV = {k: wv_val(v) for k,v in C.items()}
def texp(a):
    e = a.numerator.bit_length()-a.denominator.bit_length()
    while TWO**e > a: e -= 1
    while TWO**(e+1) <= a: e += 1
    return e
def chop_i(v,bits):
    a = abs(v); g = TWO**(texp(a)-bits+1)
    return int(a/g), (v<0)
def rn64_i(v):
    a = abs(v); g = TWO**(texp(a)-63)
    q = a/g; fl = q.__floor__(); r = q-fl
    if r>HALF or (r==HALF and fl%2==1): fl += 1
    return int(fl), (v<0)
def sigs(m):
    out = {}
    out['mag'] = chop_i(m,64)[0]
    sq = m*m; sqi,_ = chop_i(sq,67); sqv = Fraction(sqi)*TWO**(texp(abs(sq))-66)
    out['sq'] = sqi
    f4 = sqv*sqv; f4i,_ = chop_i(f4,67); f4v = Fraction(f4i)*TWO**(texp(abs(f4))-66)
    out['f4'] = f4i
    def cm(a,b,bits):
        v = a*b; i,_ = chop_i(v,bits)
        s = Fraction(i)*TWO**(texp(abs(v))-bits+1)
        return (s if v>0 else -s), i
    def ad(a,b):
        v = a+b; i,neg = rn64_i(v)
        s = Fraction(i)*TWO**(texp(abs(v))-63)
        return (s if v>0 else -s), i
    o,_ = cm(f4v,CV[5],67); o,i = ad(CV[3],o); out['os1']=i
    o,_ = cm(f4v,o,67); o,i = ad(CV[1],o); out['os2']=i
    o,i = cm(sqv,o,67); out['op3']=i
    e,_ = cm(f4v,CV[6],67); e,i = ad(CV[4],e); out['es1']=i
    e,_ = cm(f4v,e,67); e,i = ad(CV[2],e); out['es2']=i
    e,i = cm(f4v,e,67); out['ep3']=i
    return out
vrec = pickle.load(open('h761_state.pkl','rb'))
vm = {}
for r in vrec:
    if r['cls']=='POS': vm[(r['se'],r['sig'],r['insn'])] = r['mval']
V = [sigs(m) for m in vm.values()]
magmap = {}
NEG = []
import random
random.seed(2)
rows = []
for fn, insn in (('h767_ck1_cos.txt','cos'),('h767_ck1_sin.txt','sin'),
                 ('h767_rvl_cos.txt','cos'),('h767_rvl_sin.txt','sin')):
    for L in open(fn):
        t = L.split()
        if 0 <= int(t[8]) <= 9 and (t[0],t[1],insn) not in vm:
            rows.append(wv_val(pw(t[4])))
NEGm = random.sample(rows, 1200)
N = [sigs(m) for m in NEGm]
print('votes:', len(V), 'negs:', len(N))
FL = [('mag',64),('sq',67),('f4',67),('os1',64),('os2',64),('op3',67),('es1',64),('es2',64),('ep3',67)]
worst = []
for f,w in FL:
    for b in range(w):
        pv = sum((x[f]>>b)&1 for x in V)/len(V)
        pn = sum((x[f]>>b)&1 for x in N)/len(N)
        se = math.sqrt(pn*(1-pn)/len(V) + 1e-12)
        z = (pv-pn)/se if se>0 else 0
        if abs(z) > 3.5: worst.append((abs(z), f, b, pv, pn))
worst.sort(reverse=True)
print('positions with |z| > 3.5 (expect ~0.3 by chance over 571 tests):')
for z,f,b,pv,pn in worst[:15]:
    print('  %s bit %2d : vote %.3f neg %.3f  z=%.1f' % (f,b,pv,pn,z))
if not worst: print('  NONE — all flat')
print('DONE')
