#!/usr/bin/env python3
# h776: recursive matched contrast — condition on found bits, rescan.
import pickle, math, collections, random
from fractions import Fraction
exec(open('h774_bitscan.py').read().split('vrec = pickle.load')[0])
vrec = pickle.load(open('h761_state.pkl','rb'))
vm = {}; vinfo = {}
for r in vrec:
    if r['cls']=='POS':
        k = (r['se'],r['sig'],r['insn'])
        vm[k] = r['mval']
        vinfo[k] = (int(float(r['mdef'])), r['de2'], r['insn'])
V = []
for k, mv in vm.items():
    s = sigs(mv); s['_m'], s['_de2'], s['_insn'] = vinfo[k]
    V.append(s)
NEG = []
for fn, insn in (('h767_ck1_cos.txt','cos'),('h767_ck1_sin.txt','sin'),
                 ('h767_rvl_cos.txt','cos'),('h767_rvl_sin.txt','sin')):
    for L in open(fn):
        t = L.split()
        mrow = int(t[8])
        if 0 <= mrow <= 9 and (t[0],t[1],insn) not in vm:
            NEG.append((mrow, int(t[9]), insn, wv_val(pw(t[4]))))
random.seed(4)
# joint (m, de2, insn) matching
vj = collections.Counter((x['_m'],x['_de2'],x['_insn']) for x in V)
bypool = collections.defaultdict(list)
for mrow, de2, insn, mag in NEG: bypool[(mrow,de2,insn)].append(mag)
Nm = []
for key, cnt in vj.items():
    pool = bypool.get(key, [])
    take = min(len(pool), cnt*8)
    for mg in random.sample(pool, take):
        s = sigs(mg); s['_m'],s['_de2'],s['_insn'] = key
        Nm.append(s)
print('joint-matched negs:', len(Nm))
FL = [('mag',64),('sq',67),('f4',67),('os1',64),('os2',64),('op3',67),('es1',64),('es2',64),('ep3',67)]
def scan(Vs, Ns, label, zthr=3.5):
    out = []
    for f,w in FL:
        for b in range(w):
            pv = sum((x[f]>>b)&1 for x in Vs)/max(len(Vs),1)
            pn = sum((x[f]>>b)&1 for x in Ns)/max(len(Ns),1)
            se = math.sqrt(pn*(1-pn)/max(len(Vs),1) + 1e-12)
            z = (pv-pn)/se if se>0 else 0
            if abs(z) > zthr: out.append((abs(z), f, b, pv, pn))
    out.sort(reverse=True)
    print('[%s] V=%d N=%d survivors:' % (label, len(Vs), len(Ns)))
    for z,f,b,pv,pn in out[:8]:
        print('   %s bit %2d : vote %.3f neg %.3f z=%.1f' % (f,b,pv,pn,z))
    if not out: print('   none')
    return out
s0 = scan(V, Nm, 'level0 joint-matched')
print('sq&7 histogram vote vs matched-neg:')
vh = collections.Counter(x['sq']&7 for x in V); nh = collections.Counter(x['sq']&7 for x in Nm)
for v in range(8):
    print('   %d : %5.3f  %5.3f' % (v, vh.get(v,0)/len(V), nh.get(v,0)/len(Nm)))
# level 1: condition on sq bit2 = 1
V1 = [x for x in V if (x['sq']>>2)&1]
N1 = [x for x in Nm if (x['sq']>>2)&1]
s1 = scan(V1, N1, 'level1 sq-bit2=1')
# also the complement
V0 = [x for x in V if not (x['sq']>>2)&1]
N0 = [x for x in Nm if not (x['sq']>>2)&1]
s0b = scan(V0, N0, 'level1c sq-bit2=0')
print('DONE')
