#!/usr/bin/env python3
"""h480a: second-variable causal readout — construct contrast pairs.

h479 proved f4_g (fourth power's chop guard) is a causal input of the
tie-loss gate (McNemar z=+5.25) but not deterministic alone (36
both-fire, 92 neither, 11 reverse).  This iteration contrasts the next
candidate variables INSIDE (cell, f4_g) strata, so both the cell's
pinned field and the known causal bit are held fixed within a pair:

  V1 rdisc_b14 : bit below rud in the right product's discarded top
  V2 p1_g      : left chain first product's chop guard (z -22 in h477d)
  V3 f4_b2     : second tail bit of the fourth power (below f4_g)
  V4 p4_g      : right chain last product's chop guard

Plus f4_g DENSITY pairs (h479 replication + more weight in the cells
that looked deterministic or inert).  All candidate inputs are exact
observable ties in pre-patch coordinates, patch lanes excluded,
payload 1..7 (payload 0/8 controls again included).

Hardware-blind: h480_locked.json is written with every input's clean
(R) and fired (R-1) tuples and the per-variable hypotheses BEFORE any
capture.  Inputs are deduplicated; pairs reference inputs by m.

Run from /tmp/stageA.  Reuses h479_locked.json candidates.
"""
import json
import random
from collections import defaultdict
from multiprocessing import Pool

from h437_gate_extraction import (ROUNDING_MODES, parse_trace_line,
                                  final_cosine_result)
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round, recover_m)
from h454_stale_carry import mul_state, add_state

E2M = -66
BLOCKS = 144
BLOCK_LEN = 500_000
VAR_PAIR_CAP_PER_STRATUM = 6
VAR_PAIR_CAP_TOTAL = 90
F4G_PAIR_CAP_PER_CELL = 8
CONTROL_CAP = 30
VARS = ("rdisc_b14", "p1_g", "f4_b2", "p4_g")


def forward(m):
    """Cheap tie filter, identical semantics to h479a."""
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
    return {"m": m, "cell": (dist, low3, k, rud), "payload": payload,
            "clean": [f"{x:016x}" for x in clean],
            "fired": [f"{x:016x}" for x in fired],
            "square": square, "fourth": fourth,
            "rproduct": rproduct, "rshift": rshift}


def enrich(c):
    """Chain-state features for a tie candidate."""
    m = c["m"]
    square, fourth = c["square"], c["fourth"]
    f4_full = square[2] * square[2]
    s4 = max(f4_full.bit_length() - 67, 0)
    if s4 < 2 or (f4_full >> s4) != fourth[2]:
        return None
    rdisc = c["rproduct"] & ((1 << c["rshift"]) - 1)
    rdisc16 = (rdisc >> (c["rshift"] - 16)) & 0xFFFF \
        if c["rshift"] >= 16 else rdisc
    p1, st_p1 = mul_state(fourth, C6_5, 67, "chop")
    a1, st_a1 = add_state(C6_3, p1, 64, "rn")
    p2, st_p2 = mul_state(fourth, a1, 67, "chop")
    neg, st_a2 = add_state(C6_1, p2, 64, "rn")
    p3, st_p3 = mul_state(fourth, C6_6, 67, "chop")
    a3, st_a3 = add_state(C6_4, p3, 64, "rn")
    p4, st_p4 = mul_state(fourth, a3, 67, "chop")
    pos, st_a4 = add_state(C6_2, p4, 64, "rn")
    feats = {
        "f4_g": (f4_full >> (s4 - 1)) & 1,
        "f4_b2": (f4_full >> (s4 - 2)) & 1,
        "rdisc_b14": (rdisc16 >> 14) & 1,
        "p1_g": st_p1[0], "p2_g": st_p2[0],
        "p3_g": st_p3[0], "p4_g": st_p4[0],
        "a2_g": st_a2[0], "a4_g": st_a4[0],
        "rf_low8": pos[2] & 0xFF, "rdisc16": rdisc16,
    }
    return {"m": f"{c['m']:016x}", "cell": list(c["cell"]),
            "payload": c["payload"], "clean": c["clean"],
            "fired": c["fired"], "feats": feats}


def scan_block(args):
    start, length = args
    out = []
    for m in range(start, min(start + length, 1 << 64)):
        c = forward(m)
        if c is not None:
            e = enrich(c)
            if e is not None:
                out.append(e)
    return out


