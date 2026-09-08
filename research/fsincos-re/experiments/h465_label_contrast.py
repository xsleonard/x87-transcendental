#!/usr/bin/env python3
"""h465: label the h464 family capture in both codings and run the
within-cell contrast ladder.

Labels per row (KEPT DISTINCT, per the second-pass lesson):
  fire_pre : pre-patch coding — hardware needs a nonzero offset from
             prepay = low3+8-dist (the family coding; the two ported
             Round-52 patches count as fires here);
  fire_post: post-patch coding — hardware differs from the model with
             the TRACED payload (the model's true residual).

Contrast ladder: rows grouped by nested match keys; a group containing
both fire and no-fire rows is a CONTRAST — direct evidence that the
matched state does not determine the borrow bit.  Exact matching is
only statistically reachable down to a limited granularity (the full
terminal state is injective in m — h413), so the ladder reports, per
level, how many groups have >=2 rows at all (collision mass) alongside
the contrast counts; a level with plenty of collisions and zero
contrasts is evidence FOR determination by that level's state.

  L0: dist, low3, theta
  L1: + payload(traced), ud, rud
  L2: + lane byte (rs aligned at the payload position), u5d
  L3: + rs low 16 bits, ls low 8 bits
  L4: + both products' discarded-field top bytes (from the trace)

Merges the pre-existing labeled corpus (same machinery over the h437
loaders) with the new h464 rows, deduplicated by input.

Outputs: h464_package/labels.tsv and a printed ladder report.
Run from /tmp/stageA (expects h464_package/{selected.tsv,hw_*.txt}).
"""
from collections import Counter, defaultdict
from multiprocessing import Pool

from h437_gate_extraction import (
    ROUNDING_MODES, load_labeled_rows, parse_trace_line,
    chop_to_67_bits, final_cosine_result)

PKG = "h464_package"
PROBE = list(range(-8, 9))


def label_row(job):
    """(fields, hw_sigs) -> labeled feature dict or None."""
    fields, hw_sigs = job
    if fields.get("active") != "1" or fields["lsign"] != "1" \
            or fields["rsign"] != "0":
        return None
    payload_traced = int(fields["payload"])
    if payload_traced == 0:
        return None
    dist, low3 = int(fields["dist"]), int(fields["low3"])
    prepay = low3 + 8 - dist
    le2, re2 = int(fields["le2"]), int(fields["re2"])
    ls, rs = int(fields["ls"], 16), int(fields["rs"], 16)
    scale = min(le2, re2, le2 - 8)
    A = ls << (le2 - scale)
    B = rs << (re2 - scale)
    unit = le2 - 8 - scale

    def results(payload_value):
        corr, corr_e = chop_to_67_bits(-(A - B + (payload_value << unit)),
                                       scale)
        return tuple(final_cosine_result(corr, corr_e, m)
                     for m in ROUNDING_MODES)

    hw = tuple(hw_sigs[m] for m in ROUNDING_MODES)
    allowed = [off for off in PROBE if results(prepay + off) == hw]
    if not allowed or len(allowed) == len(PROBE):
        return None
    lo_run = allowed[0] == PROBE[0]
    hi_run = allowed[-1] == PROBE[-1]
    if lo_run and not hi_run:
        b_hw, theta = 0, allowed[-1] + 1
    elif hi_run and not lo_run:
        b_hw, theta = 1, allowed[0]
    else:
        return None
    fire_pre = 1 if (1 if 0 >= theta else 0) != b_hw else 0
    fire_post = 0 if results(payload_traced) == hw else 1

    lane_shift = dist - 8
    lane = ((rs >> lane_shift) if lane_shift >= 0
            else (rs << -lane_shift)) & 0xFF
    return {
        "se": fields["_se"], "sig": fields["_sig"],
        "theta": theta, "b_hw": b_hw,
        "fire_pre": fire_pre, "fire_post": fire_post,
        "dist": dist, "low3": low3, "payload": payload_traced,
        "ud": int(fields["ud"]), "u5d": int(fields["u5d"]),
        "rud": int(fields["rud"]), "lane": lane,
        "rs_low16": rs & 0xFFFF, "ls_low8": ls & 0xFF,
        "ldisc_hi8": (int(fields["disc_hi"], 16) >> 56) & 0xFF,
        "rdisc_hi8": (int(fields["rdisc_hi"], 16) >> 56) & 0xFF,
    }


