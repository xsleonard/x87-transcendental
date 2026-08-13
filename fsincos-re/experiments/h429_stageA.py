#!/usr/bin/env python3
"""h429 Stage A: constraint database for boolean-gate synthesis.

For every active row across the hostile sets and the h422 corpus, compute:
  - the mechanism-consistency bitmask: which candidate mechanisms
    reproduce the hardware result in all three rounding modes;
  - ~40 physical datapath signals for gate synthesis.
Output: /root/search/h429_rows.pkl
"""
import collections, pickle
from multiprocessing import Pool

MODES = ("rn", "rd", "ru")
SETS = [("h363", "captures/skylake-fcos-h363", "h412/h363_trace.txt"),
        ("h372", "captures/skylake-fcos-h372", "h412/h372_trace.txt"),
        ("h380", "captures/skylake-fcos-h380", "h412/h380_trace.txt"),
        ("h384", "captures/skylake-fcos-h384", "h412/h384_trace.txt")]

MECHS = (["add"] + [f"p{k:+d}" for k in range(-6, 7) if k]
         + ["lane", "or", "xor"])

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
    if sh <= 0:
        return num << -sh
    kept = num >> sh
    rem = num & ((1 << sh) - 1)
    half = 1 << (sh - 1)
    inc = 0
    if mode == "rn":
        if rem > half or (rem == half and (kept & 1)):
            inc = 1
    elif mode == "ru":
        if rem:
            inc = 1
    kept += inc
    if kept >> 64:
        kept >>= 1
    return kept

def run_length_ones(v, frombit):
    n = 0
    while (v >> (frombit + n)) & 1:
        n += 1
    return min(n, 15)

def build_row(args):
    d, hws = args
    p = int(d["payload"])
    le2 = int(d["le2"]); re2 = int(d["re2"])
    ls = int(d["ls"], 16); rs = int(d["rs"], 16)
    lsign = int(d["lsign"]); rsign = int(d["rsign"])
    scale = min(le2, re2)
    if p:
        scale = min(scale, le2 - 8)
    base = (-1 if lsign else 1) * (ls << (le2 - scale)) \
         + (-1 if rsign else 1) * (rs << (re2 - scale))
    pos = le2 - 8 - scale
    lane_shift = (le2 - 8) - re2
    lane_full = rs >> lane_shift if lane_shift >= 0 else rs << -lane_shift
    lane = lane_full & 0xFF

    def with_payload(val):
        acc = base + ((-1 if lsign else 1) * (val << pos)) if val else base
        return chop67(acc, scale)

    def merged(op):
        neg = base < 0
        mag = -base if neg else base
        fld = (mag >> pos) & 0xFF
        nf = (fld | p) if op == "or" else (fld ^ p)
        mag2 = mag + ((nf - fld) << pos)
        return chop67(-mag2 if neg else mag2, scale)

    cands = {"add": with_payload(p), "lane": with_payload(lane),
             "or": merged("or"), "xor": merged("xor")}
    for k in range(-6, 7):
        if k:
            cands[f"p{k:+d}"] = with_payload(max(p + k, 0))
    mask = 0
    for bit, name in enumerate(MECHS):
        c, e = cands[name]
        if all(final_cos(c, e, m) == hws[m] for m in MODES):
            mask |= 1 << bit

    magb = -base if base < 0 else base
    diff = (lane - p) & 0xFF
    if diff >= 128:
        diff -= 256
    addacc = base + ((-1 if lsign else 1) * (p << pos)) if p else base
    amag = -addacc if addacc < 0 else addacc
    aw = amag.bit_length()
    cut = max(aw - 67, 0)
    sig = {
        "dist": le2 - re2 if le2 >= re2 else re2 - le2,
        "low3": int(d["low3"]), "p": p, "lane": lane,
        "diff": diff, "lane9": (lane_full >> 8) & 1,
        "ud": int(d["ud"]), "u5d": min(int(d["u5d"]), 31),
        "rud": int(d["rud"]),
        "lsign": lsign, "rsign": rsign,
        "borrow_in": 1 if (magb & ((1 << pos) - 1)) else 0,
        "sum_byte": (magb >> pos) & 0xFF,
        "run_pos": run_length_ones(magb, pos),
        "run_pos8": run_length_ones(magb, pos + 8),
        "cut_guard": (amag >> (cut - 1)) & 1 if cut else 0,
        "cut_sticky": 1 if cut > 1 and (amag & ((1 << (cut - 1)) - 1)) else 0,
        "ls_low8": ls & 0xFF, "rs_low8": rs & 0xFF,
        "lane_below3": (lane_full >> 5) & 7 if lane_shift >= 0 else 0,
        "p_par": p & 1, "lane_par": lane & 1,
        "pos_mod4": pos & 3, "le2_mod4": le2 & 3,
        "sq_low8": int(d["mul"][16:], 16) & 0xFF if "mul" in d else 0,
    }
    return sig, mask

def load_rows():
    out = []
    for name, capdir, trpath in SETS:
        traces = open(trpath).read().splitlines()
        hw = {m: [l.split() for l in open(f"{capdir}/fcos_{m}_status.txt")]
              for m in MODES}
        for i, tr in enumerate(traces):
            d = parse_trace(tr)
            if d["active"] != "1":
                continue
            out.append((d, {m: int(hw[m][i][2], 16) for m in MODES}))
    traces = open("h422/selected_traces.txt").read().splitlines()
    hw = {m: [l.split() for l in open(f"h422/hw_{m}.txt")] for m in MODES}
    for i, tr in enumerate(traces):
        d = parse_trace(tr)
        out.append((d, {m: int(hw[m][i][2], 16) for m in MODES}))
    return out

if __name__ == "__main__":
    raw = load_rows()
    print(f"rows: {len(raw)}", flush=True)
    with Pool(7) as pool:
        rows = pool.map(build_row, raw, chunksize=2000)
    n_add = sum(1 for _, m in rows if m & 1)
    n_none = sum(1 for _, m in rows if m == 0)
    informative = sum(1 for _, m in rows if not (m & 1))
    print(f"add-consistent: {n_add}  not-add (informative): {informative} "
          f"no-mechanism: {n_none}", flush=True)
    with open("h429_rows.pkl", "wb") as f:
        pickle.dump({"mechs": MECHS, "rows": rows}, f)
    print("wrote h429_rows.pkl", flush=True)
