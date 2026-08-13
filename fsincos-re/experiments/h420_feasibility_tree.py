#!/usr/bin/env python3
"""h420: greedy feasibility tree over fine features for the payload delta."""
import collections

BASE = "/home/coduoserver/fsincos-residual-20260807-1"
SETS = ["h363", "h372", "h380", "h384"]
MODES = ("rn", "rd", "ru")

def parse_trace(line):
    d = {}
    for tok in line.split()[1:]:
        k, v = tok.split("=")
        d[k] = v
    return d

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

rows = []
for s in SETS:
    traces = open(f"{BASE}/h412/{s}_trace.txt").read().splitlines()
    miss_idx = set()
    for l in open(f"{BASE}/h411/{s}_misses.txt"):
        miss_idx.add(int(l.split()[0]))
    hw = {m: [l.split() for l in open(f"{BASE}/captures/skylake-fcos-{s}/fcos_{m}_status.txt")] for m in MODES}
    for i, tr in enumerate(traces):
        d = parse_trace(tr)
        if d["active"] != "1": continue
        p = int(d["payload"])
        le2 = int(d["le2"]); re2 = int(d["re2"])
        ls = int(d["ls"], 16); rs = int(d["rs"], 16)
        lane_shift = (le2 - 8) - re2
        lane_full = rs >> lane_shift if lane_shift >= 0 else rs << -lane_shift
        lane = lane_full & 0xFF
        diff = (lane - p) & 0xFF
        if diff >= 128: diff -= 256
        if abs(diff) > 2: continue
        hw_sigs = {m: int(hw[m][i][2], 16) for m in MODES}
        allowed = frozenset(
            k for k in range(-6, 7)
            if all(final_cos(*correction(d, p + k), m) == hw_sigs[m] for m in MODES))
        below = rs & ((1 << lane_shift) - 1) if lane_shift > 0 else 0
        feats = {
            "dist": int(d["dist"]), "low3": int(d["low3"]), "diff": diff,
            "ud": int(d["ud"]), "u5d": int(d["u5d"]), "rud": int(d["rud"]),
            "p_par": p & 1, "lane_par": lane & 1,
            "lane9": (lane_full >> 8) & 1,
            "below_nz": 1 if below else 0,
            "ls0": ls & 1, "ls1": (ls >> 1) & 1, "ls2": (ls >> 2) & 1,
            "lslow3": ls & 7,
            "rs0": rs & 1,
            "udges3": 1 if int(d["ud"]) >= 3 else 0,
            "u5dges3": 1 if int(d["u5d"]) >= 3 else 0,
        }
        rows.append((feats, allowed, i in miss_idx))
print(f"rows: {len(rows)} misses: {sum(r[2] for r in rows)}")

FEATNAMES = list(rows[0][0].keys())

def feasible(group):
    inter = frozenset(range(-6, 7))
    for f, a, m in group:
        inter &= a
        if not inter: return None
    return inter

def build(group, depth, path):
    inter = feasible(group)
    if inter is not None:
        return [("LEAF", path, sorted(inter), len(group))]
    if depth == 0:
        return [("FAIL", path, None, len(group))]
    best = None
    for fn in FEATNAMES:
        vals = sorted({g[0][fn] for g in group})
        if len(vals) < 2: continue
        # try binary threshold splits
        for v in vals[1:]:
            lo = [g for g in group if g[0][fn] < v]
            hi = [g for g in group if g[0][fn] >= v]
            nf = (feasible(lo) is None) + (feasible(hi) is None)
            score = (nf, min(len(lo), len(hi)) * -1)
            if best is None or score < best[0]:
                best = (score, fn, v, lo, hi)
    if best is None:
        return [("FAIL", path, None, len(group))]
    _, fn, v, lo, hi = best
    return build(lo, depth-1, path + [f"{fn}<{v}"]) + \
           build(hi, depth-1, path + [f"{fn}>={v}"])

leaves = build(rows, 6, [])
fails = [l for l in leaves if l[0] == "FAIL"]
print(f"leaves: {len(leaves)}  failed: {len(fails)}")
for l in leaves:
    kind, path, inter, n = l
    tag = "&".join(path) if path else "(root)"
    print(f"  {kind} n={n} deltas={inter} :: {tag}")
