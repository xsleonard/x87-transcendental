#!/usr/bin/env python3
# h769: normalization-shift / low-bit joint contrast on the
# mechanism-informed frame (147 votes vs 2863 razor negatives).
import pickle, collections
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
def rnmul(a, b, bits):
    # returns (chop, norm_shift): norm=1 if exact product's top < a_top+b_top+1
    v = a*b
    ea, eb, ev = texp(abs(a)), texp(abs(b)), texp(abs(v))
    norm = 1 if ev == ea+eb else 0     # product < 2^(ea+eb+1): left-shift case
    s = -1 if v<0 else 1
    g = TWO**(ev-bits+1)
    return s*(abs(v)/g).__floor__()*g, norm
def rn64(v):
    s = -1 if v<0 else 1
    a = abs(v); g = TWO**(texp(a)-63)
    q = a/g; fl = q.__floor__(); r = q-fl
    if r>HALF or (r==HALF and fl%2==1): fl+=1
    return s*fl*g, r
def state(m):
    ns = {}
    sq,ns['sq'] = rnmul(m,m,67); f4,ns['f4'] = rnmul(sq,sq,67)
    o,ns['oP1'] = rnmul(f4,CV[5],67); o,_ = rn64(CV[3]+o)
    o,ns['oP2'] = rnmul(f4,o,67); o,_ = rn64(CV[1]+o)
    o,ns['oP3'] = rnmul(sq,o,67)
    e,ns['eP1'] = rnmul(f4,CV[6],67); e,_ = rn64(CV[4]+e)
    e,ns['eP2'] = rnmul(f4,e,67); e,_ = rn64(CV[2]+e)
    e,ns['eP3'] = rnmul(f4,e,67)
    lo3 = {}
    for nm, v, w in (('sq',sq,67),('f4',f4,67),('op3',o,67),('ep3',e,67)):
        sig = int(abs(v)/TWO**(texp(abs(v))-w+1))
        lo3[nm] = sig & 7
    return ns, lo3
D = pickle.load(open('h768_out.pkl','rb'))
votes, negs = D['votes'], D['negs']
def mag_of(se, sig, insn):
    # mag from the wall rows (negs carry it); votes: from h761
    return None
vrec = pickle.load(open('h761_state.pkl','rb'))
vm = {}
for r in vrec:
    if r['cls']=='POS': vm[(r['se'],r['sig'],r['insn'])] = r['mval']
VS = []; NS = []
for se,sg,insn in votes:
    ns, lo3 = state(vm[(se,sg,insn)])
    VS.append((ns, lo3))
# negs: mags from h767 wall files (already parsed into h768? negs store (se,sig,insn,m))
magmap = {}
for fn, insn in (('h767_ck1_cos.txt','cos'),('h767_ck1_sin.txt','sin'),
                 ('h767_rvl_cos.txt','cos'),('h767_rvl_sin.txt','sin')):
    for L in open(fn):
        t = L.split()
        magmap[(t[0],t[1],insn)] = wv_val(pw(t[4]))
import random
random.seed(1)
sub = random.sample(negs, 900)
for se,sg,insn,m in sub:
    ns, lo3 = state(magmap[(se,sg,insn)])
    NS.append((ns, lo3))
PK = ['sq','f4','oP1','oP2','oP3','eP1','eP2','eP3']
print('norm-shift P(1) vote vs neg:')
for k in PK:
    pv = sum(1 for ns,_ in VS if ns[k])/len(VS)
    nv = sum(1 for ns,_ in NS if ns[k])/len(NS)
    print('  %-4s %.3f  %.3f' % (k, pv, nv))
vpat = collections.Counter(tuple(ns[k] for k in PK) for ns,_ in VS)
npat = collections.Counter(tuple(ns[k] for k in PK) for ns,_ in NS)
print('top vote patterns (sq,f4,oP1,oP2,oP3,eP1,eP2,eP3):')
for pat, c in vpat.most_common(6):
    print('  ', pat, c, ' neg:', npat.get(pat,0))
print('low3 joints (sq,f4,op3,ep3) — top vote combos:')
vl = collections.Counter((l['sq'],l['f4'],l['op3'],l['ep3']) for _,l in VS)
for pat, c in vl.most_common(5):
    print('  ', pat, c)
print('DONE')
