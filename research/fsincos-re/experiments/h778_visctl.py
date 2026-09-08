#!/usr/bin/env python3
# h778: visibility control — for each m-matched negative, compute
# whether a poly+1 flip WOULD be output-visible in some mode; then
# re-contrast sq&7 on visibility-matched negatives only.
import pickle, math, collections, random
from fractions import Fraction
exec(open('h774_bitscan.py').read().split('vrec = pickle.load')[0])
HALF = Fraction(1,2)
def visible(mag, insn_unused):
    # chain to poly (RN64) both shipped and +1; corr = chop67(mag*poly);
    # result presum = mag + corr (sine branch, i1=0); architectural round
    # to 64 bits in rn/rd/ru: visible iff any mode's rounded output differs.
    def chain_poly(m):
        sq = m*m; sq = trunc(sq,67)
        f4 = trunc(sq*sq,67)
        o = trunc(f4*CV[5],67); o = rn(CV[3]+o,64)
        o = trunc(f4*o,67); o = rn(CV[1]+o,64); o = trunc(sq*o,67)
        e = trunc(f4*CV[6],67); e = rn(CV[4]+e,64)
        e = trunc(f4*e,67); e = rn(CV[2]+e,64); e = trunc(f4*e,67)
        return o + e
    def trunc(v,b):
        a = abs(v); g = TWO**(texp(a)-b+1)
        f = (a/g).__floor__()*g
        return f if v>0 else -f
    def rn(v,b):
        a = abs(v); g = TWO**(texp(a)-b+1)
        q = a/g; fl = q.__floor__(); r = q-fl
        if r>HALF or (r==HALF and fl%2==1): fl+=1
        return fl*g if v>0 else -fl*g
    s = chain_poly(mag)
    p0 = rn(s,64)
    g64 = TWO**(texp(abs(p0))-63)
    p1 = (abs(p0)+g64) * (1 if p0>0 else -1)
    out = []
    for p in (p0,p1):
        corr = trunc(mag*p,67)
        v = mag + corr
        modes = []
        a = abs(v); g = TWO**(texp(a)-63)
        q = a/g; fl = q.__floor__(); r = q-fl
        rnq = fl + (1 if (r>HALF or (r==HALF and fl%2==1)) else 0)
        rdq = fl
        ruq = fl + (1 if r>0 else 0)
        out.append((rnq,rdq,ruq,texp(a)))
    return out[0] != out[1]
vrec = pickle.load(open('h761_state.pkl','rb'))
vm = {}; vinfo = {}
for r in vrec:
    if r['cls']=='POS':
        k=(r['se'],r['sig'],r['insn']); vm[k]=r['mval']
        vinfo[k]=(int(float(r['mdef'])), r['de2'], r['insn'])
NEG = []
for fn, insn in (('h767_ck1_cos.txt','cos'),('h767_ck1_sin.txt','sin'),
                 ('h767_rvl_cos.txt','cos'),('h767_rvl_sin.txt','sin')):
    for L in open(fn):
        t = L.split()
        mrow = int(t[8])
        if 0 <= mrow <= 9 and (t[0],t[1],insn) not in vm:
            NEG.append(((mrow,int(t[9]),insn), wv_val(pw(t[4]))))
random.seed(6)
vj = collections.Counter(v for v in vinfo.values())
bypool = collections.defaultdict(list)
for key,mag in NEG: bypool[key].append(mag)
# sanity: all votes must be visible=True under this computation
vv = sum(1 for k,mv in vm.items() if visible(mv, None))
print('votes visible under replica visibility: %d/148' % vv)
Nm = []
for key,cnt in vj.items():
    pool = bypool.get(key,[])
    random.shuffle(pool)
    got = 0
    for mg in pool:
        if got >= cnt*6: break
        if visible(mg, None):
            Nm.append((key, mg)); got += 1
print('visibility+joint-matched negs:', len(Nm))
vh = collections.Counter()
for k,mv in vm.items():
    s = sigs(mv); vh[s['sq']&7] += 1
nh = collections.Counter()
for key,mg in Nm:
    s = sigs(mg); nh[s['sq']&7] += 1
tv = sum(vh.values()); tn = sum(nh.values())
print('sq&7: vote-frac vs visibility-matched-neg-frac')
for v in range(8):
    print('  %d : %.3f  %.3f' % (v, vh.get(v,0)/tv, nh.get(v,0)/tn))
print('DONE')
