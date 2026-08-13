#!/usr/bin/env python3
"""h417: per-miss inversion — which payload perturbation explains hardware?"""
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

results = []
for s in SETS:
    traces = open(f"{BASE}/h412/{s}_trace.txt").read().splitlines()
    miss_idx = set()
    for l in open(f"{BASE}/h411/{s}_misses.txt"):
        miss_idx.add(int(l.split()[0]))
    hw = {m: [l.split() for l in open(f"{BASE}/captures/skylake-fcos-{s}/fcos_{m}_status.txt")] for m in MODES}
    for i in sorted(miss_idx):
        d = parse_trace(traces[i])
        p = int(d["payload"])
        le2 = int(d["le2"]); re2 = int(d["re2"])
        rsig = int(d["rs"], 16)
        lane_shift = (le2 - 8) - re2
        lane = (rsig >> lane_shift if lane_shift >= 0 else rsig << -lane_shift) & 0xFF
        hw_sigs = {m: int(hw[m][i][2], 16) for m in MODES}
        # candidates: absolute payload values
        cands = sorted(set(
            [p + k for k in range(-3, 4)] + [lane + j for j in range(-3, 4)]))
        ok = []
        for cand in cands:
            good = all(final_cos(*correction(d, cand), m) == hw_sigs[m] for m in MODES)
            if good: ok.append(cand)
        diff = (lane - p) & 0xFF
        if diff >= 128: diff -= 256
        results.append((s, i, d["dist"], d["low3"], p, lane, diff,
                        d["ud"], d["u5d"], d["rud"], ok))

agg = collections.Counter()
for r in results:
    s, i, dist, low3, p, lane, diff, ud, u5d, rud, ok = r
    delta = tuple(c - p for c in ok)
    agg[(dist, low3, diff, delta)] += 1
print("=== miss rows grouped by (dist, low3, lane-payload diff, working payload deltas) ===")
for k in sorted(agg):
    print("  ", k, agg[k])
nosol = [r for r in results if not r[10]]
print(f"miss rows with no single-payload solution: {len(nosol)} / {len(results)}")
for r in nosol[:8]: print("   nosol:", r[:10])
