#!/usr/bin/env python3
"""h478-obs: observable-only recompute of the boundary-zone statistics.

h477f found that on the tie stratum 15 percent of rows are blind (the
fire delta produces an architecturally identical result) and that one
apparent exact condition was pure visibility.  This applies the same
lens to the WHOLE boundary zone (discarded field within 2 units of
either boundary, the theta in [-2,+2] corpus): per row, compute which
deltas in {-2,-1,+1,+2} are visible (differ from delta=0 in any
rounding mode) and which delta the hardware actually shows.

Questions answered:
  1. what fraction of zone rows / of each disc-code stratum is blind
     to its natural fire direction;
  2. the h471-style cell map (dist, disc_code, rud, low3, rdisc_hi3):
     how many mixed cells become pure (rate 0 or 1) when restricted to
     visible rows -- does the mid band dissolve, shrink, or persist;
  3. the corrected mid-band fire rate.

Run from /tmp/stageA.  Writes h478_zone.tsv.
"""
from collections import defaultdict
from multiprocessing import Pool

from h437_gate_extraction import (
    ROUNDING_MODES, parse_trace_line, load_labeled_rows,
    final_cosine_result)


def score_row(job):
    fields, hw_sigs = job
    if fields.get("active") != "1" or fields["lsign"] != "1" \
            or fields["rsign"] != "0":
        return None
    dist, low3 = int(fields["dist"]), int(fields["low3"])
    prepay = low3 + 8 - dist
    le2, re2 = int(fields["le2"]), int(fields["re2"])
    ls, rs = int(fields["ls"], 16), int(fields["rs"], 16)
    scale = min(le2, re2, le2 - 8)
    A = ls << (le2 - scale)
    B = rs << (re2 - scale)
    unit = le2 - 8 - scale
    Pv = prepay << unit
    hw = tuple(hw_sigs[m] for m in ROUNDING_MODES)

    M = A - B + Pv
    if M <= 0:
        return None
    k = max(M.bit_length() - 67, 0)
    if k < 3:
        return None
    mk = (1 << k) - 1
    disc = M & mk
    if 2 < disc < mk - 1:
        return None                                # boundary zone only
    disc_code = disc if disc <= 2 else disc - (1 << k)   # 0,1,2,-1,-2
    R = M >> k

    def res(delta):
        return tuple(final_cosine_result(-(R + delta), scale + k, m)
                     for m in ROUNDING_MODES)

    r0 = res(0)
    vis = {}
    fire_delta = None
    if hw == r0:
        fire_delta = 0
    for d in (-2, -1, 1, 2):
        rd = res(d)
        vis[d] = 1 if rd != r0 else 0
        if fire_delta is None and hw == rd and vis[d]:
            fire_delta = d
    if fire_delta is None:
        fire_delta = 99                                    # unexplained

    rdisc_hi = int(fields.get("rdisc_hi", "0"), 16)
    cell = (dist, disc_code, int(fields.get("rud", -1)), low3,
            rdisc_hi >> 61)
    return (cell, disc_code, fire_delta, vis[-2], vis[-1], vis[1],
            vis[2], k, prepay)


