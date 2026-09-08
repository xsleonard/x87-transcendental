#!/usr/bin/env python3
# h953: the boundary-position contrast.  Harvest the PAYOFF build's
# dump (decision-free D-side terminal + final state) for all gate
# ops, merge with h949 features, and re-run the tuple-refinement
# contrast with the unseen-bin bias FIXED (fallback = tuple
# majority).  New features: D-terminal low bits (granule position,
# mode-independent chop67 value), fin_neg, reduction-side scalars.
import pickle, re, subprocess, sys
from collections import Counter, defaultdict

table = pickle.load(open("h949_features.pkl", "rb"))
SPLIT = 96411

# --- payoff-build dump: corr_out sig + fin_neg per op (rn) ---
byinsn = defaultdict(list)
for i, r in enumerate(table): byinsn[r["insn"]].append(i)
pay_d = {}
for insn, idxs in sorted(byinsn.items()):
    fl = "--fsin-standalone" if insn == "sin" else "--fcos-standalone"
    CH = 100000
    for ci in range(0, len(idxs), CH):
        chunk = idxs[ci:ci + CH]
        inp = "\n".join(table[i]["op"] for i in chunk) + "\n"
        p = subprocess.run(["./model_h946_r92payoff", "--batch", fl,
                            "--dump-internals"],
                           input=inp, capture_output=True, text=True)
        rows, cur = [], None
        for ln in p.stderr.splitlines():
            tag = ln.split(" ", 1)[0]
            if tag == "DI_IN":
                if cur is not None: rows.append(cur)
                cur = {}
            elif cur is None: continue
            elif tag == "DI_CORR" and "dsig" not in cur:
                m = re.search(r"out=(\d+):(-?\d+):([0-9a-f]{32})", ln)
                if m:
                    cur["dsign"] = int(m.group(1))
                    cur["de2"] = int(m.group(2))
                    cur["dsig"] = int(m.group(3), 16)
            elif tag == "DI_FIN" and "fneg" not in cur:
                m = re.search(r"neg=(\d+)", ln)
                if m: cur["fneg"] = int(m.group(1))
        if cur is not None: rows.append(cur)
        assert len(rows) == len(chunk), (insn, len(rows), len(chunk))
        for i, rr in zip(chunk, rows): pay_d[i] = rr
    print(insn, "payoff dump done", file=sys.stderr)
pickle.dump(pay_d, open("h953_payoff.pkl", "wb"), protocol=4)

def derive(i, r):
    d = r["tc_dist"]
    ls, le2, lsig = r["tc_left"]; rs, re2, rsig = r["tc_right"]
    mask = (1 << d) - 1
    rlow = rsig & mask
    grl = (rlow if rlow else (1 << d)) if ls != rs else ((1 << d) - rlow)
    g = 64 if grl > 64 else int(grl)
    pd = pay_d.get(i, {})
    dsig = pd.get("dsig", 0)
    f = {}
    f["_cell"] = (d, r["tc_mul"][1]); f["_g"] = g
    f["_pay"] = r["tc_payload"]
    f["dlow3"] = dsig & 7
    f["dlow4"] = dsig & 15
    f["dlow6"] = dsig & 63
    f["dlow8"] = dsig & 255
    f["dbit3"] = (dsig >> 3) & 1
    f["fneg"] = pd.get("fneg", -1)
    f["dsign"] = pd.get("dsign", -1)
    f["rsn"] = r.get("red_rsn", -1)
    f["i0"] = r.get("red_i0", -1)
    f["i1"] = r.get("red_i1", -1)
    f["site"] = r.get("poly_site", -1)
    f["fneg_x_dlow3"] = (pd.get("fneg", 0) << 3) | (dsig & 7)
    f["ls_x_dlow3"] = (ls << 3) | (dsig & 7)
    f["rsh"] = r["tc_rsh"]; f["u5d"] = r["tc_u5d"]; f["ud"] = r["tc_ud"]
    f["low3"] = r["tc_low3"]
    f["rsh_x_dlow3"] = ((r["tc_rsh"] & 1) << 3) | (dsig & 7)
    return f

recs = []
for i, r in enumerate(table):
    if r["seed"] < SPLIT:
        recs.append((derive(i, r), r["hwlab"], r["seed"]))
print("train ops:", len(recs))

tup = lambda f: (f["_cell"], f["_g"], f["_pay"])
base = defaultdict(Counter)
for f, y, s in recs: base[tup(f)][y] += 1
base_err = sum(sum(c.values()) - max(c.values()) for c in base.values())
print("baseline tuple ceiling:", base_err)

# corrected xval: learn per-bin majority on even seeds; score odd
# seeds; UNSEEN bin falls back to the even-side TUPLE majority (or
# global FIRE if tuple unseen).
def xval(featfn):
    maj = defaultdict(Counter); tmaj = defaultdict(Counter)
    oc = []
    for f, y, s in recs:
        if s % 2 == 0:
            maj[(tup(f), featfn(f))][y] += 1
            tmaj[tup(f)][y] += 1
        else:
            oc.append((f, y))
    err = 0
    for f, y in oc:
        k = (tup(f), featfn(f))
        if k in maj: pred = maj[k].most_common(1)[0][0]
        elif tup(f) in tmaj: pred = tmaj[tup(f)].most_common(1)[0][0]
        else: pred = "FIRE"
        if pred != y: err += 1
    return err

t_base = xval(lambda f: 0)
print("tuple-majority xval baseline:", t_base)
rows = []
for feat in sorted(recs[0][0]):
    if feat.startswith("_"): continue
    raw = defaultdict(Counter)
    for f, y, s in recs: raw[(tup(f), f[feat])][y] += 1
    err = sum(sum(c.values()) - max(c.values()) for c in raw.values())
    rows.append((xval(lambda f, ft=feat: f[ft]), err, feat))
rows.sort()
print("%-14s %7s %7s" % ("feature", "xval", "raw"))
for xv, err, feat in rows:
    print("%-14s %7d %7d" % (feat, xv, err))
