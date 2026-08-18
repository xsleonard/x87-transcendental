#!/usr/bin/env python3
# h760: resolve the oP3@77 paradox — exact shift on NEG rows + which
# rows break, with their boundary distances.
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
def chain(mag, oP3spec):
    sq = rnd(mag*mag,67,'chop'); f4 = rnd(sq*sq,67,'chop')
    o = rnd(f4*CV[5],67,'chop'); o = rnd(CV[3]+o,64,'rn')
    o = rnd(f4*o,67,'chop'); o = rnd(CV[1]+o,64,'rn'); o = rnd(sq*o,*oP3spec)
    e = rnd(f4*CV[6],67,'chop'); e = rnd(CV[4]+e,64,'rn')
    e = rnd(f4*e,67,'chop'); e = rnd(CV[2]+e,64,'rn'); e = rnd(f4*e,67,'chop')
    return o, e
ROWS = pickle.load(open('h755_rows.pkl','rb'))
print('rows breaking under oP3=(77,away), with boundary distance:')
nb = 0
for i,(cls, mag, pd, lsb) in enumerate(ROWS):
    o0,e0 = chain(mag,(67,'chop'))
    o1,e1 = chain(mag,(77,'away'))
    p0 = rnd(o0+e0,64,'rn'); p1 = rnd(o1+e1,64,'rn')
    if cls!='POS' and p1 != pd:
        nb += 1
        s0=abs(o0+e0); g=TWO**(texp(s0)-63); q=s0/g; fl=q.__floor__(); fr=q-fl
        do = (abs(o1)-abs(o0))/g
        if nb<=8:
            print(' %s i=%d frac=%.6f shift_o(grid)=%.3e p0==pd:%s' % (
                cls,i,float(fr),float(do),p0==pd))
print('total broken:', nb)
