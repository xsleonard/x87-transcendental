#!/usr/bin/env python3
# h715d: (a) j-sweep for rows not explained by +-1 RU; (b) the
# per-gate misfire ledger with every gate input, for law mining.
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

def modes_pat(v_signed, hw):
    return "".join(
        "=" if F.round80(v_signed, m).split() == hw[mi] else "X"
        for mi, m in enumerate(("rn", "rd", "ru")))

print("== j-sweep (v + j*RU, all modes) for every row ==")
for se, sig, corp, hw in rows:
    d = dump[(se, sig)]
    r59 = d.get("r59", {}); poly = d.get("poly", {})
    corr = d.get("corr", {}); br = d.get("br", {})
    cw = corr.get("out") or br.get("out")
    v_pre = 1 + F.wv_val(cw)
    i0 = poly.get("i0")
    RU = Fraction(2)**(r59["rscale"] + r59["k"])
    hits = []
    for j in range(-4, 5):
        vp = v_pre + j * RU
        vs = -vp if i0 else vp
        if modes_pat(vs, hw) == "===":
            hits.append(j)
    print("  %-18s %-6s th=%-2s j-hits=%s" % (sig, corp,
          r59.get("theta"), hits))
print()
print("== GATE LEDGER ==")
hdr = ("sig", "corp", "th", "s4", "sd", "l3", "b1", "b2", "d",
       "rsh", "ce", "gate", "model", "chip", "extra")
print("%-18s %-6s %3s %2s %2s %2s %2s %2s %2s %3s %3s %-7s %-6s %-6s %s" % hdr)
for se, sig, corp, hw in rows:
    d = dump[(se, sig)]
    r59 = d.get("r59", {}); poly = d.get("poly", {})
    corr = d.get("corr", {}); br = d.get("br", {})
    crit = d.get("crit", {}); bs = d.get("bs", {})
    cw = corr.get("out") or br.get("out")
    v_pre = 1 + F.wv_val(cw)
    i0 = poly.get("i0")
    RU = Fraction(2)**(r59["rscale"] + r59["k"])
    chip = "?"
    for j in (-1, 1):
        vp = v_pre + j * RU
        vs = -vp if i0 else vp
        if modes_pat(vs, hw) == "===":
            chip = "corr%+d" % (-j)   # corr magnitude moves opposite v
    branch = br.get("br", corr.get("via", "?"))
    th = r59.get("theta"); sgn_dn = th > 0 if th is not None else None
    if branch == "tie":
        model = "tfire=%s" % br.get("tfire")
        extra = "base0=%s u0=%s Mreg_top=%x" % (
            br.get("base0"), br.get("u0"),
            (r59.get("Mreg", 0) >> 64) & 0xffffffffffffffff)
    elif branch == "band":
        model = "fire=%s" % br.get("fire")
        extra = "in_r=%s crit=%s pm=%s phw=%s bs=%s uu=%s tt=%s base=%s c=%s" % (
            br.get("in_region"), crit.get("crit"), crit.get("pm"),
            crit.get("phw"), bs, br.get("uu"), br.get("tt"),
            br.get("base"), br.get("c"))
    elif branch == "corner":
        model = "fire=%s" % br.get("fire")
        extra = "dd=%s crit=%s pm=%s phw=%s bs=%s" % (
            br.get("dd"), crit.get("crit"), crit.get("pm"),
            crit.get("phw"), bs)
    else:
        model = "nofire"
        extra = "(never-fire clause)"
    print("%-18s %-6s %3s %2s %2s %2s %2s %2s %2s %3s %3s %-7s %-6s %-6s %s"
          % (sig, corp, th, r59.get("s4"), r59.get("side"),
             r59.get("low3"), r59.get("b1"), r59.get("b2"),
             r59.get("dist"), r59.get("rsh"), r59.get("ce"),
             branch, model, chip, extra))
