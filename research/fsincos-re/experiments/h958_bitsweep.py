#!/usr/bin/env python3
# h958: the definitive raw-bit sweep on CLEAN value-level labels.
# Every bit of every dumped wide word (low 64) + the raw operand
# (sig 64 + se 16) + d60/rdisc, tested as a within-(cell,g,pay)
# refinement with the honest even/odd xval on TRAIN (seed < 96411).
# Pre-registration: any feature with train xval gain >= 41 errors
# (vs baseline) goes to ONE holdout evaluation (seed >= 96411).
# SNAP ops excluded from FIRE/DECL; separately swept SNAP-vs-FIRE.
import pickle, sys
from collections import Counter, defaultdict

table = pickle.load(open("h949_features.pkl", "rb"))
vlab = pickle.load(open("h956b_vlab.pkl", "rb"))
SPLIT = 96411

WORDS = [("tc_left", 64), ("tc_right", 64), ("tc_mul", 64),
         ("tc_lf", 64), ("tc_rf", 64), ("tc_f4", 64), ("tc_mag", 64),
         ("poly_sq", 64), ("poly_odd", 64), ("poly_even", 64),
         ("b81_tc", 64), ("d60", 64), ("rdisc", 64),
         ("opsig", 64), ("opse", 16)]

def words(r):
    w = {}
    for name, _n in WORDS[:11]:
        t = r.get(name)
        w[name] = t[2] if t else 0
    w["d60"] = r.get("acc_d60", 0)
    w["rdisc"] = r.get("tc_rdisc", 0)
    se, sig = r["op"].split()
    w["opsig"] = int(sig, 16); w["opse"] = int(se, 16)
    return w

def tup(r):
    d = r["tc_dist"]
    ls, le2, lsig = r["tc_left"]; rs, re2, rsig = r["tc_right"]
    mask = (1 << d) - 1
    rlow = rsig & mask
    grl = (rlow if rlow else (1 << d)) if ls != rs else ((1 << d) - rlow)
    g = 64 if grl > 64 else int(grl)
    return ((d, r["tc_mul"][1]), g, r["tc_payload"])

recs = []
for r in table:
    vl = vlab.get((r["insn"], r["op"]))
    if vl: recs.append((tup(r), words(r), vl, r["seed"]))

def sweep(labs, name):
    tr = [x for x in recs if x[2] in labs and x[3] < SPLIT]
    ev = [x for x in tr if x[3] % 2 == 0]
    od = [x for x in tr if x[3] % 2 == 1]
    print("=== %s: train %d (even %d / odd %d) ===" %
          (name, len(tr), len(ev), len(od)))
    maj_t = defaultdict(Counter)
    for t, w, y, s in ev: maj_t[t][y] += 1
    tpred = {t: c.most_common(1)[0][0] for t, c in maj_t.items()}
    berr = sum(1 for t, w, y, s in od if tpred.get(t, labs[0]) != y)
    print("baseline xval:", berr)
    scores = []
    for wn, nb in WORDS:
        for b in range(nb):
            maj = defaultdict(Counter)
            for t, w, y, s in ev:
                maj[(t, (w[wn] >> b) & 1)][y] += 1
            err = 0
            for t, w, y, s in od:
                k = (t, (w[wn] >> b) & 1)
                c = maj.get(k)
                pred = (c.most_common(1)[0][0] if c
                        else tpred.get(t, labs[0]))
                if pred != y: err += 1
            scores.append((err, wn, b))
    scores.sort(key=lambda x: (x[0], x[1], x[2]))
    print("top 15:")
    for err, wn, b in scores[:15]:
        print("   %-12s bit%-3d %d" % (wn, b, err))
    TH = berr - 41
    hits = [(wn, b) for err, wn, b in scores if err <= TH]
    print("pre-registered survivors (xval <= %d): %d" % (TH, len(hits)))
    if hits:
        ho = [x for x in recs if x[2] in labs and x[3] >= SPLIT]
        majh_t = defaultdict(Counter)
        for t, w, y, s in tr: majh_t[t][y] += 1
        tph = {t: c.most_common(1)[0][0] for t, c in majh_t.items()}
        bh = sum(1 for t, w, y, s in ho if tph.get(t, labs[0]) != y)
        print("HOLDOUT n=%d baseline=%d" % (len(ho), bh))
        for wn, b in hits[:6]:
            maj = defaultdict(Counter)
            for t, w, y, s in tr: maj[(t, (w[wn] >> b) & 1)][y] += 1
            err = 0
            for t, w, y, s in ho:
                c = maj.get((t, (w[wn] >> b) & 1))
                pred = (c.most_common(1)[0][0] if c
                        else tph.get(t, labs[0]))
                if pred != y: err += 1
            print("  HOLDOUT %-12s bit%-3d %d (baseline %d)"
                  % (wn, b, err, bh))

sweep(["FIRE", "DECL"], "FIRE-vs-DECL")
sweep(["SNAP", "FIRE"], "SNAP-vs-FIRE")
