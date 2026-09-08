#!/usr/bin/env python3
"""h467: characterize the rdisc signal — direction split and response
curve.

h466's paired mining found one replicated gate-input candidate: the
right terminal product's discarded-field top byte (rdisc_hi8),
z=+4.4/+5.1 across held-out halves, with a secondary in p4_g.  By the
h443 alias structure, right-product-up (rs+1) is the theta<=0 fire
family (borrow injection), so if hardware conditionally rounds the
right product by its discarded field, the rdisc association should be
concentrated in DOWN-fires and the response P(fire | rdisc_hi8) should
show a threshold.

This script, over all labeled rows (both codings kept distinct):
  1. re-scores the paired ordering split by fire direction;
  2. prints P(fire_pre | rdisc_hi8 bucket) separately for theta<=0 and
     theta>0 rows (16 buckets of 16), with counts;
  3. same for ldisc_hi8 as the mirror control;
  4. tests candidate hard rules on every constrained row with held-out
     halves: fire_down iff rdisc_hi8 >= t for t in 8..248 step 8 —
     scored as (caught fires, false fires) per half.

Run from /tmp/stageA (expects h464_package/labels.tsv).
"""
import math
from collections import defaultdict

PKG = "h464_package"
L2_KEYS = ["dist", "low3", "theta", "payload", "ud", "rud", "lane", "u5d"]


def main():
    rows = []
    with open(f"{PKG}/labels.tsv") as fh:
        header = fh.readline().rstrip("\n").split("\t")
        for line in fh:
            r = dict(zip(header, line.rstrip("\n").split("\t")))
            for k in ("theta", "b_hw", "fire_pre", "fire_post", "dist",
                      "low3", "payload", "ud", "u5d", "rud", "lane",
                      "rs_low16", "ls_low8", "ldisc_hi8", "rdisc_hi8"):
                r[k] = int(r[k])
            rows.append(r)
    print(f"rows: {len(rows)}")

    # 1. paired ordering by direction
    groups = defaultdict(list)
    for r in rows:
        groups[tuple(r[k] for k in L2_KEYS)].append(r)
    for direction, want in (("down (theta<=0)", lambda t: t <= 0),
                            ("up (theta>0)", lambda t: t > 0)):
        wins = losses = 0
        for key, members in groups.items():
            if not want(members[0]["theta"]):
                continue
            fires = [r for r in members if r["fire_pre"]]
            cools = [r for r in members if not r["fire_pre"]]
            for F in fires:
                for N in cools:
                    if F["rdisc_hi8"] > N["rdisc_hi8"]:
                        wins += 1
                    elif F["rdisc_hi8"] < N["rdisc_hi8"]:
                        losses += 1
        n = wins + losses
        z = (wins - losses) / math.sqrt(n) if n else 0.0
        print(f"  paired rdisc_hi8, {direction}: F>N {wins}, F<N {losses}, "
              f"z={z:+.1f}")

    # 2/3. response curves
    for feat in ("rdisc_hi8", "ldisc_hi8"):
        print(f"\nP(fire_pre | {feat} bucket):")
        print("bucket   theta<=0: fires/rows      theta>0: fires/rows")
        for b in range(16):
            lo, hi = b * 16, b * 16 + 15
            cells = []
            for want in (lambda t: t <= 0, lambda t: t > 0):
                sel = [r for r in rows
                       if lo <= r[feat] <= hi and want(r["theta"])]
                f = sum(r["fire_pre"] for r in sel)
                cells.append((f, len(sel)))
            print(f"{lo:3d}-{hi:3d}   {cells[0][0]:5d}/{cells[0][1]:6d} "
                  f"({cells[0][0] / max(cells[0][1], 1):.3f})    "
                  f"{cells[1][0]:5d}/{cells[1][1]:6d} "
                  f"({cells[1][0] / max(cells[1][1], 1):.3f})")

    # 4. hard threshold rules, held-out
    print("\nhard rule: predict fire on theta<=0 rows iff rdisc_hi8 >= t")
    print("t     half0 caught/all-fires false/all-cool   half1 ...")
    for t in range(8, 249, 8):
        line = f"{t:4d}"
        for half in (0, 1):
            caught = fires = false = cool = 0
            for r in rows:
                if r["theta"] > 0:
                    continue
                if (hash((r["se"], r["sig"])) & 1) != half:
                    continue
                pred = 1 if r["rdisc_hi8"] >= t else 0
                if r["fire_pre"]:
                    fires += 1
                    caught += pred
                else:
                    cool += 1
                    false += pred
            line += (f"   h{half} {caught:4d}/{fires:4d} "
                     f"{false:5d}/{cool:5d}")
        print(line)


if __name__ == "__main__":
    main()
