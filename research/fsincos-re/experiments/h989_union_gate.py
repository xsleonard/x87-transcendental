#!/usr/bin/env python3
# h989: the R95 UNION value gate (run on i7 /root/r84, after
# h988_gate_r95.py).  Merges the two hardware truth sets — the
# 8,315-op h968 census bank (2026-08-30) and the 841-op h988 fresh
# capture (2026-09-01) — into one 8,518-op union (638-op overlap:
# ZERO leg mismatches = capture stability / implicit epoch check),
# then scores model_r93_ref3 / model_r95 / model_r95_nolc on every
# leg and cross-tabulates the carve-decided legs by the arm's own
# cell coordinates (model_r95_diag prints DI_R95 md/sum/d/me2/g/keep
# under --dump-internals; built by sed-inserting the fprintf before
# the "if (!keep95)" line of the h987 arm).
# RESULT 2026-09-01 (widened side-agnostic g7 carve): FIX 1,259 /
# BREAK 0 / UNFIXED 1,831 over 34,072 legs.  Pre-widening the 3
# breaks sat in md=1 d=12 me2=-75 g=7 (sums 7,9) — the magdown
# mirror of the magup-only g7 carve — with ZERO fix legs there.
import subprocess
from collections import defaultdict, Counter

census = {}
hdr = None
for l in open("h968_ops.tsv"):
    t = l.rstrip("\n").split("\t")
    if hdr is None:
        hdr = t
        continue
    d = dict(zip(hdr, t))
    census[(d["insn"], d["op"])] = {
        m: d["h_" + m].replace(":", " ") for m in ("rn", "rd", "ru", "rz")}
print("census ops:", len(census))
fresh = defaultdict(dict)
for l in open("h988_legs.tsv"):
    t = l.rstrip("\n").split("\t")
    if t[0] == "insn":
        continue
    fresh[(t[0], t[1])][t[2]] = t[3].replace(":", " ")
print("h988 ops:", len(fresh))
ovl = [k for k in fresh if k in census]
mism = sum(1 for k in ovl for m in ("rn", "rd", "ru", "rz")
           if fresh[k][m].lower() != census[k][m].lower())
print("overlap ops:", len(ovl), "hw leg mismatches:", mism)
truth = {}
truth.update(census)
truth.update({k: dict(v) for k, v in fresh.items()})
print("union ops:", len(truth))
ops = {"cos": [], "sin": []}
for insn, op in sorted(truth):
    ops[insn].append(op)

def runm(model, insn, mode, lst):
    fl = "--fsin-standalone" if insn == "sin" else "--fcos-standalone"
    args = [model, "--batch", fl]
    if mode != "rn":
        args.insert(2, "--rc=" + mode)
    p = subprocess.run(args, input="\n".join(lst) + "\n",
                       capture_output=True, text=True)
    out = [" ".join(l.split()[1:3]).lower() for l in p.stdout.splitlines()]
    assert len(out) == len(lst)
    return out

coords = {}
for insn, lst in ops.items():
    fl = "--fsin-standalone" if insn == "sin" else "--fcos-standalone"
    for op in lst:
        p = subprocess.run(["./model_r95_diag", "--batch", fl,
                            "--dump-internals"], input=op + "\n",
                           capture_output=True, text=True)
        d = [l for l in p.stderr.splitlines() if l.startswith("DI_R95")]
        coords[(insn, op)] = d[0].split(None, 1)[1] if d else "NOARM"

tab = open("h989_union_legs.tsv", "w")
print("insn\top\tmode\thw\tm93\tm95\tmnolc\tcell", file=tab)
cellw = defaultdict(Counter)
tot = Counter()
for insn, lst in ops.items():
    for mode in ("rn", "rd", "ru", "rz"):
        m93 = runm("./model_r93_ref3", insn, mode, lst)
        m95 = runm("./model_r95", insn, mode, lst)
        mnl = runm("./model_r95_nolc", insn, mode, lst)
        for op, a, b, c in zip(lst, m93, m95, mnl):
            h = truth[(insn, op)][mode].lower()
            cell = coords.get((insn, op), "MISSING")
            print("\t".join([insn, op, mode, h, a, b, c, cell]), file=tab)
            if b != c:
                cellw[cell]["FITTED_RIGHT" if b == h else
                           "SUPPR_RIGHT" if c == h else "BOTH_WRONG"] += 1
            if a == h and b != h:
                tot["BREAK95"] += 1
            elif a != h and b == h:
                tot["FIX95"] += 1
            elif a != h and b != h:
                tot["UNFIXED"] += 1
tab.close()
print("=== union totals ===")
for k in sorted(tot):
    print(k, tot[k])
print("=== carve-decision cells (union) ===")
for k in sorted(cellw):
    print(k, "|", dict(cellw[k]))
