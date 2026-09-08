#!/usr/bin/env python3
# h952: THE DATAPATH-WIDTH LAW SWEEP.  h951 showed three regimes
# (hw = P-composition on fire legs, plain chop on decline legs,
# exact-LF on the band residual) — the signature of the left product
# carried at intermediate width 67+K, chopped, then composed.
# Build G_TAILS=3 (-DG_LKEEP=K, -DG_PAYOFF=1: no payload object) for
# K in the sweep and score EVERY labeled leg against hw:
#   - decisive legs (F != D): does the candidate land on hw's side?
#   - invisible-C legs: does it equal hw (band recovery)?
#   - invisible-AGREE legs: collateral (candidate != hw == F == D).
# Reference rows: the shipped R92 (L_D gate) errors 1,781 decisive
# legs; LF (K=inf) errors 621 fire-side + unknown decline-side.
import subprocess, sys
from collections import Counter, defaultdict

KS = [4, 6, 8, 10, 12, 16, 24, 40]
SRC = "/root/r59/fsincos_skylake.c"
for K in KS:
    p = subprocess.run(["gcc", "-O2", "-ffp-contract=off",
                        "-DG_TAILS=3", "-DG_LKEEP=%d" % K,
                        "-DG_PAYOFF=1", SRC, "-lm",
                        "-o", "model_h952_k%d" % K],
                       capture_output=True, text=True)
    if p.returncode != 0:
        print(p.stderr[-2000:]); sys.exit(1)
print("built", len(KS), "width models", file=sys.stderr)

legs = defaultdict(list)
for ln in open("h931_labels.tsv"):
    t = ln.rstrip("\n").split("\t")
    if len(t) != 9: continue
    legs[(t[1], t[2])].append((t[3], t[4].lower() + ":" + t[5].lower(),
                               t[8]))

def run(model, insn, mode, ops):
    fl = "--fsin-standalone" if insn == "sin" else "--fcos-standalone"
    args = [model, "--batch", fl]
    if mode != "rn": args.insert(2, "--rc=" + mode)
    p = subprocess.run(args, input="\n".join(ops) + "\n",
                       capture_output=True, text=True)
    o = [l.split() for l in p.stdout.splitlines()]
    assert len(o) == len(ops), (model, insn, mode, len(o), len(ops))
    return [w[1].lower() + ":" + w[2].lower() for w in o]

tally = defaultdict(Counter)
for (insn, mode), rows in sorted(legs.items()):
    ops = [r[0] for r in rows]
    F = run("./model_h946_pg0", insn, mode, ops)
    D = run("./model_h946_r92payoff", insn, mode, ops)
    hwside = []
    for (op, hw, cls), f_, d_ in zip(rows, F, D):
        if f_ == d_: hwside.append("invis")
        else: hwside.append("F" if hw == f_ else ("D" if hw == d_ else "O"))
    for K in KS:
        out = run("./model_h952_k%d" % K, insn, mode, ops)
        t = tally[K]
        for (op, hw, cls), f_, d_, hs, o_ in zip(rows, F, D, hwside, out):
            if hs == "invis":
                t[("invis", cls, "eq" if o_ == hw else "ne")] += 1
            else:
                cs = "F" if o_ == f_ else ("D" if o_ == d_ else "O")
                t[("dec", cls, hs, cs)] += 1
    print(insn, mode, "done", file=sys.stderr)

for K in KS:
    t = tally[K]
    gate_err = sum(v for (k0, cls, hs, *rest), v in
                   ((k, v) for k, v in t.items() if k[0] == "dec")
                   if rest and rest[0] != hs)
    dec_tot = sum(v for k, v in t.items() if k[0] == "dec")
    invc_eq = t[("invis", "C", "eq")]
    invc_ne = t[("invis", "C", "ne")]
    inva_ne = t[("invis", "AGREE", "ne")]
    print("K=%-3d decisive-side-errors=%d/%d  invisC hw-match=%d/%d  "
          "invisAGREE collateral=%d"
          % (K, gate_err, dec_tot, invc_eq, invc_eq + invc_ne, inva_ne))
    for k in sorted(t, key=str):
        if k[0] == "dec": print("   ", k, t[k])
