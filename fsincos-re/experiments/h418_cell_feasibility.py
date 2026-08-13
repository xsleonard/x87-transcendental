#!/usr/bin/env python3
"""h418: allowed-delta sets for all near-collision rows; cell feasibility."""
import collections, itertools

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
        rsig = int(d["rs"], 16)
        lane_shift = (le2 - 8) - re2
        lane_full = rsig >> lane_shift if lane_shift >= 0 else rsig << -lane_shift
        lane = lane_full & 0xFF
        diff = (lane - p) & 0xFF
        if diff >= 128: diff -= 256
        if abs(diff) > 2: continue
        hw_sigs = {m: int(hw[m][i][2], 16) for m in MODES}
        allowed = frozenset(
            k for k in range(-6, 7)
            if all(final_cos(*correction(d, p + k), m) == hw_sigs[m] for m in MODES))
        rows.append({
            "set": s, "i": i, "p": p, "lane": lane, "diff": diff,
            "dist": int(d["dist"]), "low3": int(d["low3"]),
            "ud": int(d["ud"]), "u5d": int(d["u5d"]), "rud": int(d["rud"]),
            "lane_bit0": lane & 1, "lane_full_low": lane_full & 0x1FF,
            "miss": i in miss_idx, "allowed": allowed,
        })
print(f"near-collision active rows: {len(rows)}  (misses: {sum(r['miss'] for r in rows)})")

def feasibility(keys):
    cells = collections.defaultdict(lambda: frozenset(range(-6, 7)))
    members = collections.Counter()
    for r in rows:
        key = tuple(r[k] for k in keys)
        cells[key] &= r["allowed"]
        members[key] += 1
    bad = [(k, members[k]) for k, v in cells.items() if not v]
    return cells, bad

for keys in (("diff",), ("diff","dist"), ("diff","low3"), ("diff","dist","low3"),
             ("diff","dist","low3","ud"), ("diff","dist","low3","rud"),
             ("diff","dist","low3","u5d")):
    cells, bad = feasibility(keys)
    print(f"keys={keys}: cells={len(cells)} infeasible={len(bad)}")
    if not bad:
        nonzero = {k: sorted(v) for k, v in cells.items() if 0 not in v}
        print("   cells requiring nonzero delta:", len(nonzero))
        for k in sorted(nonzero)[:20]: print("     ", k, nonzero[k])
        break
