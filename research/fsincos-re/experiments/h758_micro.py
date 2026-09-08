#!/usr/bin/env python3
# h758: differential microscope — per-row boundary distance (deficit/
# headroom) + wide-width per-edge sweep (65..78 x jam/odd/away) with
# per-row masks + greedy set cover.
import pickle
from fractions import Fraction
TWO = Fraction(2); HALF = Fraction(1,2)
def wv_val(w):
    v = Fraction(w[2]) * TWO**w[1]
    return -v if w[0] else v
C = {1:(1,-69,(0x5<<64)|0x5555555555555555), 2:(0,-73,(0x4<<64)|0x4444444444443e35),
     3:(1,-79,(0x6<<64)|0x806806806773c774), 4:(0,-85,(0x5<<64)|0xc778e94f50956d70),
     5:(1,-92,(0x6<<64)|0xb991122efa0532f0), 6:(0,-99,(0x5<<64)|0x8303f02614d5e4d8)}
CV = {k: wv_val(v) for k, v in C.items()}
def texp(a):
    e = a.numerator.bit_length() - a.denominator.bit_length()
    while TWO**e > a: e -= 1
    while TWO**(e+1) <= a: e += 1
    return e
def rnd(v, bits, mode):
    if v == 0: return v
    s = -1 if v < 0 else 1
    a = abs(v); e = texp(a)
    g = TWO**(e - bits + 1)
    q = a / g; fl = q.__floor__(); r = q - fl
    if mode == 'chop': pass
    elif mode == 'rn':
        if r > HALF or (r == HALF and fl % 2 == 1): fl += 1
    elif mode == 'away':
        if r > 0: fl += 1
    elif mode == 'odd':
        if r > 0 and fl % 2 == 0: fl += 1
    elif mode == 'jam':
        if fl % 2 == 0: fl += 1
    return s * fl * g
ST = ['sq','f4','oP1','oS1','oP2','oS2','oP3','eP1','eS1','eP2','eS2','eP3','fin']
SHIPC = [(67,'chop'),(67,'chop'),(67,'chop'),(64,'rn'),(67,'chop'),(64,'rn'),
         (67,'chop'),(67,'chop'),(64,'rn'),(67,'chop'),(64,'rn'),(67,'chop'),(64,'rn')]
def chain(mag, cfg, want_frac=False):
    sq = rnd(mag*mag, *cfg[0]); f4 = rnd(sq*sq, *cfg[1])
    o = rnd(f4*CV[5], *cfg[2]); o = rnd(CV[3]+o, *cfg[3])
    o = rnd(f4*o, *cfg[4]); o = rnd(CV[1]+o, *cfg[5]); o = rnd(sq*o, *cfg[6])
    e = rnd(f4*CV[6], *cfg[7]); e = rnd(CV[4]+e, *cfg[8])
    e = rnd(f4*e, *cfg[9]); e = rnd(CV[2]+e, *cfg[10]); e = rnd(f4*e, *cfg[11])
    s = o + e
    if want_frac:
        a = abs(s); g = TWO**(texp(a)-63)
        q = a/g; fl = q.__floor__()
        return q - fl, fl, o, e
    return rnd(s, *cfg[12])
ROWS = pickle.load(open('h755_rows.pkl','rb'))
# 1) boundary-distance table under SHIP
print('=== per-row (1/2 - frac) in units of 2^-20: POS deficits vs NEG/CLN headroom ===')
tab = []
for i,(cls, mag, pd, lsb) in enumerate(ROWS):
    frac, fl, o, e = chain(mag, SHIPC, want_frac=True)
    d = (HALF - frac) * 2**20
    lo = texp(abs(o))-66; le = texp(abs(e))-66
    tab.append((cls, i, float(d), fl%2, abs(lo-le), frac))
pos = sorted([t for t in tab if t[0]=='POS'], key=lambda t:-t[2])
neg = sorted([t for t in tab if t[0]=='NEG'], key=lambda t:t[2])
cln = sorted([t for t in tab if t[0]=='CLN'], key=lambda t:t[2])
print('POS worst deficits (need eps > d): ', [round(t[2],1) for t in pos[:12]])
print('POS parity split lsb: odd=%d even=%d; ties(d==0)=%d' % (
    sum(1 for t in pos if t[3]==1), sum(1 for t in pos if t[3]==0),
    sum(1 for t in pos if t[5]==HALF)))
print('NEG tightest headroom (need eps < d):', [round(t[2],1) for t in neg[:19]])
print('NEG parity split lsb: odd=%d even=%d' % (
    sum(1 for t in neg if t[3]==1), sum(1 for t in neg if t[3]==0)))
print('CLN below-half tightest headroom:', [round(t[2],1) for t in cln[:12] if t[2]>0])
print('POS d_e2 histo:', sorted(set((t[4], sum(1 for u in pos if u[4]==t[4])) for t in pos)))
print('NEG d_e2 histo:', sorted(set((t[4], sum(1 for u in neg if u[4]==t[4])) for t in neg)))
# 2) wide sweep with masks
POSN = sum(1 for r in ROWS if r[0]=='POS')
def score(cfg):
    fm = 0; bn = 0; bneg = 0; pi = 0
    for cls, mag, pd, lsb in ROWS:
        pl = chain(mag, cfg)
        if cls == 'POS':
            if abs(pl) == abs(pd) + lsb: fm |= 1 << pi
            pi += 1
        else:
            if pl != pd:
                bn += 1
                if cls=='NEG': bneg += 1
    return fm, bn, bneg
res = {}
for si in range(13):
    for w in range(65, 79):
        for md in ('jam','odd','away'):
            if (w, md) == SHIPC[si]: continue
            cfg = list(SHIPC); cfg[si] = (w, md)
            fm, bn, bneg = score(cfg)
            n = bin(fm).count('1')
            if n > 0:
                res[(si,w,md)] = (fm, bn, bneg)
pickle.dump({'tab':tab,'res':res}, open('h758_out.pkl','wb'))
print('=== zero-collateral configs (pos desc) ===')
zc = sorted([(bin(v[0]).count('1'), k, v[0]) for k,v in res.items() if v[1]==0], reverse=True)
for n,k,fm in zc[:20]:
    print('  %s w=%d %-4s : pos %d' % (ST[k[0]], k[1], k[2], n))
print('=== full-fix configs, fewest broken ===')
ff = sorted([(v[1], k, v[2]) for k,v in res.items() if bin(v[0]).count('1')==POSN])
for bn,k,bneg in ff[:15]:
    print('  %s w=%d %-4s : broken %d (neg %d)' % (ST[k[0]], k[1], k[2], bn, bneg))
# 3) greedy set cover from zero-collateral masks
cov = 0; pick = []
while True:
    bestk = None; bestg = 0
    for n,k,fm in zc:
        g = bin(fm & ~cov).count('1')
        if g > bestg: bestg, bestk = g, (k, fm)
    if not bestk: break
    pick.append((bestk[0], bestg)); cov |= bestk[1]
    if bin(cov).count('1') == POSN: break
print('=== greedy cover (zero-collateral union):', bin(cov).count('1'), '/', POSN, '===')
for k,g in pick[:12]: print('  ', ST[k[0]], k[1], k[2], '+%d' % g)
print('DONE')
