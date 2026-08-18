#!/usr/bin/env python3
# h759: remainder bit-pattern contrast — for each POS/NEG (and near CLN)
# row, dump the exact final-add remainder as a bit string in even-lsb
# columns; test: does the ones-run reach even's lsb for POS but not NEG?
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
def chop(v, bits):
    s = -1 if v < 0 else 1
    a = abs(v); g = TWO**(texp(a)-bits+1)
    return s * (a/g).__floor__() * g
def rn(v, bits):
    s = -1 if v < 0 else 1
    a = abs(v); g = TWO**(texp(a)-bits+1)
    q = a/g; fl = q.__floor__(); r = q-fl
    if r > HALF or (r==HALF and fl%2==1): fl += 1
    return s*fl*g
ROWS = pickle.load(open('h755_rows.pkl','rb'))
out = []
for i,(cls, mag, pd, lsb) in enumerate(ROWS):
    sq = chop(mag*mag,67); f4 = chop(sq*sq,67)
    o = chop(f4*CV[5],67); o = rn(CV[3]+o,64); o = chop(f4*o,67)
    o = rn(CV[1]+o,64); o = chop(sq*o,67)
    e = chop(f4*CV[6],67); e = rn(CV[4]+e,64); e = chop(f4*e,67)
    e = rn(CV[2]+e,64); e = chop(f4*e,67)
    s = o + e
    a = abs(s)
    lo = texp(abs(o))-66; le = texp(abs(e))-66
    E = texp(a)
    # remainder in even-lsb integer units: a / 2^le is an integer N
    N = a / TWO**le
    assert N.denominator == 1
    N = N.numerator
    cR = (E-64) - le          # column of the round bit (grid lsb-1)
    if cR < 0: continue
    rem = N & ((1<<(cR+1)) - 1)   # bits cR..0 = remainder field
    W = cR+1
    bits = format(rem, '0%db' % W)
    # ones-run below the round bit
    run = 0
    for b in bits[1:]:
        if b=='1': run += 1
        else: break
    tail_after_run = bits[1+run:]
    out.append((cls, i, W, bits, run, int(bits[0]), lo-le, tail_after_run))
def show(cls, rows, lim=40):
    print('=== %s (%d) ===' % (cls, len(rows)))
    for cl,i,W,bits,run,rb,de2,tail in rows[:lim]:
        print(' i=%3d de2=%2d W=%2d rb=%d run=%2d rem=%s' % (i,de2,W,rb,run,bits))
P = [t for t in out if t[0]=='POS']
N = [t for t in out if t[0]=='NEG']
CL = [t for t in out if t[0]=='CLN']
show('POS', P, 200)
show('NEG', N, 40)
# clean rows with longest runs (the danger zone)
CLs = sorted(CL, key=lambda t:-t[4])
show('CLN-longest-runs', CLs, 25)
# summary: does run reach bottom (run == W-1) or leave a tail?
for nm, rows in (('POS',P),('NEG',N),('CLN',CL)):
    full = sum(1 for t in rows if t[4]==t[2]-1 and t[5]==0)
    tie  = sum(1 for t in rows if t[5]==1 and t[3][1:]== '0'*(t[2]-1))
    print('%s: n=%d run-to-bottom(rb=0)=%d exact-tie=%d' % (nm, len(rows), full, tie))
print('DONE')
