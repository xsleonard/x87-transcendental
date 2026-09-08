#!/usr/bin/env python3
# h730: score the reduced-argument perturbation sweep.  Per randv1
# miss operand: which red:d reproduces hardware in ALL THREE modes
# of the missing instruction.
import re
miss = {}
for l in open("h728.log"):
    m = re.match(r"MISMATCH (\w+) (\w+) line (\d+)", l)
    if m: miss.setdefault(int(m.group(3)), set()).add(m.group(1))
inp = open("randv1_inputs.txt").read().splitlines()
lns = sorted(miss)
ops = [inp[ln] for ln in lns]
opidx = {op: i for i, op in enumerate(open("h729_ops.txt").read().split("\n"))
         if op}
def norm(l):
    t = l.split()
    return "C2" if t[0] == "C2" else "%s/%s" % (t[1], t[2])
hw = {}
for insn in ("cos","sin"):
    for mode in ("rn","rd","ru"):
        lines = open(f"randv1_{insn}_{mode}_hw.txt")
        vals = {}
        for i, l in enumerate(lines):
            if i in miss: vals[i] = norm(l)
        hw[(insn,mode)] = vals
rp = {}
for insn in ("cos","sin"):
    for d in (-2,-1,1,2):
        for mode in ("rn","rd","ru"):
            rp[(insn,d,mode)] = [norm(l) for l in open(f"rp_{insn}_{d}_{mode}.txt")]
print("%-8s %-22s %-6s | fits (red:d reproducing all 3 modes)"
      % ("line","operand","insns"))
for ln in lns:
    op = inp[ln]
    oi = opidx[op]
    for insn in sorted(miss[ln]):
        fits = []
        for d in (-2,-1,1,2):
            ok = all(rp[(insn,d,m)][oi] == hw[(insn,m)][ln]
                     for m in ("rn","rd","ru"))
            if ok: fits.append(d)
        print("%-8d %-22s %-6s | %s" % (ln, op, insn,
              fits if fits else "NONE"))
