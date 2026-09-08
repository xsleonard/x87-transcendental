#!/usr/bin/env python3
"""h495b: range-shift probe.  Per (stratum, m-range) fire rates over
the 16 disjoint scan ranges (8 x 1B original + 8 x 500M fresh).
Flags strata whose rate varies across ranges beyond binomial noise.
Uses original map data + fresh captures (fcos2_*)."""
from collections import defaultdict
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result

RANGES = [(0x8100000000000000, 1_000_000_000),
          (0x8f00000000000000, 1_000_000_000),
          (0x9d00000000000000, 1_000_000_000),
          (0xab00000000000000, 1_000_000_000),
          (0xb900000000000000, 1_000_000_000),
          (0xc700000000000000, 1_000_000_000),
          (0xd500000000000000, 1_000_000_000),
          (0xe300000000000000, 1_000_000_000),
          (0x8800000000000000, 500_000_000),
          (0x9600000000000000, 500_000_000),
          (0xa400000000000000, 500_000_000),
          (0xb200000000000000, 500_000_000),
          (0xc000000000000000, 500_000_000),
          (0xce00000000000000, 500_000_000),
          (0xdc00000000000000, 500_000_000),
          (0xea00000000000000, 500_000_000)]

def range_of(m):
    for i, (s, c) in enumerate(RANGES):
        if s <= m < s + c:
            return i
    return -1

counts = defaultdict(lambda: defaultdict(lambda: [0, 0]))

# original map data
with open("h491_mapdata.tsv") as fh:
    fh.readline()
    for line in fh:
        f = line.rstrip("\n").split("\t")
        if f[7] not in ("CLEAN", "FIRE"):
            continue
        m = int(f[0], 16)
        r = range_of(m)
        key = (f[1], f[2], f[3], f[4])
        c = counts[key][r]
        c[0] += 1
        c[1] += f[7] == "FIRE"

# fresh: recompute expected tuples from ties_fresh + fcos2 captures
fresh = []
seen = set()
for line in open("ties_fresh.txt"):
    f = line.split()
    if f[0] in seen:
        continue
    seen.add(f[0])
    fresh.append(f)
inputs = sorted(f[0] for f in fresh)
order = {m: i for i, m in enumerate(inputs)}
st = {md: open(f"fcos2_{md}_status.txt").read().splitlines()
      for md in ROUNDING_MODES}
for f in fresh:
    m = f[0]
    R = int(f[7], 16)
    ce = int(f[8])
    i = order[m]
    hw = []
    bad = False
    for md in ROUNDING_MODES:
        t = st[md][i].split()
        if t[0] != "OK":
            bad = True
            break
        hw.append(int(t[2], 16))
    if bad:
        continue
    clean = [final_cosine_result(-R, ce, md) for md in ROUNDING_MODES]
    fired = [final_cosine_result(-(R - 1), ce, md)
             for md in ROUNDING_MODES]
    if hw == clean:
        fire = 0
    elif hw == fired:
        fire = 1
    else:
        continue
    r = range_of(int(m, 16))
    key = (f[1], f[2], f[3], f[4])
    c = counts[key][r]
    c[0] += 1
    c[1] += fire

print(f"{'stratum':20s} " + " ".join(f"r{i:02d}" for i in range(16)))
flagged = []
for key in sorted(counts):
    per = counts[key]
    tot = sum(v[0] for v in per.values())
    if tot < 2000:
        continue
    rates = []
    line = []
    for i in range(16):
        n, fi = per[i]
        if n >= 100:
            rates.append(fi / n)
            line.append(f"{100*fi/n:3.0f}")
        else:
            line.append("  .")
    if len(rates) >= 6:
        spread = max(rates) - min(rates)
        mark = "  <== RANGE-SHIFT" if spread > 0.15 else ""
        if spread > 0.15:
            flagged.append((key, spread))
        print(f"{str(key):20s} " + " ".join(line) + mark)
print(f"\nflagged strata (spread > 0.15): {len(flagged)}")
for key, s in sorted(flagged, key=lambda x: -x[1]):
    print(f"  {key}: spread {s:.2f}")
