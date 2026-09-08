#!/usr/bin/env python3
# h755: per-edge sine-chain campaign, round 1.  Cache (mag, shipped
# poly, lsb, class) for 148 POS + neg/clean; then sweep every
# single-stage (width, mode) change from shipped; hard wall = zero
# neg/clean flips; rank by positives fixed.
import subprocess, collections, pickle, os, itertools
from fractions import Fraction
def parse_wv(s):
    sg, e2, hx = s.split(":")
    return (int(sg), int(e2), int(hx, 16))
def wv_val(w):
    v = Fraction(w[2]) * Fraction(2)**w[1]
    return -v if w[0] else v
C = {1:(1,-69,(0x5<<64)|0x5555555555555555), 2:(0,-73,(0x4<<64)|0x4444444444443e35),
     3:(1,-79,(0x6<<64)|0x806806806773c774), 4:(0,-85,(0x5<<64)|0xc778e94f50956d70),
     5:(1,-92,(0x6<<64)|0xb991122efa0532f0), 6:(0,-99,(0x5<<64)|0x8303f02614d5e4d8)}
CV = {k: wv_val(v) for k, v in C.items()}
TWO = Fraction(2)
def rnd(v, bits, mode):
    if v == 0: return v
    s = -1 if v < 0 else 1
    a = abs(v)
    e = a.numerator.bit_length() - a.denominator.bit_length()
    while TWO**e > a: e -= 1
    while TWO**(e+1) <= a: e += 1
    g = TWO**(e - bits + 1)
    q = a / g
    fl = q.__floor__()
    r = q - fl
    if mode == "chop": pass
    elif mode == "rn":
        if r > Fraction(1,2) or (r == Fraction(1,2) and fl % 2 == 1): fl += 1
    elif mode == "away":
        if r > 0: fl += 1
    elif mode == "odd":
        if r > 0 and fl % 2 == 0: fl += 1
    elif mode == "jam":
        if fl % 2 == 0: fl += 1
    return s * fl * g
SHIP = [("m",67,"chop"),("m",67,"chop"),("m",67,"chop"),("a",64,"rn"),
        ("m",67,"chop"),("a",64,"rn"),("m",67,"chop"),
        ("m",67,"chop"),("a",64,"rn"),("m",67,"chop"),("a",64,"rn"),
        ("m",67,"chop"),("a",64,"rn")]
def chain(mag, cfg):
    sq = rnd(mag*mag, cfg[0][1], cfg[0][2])
    f4 = rnd(sq*sq, cfg[1][1], cfg[1][2])
    odd = rnd(f4*CV[5], cfg[2][1], cfg[2][2])
    odd = rnd(CV[3]+odd, cfg[3][1], cfg[3][2])
    odd = rnd(f4*odd, cfg[4][1], cfg[4][2])
    odd = rnd(CV[1]+odd, cfg[5][1], cfg[5][2])
    odd = rnd(sq*odd, cfg[6][1], cfg[6][2])
    ev = rnd(f4*CV[6], cfg[7][1], cfg[7][2])
    ev = rnd(CV[4]+ev, cfg[8][1], cfg[8][2])
    ev = rnd(f4*ev, cfg[9][1], cfg[9][2])
    ev = rnd(CV[2]+ev, cfg[10][1], cfg[10][2])
    ev = rnd(f4*ev, cfg[11][1], cfg[11][2])
    return rnd(odd+ev, cfg[12][1], cfg[12][2])
CACHE = "h755_rows.pkl"
if os.path.exists(CACHE):
    ROWS = pickle.load(open(CACHE, "rb"))
else:
    def state(se, sig, insn):
        flag = "--fcos-standalone" if insn=="cos" else "--fsin-standalone"
        p = subprocess.run(["./model_h235","--batch",flag,"--dump-internals"],
                           input=f"{se} {sig}\n", capture_output=True, text=True)
        if "DI_CORR" in p.stderr or "DI_SPOLY" not in p.stderr: return None
        for L in p.stderr.splitlines():
            if L.startswith("DI_SPOLY"):
                sp = dict(x.split("=",1) for x in L.split()[1:])
                return (wv_val(parse_wv(sp["mag"])),
                        wv_val(parse_wv(sp["poly"])),
                        TWO**parse_wv(sp["poly"])[1])
    ROWS = []
    votes = collections.defaultdict(dict)
    for l in open("h753_allvotes.txt"):
        t = l.split()
        votes[(t[3], t[4], t[1])][t[2]] = 1
    for (se, sig, insn) in sorted(votes):
        st = state(se, sig, insn)
        if st: ROWS.append(("POS",) + st)
    orig = set(tuple(l.split()) for l in open("h714_ops.txt"))
    for l in open("h754_neg102.txt"):
        t = l.split()
        if (t[3], t[4]) in orig: continue
        st = state(t[3], t[4], t[1])
        if st: ROWS.append(("NEG",) + st)
    for insn in ("cos","sin"):
        for op in open(f"sops_{insn}.txt").read().splitlines()[49:249]:
            se, sig = op.split()
            st = state(se, sig, insn)
            if st: ROWS.append(("CLN",) + st)
    pickle.dump(ROWS, open(CACHE, "wb"))
npos = sum(1 for r in ROWS if r[0]=="POS")
print("rows cached:", len(ROWS), "POS:", npos)
def score(cfg):
    okp = bad = 0
    for cls, mag, pd, lsb in ROWS:
        pl = chain(mag, cfg)
        if cls == "POS":
            if abs(pl) == abs(pd) + lsb: okp += 1
        else:
            if abs(pl) != abs(pd): bad += 1
    return okp, bad
res = []
for si in range(13):
    kind = SHIP[si][0]
    widths = range(64, 71)
    for w in widths:
        for md in ("chop","rn","away","odd","jam"):
            if (w, md) == (SHIP[si][1], SHIP[si][2]): continue
            cfg = list(SHIP); cfg[si] = (kind, w, md)
            okp, bad = score(cfg)
            if okp > 0:
                res.append((okp, bad, si, w, md))
res.sort(key=lambda x: (x[1] != 0, -x[0], x[1]))
print("single-stage sweep (stage, width, mode): top by pos with zero collateral first")
for okp, bad, si, w, md in res[:20]:
    print("  stage %-2d w=%-3d %-5s : pos %d/%d  broken %d" % (si, w, md, okp, npos, bad))
