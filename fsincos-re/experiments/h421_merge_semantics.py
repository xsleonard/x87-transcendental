#!/usr/bin/env python3
"""h421: OR/XOR payload merge variants on all active rows."""
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

def models(d):
    le2 = int(d["le2"]); re2 = int(d["re2"])
    ls = int(d["ls"], 16); rs = int(d["rs"], 16)
    lsign = int(d["lsign"]); rsign = int(d["rsign"])
    p = int(d["payload"])
    scale = min(le2, re2)
    if p: scale = min(scale, le2 - 8)
    base = (-1 if lsign else 1) * (ls << (le2 - scale)) \
         + (-1 if rsign else 1) * (rs << (re2 - scale))
    pos = le2 - 8 - scale
    out = {}
    # M0 arithmetic add (current)
    out["m0"] = base + ((-1 if lsign else 1) * (p << pos)) if p else base
    if p:
        # M2: OR payload into right product's aligned byte (pre-subtract)
        lane_shift = (le2 - 8) - re2
        if lane_shift >= 0:
            fld = (rs >> lane_shift) & 0xFF
            rs2 = rs + (((fld | p) - fld) << lane_shift)
        else:
            rsx = rs << -lane_shift
            fld = rsx & 0xFF
            rs2 = (rsx + ((fld | p) - fld)) >> -lane_shift if False else rs  # sub-lsb OR undefined; keep rs
        out["m2"] = (-1 if lsign else 1) * (ls << (le2 - scale)) \
                  + (-1 if rsign else 1) * (rs2 << (re2 - scale))
        # M5: XOR payload into |acc| byte at pos
        neg = base < 0
        mag = -base if neg else base
        fld = (mag >> pos) & 0xFF
        mag5 = mag + (((fld ^ p) - fld) << pos)
        out["m5"] = -mag5 if neg else mag5
        # M6: OR payload into |acc| byte at pos
        fld = (mag >> pos) & 0xFF
        mag6 = mag + (((fld | p) - fld) << pos)
        out["m6"] = -mag6 if neg else mag6
    else:
        out["m2"] = out["m5"] = out["m6"] = base
    return {k: chop67(v, scale) for k, v in out.items()}

score = {k: [0, 0] for k in ("m0", "m2", "m5", "m6")}
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
        for name, (c, e) in models(d).items():
            ok = all(final_cos(c, e, m) == hw_sigs[m] for m in MODES)
            if i in miss_idx:
                if ok: score[name][1] += 1
            else:
                if not ok: score[name][0] += 1
for k in ("m0", "m2", "m5", "m6"):
    print(f"{k}: exact_broken={score[k][0]} misses_fixed={score[k][1]}/104")
