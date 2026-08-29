#!/usr/bin/env python3
# h956b: half-ulp-grid value relabel.  Position code from 4-mode
# outputs: ("exact", lo) or ("half", lo, h) with h = rn side
# (0 = lower half, 1 = upper half; exact-midpoint folds into h by
# parity of lo — noted, bounded).  FIRE iff hwpos == Fpos != Dpos,
# DECL iff hwpos == Dpos != Fpos, SNAP iff hw ulp-exact at a shared
# closure point of the F/D positions, INVIS iff Fpos == Dpos,
# else OTHER.
import pickle, subprocess, sys
from collections import Counter, defaultdict

table = pickle.load(open("h949_features.pkl", "rb"))
MODES = ["rn", "rd", "ru", "rz"]
byinsn = defaultdict(list)
for r in table: byinsn[r["insn"]].append(r["op"])

def run_model(model, insn, mode, ops):
    fl = "--fsin-standalone" if insn == "sin" else "--fcos-standalone"
    args = [model, "--batch", fl]
    if mode != "rn": args.insert(2, "--rc=" + mode)
    p = subprocess.run(args, input="\n".join(ops) + "\n",
                       capture_output=True, text=True)
    o = [tuple(l.split()[1:3]) for l in p.stdout.splitlines()]
    assert len(o) == len(ops)
    return o

def capture(insn, mode, ops):
    p = subprocess.run(["/root/x87_capture_x86_64", mode, insn],
                       input="\n".join(ops) + "\n",
                       capture_output=True, text=True)
    o = []
    for l in p.stdout.splitlines():
        w = l.split()
        o.append((w[1], w[2]) if w and w[0] == "OK" else None)
    assert len(o) == len(ops)
    return o

vals = defaultdict(dict)
for insn, ops in sorted(byinsn.items()):
    for mode in MODES:
        hw = capture(insn, mode, ops)
        F = run_model("./model_h946_pg0", insn, mode, ops)
        D = run_model("./model_h946_r92payoff", insn, mode, ops)
        for op, h, f_, d_ in zip(ops, hw, F, D):
            vals[(insn, op)].setdefault("hw", {})[mode] = h
            vals[(insn, op)].setdefault("F", {})[mode] = f_
            vals[(insn, op)].setdefault("D", {})[mode] = d_
    print(insn, "done", file=sys.stderr)
pickle.dump(vals, open("h956_vals.pkl", "wb"), protocol=4)

def key(t): return (t[0].lower(), int(t[1], 16))
def succ(v):
    se, sig = v
    if sig == 0xFFFFFFFFFFFFFFFF:
        return (format(int(se, 16) + 1, "04x"), 1 << 63)
    return (se, sig + 1)

def pos(mv):
    if None in mv.values(): return ("err",)
    ks = {m: key(t) for m, t in mv.items()}
    s = set(ks.values())
    if len(s) == 1: return ("exact", ks["rn"])
    neg = int(ks["rn"][0], 16) >> 15 & 1
    mag_lo = ks["ru"] if neg else ks["rd"]
    mag_hi = ks["rd"] if neg else ks["ru"]
    if ks["rz"] != mag_lo or succ(mag_lo) != mag_hi or len(s) > 2:
        return ("odd", tuple(sorted(s)))
    return ("half", mag_lo, 0 if ks["rn"] == mag_lo else 1)

def closure(p):
    if p[0] == "exact": return {("pt", p[1])}
    if p[0] != "half": return set()
    lo = p[1]
    return ({("pt", lo), ("mid", lo)} if p[2] == 0
            else {("mid", lo), ("pt", succ(lo))})

out = open("h956b_value_labels.tsv", "w")
out.write("insn\top\toldlab\tvlab\thwpos\tFpos\tDpos\n")
cnt = Counter(); vlab_of = {}
old = {(r["insn"], r["op"]): r["hwlab"] for r in table}
for k in sorted(vals):
    v = vals[k]
    hwp, Fp, Dp = pos(v["hw"]), pos(v["F"]), pos(v["D"])
    if hwp[0] in ("err", "odd") or Fp[0] in ("err", "odd") \
       or Dp[0] in ("err", "odd"):
        vlab = "ODD"
    elif Fp == Dp: vlab = "INVIS"
    elif hwp == Fp: vlab = "FIRE"
    elif hwp == Dp: vlab = "DECL"
    elif hwp[0] == "exact" and \
            ("pt", hwp[1]) in (closure(Fp) & closure(Dp)):
        vlab = "SNAP"
    elif hwp[0] == "half" and closure(hwp) & closure(Fp) \
            and closure(hwp) & closure(Dp):
        vlab = "MIDSNAP"
    else: vlab = "OTHER"
    cnt[(old[k], vlab)] += 1
    vlab_of[k] = vlab
    out.write("\t".join((k[0], k[1], old[k], vlab, str(hwp), str(Fp),
                         str(Dp))) + "\n")
out.close()
print("old-label x half-grid value-label:")
for k2 in sorted(cnt, key=str): print("  ", k2, cnt[k2])

def tup(r):
    d = r["tc_dist"]
    ls, le2, lsig = r["tc_left"]; rs, re2, rsig = r["tc_right"]
    mask = (1 << d) - 1
    rlow = rsig & mask
    grl = (rlow if rlow else (1 << d)) if ls != rs else ((1 << d) - rlow)
    g = 64 if grl > 64 else int(grl)
    return ((d, r["tc_mul"][1]), g, r["tc_payload"])
base = defaultdict(Counter); base_old = defaultdict(Counter)
for r in table:
    vl = vlab_of.get((r["insn"], r["op"]))
    if vl in ("FIRE", "DECL"):
        base[tup(r)][vl] += 1
        base_old[tup(r)][r["hwlab"]] += 1
minr = sum(sum(c.values()) - max(c.values()) for c in base.values())
nmix = sum(1 for c in base.values() if len(c) > 1)
tot = sum(sum(c.values()) for c in base.values())
mino = sum(sum(c.values()) - max(c.values()) for c in base_old.values())
nmixo = sum(1 for c in base_old.values() if len(c) > 1)
print("CLEAN ceiling: %d minority / %d ops in %d mixed tuples "
      "(same ops OLD labels: %d minority in %d mixed)"
      % (minr, tot, nmix, mino, nmixo))
pickle.dump(vlab_of, open("h956b_vlab.pkl", "wb"), protocol=4)
