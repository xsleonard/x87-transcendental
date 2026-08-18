#!/usr/bin/env python3
# h718: THE EXACT-DIFFERENCE HYPOTHESIS.  The gate apparatus
# (payload + r59/r60/r64 fires + taps) reads exactly the quantities
# a truncated fused multiplier-subtractor would need to resolve its
# retained lsb: rdisc (right product discard), t4 (fourth's own
# discard), low3*sqlow (squarer missing mass).  Hypothesis: the chip
# computes S-B with product content kept EXACT (single truncation at
# the end); the model's chop67-per-product + gate stack is a fitted
# surrogate.  Test variants against the 29 chip-implied flips:
#   VL : left product exact, right chopped
#   VR : right product exact, left chopped
#   VB : both products exact
#   V2 : both exact AND fourth exact (= square.sig^2)
#   V3 : everything exact from m (square=m^2, fourth=m^4)
# each with and without the model's payload term.
# Chip target: retained_chip = retained_model + delta,
# delta from h715c (corr+1 => +1, corr-1 => -1, fb90 => -2..-4).
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

# chip-implied retained delta per row (h715c verdicts)
CORR_P1 = {"44ca2bf","9242f0c","0749eaa","750943e","56e0a67",
           "54e2537","7503a2f","59862dd"}  # chip corr larger => retained+1
def chip_delta(sig):
    for s in CORR_P1:
        if sig.endswith(s): return +1
    if sig.endswith("30c1fc9"): return None   # fb90: -2..-4
    return -1

def main():
    dump = parse_dump("h714_dump.txt")
    ops = [l.split() for l in open("h714_ops.txt")]
    names = ["VL","VR","VB","V2","V3"]
    score = {(n,p): 0 for n in names for p in (0,1)}
    nrows = 0
    print("%-18s %3s tgt | %s" % ("sig","th","  ".join(
        "%-7s" % ("%s%s" % (n, "+p" if p else "  "))
        for n in names for p in (0,1))))
    for se, sig in ops:
        d = dump[(se, sig)]
        poly = d["DI_POLY"]; tc = d["DI_TC"]; r59 = d["DI_R59"]
        mag = wv(poly["mag"]); sq = wv(poly["sq"]); f4 = wv(poly["f4"])
        odd = wv(poly["odd"]); ev = wv(poly["even"])
        left = wv(tc["left"]); right = wv(tc["right"])
        payload = r59["payload"]; dp = r59["dp"]
        rscale = r59["rscale"]; k = r59["k"]
        umag = r59["umag"]
        ret_model = umag >> k
    	# absolute exponents of candidate S/B terms (value = sig*2^e2)
        SL_ch = (left[2], left[1])
        SR_ch = (right[2], right[1])
        SL_ex = (sq[2]*odd[2], sq[1]+odd[1])
        SR_ex = (f4[2]*ev[2], f4[1]+ev[1])
        SR_x2 = (sq[2]*sq[2]*ev[2], 2*sq[1]+ev[1])
        SL_x3 = (mag[2]*mag[2]*odd[2], 2*mag[1]+odd[1])
        SR_x3 = (mag[2]**4*ev[2], 4*mag[1]+ev[1])
        variants = {"VL": (SL_ex, SR_ch), "VR": (SL_ch, SR_ex),
                    "VB": (SL_ex, SR_ex), "V2": (SL_ex, SR_x2),
                    "V3": (SL_x3, SR_x3)}
        tgt = chip_delta(sig)
        cells = []
        nrows += 1
        for n in names:
            (sS, eS), (sB, eB) = variants[n]
            for p in (0, 1):
                Q = min(eS, eB, rscale) - 4
                v = (sS << (eS - Q)) - (sB << (eB - Q))
                if p and payload:
                    v += payload << (rscale + dp - Q)
                ret = v >> (rscale + k - Q)
                dlt = ret - ret_model
                ok = (dlt == tgt) if tgt is not None else (-4 <= dlt <= -2)
                if ok: score[(n,p)] += 1
                cells.append("%-7s" % ("%+d%s" % (dlt, "*" if ok else "")))
        print("%-18s %3s %3s | %s" % (sig[-8:], r59["theta"],
              tgt if tgt is not None else "-2..4", "  ".join(cells)))
    print()
    print("SCORE (rows whose chip flip is exactly predicted), n=%d:" % nrows)
    for n in names:
        for p in (0,1):
            print("  %-3s%s : %d/29" % (n, "+payload" if p else "        ",
                                        score[(n,p)]))
main()
