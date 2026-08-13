#!/usr/bin/env python3
"""h466: paired-difference mining over the L2 contrast groups.

h465 produced 872 groups matched on (dist, low3, theta, payload, ud,
rud, lane, u5d) that contain both firing and non-firing rows — 2,995
fire/no-fire pairs.  Within a pair every matched quantity cancels, so a
feature that systematically orders (fire > no-fire) across pairs is a
gate input candidate with cell confounds removed.

Per row, the feature panel combines:
  - deeper terminal windows: rs bits 8..23, ls low byte, both traced
    discarded-field top bytes;
  - upstream state via the h453 bit-exact replica (m recovered from the
    traced square, exponent by chain validation): m low byte, the
    square's discarded fraction top byte, the four chain adds'
    guard/sticky/round-up bits, the four product chops' guard/sticky;
  - the exact boundary residue rem (distance to the crossing in
    sub-payload units, 16-bit window).

Scoring per feature f over pairs (F fires, N does not):
  wins  = #pairs with f(F) > f(N);  losses = #pairs with f(F) < f(N)
A feature with wins+losses large and one side dominant orders the gate.
Binary features are reported as (F=1,N=0) vs (F=0,N=1) counts.

Held-out discipline: pairs are split by group-key hash into two halves;
scores are printed per half — only features whose imbalance replicates
across halves count.

Run from /tmp/stageA (expects h464_package/labels.tsv).
"""
import math
from collections import defaultdict
from multiprocessing import Pool

from h437_gate_extraction import parse_trace_line
from h453_chain_variants import (
    C6_1, C6_2, C6_3, C6_4, C6_5, C6_6, recover_m, mul_round)
from h454_stale_carry import normalize_state, mul_state, add_state

PKG = "h464_package"
L2_KEYS = ["dist", "low3", "theta", "payload", "ud", "rud", "lane", "u5d"]


def upstream_features(fields):
    """Replica intermediates from the traced square (self-contained)."""
    square_sig = int(fields["mul"], 16)
    m = recover_m(square_sig)
    if m is None:
        return None
    lf_t, rf_t = int(fields["lf"], 16), int(fields["rf"], 16)
    for e2m in (-66, -67, -65, -68, -64):
        mag = (0, e2m, m)
        sq, st_sq = mul_state(mag, mag, 67, "chop")
        if sq[2] != square_sig:
            return None
        f4, st_f4 = mul_state(sq, sq, 67, "chop")
        p1, st_p1 = mul_state(f4, C6_5, 67, "chop")
        a1, st_a1 = add_state(C6_3, p1, 64, "rn")
        p2, st_p2 = mul_state(f4, a1, 67, "chop")
        neg, st_a2 = add_state(C6_1, p2, 64, "rn")
        p3, st_p3 = mul_state(f4, C6_6, 67, "chop")
        a3, st_a3 = add_state(C6_4, p3, 64, "rn")
        p4, st_p4 = mul_state(f4, a3, 67, "chop")
        pos, st_a4 = add_state(C6_2, p4, 64, "rn")
        if neg[2] == lf_t and pos[2] == rf_t:
            msq = m * m
            s = msq.bit_length() - 67
            feats = {
                "m_low8": m & 0xFF,
                "sqdisc_hi8": (msq & ((1 << s) - 1)) >> (s - 8),
            }
            for name, st in (("sq", st_sq), ("f4", st_f4),
                             ("p1", st_p1), ("a1", st_a1),
                             ("p2", st_p2), ("a2", st_a2),
                             ("p3", st_p3), ("a3", st_a3),
                             ("p4", st_p4), ("a4", st_a4)):
                feats[f"{name}_g"], feats[f"{name}_s"], feats[f"{name}_u"] = st
            return feats
    return None


def row_features(job):
    label_row, trace = job
    fields = parse_trace_line(trace)
    dist = int(fields["dist"])
    low3 = int(fields["low3"])
    prepay = low3 + 8 - dist
    le2, re2 = int(fields["le2"]), int(fields["re2"])
    ls, rs = int(fields["ls"], 16), int(fields["rs"], 16)
    scale = min(le2, re2, le2 - 8)
    A = ls << (le2 - scale)
    B = rs << (re2 - scale)
    unit = le2 - 8 - scale
    mag = A - B + (prepay << unit)
    shift = mag.bit_length() - 67
    rem = mag & ((1 << shift) - 1)
    feats = {
        "rs_b8_23": (rs >> 8) & 0xFFFF,
        "rs_low8": rs & 0xFF,
        "ls_low8": ls & 0xFF,
        "ls_b8_15": (ls >> 8) & 0xFF,
        "ldisc_hi8": (int(fields["disc_hi"], 16) >> 56) & 0xFF,
        "rdisc_hi8": (int(fields["rdisc_hi"], 16) >> 56) & 0xFF,
        "rem_low16": rem & 0xFFFF,
        "rem_hi8": (rem >> max(shift - 8, 0)) & 0xFF,
    }
    up = upstream_features(fields)
    if up is None:
        return None
    feats.update(up)
    key = tuple(int(label_row[k]) for k in L2_KEYS)
    return (key, int(label_row["fire_pre"]), label_row["se"],
            label_row["sig"], feats)


def main():
    header = None
    labels = []
    with open(f"{PKG}/labels.tsv") as fh:
        header = fh.readline().rstrip("\n").split("\t")
        for line in fh:
            labels.append(dict(zip(header, line.rstrip("\n").split("\t"))))
    # need the trace per labeled row: rebuild the (se,sig)->trace map
    trace_of = {}
    with open(f"{PKG}/selected.tsv") as fh:
        for line in fh:
            se, sig, theta, trace = line.rstrip("\n").split("\t")
            trace_of[(se, sig)] = trace
    from h437_gate_extraction import load_labeled_rows
    for fields, _ in load_labeled_rows():
        raw = "COS_CARRIER " + " ".join(f"{k}={v}" for k, v in fields.items())
        trace_of[("corp", fields["mul"])] = raw

    jobs = []
    for r in labels:
        trace = trace_of.get((r["se"], r["sig"]))
        if trace is not None:
            jobs.append((r, trace))
    with Pool(8) as pool:
        rows = [r for r in pool.map(row_features, jobs, chunksize=500)
                if r is not None]
    print(f"feature rows: {len(rows)}")

    groups = defaultdict(list)
    for key, fire, se, sig, feats in rows:
        groups[key].append((fire, feats))
    pairs = []
    for key, members in groups.items():
        fires = [f for f in members if f[0]]
        cools = [f for f in members if not f[0]]
        half = hash(key) & 1
        for F in fires:
            for N in cools:
                pairs.append((half, F[1], N[1]))
    print(f"contrast pairs: {len(pairs)} "
          f"(half0: {sum(1 for h, _, _ in pairs if h == 0)})")

    names = sorted(pairs[0][1])
    print(f"\n{'feature':12s} {'half':4s} {'F>N':>6s} {'F<N':>6s} "
          f"{'F=N':>6s}  imbalance")
    for name in names:
        line = f"{name:12s}"
        for half in (0, 1):
            wins = losses = ties = 0
            for h, F, N in pairs:
                if h != half:
                    continue
                if F[name] > N[name]:
                    wins += 1
                elif F[name] < N[name]:
                    losses += 1
                else:
                    ties += 1
            n = wins + losses
            z = (wins - losses) / math.sqrt(n) if n else 0.0
            line += f"  h{half} {wins:5d} {losses:5d} {ties:5d} z={z:+5.1f}"
        print(line)


if __name__ == "__main__":
    main()
