#!/usr/bin/env python3
# h967: diagnose the h966 FAIL (522 breaks / 459 unfixed).
# Saves every in-table leg with fresh hw + m93 + m94, then answers:
#  (1) were the contradicting legs IN the corpus (h931_labels) — and
#      does fresh hw agree with banked hw on corpus legs (provenance/
#      epoch check), or are they never-scanned legs (corpus-scope
#      illusion)?
#  (2) is the damage mode/sign/stratum-structured (salvageable by a
#      mode-aware refit) or unstructured (arm dead)?
import pickle, subprocess, sys
from collections import Counter, defaultdict

table = set(pickle.load(open("h964_table.pkl", "rb")))
strata = pickle.load(open("h963_op_strata.pkl", "rb"))
sel = sorted((insn, op) for (insn, op), st in strata.items()
             if st in table)
print("in-table ops:", len(sel))
stmap = {k: strata[k] for k in sel}
del strata

# corpus legs + banked hw for the selected ops only
want = set(sel)
corpus = {}                      # (insn, mode, op) -> (cls, hw_se, hw_sig)
for ln in open("h931_labels.tsv"):
    t = ln.rstrip("\n").split("\t")
    if len(t) != 9:
        continue
    if (t[1], t[3]) in want:
        corpus[(t[1], t[2], t[3])] = (t[8], t[4].lower(), t[5].lower())
print("corpus legs of in-table ops:", len(corpus))

byinsn = defaultdict(list)
for insn, op in sel:
    byinsn[insn].append(op)

def runm(model, insn, mode, ops):
    fl = "--fsin-standalone" if insn == "sin" else "--fcos-standalone"
    args = [model, "--batch", fl]
    if mode != "rn":
        args.insert(2, "--rc=" + mode)
    p = subprocess.run(args, input="\n".join(ops) + "\n",
                       capture_output=True, text=True)
    out = [tuple(l.split()[1:3]) for l in p.stdout.splitlines()]
    assert len(out) == len(ops)
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
    assert len(rows) == len(ops)
    return rows

out = open("h967_legs.tsv", "w")
out.write("insn\tmode\top\tact\tsum8\td\tme2\tg\tcls\tfired\t"
          "incorpus\tcorpuscls\thwmatch\thse\thsig\tmse\tmsig\n")
res = Counter()
modecx = Counter()
stratcx = Counter()
opclass = defaultdict(dict)      # (insn,op) -> mode -> (cls, fired)
for insn, ops in sorted(byinsn.items()):
    for mode in ("rn", "rd", "ru", "rz"):
        hw = runhw(insn, mode, ops)
        m93 = runm("./model_r93_ref", insn, mode, ops)
        m94 = runm("./model_r94", insn, mode, ops)
        for op, h, a, b in zip(ops, hw, m93, m94):
            h = tuple(x.lower() for x in h)
            a = tuple(x.lower() for x in a)
            b = tuple(x.lower() for x in b)
            st = stmap[(insn, op)]
            if h[0] == "weird":
                res["WEIRD"] += 1
                continue
            fired = int(b != a)
            if a == h and b == h:
                cls = "OK"        # agree, untouched
            elif a == h:
                cls = "BREAK"     # arm broke an agree leg
            elif b == h:
                cls = "FIX"
            else:
                cls = "UNFIXED"   # miss under both
            k = (insn, mode, op)
            cor = corpus.get(k)
            incorp = int(cor is not None)
            corcls = cor[0] if cor else "-"
            hwmatch = "-"
            if cor:
                hwmatch = int((cor[1], cor[2]) == h)
            res[(cls, "fired%d" % fired, "corp%d" % incorp,
                 "corcls" + corcls, "hwm%s" % hwmatch)] += 1
            modecx[(cls, mode)] += 1
            if cls in ("BREAK", "UNFIXED"):
                stratcx[(cls, st)] += 1
            opclass[(insn, op)][mode] = (cls, fired)
            out.write("\t".join(map(str, (
                insn, mode, op, st[0], st[1], st[2], st[3], st[4],
                cls, fired, incorp, corcls, hwmatch,
                h[0], h[1], a[0], a[1]))) + "\n")
out.close()

print("\n== overall (cls, fired, in-corpus, corpus-cls, hw-match) ==")
for k in sorted(res):
    print(k, res[k])
print("\n== by mode ==")
for k in sorted(modecx):
    print(k, modecx[k])
print("\n== damage by stratum (top 40) ==")
for k, v in sorted(stratcx.items(), key=lambda x: -x[1])[:40]:
    print(k, v)

# mode-pattern of each op: is C-ness mode-structured?
pat = Counter()
for (insn, op), mm in opclass.items():
    sig = tuple(mm.get(m, ("-",))[0][0] for m in ("rn", "rd", "ru", "rz"))
    pat[sig] += 1
print("\n== per-op mode pattern (rn,rd,ru,rz first letters) ==")
for k, v in sorted(pat.items(), key=lambda x: -x[1])[:25]:
    print("".join(k), v)
