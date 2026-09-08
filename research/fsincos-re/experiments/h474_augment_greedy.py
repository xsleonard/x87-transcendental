#!/usr/bin/env python3
"""h474: augment the merged corpus with the h473 signals and re-run the
held-out greedy.

Precomputes per row (both batches + legacy corpus): lf/rf/mul/f4 low
bytes, chain product guard bits p1_g..p4_g (via the h453 replica), and
writes h464_package/augmented_labels.tsv.  Then greedy forward
selection from the frame (theta, rud, dist, low3) over the widened
pool: rdisc/ldisc top bits, rs bits 4..15, lane bits, u5d/ud bits,
ls bits, payload, lf/rf low nibbles, p1_g..p4_g — recursive-backoff
smoothing, held-out logloss, final determinism profile.

Run from /tmp/stageA.
"""
import math
from collections import defaultdict
from multiprocessing import Pool

from h437_gate_extraction import parse_trace_line, load_labeled_rows
from h466_paired_mining import upstream_features
from h471_frame_refine import load, build_tables, predict

PKG = "h464_package"
OUT = f"{PKG}/augmented_labels.tsv"


def augment(job):
    label_row, trace = job
    fields = parse_trace_line(trace)
    up = upstream_features(fields)
    if up is None:
        return None
    out = dict(label_row)
    out["lf_low8"] = int(fields["lf"], 16) & 0xFF
    out["rf_low8"] = int(fields["rf"], 16) & 0xFF
    out["mul_low8"] = int(fields["mul"], 16) & 0xFF
    out["f4_low8"] = int(fields["f4"], 16) & 0xFF
    for k in ("p1_g", "p2_g", "p3_g", "p4_g", "a1_g", "a2_g",
              "a3_g", "a4_g"):
        out[k] = up[k]
    return out


def main():
    rows = load()
    trace_of = {}
    for pkg in ("h464_package", "h469_package"):
        with open(f"{pkg}/selected.tsv") as fh:
            for line in fh:
                se, sig, theta, trace = line.rstrip("\n").split("\t")
                trace_of[(se, sig)] = trace
    for fields, _ in load_labeled_rows():
        raw = "COS_CARRIER " + " ".join(f"{k}={v}" for k, v in fields.items())
        trace_of[("corp", fields["mul"])] = raw
    jobs = [(r, trace_of[(r["se"], r["sig"])]) for r in rows
            if (r["se"], r["sig"]) in trace_of]
    with Pool(8) as pool:
        aug = [r for r in pool.map(augment, jobs, chunksize=500)
               if r is not None]
    print(f"augmented rows: {len(aug)}")
    cols = list(aug[0].keys())
    with open(OUT, "w") as fh:
        fh.write("\t".join(str(c) for c in cols) + "\n")
        for r in aug:
            fh.write("\t".join(str(r[c]) for c in cols) + "\n")

    frame = [
        ("theta", lambda r: r["theta"]),
        ("rud", lambda r: r["rud"]),
        ("dist", lambda r: r["dist"]),
        ("low3", lambda r: r["low3"]),
    ]
    pool_feats = (
        [(f"rd_b{b}", (lambda b: lambda r: (r["rdisc_hi8"] >> b) & 1)(b))
         for b in range(8)]
        + [(f"ld_b{b}", (lambda b: lambda r: (r["ldisc_hi8"] >> b) & 1)(b))
           for b in range(4, 8)]
        + [(f"rs_b{b}", (lambda b: lambda r: (r["rs_low16"] >> b) & 1)(b))
           for b in range(4, 16)]
        + [(f"lane_b{b}", (lambda b: lambda r: (r["lane"] >> b) & 1)(b))
           for b in range(8)]
        + [(f"u5d_b{b}", (lambda b: lambda r: (r["u5d"] >> b) & 1)(b))
           for b in range(5)]
        + [(f"ud_b{b}", (lambda b: lambda r: (r["ud"] >> b) & 1)(b))
           for b in range(3)]
        + [(f"ls_b{b}", (lambda b: lambda r: (r["ls_low8"] >> b) & 1)(b))
           for b in range(6)]
        + [("payload", lambda r: r["payload"]),
           ("lf_nib1", lambda r: r["lf_low8"] >> 4),
           ("lf_nib0", lambda r: r["lf_low8"] & 0xF),
           ("rf_nib1", lambda r: r["rf_low8"] >> 4)]
        + [(g, (lambda g: lambda r: r[g])(g))
           for g in ("p1_g", "p2_g", "p3_g", "p4_g",
                     "a1_g", "a2_g", "a3_g", "a4_g")]
    )
    for r in aug:
        pass
    train = [r for r in aug if hash((r["se"], r["sig"])) & 1 == 0]
    test = [r for r in aug if hash((r["se"], r["sig"])) & 1 == 1]
    print(f"train {len(train)}, test {len(test)}")

    def ll(tables, feats):
        return sum(-math.log(predict(tables, feats, r)) if r["fire_pre"]
                   else -math.log(1 - predict(tables, feats, r))
                   for r in test) / len(test)

    feats = list(frame)
    tables = build_tables(train, feats)
    current = ll(tables, feats)
    print(f"frame baseline: {current:.4f}")
    remaining = list(pool_feats)
    while True:
        best = None
        for cand in remaining:
            trial = feats + [cand]
            tt = build_tables(train, trial)
            v = ll(tt, trial)
            if best is None or v < best[0]:
                best = (v, cand)
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
    print("determinism profile (held-out):")
    for band in ("<0.02", "mid", ">0.9"):
        n0, n1 = bands[band]
        n = n0 + n1
        print(f"  {band:5s}: {n:6d} rows ({n / len(test):.2%}), "
              f"actual fire rate {n1 / max(n, 1):.4f}")


if __name__ == "__main__":
    main()
