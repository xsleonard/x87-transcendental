#!/usr/bin/env python3
"""h479a: construct f4_g-contrast tie pairs for i7 capture.

Goal: within pinned tie cells (dist, low3, k, rud) -- where the entire
terminal discarded field is forced by the cell -- emit input PAIRS
differing in f4_g (the fourth power's chop guard bit, the strongest
within-cell correlate, z ~ +100).  Captured on the i7, each pair is a
single-variable causal probe of the tie-loss gate.

Protocol (hardware-blind): this script writes h479_locked.json with
every prediction BEFORE any capture: per input the model's clean
result tuple (R) and fire tuple (R-1) for rn/rd/ru, the cell, and
f4_g.  The hypotheses under test, locked now:
  H-causal : within-pair fire discordance is one-sided (g=1 fires,
             g=0 does not); strict version fire <=> f4_g.
  H-proxy  : discordant pairs split evenly (f4_g only proxies deeper
             state that pairing does not control).
Corpus-based expectation if f4_g is merely associated: within-pair
delta ~ +0.17 (0.42 vs 0.25).

Steps: (1) validate the forward replica against corpus2 traces;
(2) scan m blocks at se=3ffc (value = m * 2^-66) for observable
exact ties, PRE-PATCH coordinates, patch lanes excluded; (3) pair and
lock; (4) write capture package (inputs.txt, run_h479.sh).

Run from /tmp/stageA.
"""
import json
import random
from collections import defaultdict
from multiprocessing import Pool

from h437_gate_extraction import (ROUNDING_MODES, parse_trace_line,
                                  final_cosine_result)
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round, recover_m)

E2M = -66
BLOCKS = 48
BLOCK_LEN = 500_000
PAIR_CAP = 20
CONTROL_CAP = 40


def forward(m):
    """Forward replica, PRE-PATCH terminal coordinates.  Returns None
    or a candidate dict."""
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
        return None                                # patch lanes: skip
    payload = low3 + 8 - dist
    if not 0 <= payload <= 8:
        return None
    scale = min(left[1], right[1])
    if payload and left[1] - 8 < scale:
        scale = left[1] - 8
    A = left[2] << (left[1] - scale)
    B = right[2] << (right[1] - scale)
    Pv = payload << (left[1] - 8 - scale)
    M = A + Pv - B
    if M <= 0:
        return None
    k = max(M.bit_length() - 67, 0)
    if k < 3 or (M & ((1 << k) - 1)):
        return None                                # exact ties only
    R = M >> k

    def res(delta):
        return [final_cosine_result(-(R + delta), scale + k, mode)
                for mode in ROUNDING_MODES]

    clean, fired = res(0), res(-1)
    if clean == fired:
        return None                                # blind
    f4_full = square[2] * square[2]
    s4 = max(f4_full.bit_length() - 67, 0)
    if s4 == 0 or (f4_full >> s4) != fourth[2]:
        return None
    f4_g = (f4_full >> (s4 - 1)) & 1
    return {"m": f"{m:016x}", "cell": [dist, low3, k, rud],
            "payload": payload, "f4_g": f4_g,
            "clean": [f"{x:016x}" for x in clean],
            "fired": [f"{x:016x}" for x in fired]}


def scan_block(args):
    start, length = args
    out = []
    for m in range(start, min(start + length, 1 << 64)):
        c = forward(m)
        if c is not None:
            out.append(c)
    return out


