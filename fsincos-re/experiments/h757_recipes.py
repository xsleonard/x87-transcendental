#!/usr/bin/env python3
# h757: sine-chain recipe round 2 — h242 transplant + edge combos +
# sinefin lookahead family, scored on the 567-row pool with per-row masks.
import pickle, itertools
from fractions import Fraction
TWO = Fraction(2)
HALF = Fraction(1,2)
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
    a = abs(v)
    e = texp(a)
    g = TWO**(e - bits + 1)
    q = a / g
    fl = q.__floor__()
    r = q - fl
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
def chain2(mag, cfg):
    sq = rnd(mag*mag, *cfg['sq'])
    f4 = rnd(sq*sq, *cfg['f4'])
    o = rnd(f4*CV[5], *cfg['oP1'])
    o = rnd(CV[3]+o, *cfg['oS1'])
    o = rnd(f4*o, *cfg['oP2'])
    o = rnd(CV[1]+o, *cfg['oS2'])
    o = rnd(sq*o, *cfg['oP3'])
    e = rnd(f4*CV[6], *cfg['eP1'])
    e = rnd(CV[4]+e, *cfg['eS1'])
    e = rnd(f4*e, *cfg['eP2'])
    c2 = cfg.get('c2')
    C2v = rnd(CV[2], *c2) if c2 else CV[2]
    e = rnd(C2v+e, *cfg['eS2'])
    e = rnd(f4*e, *cfg['eP3'])
    fin = cfg['fin']
    if fin[0] != 'la':
        return rnd(o+e, *fin)
    _, kspec, thr = fin
    lo = texp(abs(o)) - (cfg['oP3'][0]-1)
    le = texp(abs(e)) - (cfg['eP3'][0]-1)
    de2 = abs(lo - le)
    K = kspec[1] if kspec[0]=='fix' else max(2, min(40, de2 + kspec[1] - 2))
    s = o + e
    sg = -1 if s < 0 else 1
    a = abs(s)
    g = TWO**(texp(a) - 63)
    q = a / g
    fl = q.__floor__()
    frac = q - fl
    t = HALF - TWO**(-K) if thr==1 else HALF
    if frac >= t: fl += 1
    return sg * fl * g
SHIPC = dict(sq=(67,'chop'), f4=(67,'chop'), oP1=(67,'chop'), oS1=(64,'rn'),
             oP2=(67,'chop'), oS2=(64,'rn'), oP3=(67,'chop'), eP1=(67,'chop'),
             eS1=(64,'rn'), eP2=(67,'chop'), eS2=(64,'rn'), eP3=(67,'chop'),
             fin=(64,'rn'))
ROWS = pickle.load(open('h755_rows.pkl','rb'))
POSI = [i for i,r in enumerate(ROWS) if r[0]=='POS']
def score(cfg):
    fm = bm = 0; fn = bn = 0; pi = 0
    for cls, mag, pd, lsb in ROWS:
        pl = chain2(mag, cfg)
        if cls == 'POS':
            if abs(pl) == abs(pd) + lsb: fm |= 1 << pi
            pi += 1
        else:
            if pl != pd:
                bn += 1
                if cls == 'NEG': fn += 1
    return fm, bn, fn
def rep(name, cfg):
    fm, bn, fn = score(cfg)
    n = bin(fm).count('1')
    print('%-34s pos %3d/148  broken %2d (neg %d)' % (name, n, bn, fn), flush=True)
    return fm, bn
# sanity: SHIP fixes 0, breaks 0
rep('SHIP', SHIPC)
H242E = dict(f4=(65,'rn'), oS1=(67,'chop'), eS1=(67,'chop'), eS2=(66,'odd'),
             eP3=(64,'chop'))
def mk(**kw):
    c = dict(SHIPC); c.update(kw); return c
print('--- h242-edge subsets (c2away64 rides with eS2 unless noted) ---')
MASKS = {}
for r in range(6):
    for sub in itertools.combinations(sorted(H242E), r):
        kw = {k: H242E[k] for k in sub}
        if 'eS2' in sub: kw['c2'] = (64,'away')
        nm = 'h242[' + ','.join(sub) + ']' if sub else 'h242[]'
        MASKS[nm] = rep(nm, mk(**kw))
print('--- eS2 odd66 without const re-round ---')
MASKS['eS2only'] = rep('eS2-odd66-natc', mk(eS2=(66,'odd')))
MASKS['eS2+c2'] = rep('eS2-odd66+c2away64', mk(eS2=(66,'odd'), c2=(64,'away')))
print('--- combo grid ---')
best = []
for f4 in ((67,'chop'),(65,'chop'),(65,'rn'),(66,'chop'),(65,'odd'),(65,'jam')):
    for oS1 in ((64,'rn'),(67,'chop')):
        for eS1 in ((64,'rn'),(67,'chop')):
            for eS2 in ((64,'rn'),(66,'odd'),(66,'jam'),(64,'away')):
                for eP3 in ((67,'chop'),(64,'chop'),(65,'rn'),(66,'chop')):
                    cfg = mk(f4=f4, oS1=oS1, eS1=eS1, eS2=eS2, eP3=eP3)
                    fm, bn, fn = score(cfg)
                    n = bin(fm).count('1')
                    if n >= 50 or (n >= 30 and bn == 0):
                        best.append((bn, -n, f4, oS1, eS1, eS2, eP3, fm))
best.sort()
for bn, mn, f4, oS1, eS1, eS2, eP3, fm in best[:25]:
    print('  f4=%s oS1=%s eS1=%s eS2=%s eP3=%s : pos %d broken %d' %
          (f4, oS1, eS1, eS2, eP3, -mn, bn), flush=True)
print('--- sinefin family ---')
SF = {}
for kk in list(range(2,21)):
    for thr in (1,2):
        nm = 'la-fix%d-t%d' % (kk, thr)
        SF[nm] = rep(nm, mk(fin=('la',('fix',kk),thr)))
for cc in range(0,7):
    for thr in (1,2):
        nm = 'la-rel%+d-t%d' % (cc, thr)
        SF[nm] = rep(nm, mk(fin=('la',('rel',cc),thr)))
pickle.dump({'MASKS':MASKS,'SF':SF,'best':best}, open('h757_masks.pkl','wb'))
print('DONE')
