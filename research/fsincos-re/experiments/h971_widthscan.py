#!/usr/bin/env python3
# h971: THE VALUE-LEVEL WIDTH SCAN.  The width law was refuted
# twice on exposure-confounded LEG labels; h968/h970 produced the
# first clean OP-level labels (single-direction sub-ulp epsilon:
# DOWN 1338 / ZERO 1793 / UP 598 / UNEXPOSED 4586).  Score every
# terminal-composition variant against the CAPTURED hw values of
# all 8,315 band-strata ops, all 4 modes, all-legs-exact per op:
#   t3_kNN  = chopped left at 67+NN bits (G_TAILS=3 G_LKEEP=NN)
#   t2      = full left product, right chopped   (G_TAILS=2)
#   t1      = full left + full right             (G_TAILS=1)
# each with the R88/R70 terminal adder ON and OFF (G_ROUND70=0).
# Baseline m93 (shipped composition) scored from banked columns.
import subprocess, sys
from collections import Counter, defaultdict

MODES = ("rn", "rd", "ru", "rz")
rows = []
for ln in open("h968_ops.tsv"):
    t = ln.rstrip("\n").split("\t")
    if t[0] == "insn":
        continue
    rows.append(t)

# label per op from h970 (DOWN/ZERO/UP/UNEXPOSED)
lab = {}
pay2 = {}
for ln in open("h970_features.tsv"):
    t = ln.rstrip("\n").split("\t")
    if t[0] == "insn":
        continue
    lab[(t[0], t[1])] = t[9]
    pay2[(t[0], t[1])] = t[34]

byinsn = defaultdict(list)
for t in rows:
    byinsn[t[0]].append(t)

def runm(model, insn, mode, ops):
    fl = "--fsin-standalone" if insn == "sin" else "--fcos-standalone"
    args = [model, "--batch", fl]
    if mode != "rn":
        args.insert(2, "--rc=" + mode)
    p = subprocess.run(args, input="\n".join(ops) + "\n",
                       capture_output=True, text=True)
    out = [l.split()[1] + ":" + l.split()[2] for l in
           p.stdout.splitlines()]
    assert len(out) == len(ops)
    return out

def score(getter, name):
    c = defaultdict(Counter)
    for insn, rws in byinsn.items():
        vals = getter(insn)
        for i, t in enumerate(rws):
            k = (t[0], t[1])
            l = lab.get(k, "?")
            ok = True
            for j in range(4):
                h = t[13 + 2 * j].lower()
                if h.startswith("weird"):
                    ok = None
                    break
                if vals[j][i].lower() != h:
                    ok = False
            if ok is None:
                continue
            c[l]["ok" if ok else "miss"] += 1
            c["ALL"]["ok" if ok else "miss"] += 1
            if pay2.get(k, "0") not in ("0", "-"):
                c["fired"]["ok" if ok else "miss"] += 1
    parts = []
    for l in ("DOWN", "ZERO", "UP", "UNEXPOSED", "fired", "ALL"):
        o, m = c[l]["ok"], c[l]["miss"]
        parts.append("%s %d/%d" % (l, o, o + m))
    print(name.ljust(10), " ".join(parts))
    return c

# baseline from banked m93 columns
def m93_getter(insn):
    rws = byinsn[insn]
    return [[t[12 + 2 * j] for t in rws] for j in range(4)]
score(m93_getter, "m93")

VARIANTS = []
for k in (8, 12, 16, 20, 24, 32, 44, 52, 60):
    VARIANTS.append(("t3_k%02d" % k,
                     ["-DG_TAILS=3", "-DG_LKEEP=%d" % k]))
VARIANTS.append(("t2", ["-DG_TAILS=2"]))
VARIANTS.append(("t1", ["-DG_TAILS=1"]))
allv = []
for nm, fl in VARIANTS:
    allv.append((nm, fl))
    allv.append((nm + "_na", fl + ["-DG_ROUND70=0"]))

for nm, flags in allv:
    b = subprocess.run(
        ["gcc", "-O2", "-ffp-contract=off", "-x", "c"] + flags
        + ["-o", "model_h971_" + nm,
           "/root/r59/fsincos_skylake.c.preR94", "-lm"],
        capture_output=True, text=True)
    if b.returncode != 0:
        print(nm, "BUILD FAIL", b.stderr[-200:])
        continue
    cache = {}
    def getter(insn, _nm=nm):
        if insn not in cache:
            ops = [t[1] for t in byinsn[insn]]
            cache[insn] = [runm("./model_h971_" + _nm, insn, md, ops)
                           for md in MODES]
        return cache[insn]
    score(getter, nm)
