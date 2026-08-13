#!/usr/bin/env python3
"""h431: enriched signals (full discarded fields) + zone-restricted deep synthesis."""
import pickle, sys, time
from collections import Counter
from multiprocessing import Pool

MODES = ("rn", "rd", "ru")
SETS = [("h363", "captures/skylake-fcos-h363", "h412/h363_trace.txt"),
        ("h372", "captures/skylake-fcos-h372", "h412/h372_trace.txt"),
        ("h380", "captures/skylake-fcos-h380", "h412/h380_trace.txt"),
        ("h384", "captures/skylake-fcos-h384", "h412/h384_trace.txt")]
MECHS = (["add"] + [f"p{k:+d}" for k in range(-6, 7) if k] + ["lane", "or", "xor"])

def parse_trace(line):
    d = {}
    for tok in line.split()[1:]:
        k, v = tok.split("=")
        d[k] = v
    return d

def chop67(acc, scale):
    neg = acc < 0
    mag = -acc if neg else acc
    sh = max(mag.bit_length() - 67, 0)
    return ((-(mag >> sh)) if neg else (mag >> sh)), scale + sh

def final_cos(corr, ce2, mode):
    num = (1 << -ce2) + corr
    sh = num.bit_length() - 64
    if sh <= 0:
        return num << -sh
    kept, rem, half = num >> sh, num & ((1 << sh) - 1), 1 << (sh - 1)
    if (mode == "rn" and (rem > half or (rem == half and kept & 1))) or (mode == "ru" and rem):
        kept += 1
    if kept >> 64:
        kept >>= 1
    return kept

def build(args):
    d, hws = args
    p = int(d["payload"])
    le2, re2 = int(d["le2"]), int(d["re2"])
    ls, rs = int(d["ls"], 16), int(d["rs"], 16)
    lsign, rsign = int(d["lsign"]), int(d["rsign"])
    mul, lf = int(d["mul"], 16), int(d["lf"], 16)
    f4, rf = int(d["f4"], 16), int(d["rf"], 16)
    scale = min(le2, re2)
    if p:
        scale = min(scale, le2 - 8)
    base = (-1 if lsign else 1) * (ls << (le2 - scale)) + (-1 if rsign else 1) * (rs << (re2 - scale))
    pos = le2 - 8 - scale
    lane_shift = (le2 - 8) - re2
    lane_full = rs >> lane_shift if lane_shift >= 0 else rs << -lane_shift
    lane = lane_full & 0xFF

    def wp(val):
        return chop67(base + ((-1 if lsign else 1) * (val << pos)) if val else base, scale)

    def mg(op):
        neg = base < 0
        mag = -base if neg else base
        fld = (mag >> pos) & 0xFF
        nf = (fld | p) if op == "or" else (fld ^ p)
        m2 = mag + ((nf - fld) << pos)
        return chop67(-m2 if neg else m2, scale)

    cands = {"add": wp(p), "lane": wp(lane), "or": mg("or"), "xor": mg("xor")}
    for k in range(-6, 7):
        if k:
            cands[f"p{k:+d}"] = wp(max(p + k, 0))
    mask = 0
    for bit, name in enumerate(MECHS):
        c, e = cands[name]
        if all(final_cos(c, e, m) == hws[m] for m in MODES):
            mask |= 1 << bit

    # full discarded fields of the two chop67 products
    pl = mul * lf
    shl = max(pl.bit_length() - 67, 0)
    dl = pl & ((1 << shl) - 1)
    pr = f4 * rf
    shr = max(pr.bit_length() - 67, 0)
    dr = pr & ((1 << shr) - 1)
    dl_top16 = (dl >> (shl - 16)) if shl >= 16 else dl << (16 - shl)
    dr_top16 = (dr >> (shr - 16)) if shr >= 16 else dr << (16 - shr)
    diff = (lane - p) & 0xFF
    if diff >= 128:
        diff -= 256
    magb = -base if base < 0 else base
    sig = {
        "diff": diff, "dist": abs(le2 - re2), "low3": int(d["low3"]),
        "p": p, "lane": lane, "lane9": (lane_full >> 8) & 1,
        "lane10": (lane_full >> 9) & 1,
        "dl16": int(dl_top16) & 0xFFFF, "dr16": int(dr_top16) & 0xFFFF,
        "dl_nz": 1 if dl else 0, "dr_nz": 1 if dr else 0,
        "shl": shl, "shr": shr,
        "mul3": mul & 7, "lf3": lf & 7, "rf3": rf & 7, "f43": f4 & 7,
        "ls8": ls & 0xFF, "rs8": rs & 0xFF,
        "borrow": 1 if (magb & ((1 << pos) - 1)) else 0,
        "sum8": (magb >> pos) & 0xFF,
        "lsign": lsign, "rsign": rsign,
    }
    return sig, mask