def main():
    jobs = []
    for pkg in ("h464_package", "h469_package"):
        hw_files = {m: open(f"{pkg}/hw_{m}.txt").read().splitlines()
                    for m in ROUNDING_MODES}
        with open(f"{pkg}/selected.tsv") as fh:
            for i, line in enumerate(fh):
                se, sig, theta, trace = line.rstrip("\n").split("\t")
                fields = parse_trace_line(trace)
                hw_sigs = {}
                for m in ROUNDING_MODES:
                    tokens = hw_files[m][i].split()
                    hw_sigs[m] = int(tokens[2], 16) if tokens[0] == "OK" \
                        else -1
                jobs.append((fields, hw_sigs))
    jobs.extend(load_labeled_rows())
    with Pool(8) as pool:
        rows = [r for r in pool.map(score_row, jobs, chunksize=500)
                if r is not None]
    print(f"zone rows: {len(rows)}")

    # 1. blindness per disc_code stratum (natural direction: -1 for
    # disc_code >= 0 [low side], +1 for disc_code < 0 [high side])
    print(f"\n{'disc':5s} {'n':>7s} {'fires':>6s} {'blind':>6s} "
          f"{'vis-n':>7s} {'vis-fires':>9s} {'raw-rate':>8s} "
          f"{'vis-rate':>8s}")
    for code in (0, 1, 2, -1, -2):
        sub = [r for r in rows if r[1] == code]
        nat = 4 if code >= 0 else 5                 # vis[-1] / vis[+1]
        fires = sum(1 for r in sub if r[2] not in (0, 99))
        blind = sum(1 for r in sub if not r[nat])
        vsub = [r for r in sub if r[nat]]
        vfires = sum(1 for r in vsub if r[2] not in (0, 99))
        print(f"{code:5d} {len(sub):7d} {fires:6d} {blind:6d} "
              f"{len(vsub):7d} {vfires:9d} "
              f"{fires/len(sub) if sub else 0:8.3f} "
              f"{vfires/len(vsub) if vsub else 0:8.3f}")
    weird = sum(1 for r in rows if r[2] == 99)
    print(f"unexplained-delta rows: {weird}")

    # fire delta distribution per disc_code
    print("\n--- hardware fire_delta by disc_code ---")
    tab = defaultdict(lambda: defaultdict(int))
    for r in rows:
        tab[r[1]][r[2]] += 1
    for code in (0, 1, 2, -1, -2):
        d = tab[code]
        line = " ".join(f"{dd}:{d[dd]}" for dd in sorted(d))
        print(f"  disc={code:3d}  {line}")

    # 2. cell map purity, all vs visible
    def cellmap(visible_only):
        cells = defaultdict(lambda: [0, 0])
        for r in rows:
            nat = 4 if r[1] >= 0 else 5
            if visible_only and not r[nat]:
                continue
            c = cells[r[0]]
            c[0] += 1
            c[1] += 1 if r[2] not in (0, 99) else 0
        return cells

    for tag, vo in (("ALL ROWS", False), ("VISIBLE ONLY", True)):
        cells = cellmap(vo)
        big = {c: v for c, v in cells.items() if v[0] >= 8}
        mixed = {c: v for c, v in big.items()
                 if 0 < v[1] < v[0]}
        mixed_mid = {c: v for c, v in mixed.items()
                     if 0.2 <= v[1] / v[0] <= 0.7}
        n_rows_big = sum(v[0] for v in big.values())
        n_rows_mixed = sum(v[0] for v in mixed.values())
        n_rows_mid = sum(v[0] for v in mixed_mid.values())
        print(f"\n=== cell map ({tag}), cells n>=8 ===")
        print(f"  cells: {len(big)}, mixed: {len(mixed)}, "
              f"mid (0.2-0.7): {len(mixed_mid)}")
        print(f"  rows in cells: {n_rows_big}, in mixed: "
              f"{n_rows_mixed} ({n_rows_mixed/n_rows_big:.1%}), "
              f"in mid: {n_rows_mid} ({n_rows_mid/n_rows_big:.1%})")

    with open("h478_zone.tsv", "w") as fh:
        fh.write("dist\tdisc_code\trud\tlow3\trdhi3\tfire_delta\t"
                 "vis_m2\tvis_m1\tvis_p1\tvis_p2\tk\tprepay\n")
        for cell, code, fd, vm2, vm1, vp1, vp2, k, pp in rows:
            fh.write("\t".join(str(x) for x in
                               (*cell, fd, vm2, vm1, vp1, vp2, k, pp))
                     + "\n")
    print("\nwrote h478_zone.tsv")


if __name__ == "__main__":
    main()
