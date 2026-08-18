#!/usr/bin/env python3
# h761: twin microscope — full state per POS/NEG row (operand + DI dumps
# + replica intermediates with exact tails), pattern-twin contrast.
import subprocess, collections, pickle
from fractions import Fraction
TWO = Fraction(2); HALF = Fraction(1,2)
def wv_val(w):
    v = Fraction(w[2]) * TWO**w[1]
    return -v if w[0] else v
def parse_wv(s):
    sg, e2, hx = s.split(':')
    return (int(sg), int(e2), int(hx,16))
C = {1:(1,-69,(0x5<<64)|0x5555555555555555), 2:(0,-73,(0x4<<64)|0x4444444444443e35),
     3:(1,-79,(0x6<<64)|0x806806806773c774), 4:(0,-85,(0x5<<64)|0xc778e94f50956d70),
     5:(1,-92,(0x6<<64)|0xb991122efa0532f0), 6:(0,-99,(0x5<<64)|0x8303f02614d5e4d8)}
CV = {k: wv_val(v) for k, v in C.items()}
def texp(a):
    e = a.numerator.bit_length() - a.denominator.bit_length()
    while TWO**e > a: e -= 1
    while TWO**(e+1) <= a: e += 1
    return e
def rnd_t(v, bits, mode):
    # returns (rounded, sig_int, tail_frac_of_lsb, rounded_up)
    if v == 0: return v, 0, Fraction(0), 0
    s = -1 if v < 0 else 1
    a = abs(v); e = texp(a)
    g = TWO**(e-bits+1)
    q = a/g; fl = q.__floor__(); r = q-fl; up = 0
    if mode=='rn' and (r > HALF or (r==HALF and fl%2==1)): fl += 1; up = 1
    return s*fl*g, int(fl), r, up
# ordered rows exactly as h755 cache builder
votes = collections.defaultdict(dict)
for l in open('h753_allvotes.txt'):
    t = l.split(); votes[(t[3],t[4],t[1])][t[2]] = 1
order = []
for (se,sig,insn) in sorted(votes): order.append(('POS',se,sig,insn))
orig = set(tuple(l.split()) for l in open('h714_ops.txt'))
for l in open('h754_neg102.txt'):
    t = l.split()
    if (t[3],t[4]) in orig: continue
    order.append(('NEG',t[3],t[4],t[1]))
# DI dump per row (sine-branch only rows will emit DI_SPOLY)
recs = []
for cls, se, sig, insn in order:
    flag = '--fcos-standalone' if insn=='cos' else '--fsin-standalone'
    p = subprocess.run(['./model_h235','--batch',flag,'--dump-internals'],
                       input='%s %s\n' % (se,sig), capture_output=True, text=True)
    if 'DI_SPOLY' not in p.stderr or 'DI_CORR' in p.stderr: continue
    di = {}
    for L in p.stderr.splitlines():
        if L.startswith('DI_RED '):
            d = dict(x.split('=',1) for x in L.split()[1:])
            di['i0'] = int(d['i0']); di['i1'] = int(d['i1']); di['rsn'] = int(d['rsn'])
            di['mag'] = parse_wv(d['mag'])
    m = wv_val(di['mag'])
    # replica with full state
    st = {}
    sq,_,st['t_sq'],_ = rnd_t(m*m,67,'chop')
    f4,f4s,st['t_f4'],_ = rnd_t(sq*sq,67,'chop')
    o,_,st['t_oP1'],_ = rnd_t(f4*CV[5],67,'chop')
    o,os1,st['r_oS1'],st['u_oS1'] = rnd_t(CV[3]+o,64,'rn')
    o,_,st['t_oP2'],_ = rnd_t(f4*o,67,'chop')
    o,os2,st['r_oS2'],st['u_oS2'] = rnd_t(CV[1]+o,64,'rn')
    o,op3,st['t_oP3'],_ = rnd_t(sq*o,67,'chop')
    e,_,st['t_eP1'],_ = rnd_t(f4*CV[6],67,'chop')
    e,es1,st['r_eS1'],st['u_eS1'] = rnd_t(CV[4]+e,64,'rn')
    e,_,st['t_eP2'],_ = rnd_t(f4*e,67,'chop')
    e,es2,st['r_eS2'],st['u_eS2'] = rnd_t(CV[2]+e,64,'rn')
    e,ep3,st['t_eP3'],_ = rnd_t(f4*e,67,'chop')
    s = o + e; a = abs(s)
    lo = texp(abs(o))-66; le = texp(abs(e))-66; E = texp(a)
    N = a / TWO**le; N = N.numerator
    cR = (E-64)-le
    rem = N & ((1<<(cR+1))-1)
    m_def = ((HALF - (Fraction(N,1)/TWO**(cR+1) - (N>>(cR+1)))) * TWO**(cR+1))
    recs.append(dict(cls=cls, se=se, sig=sig, insn=insn, i0=di['i0'],
        rsn=di['rsn'], ce=int(se,16)&0x7fff, mval=m, de2=lo-le, W=cR+1,
        rem=format(rem,'0%db'%(cR+1)), mdef=m_def,
        f4s=f4s, os1=os1, os2=os2, op3=op3, es1=es1, es2=es2, ep3=ep3,
        **{k:(float(v) if isinstance(v,Fraction) else v) for k,v in st.items()}))
pickle.dump(recs, open('h761_state.pkl','wb'))
P = [r for r in recs if r['cls']=='POS']; Ng = [r for r in recs if r['cls']=='NEG']
print('rows:', len(recs), 'POS', len(P), 'NEG', len(Ng))
# global single-feature contrast
import statistics
feats = ['t_sq','t_f4','t_oP1','r_oS1','u_oS1','t_oP2','r_oS2','u_oS2','t_oP3',
         't_eP1','r_eS1','u_eS1','t_eP2','r_eS2','u_eS2','t_eP3','i0','rsn','ce']
print('%-8s %10s %10s' % ('feat','POSmean','NEGmean'))
for f in feats:
    pv = [float(r[f]) for r in P]; nv = [float(r[f]) for r in Ng]
    print('%-8s %10.4f %10.4f' % (f, statistics.mean(pv), statistics.mean(nv)))
# parity features of stage significands
for f in ('f4s','os1','os2','op3','es1','es2','ep3'):
    pv = [r[f]&1 for r in P]; nv = [r[f]&1 for r in Ng]
    print('%-8s lsb: POS %.3f  NEG %.3f' % (f, sum(pv)/len(pv), sum(nv)/len(nv)))
# exact pattern twins
groups = collections.defaultdict(list)
for r in recs: groups[(r['rem'], r['de2'])].append(r)
tw = [(k,v) for k,v in groups.items() if len(set(x['cls'] for x in v))>1]
print('=== exact (rem,de2) twin groups with both classes:', len(tw), '===')
for k, v in tw:
    for r in v:
        print(' %s %s/%s %s i0=%d rsn=%d ce=%04x tails oP3=%.4f eP3=%.4f eS2rem=%.4f f4=%.4f' % (
            r['cls'], r['se'], r['sig'], r['insn'], r['i0'], r['rsn'], r['ce'],
            r['t_oP3'], r['t_eP3'], r['r_eS2'], r['t_f4']))
print('DONE')
