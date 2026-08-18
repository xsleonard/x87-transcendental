#!/usr/bin/env python3
# h715c (T2 verdict): the exact fire-flip test.  For each census row
# compute v' = v_model +- 1 retained unit (2^(rscale+k)) and check
# EXACTLY (Fraction math + x87 grid replica) whether v' reproduces
# the hardware output in ALL THREE modes.  A pass proves the row is
# output-equivalent to a single fire flip at the r59 gate.
import sys
from fractions import Fraction
import h715_forensics as F

dump = F.parse_dump("h714_dump.txt")
rows = []
for line in open("h714_hw3.txt"):
    left, h3, m3 = line.strip().split(" | ")
    se, sig, corp, lineno = left.split()
    hw = [x.split("/") for x in h3.split()]
    rows.append((se, sig, corp, hw))

def modes_match(v_signed, hw):
    pat = []
    for mi, m in enumerate(("rn", "rd", "ru")):
        rep = F.round80(v_signed, m).split()
        pat.append("=" if rep == hw[mi] else "X")
    return "".join(pat)

print("%-18s %-6s %3s %-7s %-4s | %-4s %-4s | verdict" %
      ("sig", "corp", "th", "branch", "fire", "-1RU", "+1RU"))
tally = {}
for se, sig, corp, hw in rows:
    d = dump[(se, sig)]
    poly = d.get("poly", {}); r59 = d.get("r59", {})
    corr = d.get("corr", {}); br = d.get("br", {})
    branch = br.get("br", corr.get("via", "?"))
    i0 = poly.get("i0")
    cw = corr.get("out") or br.get("out")
    v_pre = 1 + F.wv_val(cw)
    rscale = r59.get("rscale"); k = r59.get("k")
    if rscale is None:
        print("%-18s %-6s no r59 frame" % (sig, corp)); continue
    RU = Fraction(2)**(rscale + k)
    res = {}
    for j in (-1, +1):
        vp = v_pre + j * RU
        vs = -vp if i0 else vp
        res[j] = modes_match(vs, hw)
    th = r59.get("theta"); fire = br.get("fire")
    v_dn = "PASS" if res[-1] == "===" else res[-1]
    v_up = "PASS" if res[+1] == "===" else res[+1]
    if v_dn == "PASS" and v_up == "PASS": verdict = "BOTH?!"
    elif v_dn == "PASS":
        verdict = "FIRE one unit DOWN (chip corr LARGER)"
    elif v_up == "PASS":
        verdict = "FIRE one unit UP (chip corr smaller)"
    else: verdict = "NOT A +-1RU FLIP"
    key = (branch, verdict.split("(")[0].strip())
    tally[key] = tally.get(key, 0) + 1
    print("%-18s %-6s %3s %-7s %-4s | %-4s %-4s | %s"
          % (sig, corp, th, branch, fire, v_dn, v_up, verdict))
print()
print("TALLY by (branch, verdict):")
for k in sorted(tally):
    print("  %-28s %d" % (str(k), tally[k]))
