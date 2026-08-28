#!/usr/bin/env python3
# h943 census wall: model_h943 vs model_r92 vs banked hw on every
# labeled leg (census C legs + h940 species legs).
import subprocess, sys
from collections import Counter

legs = {}
for ln in open("h931_labels.tsv"):
    t = ln.rstrip("\n").split("\t")
    if len(t) != 9: continue
    legs.setdefault((t[1], t[3]), {})[t[2]] = (t[8], t[6], t[7])
for ln in open("h940_species.tsv"):
    t = ln.rstrip("\n").split("\t")
    if len(t) != 9: continue
    hw = t[8].split()
    if hw[0] != "OK": continue
    legs.setdefault((t[2], t[5]), {}).setdefault(t[3], ("S", hw[1], hw[2]))
print("ops:", len(legs), file=sys.stderr)

def runm(model, insn, mode, ops):
    fl = "--fsin-standalone" if insn == "sin" else "--fcos-standalone"
    args = [model, "--batch", fl]
    if mode != "rn": args.insert(2, "--rc=" + mode)
    p = subprocess.run(args, input="\n".join(ops) + "\n",
                       capture_output=True, text=True)
    return p.stdout.splitlines()

cnt = Counter()
fixedC = brokeS = 0
anom = []
for insn in ("cos", "sin"):
    ops = sorted({op for (i, op) in legs if i == insn})
    for mode in ("rn", "rd", "ru", "rz"):
        ba = runm("./model_r92", insn, mode, ops)
        h4 = runm("./model_h943", insn, mode, ops)
        for op, b, h in zip(ops, ba, h4):
            e = legs[(insn, op)].get(mode)
            def N(l):
                t = l.split()
                return ("C2",) if t and t[0] == "C2" else tuple(t[1:3])
            nb, nh = N(b), N(h)
            if e is None:
                if nb != nh:
                    cnt[(insn, mode, "MOVED-unlabeled")] += 1
                continue
            cls, hs, hg = e
            hwt = (hs.lower(), hg.lower())
            if cls == "C":
                if nh == hwt: cnt[(insn, mode, "C-FIXED")] += 1
                elif nh == nb: cnt[(insn, mode, "C-unfixed")] += 1
                else:
                    cnt[(insn, mode, "C-WRONGMOVE")] += 1
                    if len(anom) < 10: anom.append((insn, mode, op, "C", b, h, hs, hg))
            else:
                if nh == nb: cnt[(insn, mode, "S-quiet")] += 1
                elif nh == hwt: cnt[(insn, mode, "S-??hw")] += 1
                else:
                    cnt[(insn, mode, "S-BROKEN")] += 1
                    if len(anom) < 10: anom.append((insn, mode, op, "S", b, h, hs, hg))
    print(insn, "done", file=sys.stderr)
for k in sorted(cnt):
    print(k, cnt[k])
tot = Counter()
for k, v in cnt.items(): tot[k[2]] += v
print("=== totals ===")
for k, v in sorted(tot.items()): print("%-16s %d" % (k, v))
print("--- anomalies ---")
for a in anom: print(a)
