#!/usr/bin/env python3
"""h471: refine the validated frame toward determinism.

Two passes over the merged 37,951-row corpus (held-out split by input
hash throughout):

  A. Arithmetic alignment probe: within the frame, is the real variable
     the raw rs low nibble or the subtractor-local difference
     (rs - payload)?  Prints fire-rate tables vs rs_nib0 and vs
     (rs - payload) mod 16, per (theta sign, dist), so alignment
     structure is visible by eye and by conditional entropy.

  B. Greedy bit-literal forward selection starting FROM the frame
     (theta, rs_nib0, payload, rud), offering individual bits of rs
     (4..11), lane, u5d, ud, ldisc_hi8, rdisc_hi8, ls low bits, plus
     dist and low3, with recursive backoff smoothing along the chosen
     prefix (deep tables shrink; backoff keeps estimates honest).
     Reports held-out logloss per step and the final determinism
     profile: fraction of held-out rows predicted below 0.02 or above
     0.9, with actual rates.

Run from /tmp/stageA (expects h464_package/combined_labels.tsv).
"""
import math
from collections import defaultdict

PKG = "h464_package"
ALPHA = 8.0


def load():
    rows = []
    with open(f"{PKG}/combined_labels.tsv") as fh:
        header = fh.readline().rstrip("\n").split("\t")
        for line in fh:
            r = dict(zip(header, line.rstrip("\n").split("\t")))
            for k in ("theta", "b_hw", "fire_pre", "fire_post", "dist",
                      "low3", "payload", "ud", "u5d", "rud", "lane",
                      "rs_low16", "ls_low8", "ldisc_hi8", "rdisc_hi8"):
                r[k] = int(r[k])
            rows.append(r)
    return rows


def part_a(rows):
    print("=== A: rs_nib0 vs (rs - payload) mod 16 ===")
    for tag, keyf in (("rs_nib0", lambda r: r["rs_low16"] & 0xF),
                      ("(rs-pay)&0xF",
                       lambda r: (r["rs_low16"] - r["payload"]) & 0xF)):
        ent = 0.0
        n_tot = 0
        for r in rows:
            pass
        table = defaultdict(lambda: [0, 0])
        for r in rows:
            table[(r["theta"] > 0, r["dist"], keyf(r))][r["fire_pre"]] += 1
        for key, (n0, n1) in table.items():
            n = n0 + n1
            for c in (n0, n1):
                if c:
                    ent -= c * math.log(c / n)
            n_tot += n
        print(f"  {tag:14s}: conditional entropy "
              f"{ent / n_tot:.4f} nats over {len(table)} cells")
    # visible table for dist=8, both directions
    for direction, want in (("theta<=0", lambda t: t <= 0),
                            ("theta>0", lambda t: t > 0)):
        print(f"  dist=8 {direction}: fire rate by (rs-pay)&0xF:")
        line = "    "
        for v in range(16):
            sel = [r for r in rows if r["dist"] == 8 and want(r["theta"])
                   and (r["rs_low16"] - r["payload"]) & 0xF == v]
            f = sum(r["fire_pre"] for r in sel)
            line += f"{v:X}:{f / max(len(sel), 1):.2f} "
        print(line)


FRAME = [
    ("theta", lambda r: r["theta"]),
    ("rs_nib0", lambda r: r["rs_low16"] & 0xF),
    ("payload", lambda r: r["payload"]),
    ("rud", lambda r: r["rud"]),
]
POOL = (
    [(f"rs_b{b}", (lambda b: lambda r: (r["rs_low16"] >> b) & 1)(b))
     for b in range(4, 12)]
    + [(f"lane_b{b}", (lambda b: lambda r: (r["lane"] >> b) & 1)(b))
       for b in range(8)]
    + [(f"u5d_b{b}", (lambda b: lambda r: (r["u5d"] >> b) & 1)(b))
       for b in range(5)]
    + [(f"ud_b{b}", (lambda b: lambda r: (r["ud"] >> b) & 1)(b))
       for b in range(3)]
    + [(f"ld_b{b}", (lambda b: lambda r: (r["ldisc_hi8"] >> b) & 1)(b))
       for b in range(4, 8)]
    + [(f"rd_b{b}", (lambda b: lambda r: (r["rdisc_hi8"] >> b) & 1)(b))
       for b in range(4, 8)]
    + [(f"ls_b{b}", (lambda b: lambda r: (r["ls_low8"] >> b) & 1)(b))
       for b in range(4)]
    + [("dist", lambda r: r["dist"]), ("low3", lambda r: r["low3"])]
)


def build_tables(train, feats):
    tables = []
    for depth in range(len(feats) + 1):
        t = defaultdict(lambda: [0, 0])
        for r in train:
            key = tuple(f(r) for _, f in feats[:depth])
            t[key][r["fire_pre"]] += 1
        tables.append(t)
    return tables


def predict(tables, feats, r):
    p = None
    for depth in range(len(feats) + 1):
        key = tuple(f(r) for _, f in feats[:depth])
        n0, n1 = tables[depth].get(key, [0, 0])
        n = n0 + n1
        if p is None:
            p = n1 / n if n else 0.1
        elif n:
            p = (n1 + ALPHA * p) / (n + ALPHA)
        else:
            break
    return min(max(p, 1e-6), 1 - 1e-6)


def part_b(rows):
    train = [r for r in rows if hash((r["se"], r["sig"])) & 1 == 0]
    test = [r for r in rows if hash((r["se"], r["sig"])) & 1 == 1]
    print(f"\n=== B: greedy bit refinement (train {len(train)}, "
          f"test {len(test)}) ===")
    feats = list(FRAME)
    tables = build_tables(train, feats)
    current = sum(-math.log(predict(tables, feats, r)) if r["fire_pre"]
                  else -math.log(1 - predict(tables, feats, r))
                  for r in test) / len(test)
    print(f"  frame baseline held-out logloss: {current:.4f}")
    remaining = list(POOL)
    while True:
        best = None
        for cand in remaining:
            trial = feats + [cand]
            tt = build_tables(train, trial)
            ll = sum(-math.log(predict(tt, trial, r)) if r["fire_pre"]
                     else -math.log(1 - predict(tt, trial, r))
                     for r in test) / len(test)
            if best is None or ll < best[0]:
                best = (ll, cand)
        if best is None or best[0] >= current - 5e-4:
            break
        current, cand = best
        feats.append(cand)
        remaining.remove(cand)
        print(f"  + {cand[0]:9s} -> held-out logloss {current:.4f}")

    tables = build_tables(train, feats)
    bands = defaultdict(lambda: [0, 0])
    for r in test:
        p = predict(tables, feats, r)
        band = ("<0.02" if p < 0.02 else (">0.9" if p > 0.9 else "mid"))
        bands[band][r["fire_pre"]] += 1
    print("  determinism profile (held-out):")
    for band in ("<0.02", "mid", ">0.9"):
        n0, n1 = bands[band]
        n = n0 + n1
        print(f"    {band:5s}: {n:6d} rows ({n / len(test):.2%}), "
              f"actual fire rate {n1 / max(n, 1):.4f}")


def main():
    rows = load()
    print(f"rows: {len(rows)}, fires: {sum(r['fire_pre'] for r in rows)}")
    part_a(rows)
    part_b(rows)


if __name__ == "__main__":
    main()
