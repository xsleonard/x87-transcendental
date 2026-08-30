#!/usr/bin/env python3
# h969: score the exact-left-tail composition (G_TAILS=2 G_PAYOFF=1,
# built from the R93 source as model_lf93) against the h968 census's
# CAPTURED hardware values, leg for leg, on all 8,315 band-strata
# ops.  h968 showed the deficit is a two-sided sub-ulp value offset
# (DEFICIT = hw below model, OTHER mostly hw above / SNAP-on-grid,
# mixed within strata).  If LF == hw on (nearly) all legs of all
# classes, the band object IS the exact tail and the R94 arm should
# ship the LF value in a scoped window instead of a stratum table.
import subprocess, sys
from collections import Counter, defaultdict

MODES = ("rn", "rd", "ru", "rz")
rows = []
for ln in open("h968_ops.tsv"):
    t = ln.rstrip("\n").split("\t")
    if t[0] == "insn":
        hdr = t
        continue
    rows.append(t)
print("census ops:", len(rows))

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
    out = [tuple(l.split()[1:3]) for l in p.stdout.splitlines()]
    assert len(out) == len(ops)
    return out

# h968_ops.tsv columns: 0 insn, 1 op, 2-6 stratum, 7 half, 8 cls,
# 9 ongrid, 10 sign, 11 chg, then m_rn h_rn m_rd h_rd m_ru h_ru
# m_rz h_rz at 12..19 as "se:sig"
res = Counter()
oplevel = Counter()
strat = defaultdict(Counter)
mism = []
for insn, rws in sorted(byinsn.items()):
    ops = [t[1] for t in rws]
    lf = {}
    for mode in MODES:
        lf[mode] = runm("./model_lf93", insn, mode, ops)
        print("ran", insn, mode, file=sys.stderr)
    for i, t in enumerate(rws):
        cls = t[8]
        st = tuple(t[2:7])
        allok = True
        for j, mode in enumerate(MODES):
            h = t[13 + 2 * j].lower()
            l = (lf[mode][i][0] + ":" + lf[mode][i][1]).lower()
            m = t[12 + 2 * j].lower()
            if h.startswith("weird"):
                res[(cls, mode, "WEIRD")] += 1
                continue
            ok = l == h
            allok &= ok
            res[(cls, mode, "LF==hw" if ok else "LF!=hw")] += 1
            if not ok and len(mism) < 40:
                mism.append((insn, t[1], st, cls, mode, "hw", h,
                             "lf", l, "m93", m))
        oplevel[(cls, "all4" if allok else "some-miss")] += 1
        strat[st]["ok" if allok else "miss"] += 1

print("\n== per-leg (class, mode) ==")
for k in sorted(res):
    print(k, res[k])
print("\n== per-op ==")
for k in sorted(oplevel):
    print(k, oplevel[k])
nbad = sum(c["miss"] for c in strat.values())
print("\nops with any LF!=hw leg:", nbad, "/", len(rows))
print("\n== strata with misses (top 30) ==")
for st, c in sorted(strat.items(), key=lambda x: -x[1]["miss"])[:30]:
    if c["miss"]:
        print(st, dict(c))
print("\n== first mismatch rows ==")
for r in mism:
    print(r)
