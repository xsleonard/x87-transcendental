#!/usr/bin/env python3
# h715b (T2 units): express each census row's needed delta interval
# in the frames that distinguish mechanisms:
#   RU  = retained-unit step 2^(rscale+k)  (a fire flip = +-1.0 RU)
#   UL  = umag lsb 2^rscale                (sub-ULP value error scale)
# Marks POINT rows (chip value exactly on the output grid) and
# prints their deltas exactly.  Also prints the per-mode mismatch
# pattern (which of rn/rd/ru fail).
import sys
from fractions import Fraction
sys.path.insert(0, ".")
fmod = __import__("h715_forensics")  # reuse parsers/helpers

parse_dump = fmod.parse_dump
wv_val = fmod.wv_val
preimage = fmod.preimage
intersect = fmod.intersect

def log2f(x):
    import math
    return math.log2(float(x)) if x > 0 else float("-inf")

dump = parse_dump("h714_dump.txt")
rows = []
for line in open("h714_hw3.txt"):
    left, h3, m3 = line.strip().split(" | ")
    se, sig, corp, lineno = left.split()
    hw = [x.split("/") for x in h3.split()]
    mo = [x.split("/") for x in m3.split()]
    rows.append((se, sig, corp, hw, mo))

print("%-18s %-6s %3s %-7s %-4s %5s | %-16s | %-16s | %s"
      % ("sig", "corp", "th", "branch", "fire", "modes",
         "delta in RU", "delta in UL", "note"))
for se, sig, corp, hw, mo in rows:
    d = dump[(se, sig)]
    poly = d.get("poly", {}); r59 = d.get("r59", {})
    corr = d.get("corr", {}); br = d.get("br", {})
    branch = br.get("br", corr.get("via", "?"))
    i0 = poly.get("i0")
    cw = corr.get("out") or br.get("out")
    c_val = wv_val(cw)
    v_pre = 1 + c_val
    v_signed = -v_pre if i0 else v_pre
    iv = None
    for mi, m in enumerate(("rn", "rd", "ru")):
        pi = preimage(hw[mi][0], hw[mi][1], m)
        iv = pi if iv is None else intersect(iv, pi)
    lo, hi, lc, hc = iv
    d_lo = lo - v_signed; d_hi = hi - v_signed
    if i0: d_lo, d_hi = -d_hi, -d_lo
    modes = "".join("X" if mo[mi] != hw[mi] else "="
                    for mi in range(3))
    rscale = r59.get("rscale"); k = r59.get("k")
    note = ""
    if rscale is not None:
        RU = Fraction(2)**(rscale + k)
        UL = Fraction(2)**rscale
        ru_lo, ru_hi = d_lo/RU, d_hi/RU
        ul_lo, ul_hi = d_lo/UL, d_hi/UL
        ru_s = "%+.4f..%+.4f" % (float(ru_lo), float(ru_hi))
        ul_s = "%+.3f..%+.3f" % (float(ul_lo), float(ul_hi))
        if d_lo == d_hi:
            note = "POINT delta=%s = 2^%.3f = %+.6f RU (exact %s/%s)" % (
                ("%+.3g" % float(d_lo)), log2f(abs(d_lo)),
                float(d_lo/RU), d_lo.numerator, d_lo.denominator)
        elif ru_lo <= -1 <= ru_hi or ru_lo <= 1 <= ru_hi:
            note = "1.0RU inside (fire-flip compatible)"
        else:
            note = "fire-flip EXCLUDED"
    else:
        ru_s = ul_s = "no r59"
    th = r59.get("theta")
    fire = br.get("fire")
    print("%-18s %-6s %3s %-7s %-4s %5s | %-16s | %-16s | %s"
          % (sig, corp, th, branch, fire, modes, ru_s, ul_s, note))
