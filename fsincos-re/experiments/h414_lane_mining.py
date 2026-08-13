#!/usr/bin/env python3
"""h414: mine the payload-vs-aligned-lane relationship at miss states."""
import collections

BASE = "/home/coduoserver/fsincos-residual-20260807-1"
SETS = ["h363", "h372", "h380", "h384"]

def parse_trace(line):
    d = {}
    for tok in line.split()[1:]:
        k, v = tok.split("=")
        d[k] = v
    return d

def lane_features(d):
    le2 = int(d["le2"]); re2 = int(d["re2"])
    rsig = int(d["rs"], 16)
    payload = int(d["payload"])
    lane_shift = (le2 - 8) - re2
    lane = rsig >> lane_shift if lane_shift >= 0 else rsig << -lane_shift
    lane_byte = lane & 0xFF
    below = lane & ((1 << lane_shift) - 1) if lane_shift > 0 else 0
    diff = (lane_byte - payload) & 0xFF
    if diff >= 128: diff -= 256
    return lane_byte, diff, 1 if below else 0

rows = []
for s in SETS:
    traces = open(f"{BASE}/h412/{s}_trace.txt").read().splitlines()
    miss_idx = set()
    for l in open(f"{BASE}/h411/{s}_misses.txt"):
        miss_idx.add(int(l.split()[0]))
    for i, tr in enumerate(traces):
        d = parse_trace(tr)
        rows.append((s, i, d, i in miss_idx))

# distribution of signed diff for misses vs exacts, active rows only
dist_miss = collections.Counter()
dist_exact = collections.Counter()
for s, i, d, is_miss in rows:
    if d["active"] != "1": continue
    lane_byte, diff, sticky_below = lane_features(d)
    if is_miss:
        dist_miss[diff] += 1
    else:
        dist_exact[diff] += 1
print("=== signed (lane_byte - payload) among misses ===")
for k in sorted(dist_miss): print(f"  diff={k}: {dist_miss[k]}")
print("=== same diffs among exact active rows (for the diffs seen in misses) ===")
for k in sorted(dist_miss): print(f"  diff={k}: exact={dist_exact[k]}")
# fine split for the dominant miss diff: check sticky-below and payload parity
sub = collections.Counter()
for s, i, d, is_miss in rows:
    if d["active"] != "1": continue
    lane_byte, diff, sticky_below = lane_features(d)
    if diff in dist_miss:
        sub[(diff, sticky_below, is_miss)] += 1
print("=== (diff, sticky_below_lane, is_miss) ===")
for k in sorted(sub): print("  ", k, sub[k])
