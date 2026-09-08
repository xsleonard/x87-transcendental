#!/usr/bin/env python3
# h770: BLIND out-of-sample test of the sine-branch law
# fire => (ep3 & 7) >= m, on the fresh ck9-13 votes.
import subprocess, pickle, collections
from fractions import Fraction
TWO = Fraction(2); HALF = Fraction(1,2)
def wv_val(w):
    v = Fraction(w[2]) * TWO**w[1]
    return -v if w[0] else v
def pw(s):
    sg,e2,hx = s.split(':'); return (int(sg),int(e2),int(hx,16))
C = {1:(1,-69,(0x5<<64)|0x5555555555555555), 2:(0,-73,(0x4<<64)|0x4444444444443e35),
     3:(1,-79,(0x6<<64)|0x806806806773c774), 4:(0,-85,(0x5<<64)|0xc778e94f50956d70),
     5:(1,-92,(0x6<<64)|0xb991122efa0532f0), 6:(0,-99,(0x5<<64)|0x8303f02614d5e4d8)}
CV = {k: wv_val(v) for k,v in C.items()}
def texp(a):
    e = a.numerator.bit_length() - a.denominator.bit_length()
    while TWO**e > a: e -= 1
    while TWO**(e+1) <= a: e += 1
    return e
def chop(v, bits):
    s = -1 if v<0 else 1
    a = abs(v); g = TWO**(texp(a)-bits+1)
    return s*(a/g).__floor__()*g
def rn64(v):
    s = -1 if v<0 else 1
    a = abs(v); g = TWO**(texp(a)-63)
    q = a/g; fl = q.__floor__(); r = q-fl
    if r>HALF or (r==HALF and fl%2==1): fl+=1
    return s*fl*g
fresh = {}
for L in open('h759_miner2_votes.txt'):
    t = L.split()
    if t[0] in ('ck9','ck10','ck11','ck12','ck13','ck13x'):
        fresh[(t[3],t[4],t[1])] = t[0]
print('fresh distinct (op,insn):', len(fresh))
nsine = nok = nviol = 0
joint = collections.Counter()
viols = []
for (se,sig,insn),ck in sorted(fresh.items()):
    flag = '--fcos-standalone' if insn=='cos' else '--fsin-standalone'
    p = subprocess.run(['./model_h235','--batch',flag,'--dump-internals'],
        input='%s %s\n' % (se,sig), capture_output=True, text=True)
    if 'DI_SPOLY' not in p.stderr or 'DI_CORR' in p.stderr: continue
    nsine += 1
    mag = None
    for L in p.stderr.splitlines():
        if L.startswith('DI_RED '):
            d = dict(x.split('=',1) for x in L.split()[1:])
            mag = wv_val(pw(d['mag']))
    m_ = mag
    sq = chop(m_*m_,67); f4 = chop(sq*sq,67)
    o = chop(f4*CV[5],67); o = rn64(CV[3]+o); o = chop(f4*o,67)
    o = rn64(CV[1]+o); o = chop(sq*o,67)
    e = chop(f4*CV[6],67); e = rn64(CV[4]+e); e = chop(f4*e,67)
    e = rn64(CV[2]+e); e = chop(f4*e,67)
    le = texp(abs(e))-66
    s = o+e; a = abs(s)
    N = a/TWO**le; N = N.numerator
    cR = a.numerator.bit_length()-a.denominator.bit_length()  # crude; recompute
    E = texp(a); cR = (E-64)-le
    half = 1 << cR
    m = half - (N & ((half<<1)-1))
    ep3sig = int(abs(e)/TWO**le)
    k3 = ep3sig & 7
    joint[(m, k3)] += 1
    if 0 <= m <= k3: nok += 1
    else:
        nviol += 1
        viols.append((ck,se,sig,insn,m,k3))
print('fresh sine votes:', nsine, ' law-satisfying:', nok, ' violations:', nviol)
for v in viols[:10]: print('  VIOL', v)
print('(m,k3) joint of fresh sine votes:')
for (m,k3),c in sorted(joint.items()): print('   m=%2d k3=%d : %d' % (m,k3,c))
