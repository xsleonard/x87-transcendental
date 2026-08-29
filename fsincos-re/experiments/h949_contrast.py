#!/usr/bin/env python3
# h949b: the finer-coordinate contrast.  TRAIN ops only (seed <
# 96411).  Baseline = per-(cell,g,pay)-tuple majority (the frame's
# ceiling).  For each candidate feature X, refine tuples by X's
# value and count remaining minority ops.  Features that close the
# gap get formalized and holdout-validated separately.  Within-train
# sanity: bins learned on even seeds, scored on odd seeds.
import pickle, sys
from collections import Counter, defaultdict

table = pickle.load(open("h949_features.pkl", "rb"))
SPLIT = 96411
train = [r for r in table if r["seed"] < SPLIT]
print("train ops:", len(train), "FIRE:",
      sum(1 for r in train if r["hwlab"] == "FIRE"))

def derive(r):
    d = r["tc_dist"]
    ls, le2, lsig = r["tc_left"]; rs, re2, rsig = r["tc_right"]
    ms, me2, msig = r["tc_mul"]
    mask = (1 << d) - 1
    rlow = rsig & mask
    grl = (rlow if rlow else (1 << d)) if ls != rs else ((1 << d) - rlow)
    g = 64 if grl > 64 else int(grl)
    top8 = (r["acc_d60"] >> 52) & 0xFF
    f = {}
    f["_cell"] = (d, me2); f["_g"] = g; f["_pay"] = r["tc_payload"]
    # candidates
    f["low3"] = r["tc_low3"]; f["rsh"] = r["tc_rsh"]
    f["ud"] = r["tc_ud"]; f["u5d"] = r["tc_u5d"]; f["rud"] = r["tc_rud"]
    f["pay2"] = r.get("tc2_pay2", -99)
    f["laneb"] = r.get("tc2_laneb", -99); f["lanediff"] = r.get("tc2_diff", -99)
    f["lane2"] = r.get("tc2_lane2", -99); f["lane3"] = r.get("tc2_lane3", -99)
    for k in ("lb", "df", "top", "rem", "dspan", "wk", "pm", "phw",
              "th", "at", "b8", "bbs", "neg", "act", "pay"):
        f["b81_" + k] = r.get("b81_" + k, -99)
    f["ls"] = ls; f["rs"] = rs; f["ms"] = ms
    f["lfs"] = r["tc_lf"][0]; f["rfs"] = r["tc_rf"][0]
    f["le2mm"] = le2 - me2; f["re2mm"] = re2 - me2
    f["top8"] = top8; f["sum8"] = top8 + r["tc_low3"]
    f["rmid8"] = (rsig >> d) & 0xFF; f["lmid8"] = (lsig >> d) & 0xFF
    f["llow_g"] = lsig & mask if mask < (1 << 16) else (lsig & mask) & 0xFF
    f["rlow_b"] = rlow & 0xFF
    def tz(x):
        if x == 0: return 40
        n = 0
        while not (x >> n) & 1 and n < 40: n += 1
        return n
    f["rtz"] = tz(rsig); f["ltz"] = tz(lsig); f["mtz"] = tz(msig)
    f["ftz"] = tz(r["tc_f4"][2])
    f["rdisc_t8"] = (r["tc_rdisc"] >> 56) & 0xFF
    f["rdisc_b0"] = r["tc_rdisc"] & 0xFF
    f["mag_b0"] = r["tc_mag"][2] & 0xFF
    f["f4e2"] = r["tc_f4"][1] - me2
    f["sq_b0"] = r.get("poly_sq", (0, 0, 0))[2] & 0xFF
    f["odd_tz"] = tz(r.get("poly_odd", (0, 0, 0))[2])
    f["even_tz"] = tz(r.get("poly_even", (0, 0, 0))[2])
    f["d60_b44"] = (r["acc_d60"] >> 44) & 0xFF
    f["d60_b36"] = (r["acc_d60"] >> 36) & 0xFF
    f["grl_lo6"] = int(grl) & 63 if grl <= 4096 else 99
    return f

recs = []
for r in train:
    f = derive(r)
    recs.append((f, r["hwlab"], r["seed"]))

tup = lambda f: (f["_cell"], f["_g"], f["_pay"])
base = defaultdict(Counter)
for f, y, s in recs: base[tup(f)][y] += 1
base_err = sum(sum(c.values()) - max(c.values()) for c in base.values())
n_mixed = sum(1 for c in base.values() if len(c) > 1)
print("baseline tuple ceiling: %d minority ops in %d mixed tuples"
      % (base_err, n_mixed))

FEATS = sorted(k for k in recs[0][0] if not k.startswith("_"))
rows = []
for feat in FEATS:
    ref = defaultdict(Counter)
    for f, y, s in recs: ref[(tup(f), f[feat])][y] += 1
    err = sum(sum(c.values()) - max(c.values()) for c in ref.values())
    card = len(set(f[feat] for f, y, s in recs))
    # even/odd-seed sanity: majority learned on even, scored on odd
    maj = defaultdict(Counter); oc = defaultdict(Counter)
    for f, y, s in recs:
        (maj if s % 2 == 0 else oc)[(tup(f), f[feat])][y] += 1
    xerr = 0
    for k, c in oc.items():
        if k in maj and len(maj[k]) > 0:
            pred = maj[k].most_common(1)[0][0]
            xerr += sum(v for y2, v in c.items() if y2 != pred)
        else:
            xerr += min(c.values()) if len(c) > 1 else 0
    rows.append((err, xerr, card, feat))
rows.sort()
print("%-12s %7s %7s %6s" % ("feature", "err", "xval", "card"))
for err, xerr, card, feat in rows:
    print("%-12s %7d %7d %6d" % (feat, err, xerr, card))
