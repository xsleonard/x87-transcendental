#!/usr/bin/env python3
"""h477f: observability audit of the tie stratum.

For each exact-tie row, obs = 1 iff R and R-1 yield different
architectural results in ANY rounding mode.  Blind rows (obs=0) cannot
show a lost carry regardless of what the hardware does, so every fire
rate must be recomputed over observable rows only.  This decides how
much of the h477c/e gradient structure (k, prepay, R_low3, rud) is
gate versus visibility.
"""
from multiprocessing import Pool
from collections import defaultdict
from h437_gate_extraction import (ROUNDING_MODES, parse_trace_line,
                                  load_labeled_rows, final_cosine_result)

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
    A = ls << (le2 - scale); B = rs << (re2 - scale)
    unit = le2 - 8 - scale
    Pv = prepay << unit
    hw = tuple(hw_sigs[m] for m in ROUNDING_MODES)
    M = A - B + Pv
    if M <= 0: return None
    k = max(M.bit_length() - 67, 0)
    if k < 3 or (M & ((1 << k) - 1)): return None
    R = M >> k
    def res(delta):
        return tuple(final_cosine_result(-(R+delta), scale+k, m)
                     for m in ROUNDING_MODES)
    r0, rm1 = res(0), res(-1)
    obs = 1 if r0 != rm1 else 0
    fire = 0 if r0 == hw else (1 if rm1 == hw else 2)
    return (fire, obs, k, dist, low3, prepay,
            int(fields.get("rud", -1)), R & 7)

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
                    t = hw_files[m][i].split()
                    hw_sigs[m] = int(t[2], 16) if t[0] == "OK" else -1
                jobs.append((fields, hw_sigs))
    jobs.extend(load_labeled_rows())
    with Pool(8) as pool:
        rows = [r for r in pool.map(score_row, jobs, chunksize=500) if r]

    n = len(rows); nf = sum(1 for r in rows if r[0]==1)
    nobs = sum(1 for r in rows if r[1])
    print(f"tie rows {n}, fires {nf}, observable {nobs}, "
          f"fire rate among observable {nf/nobs:.3f}")
    blind_fires = sum(1 for r in rows if r[0]==1 and not r[1])
    print(f"fires on blind rows (must be 0): {blind_fires}")

    def xtab(name, idx):
        b = defaultdict(lambda: [0,0])
        for r in rows:
            if r[1]:
                c = b[r[idx]]; c[0]+=1; c[1]+= 1 if r[0]==1 else 0
        print(f"--- observable-only fire rate by {name} ---")
        for v in sorted(b):
            tot,f = b[v]
            if tot >= 8:
                print(f"  {name}={v:<4} n={tot:6d} fires={f:5d} rate={f/tot:.3f}")
    for name, idx in (("k",2),("dist",3),("low3",4),("prepay",5),
                      ("rud",6),("R_low3",7)):
        xtab(name, idx)

    def obstab(name, idx):
        b = defaultdict(lambda: [0,0])
        for r in rows:
            c = b[r[idx]]; c[0]+=1; c[1]+=r[1]
        print(f"--- observability by {name} ---")
        for v in sorted(b):
            tot,o = b[v]
            if tot >= 8:
                print(f"  {name}={v:<4} n={tot:6d} obs={o:5d} rate={o/tot:.3f}")
    for name, idx in (("k",2),("prepay",5),("R_low3",7)):
        obstab(name, idx)

if __name__ == "__main__":
    main()
