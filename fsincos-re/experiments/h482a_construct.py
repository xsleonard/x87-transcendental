#!/usr/bin/env python3
"""h482a: residual-input hunt — five contrast variables within
(cell, f4_g, f4_b2, rud) strata.

h481b: cell + known causal bits reach only 0.752 holdout — a strong
hidden input remains.  Candidates contrasted here, everything else in
the stratum matched:
  V1 rdisc_b14 : second rdisc bit (h480 z=+2.29, unresolved)
  V2 f4_b3     : third tail bit of the fourth power (depth test)
  V3 ldisc_top : left product's discard guard (left-side participation)
  V4 t2_g      : square's own chop guard (m^2 tail, deeper upstream)
  V5 rf_b0     : rf lowest retained bit
Plus payload-0/8 controls.  Hardware-blind lock before capture.
Run from /tmp/stageA.
"""
import json, random
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)
E2M = -66
BLOCKS = 288
BLOCK_LEN = 500_000
CAP_PER_STRATUM = 4
CAP_TOTAL = 72
CONTROL_CAP = 24
VARS = ("rdisc_b14", "f4_b3", "ldisc_top", "t2_g", "rf_b0")

def build(m):
    mag = (0, E2M, m)
    square = mul_round(mag, mag, 67, "chop")
    fourth = mul_round(square, square, 67, "chop")
    negative = build_chain(fourth, C6_5, C6_3, C6_1, 67, 64, "rn",
                           False, False, False)
    positive = build_chain(fourth, C6_6, C6_4, C6_2, 67, 64, "rn",
                           False, False, False)
    left = mul_round(square, negative, 67, "chop")
    right = mul_round(fourth, positive, 67, "chop")
    if left[0] != 1 or right[0] != 0:
        return None
    product = square[2] * negative[2]
    shift = max(product.bit_length() - 67, 0)
    discarded = product & ((1 << shift) - 1) if shift else 0
    ud = (discarded << 3) >> shift if shift else 0
    u5d = (discarded << 5) >> shift if shift else 0
    rproduct = fourth[2] * positive[2]
    rshift = max(rproduct.bit_length() - 67, 0)
    rdisc = rproduct & ((1 << rshift) - 1) if rshift else 0
    rud = (rdisc << 1) >> rshift if rshift else 0
    low3 = square[2] & 7
    dist = abs(left[1] - right[1])
    active = 1 if (low3 and (ud or (dist == 7 and u5d))) else 0
    if not active:
        return None
    if (dist == 10 and low3 == 6 and rud) or \
            (dist == 8 and low3 == 7 and ud >= 3):
        return None
    payload = low3 + 8 - dist
    if not 0 <= payload <= 8:
        return None
    scale = min(left[1], right[1])
    if payload and left[1] - 8 < scale:
        scale = left[1] - 8
    M = (left[2] << (left[1] - scale)) \
        + (payload << (left[1] - 8 - scale)) \
        - (right[2] << (right[1] - scale))
    if M <= 0:
        return None
    k = max(M.bit_length() - 67, 0)
    if k < 3 or (M & ((1 << k) - 1)):
        return None
    R = M >> k
    def res(delta):
        return [final_cosine_result(-(R + delta), scale + k, mode)
                for mode in ROUNDING_MODES]
    clean, fired = res(0), res(-1)
    if clean == fired:
        return None
    sq_full = m * m
    s2 = max(sq_full.bit_length() - 67, 0)
    f4_full = square[2] * square[2]
    s4 = max(f4_full.bit_length() - 67, 0)
    if s4 < 3 or s2 < 1 or rshift < 2 or shift < 1:
        return None
    feats = {
        "f4_g": (f4_full >> (s4 - 1)) & 1,
        "f4_b2": (f4_full >> (s4 - 2)) & 1,
        "f4_b3": (f4_full >> (s4 - 3)) & 1,
        "rdisc_b14": (rdisc >> (rshift - 2)) & 1,
        "ldisc_top": (discarded >> (shift - 1)) & 1,
        "t2_g": (sq_full >> (s2 - 1)) & 1,
        "rf_b0": positive[2] & 1,
        "rud": rud,
    }
    return {"m": f"{m:016x}", "cell": (dist, low3, k, rud),
            "payload": payload,
            "clean": [f"{x:016x}" for x in clean],
            "fired": [f"{x:016x}" for x in fired], "feats": feats}

