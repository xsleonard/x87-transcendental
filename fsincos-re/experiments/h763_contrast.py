#!/usr/bin/env python3
# h763: contrast at scale — 148 votes vs ~5K razor-band clean rows.
# P(fire|m) curve; feature contrast; tie subfamily.
import pickle, collections, statistics
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
def rnd_t(v, bits, mode):
    if v == 0: return v,0,Fraction(0)
    s = -1 if v<0 else 1
    a = abs(v); g = TWO**(texp(a)-bits+1)
    q = a/g; fl = q.__floor__(); r = q-fl
    if mode=='rn' and (r>HALF or (r==HALF and fl%2==1)): fl+=1
    return s*fl*g, int(fl), r
def feats(m):
    sq,sqs,t_sq = rnd_t(m*m,67,'chop'); f4,f4s,t_f4 = rnd_t(sq*sq,67,'chop')
    o,_,t1 = rnd_t(f4*CV[5],67,'chop'); o,os1,r1 = rnd_t(CV[3]+o,64,'rn')
    o,_,t2 = rnd_t(f4*o,67,'chop'); o,os2,r2 = rnd_t(CV[1]+o,64,'rn')
    o,op3,t3 = rnd_t(sq*o,67,'chop')
    e,_,t4 = rnd_t(f4*CV[6],67,'chop'); e,es1,r3 = rnd_t(CV[4]+e,64,'rn')
    e,_,t5 = rnd_t(f4*e,67,'chop'); e,es2,r4 = rnd_t(CV[2]+e,64,'rn')
    e,ep3,t6 = rnd_t(f4*e,67,'chop')
    return dict(sqs=sqs,f4s=f4s,os1=os1,os2=os2,op3=op3,es1=es1,es2=es2,ep3=ep3,
        t_sq=float(t_sq),t_f4=float(t_f4),t_oP1=float(t1),r_oS1=float(r1),
        t_oP2=float(t2),r_oS2=float(r2),t_oP3=float(t3),t_eP1=float(t4),
        r_eS1=float(r3),t_eP2=float(t5),r_eS2=float(r4),t_eP3=float(t6))
# votes with their m (from h761 state)
vrec = pickle.load(open('h761_state.pkl','rb'))
seen = set(); votes = []
for r in vrec:
    k = (r['cls'],r['se'],r['sig'],r['insn'])
    if k in seen: continue
    seen.add(k)
    if r['cls']=='POS': votes.append(r)
vmags = set()
for r in votes: vmags.add(r['mval'])
# wall rows
wall = []
for insn in ('cos','sin'):
    for L in open('h762_wall_%s.txt' % insn):
        t = L.split()
        i0, rsn, mag, odd, even, poly, m, de2, top = t
        wall.append(dict(insn=insn, i0=int(i0), rsn=int(rsn),
            mag=pw(mag), m=int(m), de2=int(de2)))
inwall_votes = [w for w in wall if wv_val(w['mag']) in vmags]
print('wall rows:', len(wall), ' of which known votes:', len(inwall_votes))
mh = collections.Counter(w['m'] for w in wall if wv_val(w['mag']) not in vmags)
vh = collections.Counter(w['m'] for w in inwall_votes)
print('P(fire|m) from randv1: m: clean/fired')
for m in range(0, 12):
    print('  m=%2d  clean %4d  fired %d' % (m, mh.get(m,0), vh.get(m,0)))
print('  m<0(above-half): clean %d  fired %d' % (
    sum(v for k,v in mh.items() if k<0), sum(v for k,v in vh.items() if k<0)))
# feature contrast: POS(148, all corpora) vs wall clean m in 1..12
NEGW = [w for w in wall if wv_val(w['mag']) not in vmags and 1 <= w['m'] <= 12]
print('computing replica features: POS 148 + NEG %d ...' % len(NEGW))
PF = [feats(r['mval']) for r in votes]
NF = [feats(wv_val(w['mag'])) for w in NEGW]
pickle.dump({'PF':PF,'NF':NF,'votes':votes,'NEGW':NEGW}, open('h763_feats.pkl','wb'))
for f in sorted(PF[0]):
    if f[0] in 'tr':
        pv=[x[f] for x in PF]; nv=[x[f] for x in NF]
        print('%-7s POS %7.4f+-%.3f  NEG %7.4f+-%.3f' % (f,
            statistics.mean(pv), statistics.stdev(pv),
            statistics.mean(nv), statistics.stdev(nv)))
for f in ('sqs','f4s','os1','os2','op3','es1','es2','ep3'):
    pv=[x[f]&1 for x in PF]; nv=[x[f]&1 for x in NF]
    print('%-4s lsb POS %.3f NEG %.3f' % (f, sum(pv)/len(pv), sum(nv)/len(nv)))
print('DONE')
