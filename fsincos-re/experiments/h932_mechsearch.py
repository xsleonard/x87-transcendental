#!/usr/bin/env python3
# h932: AUTOMATED MECHANISM SEARCH over the terminal-window carry.
# The statistical sweeps (h928/h931) bound single-bit information
# only; a carry CHAIN is invisible to them.  This harness screens
# whole candidate MECHANISMS — parameterized, implementable datapath
# variants — against the labeled census at an exactness bar:
#   explain every carry row WITH ITS DIRECTION, zero false fires on
#   the in-window negatives.  Survivors go to holdout/suite/blind.
# Families (twins-compatible ones read X and AR separately):
#   F1 blocked carry-select CPA: block size B, phase anchor A,
#      lookahead depth D blocks; deviation = predicted window
#      carry-in minus true carry-in.
#   F2 redundant (S,C) window read: chop(S)+chop(C) plus a below-
#      window predictor g in a small family.
#   F3 anchored byte-threshold (R88-adder generalizations; M-only,
#      cannot explain the twins' stratum but may own others).
# Usage: h932_mechsearch.py [max_candidates]
import sys, itertools
from collections import defaultdict

# ---- load rows: addends + labels + direction ----
def load():
    # direction per (insn, op): +1 hw above model, -1 below
    dirn = {}
    for ln in open("h931_labels.tsv"):
        t = ln.rstrip("\n").split("\t")
        if len(t) != 9 or t[8] != "C":
            continue
        insn, op = t[1], t[3]
        try:
            d = int(t[5], 16) - int(t[7], 16)
        except ValueError:
            continue
        if abs(d) == 1:
            dirn.setdefault((insn, op), d)
    rows = []
    with open("h931_frames.tsv") as f:
        hdr = f.readline().rstrip("\n").split("\t")
        for ln in f:
            t = ln.rstrip("\n").split("\t")
            if len(t) != len(hdr):
                continue
            r = dict(zip(hdr, t))
            le2 = int(r["lefte2"]); re2 = int(r["righte2"])
            L = int(r["leftsig"], 16); R = int(r["rightsig"], 16)
            pay = int(r["payload"])
            scale = min(le2, re2)
            if pay and le2 - 8 < scale:
                scale = le2 - 8
            X = (L << (le2 - scale))
            if pay >= 0:
                X += pay << max(0, le2 - 8 - scale)
            else:
                X -= (-pay) << max(0, le2 - 8 - scale)
            AR = R << (re2 - scale)
            M = X - AR
            if M <= 0:
                continue
            kk = M.bit_length() - 67
            if kk < 1:
                continue
            lab = 1 if r["lab"] == "C" else 0
            dd = dirn.get((r["insn"], r["se"] + " " + r["sig"]), 0) \
                if lab else 0
            rows.append(dict(X=X, AR=AR, M=M, kk=kk,
                             scale=scale, lab=lab, dirn=dd,
                             seed=int(r["seed"]),
                             act=r["active"], pay=pay))
    return rows

rows = load()
C = [r for r in rows if r["lab"]]
Nn = [r for r in rows if not r["lab"]]
up = sum(1 for r in C if r["dirn"] > 0)
dn = sum(1 for r in C if r["dirn"] < 0)
print("rows %d  C %d (up %d / dn %d / ? %d)  N %d"
      % (len(rows), len(C), up, dn, len(C) - up - dn, len(Nn)))

# ---- mechanism evaluators ----
def true_cin(r):
    # exact borrow already inside M; a mechanism's deviation is
    # pred - true where true = carry actually absorbed by M.
    # We model the window read of M2 = X + (~AR) + 1 at 256 bits.
    return None

MASK = (1 << 256) - 1

def f1_dev(r, B, D, anchor):
    """blocked carry-select: two's-complement X + ~AR + 1 in blocks
    of B bits; the window boundary sits at bit kk; block edges at
    positions == phase (mod B).  Lookahead sees only the D blocks
    below the boundary block edge; deeper borrow is JAMMED to the
    select default (no-carry).  Returns predicted - true window
    carry-in (in {-1, 0, +1})."""
    X = r["X"]; Y = (~r["AR"]) & MASK
    kk = r["kk"]
    if anchor == 0:
        ph = 0                       # blocks anchored at bit 0 of scale
    elif anchor == 1:
        ph = kk % B                  # anchored at the window boundary
    else:
        ph = (r["scale"] % B + B) % B
    # block edge at or below kk aligned to phase
    e = kk - ((kk - ph) % B)
    lo = e - D * B
    if lo <= 0:
        return 0                     # full visibility -> exact
    # true carry into e of X + Y + 1:
    below = ((X & ((1 << e) - 1)) + (Y & ((1 << e) - 1)) + 1)
    true_c = below >> e
    # predictor sees bits [lo, e) with carry-in at lo assumed 0:
    seg = ((X >> lo) & ((1 << (D * B)) - 1)) + \
          ((Y >> lo) & ((1 << (D * B)) - 1))
    pred_c = seg >> (D * B)
    # both are 0/1-ish (sum of two segs + maybe 1); clamp
    dev = int(pred_c) - int(true_c)
    # carry from e to kk propagates exactly inside the boundary block
    if dev and e < kk:
        # does the deviation survive propagation to kk?
        span = ((X >> e) & ((1 << (kk - e)) - 1)) + \
               ((Y >> e) & ((1 << (kk - e)) - 1))
        with_t = (span + int(true_c)) >> (kk - e)
        with_p = (span + int(pred_c)) >> (kk - e)
        dev = int(with_p) - int(with_t)
    return dev

