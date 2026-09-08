#!/usr/bin/env python3
# h946: the TRUE act_tail census decomposition (run on i7 /root/r84).
# Requires h931_labels.tsv produced by the FIXED h931_relabel.py
# (act_tail t[8] = hardware; the pre-h946 phantom read t[6] = payB).
# Builds referenced:
#   model_h946_pg0      = HEAD source, -DG_PAYGATE=0   (R89+R90 off)
#   model_h946_h912src  = fsincos_skylake_h912.c default (pre-R89)
#   model_h946_r92payoff= HEAD source, -DG_PAYOFF=1    (payload off)
# Output: per-leg direction x which-build-fixes cross-tab.
#   d+1 payoff-fixes  = L_D gate false-fires (hw declines payload)
#   d-1 pg0+h912-fixes= R89/R90 suppression collateral (deep zone)
#   d-1 none          = the deep residual (unexplained by any build)
import subprocess
from collections import Counter, defaultdict

legs = defaultdict(list)
for ln in open("h931_labels.tsv"):
    t = ln.rstrip("\n").split("\t")
    if len(t) != 9 or t[8] != "C":
        continue
    legs[(t[1], t[2])].append(
        (t[3], t[4].lower(), t[5].lower(), t[6].lower(), t[7].lower()))

def runm(model, insn, mode, ops):
    fl = "--fsin-standalone" if insn == "sin" else "--fcos-standalone"
    args = [model, "--batch", fl]
    if mode != "rn":
        args.insert(2, "--rc=" + mode)
    p = subprocess.run(args, input="\n".join(ops) + "\n",
                       capture_output=True, text=True)
    return [tuple(l.split()[1:3]) for l in p.stdout.splitlines()]

res = Counter()
for (insn, mode), rows in sorted(legs.items()):
    ops = [r[0] for r in rows]
    outs = {}
    for nm, mdl in (("pg0", "./model_h946_pg0"),
                    ("h912", "./model_h946_h912src"),
                    ("payoff", "./model_h946_r92payoff")):
        outs[nm] = runm(mdl, insn, mode, ops)
    for i, (op, hs, hg, ms, mg) in enumerate(rows):
        hw = (hs, hg)
        d = "d%+d" % (int(hg, 16) - int(mg, 16)) if hs == ms else "dBIG"
        key = tuple(nm for nm in ("pg0", "h912", "payoff")
                    if outs[nm][i] == hw)
        res[(d, key)] += 1
for k in sorted(res):
    print(k, res[k])
