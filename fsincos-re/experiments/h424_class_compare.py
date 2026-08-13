#!/usr/bin/env python3
"""h424: feature distributions add-only vs merge-only; invert neither-rows."""
import collections, sys
sys.path.insert(0, "/home/coduoserver/fsincos-residual-20260807-1")
exec(open("/home/coduoserver/fsincos-residual-20260807-1/h423_gate_learning.py").read().split("rows = []")[0])

BASE = "/home/coduoserver/fsincos-residual-20260807-1"
rows = []
inputs = [l.split() for l in open(f"{BASE}/h422/selected_inputs.txt")]
traces = open(f"{BASE}/h422/selected_traces.txt").read().splitlines()
hw = {m: [l.split() for l in open(f"{BASE}/h422/hw_{m}.txt")] for m in MODES}
def correction(d, payload):
    le2 = int(d["le2"]); re2 = int(d["re2"])
    ls = int(d["ls"], 16); rs = int(d["rs"], 16)
    lsign = int(d["lsign"]); rsign = int(d["rsign"])
    scale = min(le2, re2)
    if payload: scale = min(scale, le2 - 8)
    acc = (-1 if lsign else 1) * (ls << (le2 - scale)) \
        + (-1 if rsign else 1) * (rs << (re2 - scale))
    if payload:
        acc += (-1 if lsign else 1) * (payload << (le2 - 8 - scale))
    return chop67(acc, scale)
for i, tr in enumerate(traces):
    d = parse_trace(tr)
    hw_sigs = {m: int(hw[m][i][2], 16) for m in MODES}
    v = variants(d)
    ok = {n: all(final_cos(c, e, m) == hw_sigs[m] for m in MODES) for n, (c, e) in v.items()}
    x_sig = int(inputs[i][1], 16)
    p = int(d["payload"])
    le2 = int(d["le2"]); re2 = int(d["re2"])
    rs = int(d["rs"], 16)
    lane_shift = (le2 - 8) - re2
    lane_full = rs >> lane_shift if lane_shift >= 0 else rs << -lane_shift
    lane = lane_full & 0xFF
    diff = (lane - p) & 0xFF
    if diff >= 128: diff -= 256
    feats = {"dist": int(d["dist"]), "low3": int(d["low3"]), "diff": diff,
             "ud": int(d["ud"]), "u5d": min(int(d["u5d"]),8), "rud": int(d["rud"]),
             "lane_par": lane & 1, "p_par": p & 1}
    feats.update({k: v2 for k, v2 in sq_features(x_sig).items() if k in ("sq_low3","f4_low3","sq_disc_top8")})
    feats["sq_disc_top3"] = feats.pop("sq_disc_top8") >> 5
    cls = ("add" if ok["add"] else "") + ("merge" if (ok["or"] or ok["xor"]) and not ok["add"] else "")
    if not ok["add"] and not ok["or"] and not ok["xor"]: cls = "neither"
    if ok["add"] and (ok["or"] or ok["xor"]): cls = "both"
    rows.append((feats, cls, d, hw_sigs, p))

for feat in rows[0][0]:
    a = collections.Counter(f[feat] for f, c, *_ in rows if c == "add")
    m = collections.Counter(f[feat] for f, c, *_ in rows if c == "merge")
    print(f"{feat}: add={dict(sorted(a.items()))} merge={dict(sorted(m.items()))}")
print("=== neither rows: allowed payload deltas ===")
cnt = collections.Counter()
for f, c, d, hw_sigs, p in rows:
    if c != "neither": continue
    ok = [k for k in range(-6,7)
          if all(final_cos(*correction(d, p+k), m) == hw_sigs[m] for m in MODES)]
    cnt[(f["dist"], f["low3"], f["diff"], tuple(ok))] += 1
for k in sorted(cnt): print("  ", k, cnt[k])
