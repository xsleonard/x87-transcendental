#!/usr/bin/env python3
# h775: m-MATCHED bit scan — negatives sampled to match the votes'
# m-distribution exactly; surviving signals are real.
import pickle, math, collections, random
from fractions import Fraction
exec(open('h774_bitscan.py').read().split('vrec = pickle.load')[0])
vrec = pickle.load(open('h761_state.pkl','rb'))
vm = {}
vmdist = collections.Counter()
for r in vrec:
    if r['cls']=='POS':
        vm[(r['se'],r['sig'],r['insn'])] = r['mval']
        vmdist[int(float(r['mdef']))] += 1
print('vote m-distribution:', sorted(vmdist.items()))
V = [sigs(m) for m in vm.values()]
bym = collections.defaultdict(list)
for fn, insn in (('h767_ck1_cos.txt','cos'),('h767_ck1_sin.txt','sin'),
                 ('h767_rvl_cos.txt','cos'),('h767_rvl_sin.txt','sin')):
    for L in open(fn):
        t = L.split()
        mrow = int(t[8])
        if 0 <= mrow <= 9 and (t[0],t[1],insn) not in vm:
            bym[mrow].append(wv_val(pw(t[4])))
random.seed(3)
NEGm = []
SCALE = 8
for m, cnt in vmdist.items():
    pool = bym.get(m, [])
    take = min(len(pool), cnt*SCALE)
    NEGm += random.sample(pool, take)
print('m-matched negs:', len(NEGm))
N = [sigs(m) for m in NEGm]
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
print('surviving |z|>3.5 after m-matching:')
for z,f,b,pv,pn in worst[:15]:
    print('  %s bit %2d : vote %.3f neg %.3f  z=%.1f' % (f,b,pv,pn,z))
if not worst: print('  NONE — all prior signals were m-distribution artifacts')
print('DONE')
