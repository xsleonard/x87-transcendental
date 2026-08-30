#!/usr/bin/env python3
# h970a: dump-feature harvest for the value-law discriminant hunt.
# For every h968 census op, run model_r93_ref --dump-internals (RN;
# coordinates are mode-independent) and bank the full DI vector.
# The op-level label from h968 (exposure-conditioned epsilon sign)
# is the first clean label this hunt has ever had: DOWN (deficit/
# tie), ZERO (cleanexp), UP/MIXED (from OTHER's change pattern).
import re, subprocess, sys
from collections import Counter, defaultdict

MODES = ("rn", "rd", "ru", "rz")
rows = []
for ln in open("h968_ops.tsv"):
    t = ln.rstrip("\n").split("\t")
    if t[0] == "insn":
        continue
    rows.append(t)
print("ops:", len(rows), file=sys.stderr)

def dec1(v):
    se, sig = v.split(":")
    se, sig = int(se, 16), int(sig, 16)
    if sig == 0x8000000000000000:
        return "%04x:ffffffffffffffff" % (
            (se & 0x8000) | (((se & 0x7FFF) - 1) & 0x7FFF))
    return "%04x:%016x" % (se, sig - 1)

def inc1(v):
    se, sig = v.split(":")
    se, sig = int(se, 16), int(sig, 16)
    if sig == 0xFFFFFFFFFFFFFFFF:
        return "%04x:8000000000000000" % (
            (se & 0x8000) | (((se & 0x7FFF) + 1) & 0x7FFF))
    return "%04x:%016x" % (se, sig + 1)

# refine OTHER into UP / SNAPUP / MIXED via leg directions
def lab_of(t):
    cls = t[8]
    if cls in ("DEFICIT", "TIE"):
        return "DOWN"
    if cls == "CLEANEXP":
        return "ZERO"
    if cls == "CLEAN":
        return "UNEXPOSED"
    if cls == "WEIRD":
        return "WEIRD"
    dirs = set()
    for j in range(4):
        m = t[12 + 2 * j].lower()
        h = t[13 + 2 * j].lower()
        if h == m:
            continue
        if h == dec1(m):
            dirs.add("d")
        elif h == inc1(m):
            dirs.add("u")
        else:
            dirs.add("x")
    if dirs == {"u"}:
        return "UP"
    if dirs == {"d"}:
        return "DOWN"
    return "MIXED"

WVRE = re.compile(
    r"(mul|lf|rf|f4|mag|left|right)=(\d+):(-?\d+):([0-9a-f]{32})")

byinsn = defaultdict(list)
for t in rows:
    byinsn[t[0]].append(t)

out = open("h970_features.tsv", "w")
out.write("insn\top\tact\tsum8\td\tme2\tg\thalf\tcls\tlab\t"
          "low3\tdist\trsh\tpayload\tud\tu5d\trud\t"
          "mule2\tmulsig\tlfe2\tlfsig\trfe2\trfsig\tf4e2\tf4sig\t"
          "mage2\tmagsig\tlefte2\tleftsig\tleftsign\t"
          "righte2\trightsig\trightsign\trdisc\td60\t"
          "pay2\tlaneb\tlanediff\tlane2\tlane3\n")
n = 0
for insn, rws in sorted(byinsn.items()):
    ops = [t[1] for t in rws]
    fl = "--fsin-standalone" if insn == "sin" else "--fcos-standalone"
    p = subprocess.run(["./model_r93_ref", "--batch", fl,
                        "--dump-internals"],
                       input="\n".join(ops) + "\n",
                       capture_output=True, text=True)
    recs, cur = [], None
    for ln in p.stderr.splitlines():
        if ln.startswith("DI_IN"):
            if cur is not None:
                recs.append(cur)
            cur = {}
            continue
        if cur is None:
            continue
        if ln.startswith("DI_TC ") and "low3" not in cur:
            w = {}
            for tok in ln.split()[1:]:
                if "=" in tok:
                    k, v = tok.split("=", 1)
                    w[k] = v
            for k in ("active", "low3", "dist", "rsh", "payload",
                      "ud", "u5d", "rud"):
                cur[k] = w.get(k, "-1")
            for m in WVRE.finditer(ln):
                nm, sg, e2, sig = m.groups()
                cur[nm] = (sg, e2, sig)
            cur["rdisc"] = ln.split("rdisc=")[1][:16] \
                if "rdisc=" in ln else "-"
        elif ln.startswith("DI_ACC") and "d60" not in cur:
            cur["d60"] = ln.split("d60=")[1][:32]
        elif ln.startswith("DI_TC2") and "pay2" not in cur:
            w = {}
            for tok in ln.split()[1:]:
                if "=" in tok:
                    k, v = tok.split("=", 1)
                    w[k] = v
            for k in ("pay2", "laneb", "diff", "lane2", "lane3"):
                cur[k] = w.get(k, "-")
    if cur is not None:
        recs.append(cur)
    assert len(recs) == len(ops), (insn, len(recs), len(ops))
    for t, r in zip(rws, recs):
        def wv(nm):
            v = r.get(nm, ("-1", "0", "0"))
            return (v[1], v[2], v[0])
        me, ms, _ = wv("mul")
        lfe, lfs, _ = wv("lf")
        rfe, rfs, _ = wv("rf")
        f4e, f4s, _ = wv("f4")
        mge, mgs, _ = wv("mag")
        lee, les, lesg = wv("left")
        rie, ris, risg = wv("right")
        out.write("\t".join(map(str, (
            t[0], t[1], t[2], t[3], t[4], t[5], t[6], t[7], t[8],
            lab_of(t),
            r.get("low3", "-1"), r.get("dist", "-1"),
            r.get("rsh", "-1"), r.get("payload", "-1"),
            r.get("ud", "-1"), r.get("u5d", "-1"),
            r.get("rud", "-1"),
            me, ms, lfe, lfs, rfe, rfs, f4e, f4s, mge, mgs,
            lee, les, lesg, rie, ris, risg,
            r.get("rdisc", "-"), r.get("d60", "-"),
            r.get("pay2", "-"), r.get("laneb", "-"),
            r.get("diff", "-"), r.get("lane2", "-"),
            r.get("lane3", "-")))) + "\n")
        n += 1
    print("done", insn, n, file=sys.stderr)
out.close()
lc = Counter()
for ln in open("h970_features.tsv"):
    t = ln.split("\t")
    if t[0] != "insn":
        lc[t[9]] += 1
print("labels:", dict(lc))
