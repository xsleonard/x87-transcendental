#!/usr/bin/env python3
"""h415: boundary-sensitivity analysis of the terminal payload.

For each hostile row, reconstruct the correction exactly from the trace,
compute the final cosine under payload and payload-1, find rows where the
two differ (boundary rows), and test whether the misses are exactly the
boundary rows selected by a clean feature.
"""
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
    acc = 0
    acc += (-1 if lsign else 1) * (ls << (le2 - scale))
    acc += (-1 if rsign else 1) * (rs << (re2 - scale))
    if payload:
        acc += (-1 if (lsign ^ (payload < 0)) else 1) * (abs(payload) << (le2 - 8 - scale))
    # chop67
    neg = acc < 0
    mag = -acc if neg else acc
    if mag == 0: return 0, 0, False
    w = mag.bit_length()
    sh = w - 67
    if sh > 0: mag >>= sh
    else: sh = 0
    return (-mag if neg else mag), scale + sh, neg

def final_cos(corr, ce2, mode):
    # result = round64(1 + corr * 2^ce2), corr negative; positive result < 1
    # exact value as fraction with denominator 2^-ce2 (ce2 negative)
    num = (1 << -ce2) + corr    # 1 + correction
    # normalize to 64-bit significand: value in (0,1): exponent -1 typically
    w = num.bit_length()
    sh = w - 64
    if sh <= 0:
        return num << -sh, w + ce2 - 1, 0
    kept = num >> sh
    rem = num & ((1 << sh) - 1)
    half = 1 << (sh - 1)
    inc = 0
    if mode == "rn":
        if rem > half or (rem == half and (kept & 1)): inc = 1
    elif mode == "ru":
        if rem: inc = 1
    # rd: truncate (positive value)
    kept += inc
    if kept >> 64:
        kept >>= 1
        w += 1
    return kept, w + ce2 - 1, inc

rows = []
for s in SETS:
    traces = open(f"{BASE}/h412/{s}_trace.txt").read().splitlines()
    miss = collections.defaultdict(dict)
    for l in open(f"{BASE}/h411/{s}_misses.txt"):
        t = l.split()
        miss[int(t[0])][t[1]] = (t[3], t[4], t[5], t[6])
    hwsig = {}
    for m in MODES:
        hwsig[m] = [l.split() for l in open(f"{BASE}/captures/skylake-fcos-{s}/fcos_{m}_status.txt")]
    for i, tr in enumerate(traces):
        d = parse_trace(tr)
        rows.append((s, i, d, miss.get(i, {}), {m: hwsig[m][i] for m in MODES}))

sane = insane = 0
boundary = []
for s, i, d, mm, hw in rows:
    if d["active"] != "1": continue
    p = int(d["payload"])
    c0, e0, _ = correction(d, p)
    c1, e1, _ = correction(d, p - 1)
    diffmodes = []
    for m in MODES:
        r0 = final_cos(c0, e0, m)
        r1 = final_cos(c1, e1, m)
        # sanity: r0 should equal model output = hw output unless miss
        model_sig = int(hw[m][2], 16) if m not in mm else int(mm[m][3], 16)
        if r0[0] == model_sig: sane += 1
        else: insane += 1
        if r0[0] != r1[0]: diffmodes.append(m)
    if diffmodes:
        boundary.append((s, i, d, mm, diffmodes))
print(f"offline-model sanity: match={sane} mismatch={insane}")
print(f"boundary rows (payload-1 changes some mode): {len(boundary)}")
n_miss_boundary = sum(1 for b in boundary if b[3])
total_miss_rows = sum(1 for s,i,d,mm,hw in rows if mm)
print(f"boundary rows that are misses: {n_miss_boundary} / misses total rows: {total_miss_rows}")
# among boundary rows: feature table
import sys
feat = collections.Counter()
for s, i, d, mm, dm in boundary:
    le2 = int(d["le2"]); re2 = int(d["re2"])
    rsig = int(d["rs"], 16)
    p = int(d["payload"])
    lane_shift = (le2 - 8) - re2
    lane = rsig >> lane_shift if lane_shift >= 0 else rsig << -lane_shift
    diff = ((lane & 0xFF) - p) & 0xFF
    if diff >= 128: diff -= 256
    feat[(diff, bool(mm))] += 1
print("=== boundary rows by (lane-payload diff, is_miss) ===")
for k in sorted(feat): print("  ", k, feat[k])