def load():
    out = []
    for name, capdir, trpath in SETS:
        traces = open(trpath).read().splitlines()
        hw = {m: [l.split() for l in open(f"{capdir}/fcos_{m}_status.txt")] for m in MODES}
        for i, tr in enumerate(traces):
            d = parse_trace(tr)
            if d["active"] != "1":
                continue
            out.append((d, {m: int(hw[m][i][2], 16) for m in MODES}))
    traces = open("h422/selected_traces.txt").read().splitlines()
    hw = {m: [l.split() for l in open(f"h422/hw_{m}.txt")] for m in MODES}
    for i, tr in enumerate(traces):
        out.append((parse_trace(tr), {m: int(hw[m][i][2], 16) for m in MODES}))
    return out

if __name__ == "__main__":
    with Pool(8) as pool:
        rows = pool.map(build, load(), chunksize=2000)
    zone = [(s, m) for s, m in rows if -3 <= s["diff"] <= 3]
    outside_bad = sum(1 for s, m in rows if not (-3 <= s["diff"] <= 3) and not (m & 1))
    print(f"zone rows: {len(zone)}  informative in zone: {sum(1 for s,m in zone if not m&1)}"
          f"  outside-zone non-add rows: {outside_bad}", flush=True)
    FEATS = sorted(zone[0][0].keys())
    BYTE = {"p", "lane", "ls8", "rs8", "sum8", "dl16", "dr16"}
    def vec(s):
        v = []
        for f in FEATS:
            x = s[f]
            if f in BYTE:
                v.extend((x >> b) & 1 for b in range(16 if f.endswith("16") else 8))
            else:
                v.append(x)
        return tuple(v)
    NAMES = []
    for f in FEATS:
        if f in BYTE:
            NAMES.extend(f"{f}.b{b}" for b in range(16 if f.endswith("16") else 8))
        else:
            NAMES.append(f)
    gm, gc = {}, Counter()
    for s, m in zone:
        t = vec(s)
        gc[t] += 1
        gm[t] = gm.get(t, (1 << 20) - 1) & m
    ROWS = [(t, gm[t], gc[t]) for t in gm]
    print(f"unique vectors: {len(ROWS)}", flush=True)
    FULL = (1 << len(MECHS)) - 1
    def feas(rr):
        a = FULL
        for t, m, c in rr:
            a &= m
            if not a:
                return 0
        return a
    best_fail = [None]
    def search(rr, depth, path):
        a = feas(rr)
        if a:
            return [(path, a, sum(c for *_, c in rr))]
        if depth == 0:
            n = sum(c for *_, c in rr)
            if best_fail[0] is None or n < best_fail[0][0]:
                best_fail[0] = (n, path)
            return None
        scored = []
        nf = len(rr[0][0])
        for fi in range(nf):
            vals = sorted({t[fi] for t, m, c in rr})
            for v in vals[1:]:
                lo = [r for r in rr if r[0][fi] < v]
                hi = [r for r in rr if r[0][fi] >= v]
                bad = (0 if feas(lo) else 1) + (0 if feas(hi) else 1)
                scored.append((bad, -min(len(lo), len(hi)), fi, v, lo, hi))
        scored.sort(key=lambda s: (s[0], s[1]))
        for bad, _, fi, v, lo, hi in scored[:4]:
            rl = search(lo, depth - 1, path + [f"{NAMES[fi]}<{v}"])
            if rl is None:
                continue
            rh = search(hi, depth - 1, path + [f"{NAMES[fi]}>={v}"])
            if rh is not None:
                return rl + rh
        return None
    for depth in (4, 6, 8, 10):
        t0 = time.time()
        best_fail[0] = None
        res = search(ROWS, depth, [])
        if res:
            print(f"DEPTH {depth}: SOLVED, {len(res)} leaves ({time.time()-t0:.0f}s)")
            for path, a, n in res:
                ms = [MECHS[i] for i in range(len(MECHS)) if a & (1 << i)]
                print(f"  n={n} mechs={ms} :: {' & '.join(path) or '(root)'}")
            sys.exit(0)
        print(f"DEPTH {depth}: no gate ({time.time()-t0:.0f}s); "
              f"hardest={best_fail[0][0]} at {' & '.join(best_fail[0][1])}", flush=True)
    print("NO GATE up to depth 10 with enriched signals")
