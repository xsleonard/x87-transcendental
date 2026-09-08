#!/usr/bin/env python3
# h973: OFFLINE EXACT-TAIL PROGRAM.  Reconstruct the terminal
# composition from banked operand decompositions (h970_features:
# full mul/lf/rf/f4 sigs; h972: full rdisc + DI_CORR terminal
# ground truth), validate the replica bit-exactly (ud/u5d/rsh/rud/
# left/right/d60, model-carry extraction, final-add rounding vs all
# 33,260 banked m93 legs), then search tail-hypothesis variants
#   V(jL, jR, keep) = chop67(A + trunc_top(TL, jL) + trunc_top(TR, jR))
#                     [+ model net-carry if keep]
# scored by predicted-vs-captured hw legs on all census ops.
# The census labels say: DOWN needs eps<0, ZERO needs eps==0
# exactly, UP needs eps>0 — a variant must earn all three at once.
import sys
from collections import Counter, defaultdict

MODES = ("rn", "rd", "ru", "rz")

feat = {}
hdr = None
for ln in open("h970_features.tsv"):
    t = ln.rstrip("\n").split("\t")
    if t[0] == "insn":
        hdr = t
        ix = {c: i for i, c in enumerate(hdr)}
        continue
    feat[(t[0], t[1])] = t
corr = {}
for ln in open("h972_corr.tsv"):
    t = ln.rstrip("\n").split("\t")
    if t[0] == "insn":
        continue
    corr[(t[0], t[1])] = t
legs = {}
for ln in open("h968_ops.tsv"):
    t = ln.rstrip("\n").split("\t")
    if t[0] == "insn":
        continue
    m4 = {}
    h4 = {}
    for j, md in enumerate(MODES):
        m4[md] = t[12 + 2 * j].lower()
        h4[md] = t[13 + 2 * j].lower()
    legs[(t[0], t[1])] = (t[8], m4, h4)   # cls, model legs, hw legs
print("ops:", len(feat), len(corr), len(legs))

def x87val(s):
    se, sig = s.split(":")
    se, sig = int(se, 16), int(sig, 16)
    return ((se >> 15) & 1, se & 0x7FFF, sig)

def round64(num, sh, neg, mode):
    # value = num * 2^sh (num>0 int); round mantissa to 64 bits
    w = num.bit_length()
    k = w - 64
    if k <= 0:
        top, g, below, e = num << -k, 0, 0, sh - (-k)
    else:
        top = num >> k
        g = (num >> (k - 1)) & 1
        below = num & ((1 << (k - 1)) - 1) if k > 1 else 0
        e = sh + k
    inc = 0
    if mode == "rn":
        inc = g and (below or (top & 1))
    elif mode == "ru":
        inc = (not neg) and (g or below)
    elif mode == "rd":
        inc = neg and (g or below)
    if inc:
        top += 1
        if top >> 64:
            top >>= 1
            e += 1
    return (neg, e + 63 + 16383, top)   # (sign, biased exp, sig)

ops = sorted(feat)
bad = Counter()
R = {}
for k in ops:
    t = feat[k]
    c = corr[k]
    g = lambda col: t[ix[col]]
    mulsig = int(g("mulsig"), 16)
    lfsig = int(g("lfsig"), 16)
    rfsig = int(g("rfsig"), 16)
    f4sig = int(g("f4sig"), 16)
    ls, rs = int(g("leftsign")), int(g("rightsign"))
    le2, re2 = int(g("lefte2")), int(g("righte2"))
    PL = mulsig * lfsig
    shL = PL.bit_length() - 67
    PR = f4sig * rfsig
    shR = PR.bit_length() - 67
    okc = True
    okc &= (PL >> shL) == int(g("leftsig"), 16)
    okc &= int(g("mule2")) + int(g("lfe2")) + shL == le2
    okc &= (PR >> shR) == int(g("rightsig"), 16)
    okc &= int(g("f4e2")) + int(g("rfe2")) + shR == re2
    okc &= shR == int(g("rsh"))
    dL = PL & ((1 << shL) - 1)
    dR = PR & ((1 << shR) - 1)
    okc &= (dL >> (shL - 3)) == int(g("ud"))
    okc &= (dL >> (shL - 5)) == int(g("u5d"))
    okc &= (dR >> (shR - 1)) == int(g("rud"))
    okc &= dR == int(c[2], 16)
    if not okc:
        bad["decomp"] += 1
        continue
    pay = int(g("pay2")) if g("pay2") not in ("-",) else 0
    # common scale for exact integer arithmetic
    b = min(le2 - shL, re2 - shR, le2 - 8) - 4
    A = (-1) ** ls * (int(g("leftsig"), 16) << (le2 - b)) \
        + (-1) ** rs * (int(g("rightsig"), 16) << (re2 - b))
    if pay:
        A += (-1) ** (ls ^ (pay < 0)) * (abs(pay) << (le2 - 8 - b))
    mag = -A if A < 0 else A
    w = mag.bit_length()
    d60_rep = ((mag >> (w - 127)) if w >= 127
               else (mag << (127 - w))) & ((1 << 60) - 1)
    if g("d60") != "-" and d60_rep != int(g("d60"), 16):
        bad["d60"] += 1
        continue
    # chop67 of A at scale b -> value integer at scale b2
    ch = (mag >> (w - 67)) << (w - 67)
    chval = -ch if A < 0 else ch          # x 2^b
    ulp67 = 1 << (w - 67)
    cs, ce2, csig = int(c[5]), int(c[6]), int(c[7], 16)
    corrval = (-1) ** cs * (csig << (ce2 - b)) if ce2 >= b else None
    if corrval is None:
        # corr below scale base (shouldn't happen)
        bad["scale"] += 1
        continue
    ncar = corrval - chval
    if ncar % ulp67:
        bad["carfrac"] += 1
        continue
    ncar //= ulp67
    R[k] = dict(A=A, dL=dL, shL=shL, dR=dR, shR=shR, ls=ls, rs=rs,
                le2=le2, re2=re2, b=b, w=w, ncar=ncar,
                corrval=corrval, ulp67=ulp67)
