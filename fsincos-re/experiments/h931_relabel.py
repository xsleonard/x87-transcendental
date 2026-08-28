#!/usr/bin/env python3
# h931 step 1: relabel the completed act_tail.tsv census against the
# CURRENT model (R92).  Output h931_labels.tsv: one row per
# (seed, insn, mode, op) with cls C (hw differs from model) or
# AGREE.  Runs unattended after the h929 chain completes.
import subprocess, sys
from collections import defaultdict

MODEL = "./model_r92"
legs = defaultdict(dict)          # (insn,mode) -> {op: (seed, hw_se, hw_sig)}
n = 0
for ln in open("act_tail.tsv"):
    t = ln.rstrip("\n").split("\t")
    if len(t) != 9:
        continue
    n += 1
    tag, seed, insn, mode, row, op, hw = t[0], t[1], t[2], t[3], t[4], t[5], t[6]
    h = hw.split()
    if len(h) != 3 or h[0] != "OK":
        continue
    d = legs[(insn, mode)]
    if op not in d:
        d[op] = (int(seed), h[1], h[2])
print("act_tail rows:", n, " legs:", len(legs),
      " ops:", sum(len(v) for v in legs.values()), file=sys.stderr)

out = open("h931_labels.tsv", "w")
bad = 0
for (insn, mode), d in sorted(legs.items()):
    ops = list(d.keys())
    fl = "--fsin-standalone" if insn == "sin" else "--fcos-standalone"
    args = [MODEL, "--batch", fl]
    if mode != "rn":
        args.append("--rc=" + mode)
    p = subprocess.Popen(args, stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, text=True)
    inp = "".join(op + "\n" for op in ops)
    so, _ = p.communicate(inp)
    lines = so.splitlines()
    assert len(lines) == len(ops), (insn, mode, len(lines), len(ops))
    nc = 0
    for op, mo in zip(ops, lines):
        seed, hse, hsig = d[op]
        m = mo.split()
        mse, msig = (m[1], m[2]) if m and m[0] == "OK" else ("--", "--")
        if (mse, msig) == (hse, hsig):
            cls = "AGREE"
        else:
            cls = "C"
            nc += 1
            if mse == hse:
                if abs(int(msig, 16) - int(hsig, 16)) != 1:
                    bad += 1
        out.write("\t".join((str(seed), insn, mode, op, hse, hsig,
                             mse, msig, cls)) + "\n")
    print("leg %s %s: %d ops, %d C" % (insn, mode, len(ops), nc),
          file=sys.stderr)
out.close()
print("non-ulp1 anomalies:", bad, file=sys.stderr)
