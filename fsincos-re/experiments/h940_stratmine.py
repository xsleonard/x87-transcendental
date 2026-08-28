#!/usr/bin/env python3
# h940: the FULL-STRATUM v2 wall — every act_tail hit leg, no sum
# filter.  Per leg: hw (banked) vs base(R92) vs v2(sticky-borrow).
import subprocess, sys
from collections import Counter

legs = {}
for ln in open("act_tail.tsv"):
    t = ln.rstrip("\n").split("\t")
    if len(t) != 9: continue
    legs.setdefault((t[2], t[3]), []).append((t[5], t[8], ln.rstrip("\n")))
def run(model, insn, mode, inps):
    fl = "--fsin-standalone" if insn == "sin" else "--fcos-standalone"
    args = [model, "--batch", fl]
    if mode != "rn": args.insert(2, "--rc=" + mode)
    p = subprocess.run(args, input="\n".join(inps) + "\n",
                       capture_output=True, text=True)
    return p.stdout.splitlines()
def norm(l):
    t = l.split()
    return ("C2",) if t and t[0] == "C2" else tuple(t[1:3])
cnt = Counter()
out = open("h940_species.tsv", "w")
for (insn, mode), rows in sorted(legs.items()):
    inps = [r[0] for r in rows]
    ba = run("./model_r92", insn, mode, inps)
    v2 = run("./model_h937_v2", insn, mode, inps)
    assert len(ba) == len(inps) and len(v2) == len(inps), (insn, mode, len(ba), len(v2))
    for (inp, hw, full), b, v in zip(rows, ba, v2):
        nh = norm(hw.replace("OK ", "OK\t", 1).replace("\t", " "))
        # hw field is "OK se sig" already; normalize directly
        th = hw.split(); nh = ("C2",) if th and th[0] == "C2" else tuple(th[1:3])
        nb, nv = norm(b), norm(v)
        fire = nb != nv
        agree = nh == nb
        if agree and fire:
            cls = "SPECIES(collateral)"
            out.write(full + "\n")
        elif agree:
            cls = "quiet-agree"
        elif nh == nv and fire:
            cls = "carry-FIXED-by-v2"
        elif fire:
            cls = "fire-but-wrong"
        else:
            cls = "miss-untouched"
        cnt[(insn, mode, cls)] += 1
    print(insn, mode, "done", file=sys.stderr)
out.close()
tot = Counter()
for k, v in sorted(cnt.items()):
    print("%-4s %-3s %-22s %d" % (k + (v,)))
    tot[k[2]] += v
print("=== totals ===")
for k, v in sorted(tot.items()):
    print("%-22s %d" % (k, v))
