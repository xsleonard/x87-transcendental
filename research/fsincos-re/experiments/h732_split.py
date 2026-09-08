#!/usr/bin/env python3
# h732: the split-shift test.  red:+-2 on rw is downstream-identical
# to a sum-preserving reduction split shift (r' = r +- ulp, c' = c
# -+ ulp).  For each of the 21 randv1 miss operands: does red:+2 or
# red:-2 reproduce hardware in ALL SIX insn-modes (both FCOS and
# FSIN x rn/rd/ru)?  Both-insn consistency is the split hypothesis'
# signature (one shared rw feeds both kernels).
import subprocess, re
def norm(l):
    t = l.split()
    return "C2" if t[0] == "C2" else "%s/%s" % (t[1], t[2])
miss = {}
for l in open("h728.log"):
    m = re.match(r"MISMATCH (\w+) (\w+) line (\d+)", l)
    if m: miss.setdefault(int(m.group(3)), set()).add(m.group(1))
inp = open("/root/h491/randv1_inputs.txt").read().splitlines()
lns = sorted(miss)
ops = [inp[ln] for ln in lns]
hw = {}
for insn in ("cos","sin"):
    for mode in ("rn","rd","ru"):
        vals = {}
        for i, l in enumerate(open(f"/root/h491/randv1_{insn}_{mode}_hw_status.txt")):
            if i in miss: vals[i] = norm(l)
        hw[(insn,mode)] = vals
out = {}
for d in (0, -2, 2, -4, 4):
    for insn in ("cos","sin"):
        flag = "--fcos-standalone" if insn=="cos" else "--fsin-standalone"
        for mode in ("rn","rd","ru"):
            args = ["./model_di","--batch",flag]
            if d: args.append(f"--perturb=red:{d}")
            if mode != "rn": args.append(f"--rc={mode}")
            p = subprocess.run(args, input="\n".join(ops)+"\n",
                               capture_output=True, text=True)
            out[(d,insn,mode)] = [norm(x) for x in p.stdout.splitlines()]
print("%-8s %-22s miss      | d=0 base | -2   +2   -4   +4  (== all 6 match)")
nfix = 0
for oi, ln in enumerate(lns):
    cells = []
    for d in (0, -2, 2, -4, 4):
        ok = all(out[(d,insn,mode)][oi] == hw[(insn,mode)][ln]
                 for insn in ("cos","sin") for mode in ("rn","rd","ru"))
        cells.append("FIX " if ok else "-   ")
    if "FIX " in cells[1:]: nfix += 1
    print("%-8d %-22s %-9s | %s  | %s" % (ln, inp[ln],
          "/".join(sorted(miss[ln])), cells[0], " ".join(cells[1:])))
print()
print("rows fixed by a split-shift (+-2/+-4), BOTH insns all modes:", nfix, "/21")