LEVELS = [
    ("L0", ["dist", "low3", "theta"]),
    ("L1", ["dist", "low3", "theta", "payload", "ud", "rud"]),
    ("L2", ["dist", "low3", "theta", "payload", "ud", "rud",
            "lane", "u5d"]),
    ("L3", ["dist", "low3", "theta", "payload", "ud", "rud",
            "lane", "u5d", "rs_low16", "ls_low8"]),
    ("L4", ["dist", "low3", "theta", "payload", "ud", "rud",
            "lane", "u5d", "rs_low16", "ls_low8",
            "ldisc_hi8", "rdisc_hi8"]),
]


def ladder(rows, coding):
    print(f"\n=== contrast ladder ({coding}) — "
          f"{len(rows)} rows, {sum(r[coding] for r in rows)} fires ===")
    print("level  groups  multi-row  contrast-groups  contrast-pairs")
    finest_pairs = []
    for name, keys in LEVELS:
        groups = defaultdict(list)
        for r in rows:
            groups[tuple(r[k] for k in keys)].append(r)
        multi = {k: g for k, g in groups.items() if len(g) > 1}
        contrast = {k: g for k, g in multi.items()
                    if len({r[coding] for r in g}) > 1}
        pairs = sum(sum(1 for r in g if r[coding]) *
                    sum(1 for r in g if not r[coding])
                    for g in contrast.values())
        print(f"{name}   {len(groups):7d}  {len(multi):8d}  "
              f"{len(contrast):14d}  {pairs:13d}")
        if contrast:
            finest_pairs = [(name, k, g) for k, g in contrast.items()]
    return finest_pairs


def main():
    jobs = []
    hw_files = {m: open(f"{PKG}/hw_{m}.txt").read().splitlines()
                for m in ROUNDING_MODES}
    with open(f"{PKG}/selected.tsv") as fh:
        for i, line in enumerate(fh):
            se, sig, theta_f, trace = line.rstrip("\n").split("\t")
            fields = parse_trace_line(trace)
            fields["_se"], fields["_sig"] = se, sig
            hw_sigs = {}
            for m in ROUNDING_MODES:
                tokens = hw_files[m][i].split()
                hw_sigs[m] = int(tokens[2], 16) if tokens[0] == "OK" else -1
            jobs.append((fields, hw_sigs))
    print(f"h464 captured rows: {len(jobs)}")

    # pre-existing corpus through the same labeling
    for fields, hw_sigs in load_labeled_rows():
        fields = dict(fields)
        fields["_se"], fields["_sig"] = "corp", fields["mul"]
        jobs.append((fields, hw_sigs))
    print(f"total rows incl. existing corpus: {len(jobs)}")

    with Pool(8) as pool:
        labeled = [r for r in pool.map(label_row, jobs, chunksize=2000)
                   if r is not None]
    # dedupe by input identity (corp rows key on traced square)
    unique = {}
    for r in labeled:
        unique[(r["se"], r["sig"])] = r
    rows = [r for r in unique.values() if -3 <= r["theta"] <= 3]
    print(f"labeled constrained unique rows (|theta|<=3): {len(rows)}")

    with open(f"{PKG}/labels.tsv", "w") as fh:
        cols = list(rows[0].keys())
        fh.write("\t".join(cols) + "\n")
        for r in rows:
            fh.write("\t".join(str(r[c]) for c in cols) + "\n")

    for coding in ("fire_pre", "fire_post"):
        finest = ladder(rows, coding)
        for name, key, group in finest[:4]:
            print(f"  sample contrast at {name}: key={key}")
            for r in group[:4]:
                print(f"    {r['se']}:{r['sig']} theta={r['theta']} "
                      f"{coding}={r[coding]}")


if __name__ == "__main__":
    main()
