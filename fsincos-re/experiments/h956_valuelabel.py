#!/usr/bin/env python3
# h956: VALUE-LEVEL RELABEL of the h948 gate corpus.  h955 showed
# hardware can land EXACTLY on the output-grid point that the F/D
# compositions bracket (all-4-mode captures identical; F strictly
# below, D strictly above) — a third class ("SNAP") invisible to
# single-leg labeling and polluting the gate labels (~5% of mixed-
# tuple ops).  Capture all 4 modes for every op, recover each
# value's grid position by mode-bracketing, and classify:
#   hw interval == F interval  -> FIRE
#   hw interval == D interval  -> DECL
#   hw exact at the F/D shared boundary -> SNAP
#   anything else              -> OTHER
# Output h956_value_labels.tsv + purity re-analysis on clean labels.
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
    assert len(o) == len(ops), (insn, mode, len(o), len(ops))
    return o

# gather per (insn, op): {src: {mode: (se, sig)}}
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
    print(insn, "captured+modeled", file=sys.stderr)

def interval(mv):
    """4-mode outputs -> value position.
    Returns ('exact', v) if all agree, ('frac', lo) if the down-
    modes give lo and ru gives lo+1 (value in (lo, lo+1)), else
    ('odd', tuple).  v encoded as (se, sig-int, sign-ignored)."""
    if None in mv.values(): return ("err", None)
    def key(t): return (t[0].lower(), int(t[1], 16))
    ks = {m: key(t) for m, t in mv.items()}
    s = set(ks.values())
    if len(s) == 1: return ("exact", ks["rn"])
    # negative numbers: rd is away from zero, rz/ru toward. Use
    # magnitude ordering: se sign bit in se's top bit (x87 se).
    neg = int(ks["rn"][0], 16) >> 15 & 1
    lo_m, hi_m = (("ru", "rd") if neg else (("rd", "ru")))
    lo, hi = ks[lo_m], ks[hi_m]
    # rz truncates toward zero = magnitude-lo
    mag_lo = ks["ru"] if neg else ks["rd"]
    if ks["rz"] != mag_lo: return ("odd", tuple(sorted(s)))
    def succ(v):
        se, sig = v
        if sig == 0xFFFFFFFFFFFFFFFF:
            return (format(int(se, 16) + 1, "04x"), 1 << 63)
        return (se, sig + 1)
    if len(s) == 2 and succ(mag_lo) == (ks["rd"] if neg else ks["ru"]) \
       and ks["rn"] in s:
        return ("frac", mag_lo)
    return ("odd", tuple(sorted(s)))

out = open("h956_value_labels.tsv", "w")
out.write("insn\top\toldlab\tvlab\thwpos\tFpos\tDpos\n")
cnt = Counter(); vlab_of = {}
old = {(r["insn"], r["op"]): r["hwlab"] for r in table}
for k in sorted(vals):
    v = vals[k]
    hwp = interval(v["hw"]); Fp = interval(v["F"]); Dp = interval(v["D"])
    if "err" in (hwp[0], Fp[0], Dp[0]) or hwp[0] == "odd":
        vlab = "ODD"
    elif Fp == Dp:
        vlab = "INVIS"
    elif hwp == Fp: vlab = "FIRE"
    elif hwp == Dp: vlab = "DECL"
    elif hwp[0] == "exact":
        def bp(p):
            if p[0] != "frac": return set()
            se, sig = p[1]
            if sig == 0xFFFFFFFFFFFFFFFF:
                up = (format(int(se, 16) + 1, "04x"), 1 << 63)
            else:
                up = (se, sig + 1)
            return {p[1], up}
        vlab = ("SNAP" if hwp[1] in (bp(Fp) & bp(Dp)) else "OTHER")
    else: vlab = "OTHER"
    cnt[(old[k], vlab)] += 1
    vlab_of[k] = vlab
    out.write("\t".join((k[0], k[1], old[k], vlab, str(hwp), str(Fp),
                         str(Dp))) + "\n")
out.close()
print("old-label x value-label:")
for k2 in sorted(cnt, key=str): print("  ", k2, cnt[k2])

# purity re-analysis on clean FIRE/DECL (drop SNAP/ODD/OTHER/INVIS)
def tup(r):
    d = r["tc_dist"]
    ls, le2, lsig = r["tc_left"]; rs, re2, rsig = r["tc_right"]
    mask = (1 << d) - 1
    rlow = rsig & mask
    grl = (rlow if rlow else (1 << d)) if ls != rs else ((1 << d) - rlow)
    g = 64 if grl > 64 else int(grl)
    return ((d, r["tc_mul"][1]), g, r["tc_payload"])
base = defaultdict(Counter)
for r in table:
    vl = vlab_of.get((r["insn"], r["op"]))
    if vl in ("FIRE", "DECL"): base[tup(r)][vl] += 1
minr = sum(sum(c.values()) - max(c.values()) for c in base.values())
nmix = sum(1 for c in base.values() if len(c) > 1)
tot = sum(sum(c.values()) for c in base.values())
print("CLEAN-label tuple ceiling: %d minority ops / %d in %d mixed "
      "tuples" % (minr, tot, nmix))
pickle.dump(vlab_of, open("h956_vlab.pkl", "wb"), protocol=4)
