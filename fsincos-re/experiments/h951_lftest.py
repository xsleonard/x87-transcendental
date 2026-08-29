#!/usr/bin/env python3
# h951: THE ONE-CARRIER COMPOSITION TEST.  Build the pure full-left
# composition (chop67(fullL + chopR): -DG_TAILS=2 -DG_PAYOFF=1, no
# payload, no gate) from the R92 source and run it over EVERY
# labeled leg in h931_labels.tsv.  Cross-tab hw==LF by leg class:
#   - decisive legs (h948_gate_corpus): does LF land on hw's side,
#     including the 1,781 L_D-error legs?
#   - invisible-C legs (the 1,160 band-shaped deep residual)
#   - AGREE legs: collateral count (LF != model where hw == model)
# If LF matches hw on the decisive+residual legs at ~zero AGREE
# collateral, the payload/gate machinery and the parked band are one
# arithmetic object: the left tail carried exactly.
import subprocess, sys
from collections import Counter, defaultdict

BUILD = ["gcc", "-O2", "-ffp-contract=off", "-DG_TAILS=2",
         "-DG_PAYOFF=1", "/root/r59/fsincos_skylake.c", "-lm",
         "-o", "model_h951_lf"]
p = subprocess.run(BUILD, capture_output=True, text=True)
if p.returncode != 0:
    print(p.stderr[-3000:]); sys.exit(1)
print("built model_h951_lf", file=sys.stderr)

vis = {}
f = open("h948_gate_corpus.tsv"); f.readline()
for ln in f:
    t = ln.rstrip("\n").split("\t")
    if len(t) == 6: vis[(t[0], t[1], t[2])] = (t[3], t[4])

legs = defaultdict(list)
for ln in open("h931_labels.tsv"):
    t = ln.rstrip("\n").split("\t")
    if len(t) != 9: continue
    legs[(t[1], t[2])].append((t[3], t[4].lower(), t[5].lower(),
                               t[6].lower(), t[7].lower(), t[8]))

res = Counter()
err_rows = open("h951_errors.tsv", "w")
err_rows.write("insn\tmode\top\tclass\thwlab\tldlab\thw\tmodel\tlf\n")
for (insn, mode), rows in sorted(legs.items()):
    ops = [r[0] for r in rows]
    fl = "--fsin-standalone" if insn == "sin" else "--fcos-standalone"
    args = ["./model_h951_lf", "--batch", fl]
    if mode != "rn": args.insert(2, "--rc=" + mode)
    p = subprocess.run(args, input="\n".join(ops) + "\n",
                       capture_output=True, text=True)
    out = [tuple(l.split()[1:3]) for l in p.stdout.splitlines()]
    assert len(out) == len(rows), (insn, mode, len(out), len(rows))
    for (op, hs, hg, ms, mg, cls), lfv in zip(rows, out):
        lf_eq_hw = (hs, hg) == tuple(x.lower() for x in lfv)
        k = (insn, mode, op)
        if k in vis:
            hwlab, ldlab = vis[k]
            ld_ok = hwlab.lower() == ldlab
            res[("decisive", cls, hwlab, "LDok" if ld_ok else "LDerr",
                 "LF==hw" if lf_eq_hw else "LF!=hw")] += 1
            if not lf_eq_hw:
                err_rows.write("\t".join((insn, mode, op, "decisive-" + cls,
                    hwlab, ldlab, hs + ":" + hg, ms + ":" + mg,
                    lfv[0] + ":" + lfv[1])) + "\n")
        else:
            res[("invis", cls,
                 "LF==hw" if lf_eq_hw else "LF!=hw")] += 1
            if not lf_eq_hw and cls == "C":
                err_rows.write("\t".join((insn, mode, op, "invisC",
                    "-", "-", hs + ":" + hg, ms + ":" + mg,
                    lfv[0] + ":" + lfv[1])) + "\n")
    print(insn, mode, "done", file=sys.stderr)
err_rows.close()
for k in sorted(res, key=str): print(k, res[k])
