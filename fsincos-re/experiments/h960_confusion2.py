#!/usr/bin/env python3
# h960a: the GROWN-corpus gate confusion (6.79M legs, 1.42x h948),
# now with the shipped R93 alongside R92.  Per labeled leg:
# visible iff pg0 != payoff; hw/r92/r93 each classified to a side.
# Outputs h960_gate_corpus.tsv (visible legs) + summary; band
# population = invisible legs where hw != r93.
import subprocess, sys
from collections import Counter, defaultdict

legs = defaultdict(list)
for ln in open("h931_labels.tsv"):
    t = ln.rstrip("\n").split("\t")
    if len(t) != 9: continue
    legs[(t[1], t[2])].append((t[3], t[4].lower(), t[5].lower()))

def runm(model, insn, mode, ops):
    fl = "--fsin-standalone" if insn == "sin" else "--fcos-standalone"
    args = [model, "--batch", fl]
    if mode != "rn": args.insert(2, "--rc=" + mode)
    p = subprocess.run(args, input="\n".join(ops) + "\n",
                       capture_output=True, text=True)
    o = [tuple(x.lower() for x in l.split()[1:3])
         for l in p.stdout.splitlines()]
    assert len(o) == len(ops), (model, insn, mode, len(o), len(ops))
    return o

res = Counter()
corpus = open("h960_gate_corpus.tsv", "w")
corpus.write("insn\tmode\top\thwlab\tr92lab\tr93lab\n")
band = open("h960_band_legs.tsv", "w")
band.write("insn\tmode\top\thw\tr93\n")
for (insn, mode), rows in sorted(legs.items()):
    ops = [r[0] for r in rows]
    F = runm("./model_h946_pg0", insn, mode, ops)
    D = runm("./model_h946_r92payoff", insn, mode, ops)
    R2 = runm("./model_r92", insn, mode, ops)
    R3 = runm("./model_r93", insn, mode, ops)
    for (op, hs, hg), f_, d_, r2, r3 in zip(rows, F, D, R2, R3):
        hw = (hs, hg)
        if f_ == d_:
            c92 = "C" if hw != r2 else "A"
            c93 = "C" if hw != r3 else "A"
            res[("invis", c92 + c93)] += 1
            if c93 == "C":
                band.write("\t".join((insn, mode, op, hs + ":" + hg,
                                      r3[0] + ":" + r3[1])) + "\n")
            continue
        def side(v):
            return "F" if v == f_ else ("D" if v == d_ else "O")
        hwl, l92, l93 = side(hw), side(r2), side(r3)
        res[("vis", hwl, l92, l93)] += 1
        corpus.write("\t".join((insn, mode, op, hwl, l92, l93)) + "\n")
    print(insn, mode, "done", file=sys.stderr)
corpus.close(); band.close()
for k in sorted(res, key=str): print(k, res[k])
