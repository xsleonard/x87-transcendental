#!/usr/bin/env python3
# h719: THE CUT-COLUMN SEARCH.  Frame-corrected targets (relative to
# the PRE-fire retained value): chip_retained = (umag>>k) + fire_adj
# + delta(h715c).  Candidate arithmetic:
#   U(gL,gR) = S_pure + T(discL,gL) - B - T(discR,gR)   [+ payload?]
#   T(x,g) = floor(x / 2^g) * 2^g   (truncate at column g; units of
#   2^rscale; g=-inf => exact; g=+inf => drop)
# discL/discR = the exact chop67 discards of the left/right products.
# Search gL,gR (and payload on/off) for the pair reproducing every
# non-singleton row's chip retained value.
import sys
from fractions import Fraction

HEX128 = {"umag","S","B","Mreg","t4","sqlow","rd3","disc"}
def parse_dump(path):
    ops = {}; cur = None
    for line in open(path):
        t = line.split()
        if not t: continue
        if t[0] == "DI_IN":
            cur = (t[1], t[2]); ops[cur] = {}
        elif cur is None: continue
        elif t[0] in ("DI_POLY","DI_TC","DI_R59","DI_CRIT","DI_BS","DI_BR","DI_CORR"):
            d = ops[cur].setdefault(t[0], {})
            for kv in t[1:]:
                k, v = kv.split("=", 1)
                if t[0] == "DI_R59" and k in HEX128:
                    x = int(v, 16)
                    if x >= 1 << 127: x -= 1 << 128
                    d[k] = x
                elif ":" in v and v.count(":") == 2: d[k] = v
                elif "," in v: d[k] = v
                elif v.lstrip("-").isdigit(): d[k] = int(v)
                else: d[k] = v
    return ops

def wv(s):
    sg, e2, hx = s.split(":")
    return (int(sg), int(e2), int(hx, 16))

CORR_P1 = {"44ca2bf","9242f0c","0749eaa","750943e","56e0a67",
           "54e2537","7503a2f","59862dd"}
def h715c_delta(sig):
    for s in CORR_P1:
        if sig.endswith(s): return +1
    if sig.endswith("30c1fc9"): return None      # fb90
    if sig.endswith("0688f849"): return -1       # be6 (single -1 vs final)
    return -1

def fire_adj(d):
    br = d.get("DI_BR", {}); r59 = d["DI_R59"]
    b = br.get("br", d.get("DI_CORR", {}).get("via"))
    th = r59["theta"]
    if b == "tie":
        return -1 if br.get("tfire") == 1 else 0
    if b == "band":
        if br.get("fire") == 1:
            return -1 if th > 0 else +1
        return 0
    if b == "corner":
        if br.get("fire") == 1:
            return -1 if (th == 0 or th > 0) else +1
        return 0
    return 0   # q67th2

def main():
    dump = parse_dump("h714_dump.txt")
    ops = [l.split() for l in open("h714_ops.txt")]
    rows = []
    for se, sig in ops:
        d = dump[(se, sig)]
        poly = d["DI_POLY"]; tc = d["DI_TC"]; r59 = d["DI_R59"]
        sq = wv(poly["sq"]); odd = wv(poly["odd"])
        f4 = wv(poly["f4"]); ev = wv(poly["even"])
        left = wv(tc["left"]); right = wv(tc["right"])
        rscale = r59["rscale"]; k = r59["k"]
        S = r59["S"]; B = r59["B"]
        payload = r59["payload"]; dp = r59["dp"]
        S_pure = S - (payload << dp) if payload else S
        lf = sq[2] * odd[2]
        shL = lf.bit_length() - 67
        assert (lf >> shL) == left[2], (sig, "left mismatch")
        dLi = lf & ((1 << shL) - 1)
        discL = Fraction(dLi) * Fraction(2)**(sq[1] + odd[1] - rscale)
        rf = f4[2] * ev[2]
        shR = rf.bit_length() - 67
        assert (rf >> shR) == right[2], (sig, "right mismatch")
        dRi = rf & ((1 << shR) - 1)
        discR = Fraction(dRi) * Fraction(2)**(f4[1] + ev[1] - rscale)
        dlt = h715c_delta(sig)
        tgt = None if dlt is None else (r59["umag"] >> k) + fire_adj(d) + dlt
        rows.append(dict(sig=sig, th=r59["theta"], k=k,
                         S_pure=S_pure, B=B, payload=payload, dp=dp,
                         discL=discL, discR=discR, tgt=tgt,
                         ret0=r59["umag"] >> k, fa=fire_adj(d), dlt=dlt))
    GS = list(range(-12, 5)) + [None]     # None = drop entirely
    def T(x, g):
        if g is None: return Fraction(0)
        q = Fraction(2)**g
        return (x / q).__floor__() * q
    best = []
    for gL in GS:
        for gR in GS:
            for use_pay in (0, 1):
                nok = 0; bad = []
                for r in rows:
                    if r["tgt"] is None: continue
                    U = Fraction(r["S_pure"]) + T(r["discL"], gL) \
                        - Fraction(r["B"]) - T(r["discR"], gR)
                    if use_pay and r["payload"]:
                        U += Fraction(r["payload"] << r["dp"])
                    ret = (U / Fraction(2)**r["k"]).__floor__()
                    if ret == r["tgt"]: nok += 1
                    else: bad.append(r["sig"][-7:])
                best.append((nok, gL, gR, use_pay, bad[:6]))
    best.sort(key=lambda x: -x[0])
    n_scored = sum(1 for r in rows if r["tgt"] is not None)
    print("rows scored:", n_scored, " (fb90 excluded)")
    for nok, gL, gR, up, bad in best[:12]:
        print("  gL=%-4s gR=%-4s pay=%d : %d/%d   miss: %s"
              % (gL, gR, up, nok, n_scored, ",".join(bad)))
main()