def main():
    # merge h479 candidates (recompute features from their m values)
    prev = json.load(open("h479_locked.json"))
    prev_ms = {int(p[side]["m"], 16)
               for p in prev["pairs"] for side in ("g0", "g1")}
    prev_ms |= {int(cc["m"], 16) for cc in prev["controls"]}

    rnd = random.Random(480)
    starts = sorted(rnd.randrange(1 << 63, (1 << 64) - BLOCK_LEN)
                    for _ in range(BLOCKS))
    with Pool(8) as pool:
        blocks = pool.map(scan_block,
                          [(s, BLOCK_LEN) for s in starts])
    cands = [c for b in blocks for c in b]
    for m in sorted(prev_ms):
        c = forward(m)
        if c is not None:
            e = enrich(c)
            if e is not None:
                cands.append(e)
    seen = set()
    uniq = []
    for c in cands:
        if c["m"] not in seen:
            seen.add(c["m"])
            uniq.append(c)
    cands = uniq
    print(f"candidates (incl. h479 reuse): {len(cands)}")

    controls = [c for c in cands if c["payload"] in (0, 8)][:CONTROL_CAP]
    main_c = [c for c in cands if c["payload"] not in (0, 8)]

    # V pairs within (cell, f4_g) strata
    var_pairs = {v: [] for v in VARS}
    for v in VARS:
        strata = defaultdict(lambda: {0: [], 1: []})
        for c in main_c:
            strata[(tuple(c["cell"]), c["feats"]["f4_g"])][
                c["feats"][v]].append(c)
        for key in sorted(strata):
            s = strata[key]
            for a, b in list(zip(s[0], s[1]))[
                    :VAR_PAIR_CAP_PER_STRATUM]:
                if len(var_pairs[v]) < VAR_PAIR_CAP_TOTAL:
                    var_pairs[v].append(
                        {"stratum": [list(key[0]), key[1]],
                         "v0": a["m"], "v1": b["m"]})
        print(f"  {v}: {len(var_pairs[v])} pairs")

    # f4_g density pairs (replication)
    f4g_pairs = []
    cells = defaultdict(lambda: {0: [], 1: []})
    for c in main_c:
        cells[tuple(c["cell"])][c["feats"]["f4_g"]].append(c)
    for cell in sorted(cells):
        s = cells[cell]
        for a, b in list(zip(s[0], s[1]))[:F4G_PAIR_CAP_PER_CELL]:
            f4g_pairs.append({"cell": list(cell),
                              "g0": a["m"], "g1": b["m"]})
    print(f"  f4_g density pairs: {len(f4g_pairs)}")

    # deduplicated capture list
    needed = set()
    for v in VARS:
        for p in var_pairs[v]:
            needed.add(p["v0"])
            needed.add(p["v1"])
    for p in f4g_pairs:
        needed.add(p["g0"])
        needed.add(p["g1"])
    for c in controls:
        needed.add(c["m"])
    by_m = {c["m"]: c for c in cands}
    inputs = sorted(needed)
    print(f"unique capture inputs: {len(inputs)}")

    locked = {
        "hypotheses": {
            "per-variable": "within (cell, f4_g) strata, McNemar on "
                            "discordant pairs; a causal variable is "
                            "one-sided like f4_g was",
            "f4_g-replication": "density pairs must reproduce z>0 "
                                "one-sided discordance",
            "controls": "payload 0/8 inputs show ZERO fires",
        },
        "vars": VARS,
        "var_pairs": var_pairs,
        "f4g_pairs": f4g_pairs,
        "controls": [c["m"] for c in controls],
        "inputs": [{"m": m, "cell": by_m[m]["cell"],
                    "payload": by_m[m]["payload"],
                    "clean": by_m[m]["clean"],
                    "fired": by_m[m]["fired"],
                    "feats": by_m[m]["feats"]} for m in inputs],
    }
    with open("h480_locked.json", "w") as fh:
        json.dump(locked, fh, indent=1)
    with open("h480_inputs.txt", "w") as fh:
        for m in inputs:
            fh.write(f"3ffc {m}\n")
    with open("run_h480.sh", "w") as fh:
        fh.write(f"""#!/bin/sh
# h480 second-variable readout: {len(inputs)} FCOS inputs x rn/rd/ru.
cd "$(dirname "$0")"
RUNNER=/root/x87_capture_x86_64
for mode in rn rd ru; do
    taskset -c 2 "$RUNNER" cos "$mode" --status \\
        < h480_inputs.txt > "cos_${{mode}}_status.txt" || exit 1
done
for mode in rn rd ru; do
    lines=$(wc -l < "cos_${{mode}}_status.txt")
    [ "$lines" -eq {len(inputs)} ] || {{ echo "BAD count $mode: $lines"; exit 1; }}
done
echo DONE > h480.done
""")
    print("wrote h480_locked.json, h480_inputs.txt, run_h480.sh")


if __name__ == "__main__":
    main()
