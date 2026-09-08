#!/usr/bin/env python3
"""h662j: theta ladder — up-stray denominators and the unified block law.

h662h/i: in the critical set, dn fire <=> run1 >= 1 + (phw==7) with
ZERO exceptions either side; up fire <=> run1 >= 1 except 388 stray
fires, all at (phw=7, b8=0, b9=1), spread flat over b10/b11.  Frame:
at phw=7 the next block START is w+9, not w+8; a run of ones starting
exactly at the block start may recurse the same law one level up.
Probe: (1) exact up denominators by (phw, b8, b9); (2) up phw=7 b8=0
fire rate vs run9 = run of ones from w+9 (threshold hunt + end-phase);
(3) same table for dn b8=0 as control; (4) exact scoring of unified
candidate laws on the critical set.
"""
import pickle
from collections import defaultdict

CACHE = "h662e_rows.pkl"


def run_from(mag, pos):
    r = 0
    while (mag >> (pos + r)) & 1:
        r += 1
    return r


def main():
    out = pickle.load(open(CACHE, "rb"))
    crit = [o for o in out if (o[3] + o[5]) % 8 == 7 and o[3] in (7, 8)]
    print(f"critical rows: {len(crit)}")

    rows = []
    for sign, th, fire, pm_up, w, phw, scale, S, B in crit:
        mag = S - B
        b8 = (mag >> (w + 8)) & 1
        b9 = (mag >> (w + 9)) & 1
        r1 = run_from(mag, w + 8)
        r9 = run_from(mag, w + 9)
        rows.append((sign, th, fire, w, phw, mag, b8, b9, r1, r9))

    # (1) up denominators
    print("\nup rows by (phw, b8, b9): [clean, fire]")
    t = defaultdict(lambda: [0, 0])
    for r in rows:
        if r[0] == "up":
            t[(r[4], r[6], r[7])][r[2]] += 1
    for k in sorted(t):
        c0, c1 = t[k]
        print(f"  (phw,b8,b9)={k}: n={c0+c1} [clean={c0}, fire={c1}] "
              f"rate={c1/(c0+c1):.4f}")

    # (2) up phw=7 b8=0: fire by run9, exact, no floor
    print("\nup phw=7 b8=0: fire by run9 (run of ones from w+9):")
    t = defaultdict(lambda: [0, 0])
    for r in rows:
        if r[0] == "up" and r[4] == 7 and r[6] == 0:
            t[r[9]][r[2]] += 1
    for k in sorted(t):
        c0, c1 = t[k]
        print(f"  run9={k}: n={c0+c1} [clean={c0}, fire={c1}]")

    # control: up phw=0 b8=0 by run9 (expect zero fires)
    nf = sum(r[2] for r in rows if r[0] == "up" and r[4] == 0 and r[6] == 0)
    nn = sum(1 for r in rows if r[0] == "up" and r[4] == 0 and r[6] == 0)
    print(f"control up phw=0 b8=0: {nf} fires / {nn}")

    # (3) dn b8=0 by (phw, run9) — control for a dn stray tail
    print("\ndn b8=0: fire by (phw, run9):")
    t = defaultdict(lambda: [0, 0])
    for r in rows:
        if r[0] == "dn" and r[6] == 0:
            t[(r[4], r[9])][r[2]] += 1
    for k in sorted(t):
        c0, c1 = t[k]
        print(f"  (phw,run9)={k}: n={c0+c1} [clean={c0}, fire={c1}]")

    # (4) unified law scoring on the critical set
    #   dn: fire <=> r1 >= 1 + (phw==7)
    #   up: fire <=> r1 >= 1  OR  (phw==7 and b8==0 and r9 >= T)
    print("\nunified law errors on critical set, by up-stray threshold T:")
    base_dn = sum(1 for r in rows
                  if r[0] == "dn" and r[2] != int(r[8] >= 1 + (r[4] == 7)))
    print(f"  dn law [r1 >= 1+(phw==7)]: {base_dn} errors")
    for T in list(range(4, 13)) + [99]:
        e = 0
        for r in rows:
            if r[0] != "up":
                continue
            pred = int(r[8] >= 1 or (r[4] == 7 and r[9] >= T))
            e += pred != r[2]
        print(f"  up law [r1>=1 or (phw=7 & r9>={T})]: {e} errors")

    # stray autopsy: run9 histogram of the strays and their non-firing
    # neighbours at the candidate boundary
    print("\nstray (up, phw=7, b8=0, fire=1) run9 histogram:")
    t = defaultdict(int)
    for r in rows:
        if r[0] == "up" and r[4] == 7 and r[6] == 0 and r[2]:
            t[r[9]] += 1
    for k in sorted(t):
        print(f"  run9={k}: {t[k]}")


if __name__ == "__main__":
    main()
