#!/usr/bin/env python3
# h777: Booth-recode frame — fire rate vs negative-digit counts of
# each multiplier operand's low field (joint-matched negatives).
import pickle, math, collections, random
from fractions import Fraction
exec(open('h774_bitscan.py').read().split('vrec = pickle.load')[0])
def booth_negcount(y, L):
    # radix-4 Booth digits over low L digit positions (2 bits each)
    cnt = 0
    prev = 0
    for i in range(L):
        b0 = (y >> (2*i)) & 1 if i>0 else (y>>0)&1
        pass
    # standard: d_i from bits (2i+1, 2i, 2i-1), b_{-1}=0
    cnt = 0
    for i in range(L):
        hi = (y >> (2*i+1)) & 1
        mid = (y >> (2*i)) & 1
        lo = (y >> (2*i-1)) & 1 if i > 0 else 0
        d = -2*hi + mid + lo
        if d < 0: cnt += 1
    return cnt
vrec = pickle.load(open('h761_state.pkl','rb'))
vm = {}; vinfo = {}
for r in vrec:
    if r['cls']=='POS':
        k=(r['se'],r['sig'],r['insn']); vm[k]=r['mval']
        vinfo[k]=(int(float(r['mdef'])), r['de2'], r['insn'])
V = []
for k,mv in vm.items():
    s = sigs(mv); s['_key']=vinfo[k]; V.append(s)
NEG = []
for fn, insn in (('h767_ck1_cos.txt','cos'),('h767_ck1_sin.txt','sin'),
                 ('h767_rvl_cos.txt','cos'),('h767_rvl_sin.txt','sin')):
    for L in open(fn):
        t = L.split()
        mrow = int(t[8])
        if 0 <= mrow <= 9 and (t[0],t[1],insn) not in vm:
            NEG.append(((mrow,int(t[9]),insn), wv_val(pw(t[4]))))
random.seed(5)
vj = collections.Counter(x['_key'] for x in V)
bypool = collections.defaultdict(list)
for key,mag in NEG: bypool[key].append(mag)
Nm = []
for key,cnt in vj.items():
    pool = bypool.get(key,[])
    for mg in random.sample(pool, min(len(pool), cnt*8)):
        s = sigs(mg); s['_key']=key; Nm.append(s)
print('V %d Nm %d' % (len(V), len(Nm)))
for f in ('sq','os2','es2','f4','mag'):
    for L in (4, 8):
        vc = collections.Counter(booth_negcount(x[f], L) for x in V)
        nc = collections.Counter(booth_negcount(x[f], L) for x in Nm)
        vm_ = sum(k*v for k,v in vc.items())/len(V)
        nm_ = sum(k*v for k,v in nc.items())/len(Nm)
        print('%-4s L=%d  negdig mean vote %.2f neg %.2f' % (f, L, vm_, nm_))
# detail: sq low-digit signs
print('sq&63 fire-lean (vote frac / matched-neg frac):')
vh = collections.Counter(x['sq']&63 for x in V); nh = collections.Counter(x['sq']&63 for x in Nm)
for v in range(0,64,8):
    row = ' '.join('%2d:%.3f/%.3f' % (u, vh.get(u,0)/len(V), nh.get(u,0)/len(Nm)) for u in range(v,v+8))
    print('  ', row)
print('DONE')
