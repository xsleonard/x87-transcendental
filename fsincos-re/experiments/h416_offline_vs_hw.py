#!/usr/bin/env python3
"""h416: does the plain offline reconstruction equal HARDWARE at the misses?"""
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
        acc += (-1 if lsign else 1) * (payload << (le2 - 8 - scale))
    neg = acc < 0
    mag = -acc if neg else acc
    w = mag.bit_length()
    sh = max(w - 67, 0)
    sticky = mag & ((1 << sh) - 1) if sh else 0
    mag >>= sh
    return (-mag if neg else mag), scale + sh, sticky != 0

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

match_hw = match_model = neither = 0
examples = []
for s in SETS:
    traces = open(f"{BASE}/h412/{s}_trace.txt").read().splitlines()
    miss = collections.defaultdict(dict)
    for l in open(f"{BASE}/h411/{s}_misses.txt"):
        t = l.split()
        miss[int(t[0])][t[1]] = (int(t[4],16), int(t[6],16))  # hw_sig, model_sig
    for i, tr in enumerate(traces):
        if i not in miss: continue
        d = parse_trace(tr)
        p = int(d["payload"])
        c0, e0, _ = correction(d, p)
        for m, (hw_sig, model_sig) in miss[i].items():
            r0 = final_cos(c0, e0, m)
            if r0 == hw_sig: match_hw += 1
            elif r0 == model_sig: match_model += 1
            else: neither += 1
            if len(examples) < 6:
                examples.append((s, i, m, hex(hw_sig), hex(model_sig), hex(r0), d["dist"], d["low3"], d["payload"]))
print(f"offline==hardware: {match_hw}  offline==model: {match_model}  neither: {neither}")
for e in examples: print("  ", e)
