#!/usr/bin/env python3
"""Hardware-vs-hardware: paired FSINCOS lanes vs standalone FSIN/FCOS on h347.
# Preserved verbatim from the 2026-08-07 Round-54 pass (h398): hardware
# paired-vs-standalone diff over the h347 per-instruction capture.  Ran in
# /home/coduoserver/fsincos-residual-20260807-1 on the Skylake capture host.

Compares result encodings per input per mode.  C1 (SW bit 9) is compared
too, but reported separately since paired C1 semantics may differ.
"""
import sys, collections

BASE = sys.argv[1] if len(sys.argv) > 1 else "."

def load_single(path):
    out = []
    with open(path) as f:
        for line in f:
            p = line.split()
            # OK se sig SW xxxx
            out.append((p[0], p[1], p[2], int(p[4], 16)))
    return out

def load_paired(path):
    out = []
    with open(path) as f:
        for line in f:
            p = line.split()
            # OK sin_se sin_sig cos_se cos_sig SW xxxx
            out.append((p[0], p[1], p[2], p[3], p[4], int(p[6], 16)))
    return out

inputs = [tuple(l.split()) for l in open(f"{BASE}/inputs.txt")]

total_result_diffs = 0
by_lane_mode = collections.Counter()
diff_inputs = collections.defaultdict(set)
examples = []

for mode in ("rn", "rd", "ru"):
    fsin = load_single(f"{BASE}/fsin_{mode}_status.txt")
    fcos = load_single(f"{BASE}/fcos_{mode}_status.txt")
    pair = load_paired(f"{BASE}/fsincos_{mode}_status.txt")
    n = len(inputs)
    assert len(fsin) == len(fcos) == len(pair) == n
    for i in range(n):
        s, c, p = fsin[i], fcos[i], pair[i]
        if s[0] != "OK" or c[0] != "OK" or p[0] != "OK":
            by_lane_mode[("status", mode)] += 1
            continue
        if (s[1], s[2]) != (p[1], p[2]):
            total_result_diffs += 1
            by_lane_mode[("sin", mode)] += 1
            diff_inputs[inputs[i]].add(("sin", mode))
            if len(examples) < 20:
                examples.append((i, mode, "sin", inputs[i], (s[1], s[2]), (p[1], p[2])))
        if (c[1], c[2]) != (p[3], p[4]):
            total_result_diffs += 1
            by_lane_mode[("cos", mode)] += 1
            diff_inputs[inputs[i]].add(("cos", mode))
            if len(examples) < 20:
                examples.append((i, mode, "cos", inputs[i], (c[1], c[2]), (p[3], p[4])))

print(f"inputs: {len(inputs)}  (x3 modes, 2 lanes)")
print(f"total lane/mode result diffs (paired vs standalone hardware): {total_result_diffs}")
print(f"distinct inputs affected: {len(diff_inputs)}")
for k in sorted(by_lane_mode):
    print(f"  {k}: {by_lane_mode[k]}")
print("\nfirst examples (idx mode lane input standalone paired):")
for e in examples:
    print(" ", e)