def f2_dev(r, B, mode):
    """redundant (S,C): S = X ^ ~AR, C = (X & ~AR) << 1, +1 at lsb.
    Window read = chop(S) + chop(C) + g(top-B bits of below fields).
    g modes: 0 = drop below entirely; 1 = add top-B bytes with their
    own carry only; 2 = jam (OR-reduce) below into a sticky +1."""
    X = r["X"]; Yc = (~r["AR"]) & MASK
    S = X ^ Yc
    Cv = ((X & Yc) << 1) | 1          # the +1 of two's complement
    kk = r["kk"]
    true_sum = (S + Cv) >> kk
    if mode == 0:
        pred = (S >> kk) + (Cv >> kk)
    elif mode == 1:
        sb = (S >> max(0, kk - B)) & ((1 << B) - 1)
        cb = (Cv >> max(0, kk - B)) & ((1 << B) - 1)
        pred = (S >> kk) + (Cv >> kk) + ((sb + cb) >> B)
    else:
        st = 1 if (S & ((1 << kk) - 1)) or (Cv & ((1 << kk) - 1)) else 0
        pred = (S >> kk) + (Cv >> kk) + st
    return int(pred - true_sum)

def f3_dev(r, B, T, anchor):
    """M-only byte threshold: deviation +1 iff the top-B bits of the
    below-window field of M >= T (anchored at kk or at scale grid)."""
    kk = r["kk"]
    if anchor:
        e = kk - (kk % 8)
        if e <= 0:
            return 0
        fld = (r["M"] >> max(0, e - B)) & ((1 << B) - 1)
    else:
        fld = (r["M"] >> max(0, kk - B)) & ((1 << B) - 1)
    return 1 if fld >= T else 0

# ---- screening ----
def screen(name, dev):
    """dev(r) in {-1,0,+1}; must equal r.dirn on C rows and 0 on N."""
    fn = 0
    for r in C:
        if r["dirn"] and dev(r) != r["dirn"]:
            fn += 1
            if fn > 60:               # early kill at 1% FN
                return None
    fp = 0
    for r in Nn:
        if dev(r) != 0:
            fp += 1
            if fp > 500:
                return None
    return (fn, fp)

cands = []
for B in (4, 8, 16):
    for D in (1, 2, 3, 4):
        for A in (0, 1, 2):
            cands.append(("F1 B=%d D=%d A=%d" % (B, D, A),
                          lambda r, B=B, D=D, A=A: f1_dev(r, B, D, A)))
for B in (4, 8, 16, 24):
    for m in (0, 1, 2):
        cands.append(("F2 B=%d g=%d" % (B, m),
                      lambda r, B=B, m=m: f2_dev(r, B, m)))
for B in (5, 8, 12):
    for T in ((1 << 5) - 1, (1 << 8) - 1, (1 << 8) - 4, (1 << 12) - 1):
        if T >= (1 << B):
            continue
        for A in (0, 1):
            cands.append(("F3 B=%d T=%#x A=%d" % (B, T, A),
                          lambda r, B=B, T=T, A=A: f3_dev(r, B, T, A)))
print("candidates:", len(cands))
best = []
for name, dev in cands:
    res = screen(name, dev)
    if res is not None:
        best.append((res[0] + res[1], res, name))
        print("  CANDIDATE SURVIVES SCREEN %-22s FN=%d FP=%d"
              % (name, res[0], res[1]))
best.sort()
if not best:
    print("no candidate under the screen caps (FN<=60, FP<=500)")
    # report the closest few by FN on carries only
    part = []
    for name, dev in cands:
        fn = sum(1 for r in C[:1500]
                 if r["dirn"] and dev(r) != r["dirn"])
        part.append((fn, name))
    part.sort()
    for fn, name in part[:8]:
        print("  closest by FN(first 1500 C): %-24s FN=%d/1500"
              % (name, fn))
