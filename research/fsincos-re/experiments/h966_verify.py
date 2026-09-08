#!/usr/bin/env python3
# h966: R94 value-level verification (run on i7 /root/r84).
# For EVERY (insn,op) whose h963 census stratum is in the R94 table
# (h963_op_strata.pkl x h964_table.pkl — band-C ops AND visF ops),
# fresh-capture hardware on all 4 modes and run model_r93_ref
# (incumbent, built from fsincos_skylake.c.preR94) + model_r94
# (candidate) on all 4 modes.  PASS requires:
#   - every leg where incumbent != hw is FIXED by r94 (the ~400
#     in-table band C legs, including scan-unmeasured legs), and
#   - ZERO legs where incumbent == hw are broken by r94 (the visF
#     legs and any invisible-agree leg the census missed).
import pickle, subprocess, sys
from collections import Counter

table = set(pickle.load(open("h964_table.pkl", "rb")))
strata = pickle.load(open("h963_op_strata.pkl", "rb"))
sel = sorted((insn, op) for (insn, op), st in strata.items()
             if st in table)
print("in-table ops:", len(sel), file=sys.stderr)

byinsn = {}
for insn, op in sel:
    byinsn.setdefault(insn, []).append(op)

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

res = Counter()
bad = []
for insn, ops in sorted(byinsn.items()):
    for mode in ("rn", "rd", "ru", "rz"):
        hw = runhw(insn, mode, ops)
        m93 = runm("./model_r93_ref", insn, mode, ops)
        m94 = runm("./model_r94", insn, mode, ops)
        for op, h, a, b in zip(ops, hw, m93, m94):
            h = tuple(x.lower() for x in h)
            a = tuple(x.lower() for x in a)
            b = tuple(x.lower() for x in b)
            if h[0] == "weird":
                res["WEIRD"] += 1
                continue
            res[("93" + ("=" if a == h else "!"),
                 "94" + ("=" if b == h else "!"))] += 1
            if a == h and b != h:
                bad.append(("BREAK", insn, mode, op, h, a, b))
            elif a != h and b != h:
                bad.append(("UNFIXED", insn, mode, op, h, a, b))
for k in sorted(res):
    print(k, res[k])
for r in bad[:200]:
    print(*r)
nb = sum(1 for r in bad if r[0] == "BREAK")
nu = sum(1 for r in bad if r[0] == "UNFIXED")
print("VERDICT:", "PASS" if not bad
      else "FAIL breaks=%d unfixed=%d" % (nb, nu))
