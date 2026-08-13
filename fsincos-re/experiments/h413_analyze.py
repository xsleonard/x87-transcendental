#!/usr/bin/env python3
"""h413: stratify terminal-carrier traces by hostile-set outcome."""
import collections, re, sys

BASE = "/home/coduoserver/fsincos-residual-20260807-1"
SETS = ["h363", "h372", "h380", "h384"]

def parse_trace(line):
    d = {}
    for tok in line.split()[1:]:
        k, v = tok.split("=")
        d[k] = v
    return d

rows = []          # (set, idx, trace_dict, misses{mode:step})
for s in SETS:
    traces = open(f"{BASE}/h412/{s}_trace.txt").read().splitlines()
    misses = collections.defaultdict(dict)
    for l in open(f"{BASE}/h411/{s}_misses.txt"):
        t = l.split()
        i, m = int(t[0]), t[1]
        hw = int(t[4], 16); mo = int(t[6], 16)
        misses[i][m] = 1 if hw > mo else -1
    for i, tr in enumerate(traces):
        rows.append((s, i, parse_trace(tr), misses.get(i, {})))

# stratify by (distance, low3, active, payload)
strat = collections.Counter()
strat_miss = collections.Counter()
for s, i, d, mm in rows:
    key = (d["dist"], d["low3"], d["active"], d["payload"])
    strat[key] += 1
    if mm: strat_miss[key] += 1
print("=== strata with misses (dist, low3, active, payload): miss/total ===")
for k in sorted(strat_miss):
    print(f"  {k}: {strat_miss[k]}/{strat[k]}")

# full-trace collision check: identical trace, mixed outcomes
groups = collections.defaultdict(list)
for s, i, d, mm in rows:
    key = tuple(sorted(d.items()))
    groups[key].append((s, i, bool(mm)))
coll = 0
for key, members in groups.items():
    outcomes = {m[2] for m in members}
    if len(outcomes) > 1:
        coll += 1
        if coll <= 5:
            print("COLLISION group:", [(m[0], m[1], m[2]) for m in members][:6])
print(f"full-trace collision groups: {coll} of {len(groups)} groups")

# step direction inventory among misses
dirs = collections.Counter()
for s, i, d, mm in rows:
    for m, st in mm.items():
        dirs[(s, m, st)] += 1
print("=== miss step directions (set, mode, hwstep) ===")
for k in sorted(dirs): print("  ", k, dirs[k])
