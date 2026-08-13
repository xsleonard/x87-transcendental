#!/usr/bin/env python3
"""h445: allowed-offset set distribution per (dist, low3, prediff) cell.

Follow-up to h444: for each cell near prediff 0, print the Counter of
allowed payload_hw-offset sets, to see whether one constant offset per
cell satisfies every row (=> the rule is a pure function of the cell) or
whether some cell genuinely needs a finer discriminator.

Run from /tmp/stageA.
"""
from collections import Counter, defaultdict
from multiprocessing import Pool

from h437_gate_extraction import load_labeled_rows
from h444_payload_rule import analyze_row, OFFSETS


def main():
    rows = load_labeled_rows()
    with Pool(8) as pool:
        analyzed = [a for a in pool.map(analyze_row, rows, chunksize=2000)
                    if a is not None]

    cells = defaultdict(Counter)
    for dist, low3, prediff, allowed, extras in analyzed:
        if allowed == "UNEXPLAINED" or abs(prediff) > 3:
            continue
        cells[(dist, low3, prediff)][tuple(sorted(allowed))] += 1

    grand = Counter()   # (prediff -> viable constant offsets over all cells)
    for key in sorted(cells):
        dist, low3, prediff = key
        counter = cells[key]
        total = sum(counter.values())
        viable = [off for off in OFFSETS
                  if all(off in aset for aset in counter)]
        print(f"d={dist} low3={low3} pd={prediff:+d} (n={total}): "
              f"constant-offsets-ok={viable}")
        for aset, count in sorted(counter.items(), key=lambda kv: -kv[1]):
            print(f"    {list(aset)}: {count}")
        grand[(prediff, tuple(viable))] += 1

    print("\n=== summary: prediff -> viable constant offsets per cell ===")
    for (prediff, viable), count in sorted(grand.items()):
        print(f"  pd={prediff:+d} viable={list(viable)}: {count} cells")


if __name__ == "__main__":
    main()
