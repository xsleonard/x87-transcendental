#!/usr/bin/env python3
"""h423: classify informative rows as ADD- vs MERGE-consistent; learn gate."""
import collections

BASE = "/home/coduoserver/fsincos-residual-20260807-1"
MODES = ("rn", "rd", "ru")

def parse_trace(line):
    d = {}
    for tok in line.split()[1:]:
        k, v = tok.split("=")
        d[k] = v
    return d

def chop67(acc, scale):
    neg = acc < 0
    mag = -acc if neg else acc
    w = mag.bit_length()
    sh = max(w - 67, 0)
    mag >>= sh
    return (-mag if neg else mag), scale + sh

def final_cos(corr, ce2, mode):
    num = (1 << -ce2) + corr
    w = num.bit_length()
    sh = w - 64
    if sh <= 0: return num << -sh
    kept = num >> sh
    rem = num & ((1 << sh) - 1)
    half = 1 << (sh - 1)
    inc = 0
    if mode == "rn":
        if rem > half or (rem == half and (kept & 1)): inc = 1
    elif mode == "ru":
        if rem: inc = 1
    kept += inc
    if kept >> 64: kept >>= 1
    return kept

def variants(d):
    le2 = int(d["le2"]); re2 = int(d["re2"])
    ls = int(d["ls"], 16); rs = int(d["rs"], 16)
    lsign = int(d["lsign"]); rsign = int(d["rsign"])
    p = int(d["payload"])
    scale = min(le2, re2)
    if p: scale = min(scale, le2 - 8)
    base = (-1 if lsign else 1) * (ls << (le2 - scale)) \
         + (-1 if rsign else 1) * (rs << (re2 - scale))
    pos = le2 - 8 - scale
    add = base + ((-1 if lsign else 1) * (p << pos))
    neg = base < 0
    mag = -base if neg else base
    fld = (mag >> pos) & 0xFF
    m_or = mag + (((fld | p) - fld) << pos)
    m_xor = mag + (((fld ^ p) - fld) << pos)
    return {
        "add": chop67(add, scale),
        "or": chop67(-m_or if neg else m_or, scale),
        "xor": chop67(-m_xor if neg else m_xor, scale),
    }

def sq_features(x_sig):
    # upstream: square = chop67(a*a); a = x directly (direct path, e=-3)
    prod = x_sig * x_sig
    w = prod.bit_length()
    sh = max(w - 67, 0)
    disc = prod & ((1 << sh) - 1)
    top8 = (disc >> (sh - 8)) if sh >= 8 else disc << (8 - sh)
    sq = prod >> sh
    # fourth = chop67(sq*sq)
    p2 = sq * sq
    w2 = p2.bit_length()
    sh2 = max(w2 - 67, 0)
    disc2 = p2 & ((1 << sh2) - 1)
    top8b = (disc2 >> (sh2 - 8)) if sh2 >= 8 else disc2 << (8 - sh2)
    return {
        "sq_disc_top8": int(top8) & 0xFF, "sq_disc_nz": 1 if disc else 0,
        "sq_low3": int(sq) & 7, "sq_low8": int(sq) & 0xFF,
        "f4_disc_top8": int(top8b) & 0xFF, "f4_disc_nz": 1 if disc2 else 0,
        "f4_low3": int(sq*sq >> sh2) & 7,
    }

rows = []
inputs = [l.split() for l in open(f"{BASE}/h422/selected_inputs.txt")]
traces = open(f"{BASE}/h422/selected_traces.txt").read().splitlines()
hw = {m: [l.split() for l in open(f"{BASE}/h422/hw_{m}.txt")] for m in MODES}
for i, tr in enumerate(traces):
    d = parse_trace(tr)
    hw_sigs = {m: int(hw[m][i][2], 16) for m in MODES}
    v = variants(d)
    ok = {}
    for name, (c, e) in v.items():
        ok[name] = all(final_cos(c, e, m) == hw_sigs[m] for m in MODES)
    x_sig = int(inputs[i][1], 16)
    p = int(d["payload"])
    le2 = int(d["le2"]); re2 = int(d["re2"])
    rs = int(d["rs"], 16)
    lane_shift = (le2 - 8) - re2
    lane_full = rs >> lane_shift if lane_shift >= 0 else rs << -lane_shift
    lane = lane_full & 0xFF
    diff = (lane - p) & 0xFF
    if diff >= 128: diff -= 256
    feats = {
        "dist": int(d["dist"]), "low3": int(d["low3"]), "diff": diff,
        "ud": int(d["ud"]), "u5d": int(d["u5d"]), "rud": int(d["rud"]),
        "p": p, "lane": lane,
    }
    feats.update(sq_features(x_sig))
    rows.append((feats, ok))

cnt = collections.Counter()
for f, ok in rows:
    cnt[(ok["add"], ok["or"], ok["xor"])] += 1
print("=== consistency classes (add, or, xor): count ===")
for k in sorted(cnt): print("  ", k, cnt[k])

# learn gate between ADD-only and MERGE-only (or/xor) rows
addonly = [f for f, ok in rows if ok["add"] and not ok["or"] and not ok["xor"]]
mergeonly = [f for f, ok in rows if not ok["add"] and (ok["or"] or ok["xor"])]
neither = [f for f, ok in rows if not ok["add"] and not ok["or"] and not ok["xor"]]
print(f"add-only: {len(addonly)}  merge-only: {len(mergeonly)}  neither: {len(neither)}")
if mergeonly:
    for feat in addonly[0].keys():
        av = collections.Counter(f[feat] for f in addonly)
        mv = collections.Counter(f[feat] for f in mergeonly)
        # report features with disjoint or near-disjoint supports
        a_set, m_set = set(av), set(mv)
        inter = a_set & m_set
        if len(inter) <= max(1, min(len(a_set), len(m_set)) // 4):
            print(f"  near-separating feature {feat}: add={dict(av)} merge={dict(mv)}")
