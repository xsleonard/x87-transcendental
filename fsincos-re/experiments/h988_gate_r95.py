#!/usr/bin/env python3
# h988: THE R95 VALUE GATE (run on i7 /root/r84).  The h966
# protocol applied to the R95 exact-support arm: for EVERY op the
# arm touches anywhere in the 5.09M-op scope corpus (carved arm
# r95_scope_v2.tsv UNION carve-free arm r95_scope_nolc.tsv),
# fresh-capture hardware on all 4 modes and score model_r93_ref3
# (incumbent), model_r95 (candidate, carves in), model_r95_nolc
# (carve-free) on every leg.  Outputs:
#   h988_legs.tsv   banked per-leg truth (insn op mode hw m93 m95 mnolc)
#   scorecards      per-variant fix/break/unfixed vs incumbent
#   carve analysis  legs where carve changes the outcome (m95 != mnolc)
import subprocess, sys
from collections import Counter

def load(fn):
    rows = []
    for l in open(fn):
        t = l.rstrip("\n").split("\t")
        if len(t) == 5:
            rows.append((t[0], t[1], t[2]))
    return rows

touched = set()
for fn in ("r95_scope_v2.tsv", "r95_scope_nolc.tsv"):
    for insn, mode, op in load(fn):
        touched.add((insn, op))
byinsn = {}
for insn, op in sorted(touched):
    byinsn.setdefault(insn, []).append(op)
print("touched ops:", {k: len(v) for k, v in byinsn.items()},
      file=sys.stderr)

def runm(model, insn, mode, ops):
    fl = "--fsin-standalone" if insn == "sin" else "--fcos-standalone"
    args = [model, "--batch", fl]
    if mode != "rn":
        args.insert(2, "--rc=" + mode)
    p = subprocess.run(args, input="\n".join(ops) + "\n",
                       capture_output=True, text=True)
    out = [tuple(l.split()[1:3]) for l in p.stdout.splitlines()]
    assert len(out) == len(ops), (model, insn, mode, len(out), len(ops))
    return out

def runhw(insn, mode, ops):
    p = subprocess.run(["/root/x87_capture_x86_64", mode, insn],
                       input="\n".join(ops) + "\n",
                       capture_output=True, text=True)
    rows = []
    for l in p.stdout.splitlines():
        t = l.split()
        rows.append(tuple(t[1:3]) if t and t[0] == "OK"
                    else ("WEIRD", l))
    assert len(rows) == len(ops), (insn, mode, len(rows), len(ops))
    return rows

res95 = Counter()
resnol = Counter()
carve = Counter()
legs = open("h988_legs.tsv", "w")
print("insn\top\tmode\thw\tm93\tm95\tmnolc", file=legs)
bad95 = []
badnol = []
carverows = []
for insn, ops in sorted(byinsn.items()):
    for mode in ("rn", "rd", "ru", "rz"):
        hw = runhw(insn, mode, ops)
        m93 = runm("./model_r93_ref3", insn, mode, ops)
        m95 = runm("./model_r95", insn, mode, ops)
        mnol = runm("./model_r95_nolc", insn, mode, ops)
        for op, h, a, b, c in zip(ops, hw, m93, m95, mnol):
            h = tuple(x.lower() for x in h)
            a = tuple(x.lower() for x in a)
            b = tuple(x.lower() for x in b)
            c = tuple(x.lower() for x in c)
            print("%s\t%s\t%s\t%s\t%s\t%s\t%s" % (
                insn, op, mode, ":".join(h), ":".join(a),
                ":".join(b), ":".join(c)), file=legs)
            if h[0] == "weird":
                res95["WEIRD"] += 1
                continue
            res95[("93" + ("=" if a == h else "!"),
                   "95" + ("=" if b == h else "!"))] += 1
            resnol[("93" + ("=" if a == h else "!"),
                    "nol" + ("=" if c == h else "!"))] += 1
            if a == h and b != h:
                bad95.append((insn, mode, op, h, a, b))
            if a == h and c != h:
                badnol.append((insn, mode, op, h, a, c))
            if b != c:
                # the carve decided this leg: fitted (b==a side) vs
                # suppressed (c).  Who is right?
                who = ("FITTED_RIGHT" if b == h else
                       "SUPPR_RIGHT" if c == h else "BOTH_WRONG")
                carve[who] += 1
                carverows.append((who, insn, mode, op, h, b, c))
legs.close()
print("=== model_r95 (carves in) vs incumbent ===")
for k in sorted(res95):
    print(k, res95[k])
print("=== model_r95_nolc (carve-free) vs incumbent ===")
for k in sorted(resnol):
    print(k, resnol[k])
print("=== carve-decided legs (m95 != mnolc) ===")
for k in sorted(carve):
    print(k, carve[k])
print("=== BREAKS m95 (93= 95!) ===")
for r in bad95[:100]:
    print(*r)
print("=== BREAKS nolc (93= nol!) ===")
for r in badnol[:100]:
    print(*r)
print("=== carve rows ===")
for r in carverows[:200]:
    print(*r)
b95 = len(bad95)
f95 = res95.get(("93!", "95="), 0)
u95 = res95.get(("93!", "95!"), 0)
print("SCORE m95: fixes=%d breaks=%d unfixed=%d" % (f95, b95, u95))
bnl = len(badnol)
fnl = resnol.get(("93!", "nol="), 0)
unl = resnol.get(("93!", "nol!"), 0)
print("SCORE nolc: fixes=%d breaks=%d unfixed=%d" % (fnl, bnl, unl))