def scan_block(args):
    start, length = args
    out = []
    for m in range(start, min(start + length, 1 << 64)):
        c = build(m)
        if c is not None:
            out.append(c)
    return out

def main():
    prev_ms = set()
    for fn, keys in (("h479_locked.json", None), ("h480_locked.json", None)):
        d = json.load(open(fn))
        if "inputs" in d:
            prev_ms |= {int(e["m"], 16) for e in d["inputs"]}
        else:
            for p in d["pairs"]:
                prev_ms |= {int(p["g0"]["m"], 16), int(p["g1"]["m"], 16)}
            prev_ms |= {int(c["m"], 16) for c in d["controls"]}
    rnd = random.Random(482)
    starts = sorted(rnd.randrange(1 << 63, (1 << 64) - BLOCK_LEN)
                    for _ in range(BLOCKS))
    with Pool(8) as pool:
        blocks = pool.map(scan_block, [(s, BLOCK_LEN) for s in starts])
    cands = [c for b in blocks for c in b]
    for m in sorted(prev_ms):
        c = build(m)
        if c is not None:
            cands.append(c)
    seen, uniq = set(), []
    for c in cands:
        if c["m"] not in seen:
            seen.add(c["m"]); uniq.append(c)
    cands = uniq
    print(f"candidates: {len(cands)}")
    controls = [c for c in cands if c["payload"] in (0, 8)][:CONTROL_CAP]
    main_c = [c for c in cands if c["payload"] not in (0, 8)]

    var_pairs = {v: [] for v in VARS}
    for v in VARS:
        strata = defaultdict(lambda: {0: [], 1: []})
        for c in main_c:
            key = (tuple(c["cell"]), c["feats"]["f4_g"],
                   c["feats"]["f4_b2"])
            strata[key][c["feats"][v]].append(c)
        for key in sorted(strata):
            s = strata[key]
            for a, b in list(zip(s[0], s[1]))[:CAP_PER_STRATUM]:
                if len(var_pairs[v]) < CAP_TOTAL:
                    var_pairs[v].append({"stratum_g": key[1],
                                         "v0": a["m"], "v1": b["m"]})
        print(f"  {v}: {len(var_pairs[v])} pairs")

    needed = set(c["m"] for c in controls)
    for v in VARS:
        for p in var_pairs[v]:
            needed.add(p["v0"]); needed.add(p["v1"])
    by_m = {c["m"]: c for c in cands}
    inputs = sorted(needed)
    print(f"unique capture inputs: {len(inputs)}")
    locked = {"vars": list(VARS), "var_pairs": var_pairs,
              "controls": [c["m"] for c in controls],
              "inputs": [{"m": mm, "cell": list(by_m[mm]["cell"]),
                          "payload": by_m[mm]["payload"],
                          "clean": by_m[mm]["clean"],
                          "fired": by_m[mm]["fired"],
                          "feats": by_m[mm]["feats"]} for mm in inputs]}
    with open("h482_locked.json", "w") as fh:
        json.dump(locked, fh, indent=1)
    with open("h482_inputs.txt", "w") as fh:
        for mm in inputs:
            fh.write(f"3ffc {mm}\n")
    with open("run_h482.sh", "w") as fh:
        fh.write(f"""#!/bin/sh
cd "$(dirname "$0")"
RUNNER=/root/x87_capture_x86_64
for mode in rn rd ru; do
    taskset -c 2 "$RUNNER" cos "$mode" --status \\
        < h482_inputs.txt > "cos_${{mode}}_status.txt" || exit 1
done
for mode in rn rd ru; do
    lines=$(wc -l < "cos_${{mode}}_status.txt")
    [ "$lines" -eq {len(inputs)} ] || {{ echo "BAD count $mode: $lines"; exit 1; }}
done
echo DONE > h482.done
""")
    print("wrote h482_locked.json, h482_inputs.txt, run_h482.sh")

if __name__ == "__main__":
    main()