print("replica decomp/d60/carry ok:", len(R), "bad:", dict(bad))
print("net-carry distribution:",
      dict(Counter(r["ncar"] for r in R.values())))

# final-add + rounding validation vs banked m93 legs.  The output
# SIGN is quadrant logic (i0), orthogonal to the terminal — take it
# from the banked legs; the magnitude is |1 + correction|.
vbad = 0
for k, r in list(R.items()):
    cls, m4, h4 = legs[k]
    b = r["b"]
    one = 1 << (-b)                        # 1.0 at scale b (b<0)
    v = one + r["corrval"]
    num = -v if v < 0 else v
    neg = x87val(m4["rn"])[0]
    r["neg"] = neg
    ok = True
    for md in MODES:
        sg, ex, sig = round64(num, b, neg, md)
        bs, be, bsig = x87val(m4[md])
        if (sg, ex, sig) != (bs, be, bsig):
            ok = False
    if not ok:
        vbad += 1
        del R[k]
print("final-add replica: %d/%d ops match all 4 banked m93 legs"
      % (len(R), len(R) + vbad), "(dropped %d)" % vbad)

# ---- variant search ----
def trunc_top(d, sh, j):
    if j >= sh:
        return d
    if j <= 0:
        return 0
    return (d >> (sh - j)) << (sh - j)

def score(jL, jR, keep):
    c = Counter()
    for k, r in R.items():
        cls, m4, h4 = legs[k]
        b = r["b"]
        TL = (-1) ** r["ls"] * (trunc_top(r["dL"], r["shL"], jL)
                                << (r["le2"] - r["shL"] - b))
        TR = (-1) ** r["rs"] * (trunc_top(r["dR"], r["shR"], jR)
                                << (r["re2"] - r["shR"] - b))
        A2 = r["A"] + TL + TR
        mag = -A2 if A2 < 0 else A2
        w2 = mag.bit_length()
        ch = (mag >> (w2 - 67)) << (w2 - 67)
        V = (-ch if A2 < 0 else ch)
        if keep:
            V += r["ncar"] * r["ulp67"]
        eps = V - r["corrval"]
        one = 1 << (-b)
        v = one + r["corrval"] + eps
        num = -v if v < 0 else v
        neg = r["neg"]
        ok = True
        for md in MODES:
            sg, ex, sig = round64(num, b, neg, md)
            bs, be, bsig = x87val(h4[md])
            if (sg, ex, sig) != (bs, be, bsig):
                ok = False
                break
        c[cls, ok] += 1
        c["ALL", ok] += 1
    return c

def report(name, c):
    parts = []
    for cl in ("DEFICIT", "CLEANEXP", "TIE", "OTHER", "CLEAN",
               "ALL"):
        o, m = c[(cl, True)], c[(cl, False)]
        if o + m:
            parts.append("%s %d/%d" % (cl[:5], o, o + m))
    print(name.ljust(16), " ".join(parts))

# baseline sanity: jL=jR=0, keep=1 == the model itself
report("m93(0,0,keep)", score(0, 0, 1))
for keep in (1, 0):
    for jL in (0, 1, 2, 4, 8, 999):
        for jR in (0, 1, 2, 4, 8, 999):
            if (jL, jR, keep) == (0, 0, 1):
                continue
            report("V(%s,%s,k%d)" % (jL, jR, keep),
                   score(jL, jR, keep))
