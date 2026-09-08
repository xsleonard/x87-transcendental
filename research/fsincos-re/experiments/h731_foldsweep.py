#!/usr/bin/env python3
# h731: sweep --rcfold=B:mode over the 21 randv1 miss operands.
# For each config: how many rows now match hardware in ALL 3 modes
# of their missing instruction (and none of the other rows' correct
# outputs change vs hardware — every row must match, period).
import subprocess, re
miss = {}
for l in open("h728.log"):
    m = re.match(r"MISMATCH (\w+) (\w+) line (\d+)", l)
    if m: miss.setdefault(int(m.group(3)), set()).add(m.group(1))
inp = open("randv1_inputs.txt") if False else None
inp = open("/root/h491/randv1_inputs.txt").read().splitlines()
lns = sorted(miss)
ops = [inp[ln] for ln in lns]
open("h731_ops.txt","w").write("\n".join(ops) + "\n")
def norm(l):
    t = l.split()
    return "C2" if t[0] == "C2" else "%s/%s" % (t[1], t[2])
hw = {}
for insn in ("cos","sin"):
    for mode in ("rn","rd","ru"):
        lines = open(f"/root/h491/randv1_{insn}_{mode}_hw_status.txt")
        vals = {}
        for i, l in enumerate(lines):
            if i in miss: vals[i] = norm(l)
        hw[(insn,mode)] = vals
CONFIGS = [(b, m) for b in (65,66,67,68,69,70,71,72,74,76,80)
           for m in ("jam","rn","chop")]
print("config    | rows fully matching hw (both insns, all modes) /21")
best = []
for b, md in CONFIGS:
    per_row_ok = []
    outs = {}
    for insn in ("cos","sin"):
        flag = "--fcos-standalone" if insn=="cos" else "--fsin-standalone"
        for mode in ("rn","rd","ru"):
            args = ["./model_di","--batch",flag,f"--rcfold={b}:{md}"]
            if mode != "rn": args.append(f"--rc={mode}")
            p = subprocess.run(args, input="\n".join(ops)+"\n",
                               capture_output=True, text=True)
            outs[(insn,mode)] = [norm(l) for l in p.stdout.splitlines()]
    nfix = 0
    fixed_rows = []
    for oi, ln in enumerate(lns):
        ok = all(outs[(insn,mode)][oi] == hw[(insn,mode)][ln]
                 for insn in ("cos","sin") for mode in ("rn","rd","ru"))
        if ok: nfix += 1; fixed_rows.append(str(ln))
    best.append((nfix, b, md, fixed_rows))
    print("B=%-3d %-4s | %d/21" % (b, md, nfix))
best.sort(key=lambda x: -x[0])
print()
print("BEST:", best[0][:3], "rows:", ",".join(best[0][3]))
