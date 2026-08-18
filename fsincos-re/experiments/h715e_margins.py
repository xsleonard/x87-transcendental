#!/usr/bin/env python3
# h715e: the mechanism table.  Correct hex parse of the 128-bit DI
# fields (h715's generic parse mis-reads all-decimal-digit hex), then
# per row: the gate margin in 2^66 units (Mreg vs the u-floor/tie
# threshold), offline pm/phw/bsrel/bit8/bitbs (h662k block-start
# frame), and for the (67,1)-dn-th2 never-fire family the margin
# under EXTRAPOLATED tap vectors.  Goal: a discriminant separating
# the 29 chip-fire rows from clean neighbors.
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
                    if x >= 1 << 127: x -= 1 << 128   # two's complement
                    d[k] = x
                elif ":" in v or "," in v: d[k] = v
                elif v.lstrip("-").isdigit(): d[k] = int(v)
                else: d[k] = v
    return ops

def wv(s):
    sg, e2, hx = s.split(":")
    return (int(sg), int(e2), int(hx, 16))

dump = parse_dump("h714_dump.txt")
rows = []
for line in open("h714_hw3.txt"):
    left, h3, m3 = line.strip().split(" | ")
    se, sig, corp, lineno = left.split()
    rows.append((se, sig, corp))

# u-floor quadrant params (verbatim from r59_apply)
def qparams(s4, side, dist):
    if s4 == 66 and side == 1:
        return (2,2,1,0,4,1,0, -5*(dist-7))
    if s4 == 66 and side == 0:
        return (4,1,0,0,2,1,0, -9-5*(dist-9))
    if s4 == 67 and side == 0:
        return (4,2,1,-2,4,2,1, -5*(dist-7))
    return (2,2,3,-3,8,2,1, -4-2*(dist-7))

def floordiv(a, b):
    return a // b

# tap vectors (verbatim); key (sign_dn, th, qclass)
VEC = {
 (1,1,"sh"): (8,1,-1,1,-3), (1,1,"66lo"): (1,1,-1,1,0),
 (1,1,"67hi"): (2,1,0,0,4),
 (1,2,"sh"): (18,0,0,0,-6), (1,2,"66lo"): (12,0,0,0,-3),
 (0,1,"sh"): (6,-1,0,1,-1), (0,1,"66lo"): (7,-1,1,1,-2),
 (0,1,"67hi"): (6,1,0,-2,0),
 (0,2,"sh"): (6,0,0,1,0), (0,2,"66lo"): (8,1,0,1,-2),
 (0,2,"67hi"): (12,0,0,0,0),
}
def qclass(s4, side):
    if s4 == 66 and side == 0: return "66lo"
    if s4 == 67 and side == 1: return "67hi"
    return "sh"

print("%-18s %-6s %3s %-7s %-7s | %8s | %2s %2s %3s %2s %2s | %s" %
      ("sig","corp","th","gate","chipfix","margin","pm","ph","bsr","b8","bb","note"))
for se, sig, corp in rows:
    d = dump[(se, sig)]
    r59 = d.get("DI_R59", {})
    br = d.get("DI_BR", {})
    corr = d.get("DI_CORR", {})
    branch = br.get("br", corr.get("via","?"))
    th = r59["theta"]; k = r59["k"]; ce = r59["ce"]
    s4 = r59["s4"]; side = r59["side"]; low3 = r59["low3"]
    b1 = r59["b1"]; b2 = r59["b2"]; dist = r59["dist"]
    umag = r59["umag"]; S = r59["S"]; B = r59["B"]; Mreg = r59["Mreg"]
    sign_dn = 1 if th > 0 else 0
    # offline block-start frame
    pmask = ~(S ^ B) & ((1 << 128) - 1)
    pm = 0; j = k
    while pm < 32 and (pmask >> j) & 1:
        pm += 1; j += 1
    phw = ((ce % 8) + 8) % 8
    bsrel = 8 + ((8 - phw) % 8)
    bit8 = (umag >> (k + 8)) & 1
    bitbs = (umag >> (k + bsrel)) & 1
    crit = 1 if ((pm + phw) % 8 == 7 and pm in (7,8)) else 0
    qa,qg1,qg2,qp,qq,qk,qpar,wd = qparams(s4, side, dist)
    lp = low3 & 1
    base = qa*low3 + qg1*b1 + qg2*b2 + qp*lp + wd
    note = ""
    if branch == "tie":
        u0 = qk*floordiv(base, qq) + qpar*lp
        margin = Fraction(Mreg - (u0 << 66), 1 << 66)
        gatef = "tf=%s" % br.get("tfire")
    elif branch in ("band","q67th2"):
        vec = VEC.get((sign_dn, abs(th), qclass(s4, side)))
        if vec is None:
            note = "NO VECTOR (never-fire quad)"
            # extrapolate from the two sibling quadrant vectors
            cands = []
            for qc in ("sh","66lo"):
                c0,cb1,cb2,clp,cd = VEC[(sign_dn, abs(th), qc)]
                tt = c0 + cb1*b1 + cb2*b2 + clp*lp + cd*(dist-7)
                uu = qk*floordiv(base - tt, qq) + qpar*lp
                mg = Fraction(Mreg - (uu << 66), 1 << 66)
                cands.append("%s:%+.2f" % (qc, float(mg)))
            note += " extrap " + " ".join(cands)
            margin = None
        else:
            c0,cb1,cb2,clp,cd = vec
            tt = c0 + cb1*b1 + cb2*b2 + clp*lp + cd*(dist-7)
            if sign_dn:
                uu = qk*floordiv(base - tt, qq) + qpar*lp
            else:
                uu = qk*floordiv(base + tt, qq) + qpar*lp
            margin = Fraction(Mreg - (uu << 66), 1 << 66)
        gatef = "fire=%s" % br.get("fire")
    else:
        margin = None
        gatef = "dd=%s" % br.get("dd")
        note = "corner D-ladder"
    chip = "corr%+d" % (1 if "corr+1" in "x" else 0)  # placeholder
    # chip fix direction from h715c logic: recompute quickly
    import h715_forensics as F
    cw = corr.get("out") or br.get("out")
    v_pre = 1 + F.wv_val(wv(cw) if isinstance(cw, str) else wv(cw))
    i0 = d.get("DI_POLY", {}).get("i0", 0)
    RU = Fraction(2)**(r59["rscale"] + k)
    hwline = [l for l in open("h714_hw3.txt") if l.startswith("%s %s " % (se, sig))][0]
    hw = [x.split("/") for x in hwline.strip().split(" | ")[1].split()]
    chip = "?"
    for jj in (-1, 1):
        vp = v_pre + jj * RU
        vs = -vp if i0 else vp
        pat = "".join("=" if F.round80(vs, m).split() == hw[mi] else "X"
                      for mi, m in enumerate(("rn","rd","ru")))
        if pat == "===": chip = "corr%+d" % (-jj)
    ms = ("%+8.3f" % float(margin)) if margin is not None else "    n/a "
    print("%-18s %-6s %3d %-7s %-7s | %s | %2d %2d %3d %2d %2d | %s"
          % (sig, corp, th, branch, chip, ms, pm, phw, bsrel,
             bit8, bitbs, note))
