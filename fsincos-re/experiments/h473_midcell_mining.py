#!/usr/bin/env python3
"""h473: paired mining inside the unresolved mid-band cells.

After h472 the frame (theta, rud, dist, low3, rdisc top bits) leaves a
29-percent mid band (fire rate ~0.31) concentrated at dist=8,
theta in {0,1}.  This pass mines ONLY those cells, pairing fire vs
no-fire rows matched on (theta, rud, low3, rdisc_hi8>>5) within
dist=8, with the widest feature panel yet:

  - deep terminal windows: rs bits 4..23, ls bits 0..15, full 16-bit
    discarded tops of both products (recomputed exactly from traced
    operands), the accumulator residue's upper byte;
  - upstream replica state: m low 16 bits, sqdisc top byte, all chain
    guard/sticky/round-up bits, chain low bytes (lf/rf/f4/mul & 0xFF);

scored as paired orderings per held-out half (imbalance must replicate
to count).  Traces come from both batches plus the legacy corpus.

Run from /tmp/stageA.
"""
import math
from collections import defaultdict
from multiprocessing import Pool

from h437_gate_extraction import parse_trace_line, load_labeled_rows
from h466_paired_mining import upstream_features
from h471_frame_refine import load

PAIR_KEYS = ("theta", "rud", "low3", "rd_top3")


def row_features(job):
    label_row, trace = job
    fields = parse_trace_line(trace)
    ls, rs = int(fields["ls"], 16), int(fields["rs"], 16)
    square = int(fields["mul"], 16)
    lf = int(fields["lf"], 16)
    rf = int(fields["rf"], 16)
    f4 = int(fields["f4"], 16)
    full_L = square * lf
    full_R = f4 * rf
    sL = max(full_L.bit_length() - 67, 0)
    sR = max(full_R.bit_length() - 67, 0)
    ldisc16 = ((full_L & ((1 << sL) - 1)) >> (sL - 16)) & 0xFFFF
    rdisc16 = ((full_R & ((1 << sR) - 1)) >> (sR - 16)) & 0xFFFF
    feats = {
        "rs_b4_11": (rs >> 4) & 0xFF,
        "rs_b12_23": (rs >> 12) & 0xFFF,
        "ls_low16": ls & 0xFFFF,
        "ldisc16": ldisc16,
        "rdisc16_low": rdisc16 & 0x1FFF,     # below the matched top-3
        "mul_low8": square & 0xFF,
        "lf_low8": lf & 0xFF,
        "rf_low8": rf & 0xFF,
        "f4_low8": f4 & 0xFF,
    }
    up = upstream_features(fields)
    if up is None:
        return None
    feats.update(up)
    key = tuple(int(label_row[k]) if k != "rd_top3"
                else int(label_row["rdisc_hi8"]) >> 5
                for k in PAIR_KEYS)
    return (key, int(label_row["fire_pre"]), feats)


def main():
    rows = load()
    mid = [r for r in rows if r["dist"] == 8 and r["theta"] in (0, 1)]
    print(f"mid-cell rows (dist=8, theta in 0/1): {len(mid)}, "
          f"fires {sum(r['fire_pre'] for r in mid)}")

    trace_of = {}
    for pkg in ("h464_package", "h469_package"):
        with open(f"{pkg}/selected.tsv") as fh:
            for line in fh:
                se, sig, theta, trace = line.rstrip("\n").split("\t")
                trace_of[(se, sig)] = trace
    for fields, _ in load_labeled_rows():
        raw = "COS_CARRIER " + " ".join(f"{k}={v}" for k, v in fields.items())
        trace_of[("corp", fields["mul"])] = raw

    jobs = [(r, trace_of[(r["se"], r["sig"])]) for r in mid
            if (r["se"], r["sig"]) in trace_of]
    with Pool(8) as pool:
        feat_rows = [x for x in pool.map(row_features, jobs, chunksize=500)
                     if x is not None]
    print(f"feature rows: {len(feat_rows)}")

    groups = defaultdict(list)
    for key, fire, feats in feat_rows:
        groups[key].append((fire, feats))
    pairs = []
    for key, members in groups.items():
        half = hash(key) & 1
        fires = [m for m in members if m[0]]
        cools = [m for m in members if not m[0]]
        for F in fires:
            for N in cools:
                pairs.append((half, F[1], N[1]))
    print(f"pairs: {len(pairs)} "
          f"(half0 {sum(1 for h, _, _ in pairs if h == 0)})")

    names = sorted(pairs[0][1])
    results = []
    for name in names:
        zs = []
        for half in (0, 1):
            wins = losses = 0
            for h, F, N in pairs:
                if h != half:
                    continue
                if F[name] > N[name]:
                    wins += 1
                elif F[name] < N[name]:
                    losses += 1
            n = wins + losses
            zs.append((wins - losses) / math.sqrt(n) if n else 0.0)
        results.append((min(abs(z) for z in zs)
                        if zs[0] * zs[1] > 0 else 0.0, name, zs))
    results.sort(reverse=True)
    print(f"\n{'feature':12s}  z(half0)  z(half1)   [replicated |z|]")
    for repl, name, zs in results[:16]:
        print(f"{name:12s}  {zs[0]:+7.1f}  {zs[1]:+7.1f}   {repl:5.1f}")


if __name__ == "__main__":
    main()