def validate():
    """Forward replica must reproduce corpus2 traced terminal fields."""
    traces = open("corpus2/selected_traces.txt").read().splitlines()
    checked = ok = 0
    for line in traces[:4000]:
        fields = parse_trace_line(line)
        if fields.get("active") != "1":
            continue
        m = recover_m(int(fields["mul"], 16))
        if m is None:
            continue
        mag = (0, E2M, m)
        square = mul_round(mag, mag, 67, "chop")
        if square[2] != int(fields["mul"], 16):
            continue
        fourth = mul_round(square, square, 67, "chop")
        negative = build_chain(fourth, C6_5, C6_3, C6_1, 67, 64, "rn",
                               False, False, False)
        positive = build_chain(fourth, C6_6, C6_4, C6_2, 67, 64, "rn",
                               False, False, False)
        if negative[2] != int(fields["lf"], 16) or \
                positive[2] != int(fields["rf"], 16):
            continue                       # other exponent family
        left = mul_round(square, negative, 67, "chop")
        right = mul_round(fourth, positive, 67, "chop")
        checked += 1
        if (left[2] == int(fields["ls"], 16)
                and right[2] == int(fields["rs"], 16)
                and left[1] == int(fields["le2"])
                and right[1] == int(fields["re2"])
                and left[0] == int(fields["lsign"])
                and right[0] == int(fields["rsign"])):
            ok += 1
    print(f"validation: {ok}/{checked} corpus2 rows reproduced")
    return checked > 500 and ok == checked


def main():
    if not validate():
        raise SystemExit("forward replica failed validation -- STOP")

    rnd = random.Random(479)
    starts = sorted(rnd.randrange(1 << 63, (1 << 64) - BLOCK_LEN)
                    for _ in range(BLOCKS))
    with Pool(8) as pool:
        blocks = pool.map(scan_block,
                          [(s, BLOCK_LEN) for s in starts])
    cands = [c for b in blocks for c in b]
    print(f"scanned {BLOCKS * BLOCK_LEN} inputs -> "
          f"{len(cands)} observable tie candidates")

    cells = defaultdict(lambda: {0: [], 1: []})
    controls = []
    for c in cands:
        if c["payload"] in (0, 8):
            controls.append(c)
        else:
            cells[tuple(c["cell"])][c["f4_g"]].append(c)

    pairs = []
    for cell in sorted(cells):
        g0, g1 = cells[cell][0], cells[cell][1]
        for a, b in list(zip(g0, g1))[:PAIR_CAP]:
            pairs.append({"cell": list(cell), "g0": a, "g1": b})
    controls = controls[:CONTROL_CAP]
    n_inputs = 2 * len(pairs) + len(controls)
    print(f"cells with both sides: "
          f"{sum(1 for c in cells.values() if c[0] and c[1])}, "
          f"pairs: {len(pairs)}, controls (payload 0/8): "
          f"{len(controls)}, capture inputs: {n_inputs}")
    if len(pairs) < 30:
        raise SystemExit("too few pairs -- widen the scan before "
                         "locking anything")

    locked = {
        "hypotheses": {
            "H-causal": "discordant pairs one-sided: g1 fires, g0 not;"
                        " strict: fire <=> f4_g",
            "H-proxy": "discordant pairs split ~evenly",
            "corpus_expectation_if_proxy": "within-pair delta ~ +0.17",
            "controls": "payload 0/8 inputs must show ZERO fires",
        },
        "pairs": pairs, "controls": controls,
    }
    with open("h479_locked.json", "w") as fh:
        json.dump(locked, fh, indent=1)

    with open("h479_inputs.txt", "w") as fh:
        for p in pairs:
            fh.write(f"3ffc {p['g0']['m']}\n3ffc {p['g1']['m']}\n")
        for c in controls:
            fh.write(f"3ffc {c['m']}\n")

    with open("run_h479.sh", "w") as fh:
        fh.write(f"""#!/bin/sh
# h479 constructed tie pairs: {n_inputs} FCOS inputs x rn/rd/ru.
# Launch detached:  setsid nohup sh run_h479.sh > run.log 2>&1 &
cd "$(dirname "$0")"
RUNNER=/root/x87_capture_x86_64
for mode in rn rd ru; do
    taskset -c 2 "$RUNNER" cos "$mode" --status \\
        < h479_inputs.txt > "cos_${{mode}}_status.txt" || exit 1
done
for mode in rn rd ru; do
    lines=$(wc -l < "cos_${{mode}}_status.txt")
    [ "$lines" -eq {n_inputs} ] || {{ echo "BAD count $mode: $lines"; exit 1; }}
done
echo DONE > h479.done
""")
    print("wrote h479_locked.json, h479_inputs.txt, run_h479.sh")


if __name__ == "__main__":
    main()
