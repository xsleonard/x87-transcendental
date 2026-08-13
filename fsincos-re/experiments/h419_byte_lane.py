#!/usr/bin/env python3
"""h419: test the carry-dropped 8-bit payload lane mechanism on all rows."""
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

def build_acc(d, with_payload_add=None):
    le2 = int(d["le2"]); re2 = int(d["re2"])
    ls = int(d["ls"], 16); rs = int(d["rs"], 16)
    lsign = int(d["lsign"]); rsign = int(d["rsign"])
    p = int(d["payload"])
    scale = min(le2, re2)
    if p: scale = min(scale, le2 - 8)
    acc = (-1 if lsign else 1) * (ls << (le2 - scale)) \
        + (-1 if rsign else 1) * (rs << (re2 - scale))
    return acc, scale, le2, lsign, p

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

def model_m0(d):
    acc, scale, le2, lsign, p = build_acc(d)
    if p:
        acc += (-1 if lsign else 1) * (p << (le2 - 8 - scale))
    return chop67(acc, scale)

def model_m1(d):
    acc, scale, le2, lsign, p = build_acc(d)
    if p:
        pos = le2 - 8 - scale
        delta = (-1 if lsign else 1) * p
        field = (acc >> pos) & 0xFF
        nfield = (field + delta) & 0xFF
        acc += (nfield - field) << pos
    return chop67(acc, scale)

score = {"m0": [0, 0], "m1": [0, 0]}   # [exact-row misses, miss-row fixes]
m1_breaks = []
for s in SETS:
    traces = open(f"{BASE}/h412/{s}_trace.txt").read().splitlines()
    miss_idx = set()
    for l in open(f"{BASE}/h411/{s}_misses.txt"):
        miss_idx.add(int(l.split()[0]))
    hw = {m: [l.split() for l in open(f"{BASE}/captures/skylake-fcos-{s}/fcos_{m}_status.txt")] for m in MODES}
    for i, tr in enumerate(traces):
        d = parse_trace(tr)
        if d["active"] != "1": continue
        hw_sigs = {m: int(hw[m][i][2], 16) for m in MODES}
        for name, fn in (("m0", model_m0), ("m1", model_m1)):
            c, e = fn(d)
            ok = all(final_cos(c, e, m) == hw_sigs[m] for m in MODES)
            if i in miss_idx:
                if ok: score[name][1] += 1
            else:
                if not ok:
                    score[name][0] += 1
                    if name == "m1" and len(m1_breaks) < 6:
                        m1_breaks.append((s, i, d["dist"], d["low3"], d["payload"]))
total_miss = 104
print(f"M0 (current add): exact rows broken={score['m0'][0]}, miss rows fixed={score['m0'][1]}/{total_miss//1}")
print(f"M1 (byte-lane, carry dropped): exact rows broken={score['m1'][0]}, miss rows fixed={score['m1'][1]}")
for b in m1_breaks: print("  m1 breaks:", b)
