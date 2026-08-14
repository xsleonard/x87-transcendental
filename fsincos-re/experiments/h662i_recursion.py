#!/usr/bin/env python3
"""h662i: theta ladder — the run recursion's next level.

h662h: in the critical set, up-fire <=> run1 >= 1 and dn-fire <=> run1
>= 2 (both sides exact), where run1 = run of ones in mag from w+8;
dn run1 = 1 is a 0.227 sub-coin; up run1 = 0 has 388 stray fires.
Both smell like the SAME block-edge recursion one level up.  Probe:
sub-coin cross-tabs by phw, pm_up, theta, single bits w+9..w+24,
second-level run (from w+16), and the stray-fire census.
"""
import pickle
from collections import defaultdict

CACHE = "h662e_rows.pkl"


def main():
    out = pickle.load(open(CACHE, "rb"))
    crit = [o for o in out if (o[3] + o[5]) % 8 == 7 and o[3] in (7, 8)]

    def run_from(mag, pos):
        r = 0
        while (mag >> (pos + r)) & 1:
            r += 1
        return r

    # dn run1==1 sub-coin
    sub = []
    stray = []
    for o in crit:
        sign, th, fire, pm_up, w, phw, scale, S, B = o
        mag = S - B
        r1 = run_from(mag, w + 8)
        if sign == "dn" and r1 == 1:
            sub.append(o + (mag,))
        if sign == "up" and r1 == 0 and fire:
            stray.append(o + (mag,))
    n = len(sub)
    nf = sum(o[2] for o in sub)
    print(f"dn run1==1 rows: {n}, fire rate {nf/n:.4f}")

    def xtab(tag, fn):
        t = defaultdict(lambda: [0, 0])
        for o in sub:
            t[fn(o)][o[2]] += 1
        line = []
        flag = ""
        for k in sorted(t, key=str):
            c0, c1 = t[k]
            nn = c0 + c1
            if nn < 80:
                continue
            r = c1 / nn
            if r <= 0.03 or r >= 0.97:
                flag = " FLAGGED"
            line.append(f"{k}:{nn}={r:.3f}")
        print(f"  [{tag}]{flag} " + "  ".join(line[:14]), flush=True)

    xtab("phw", lambda o: o[5])
    xtab("pm_up", lambda o: o[3])
    xtab("theta", lambda o: o[1])
    xtab("w", lambda o: o[4])
    for i in range(9, 25):
        xtab(f"bit w+{i}", lambda o, i=i: (o[9] >> (o[4] + i)) & 1)
    xtab("run2 from w+16", lambda o: min(run_from(o[9], o[4] + 16), 6))
    xtab("run2 from w+10", lambda o: min(run_from(o[9], o[4] + 10), 6))
    xtab("(b16,b17)", lambda o: ((o[9] >> (o[4] + 16)) & 1,
                                 (o[9] >> (o[4] + 17)) & 1))
    # zero-run below the next block edge: bits w+9..w+15 pattern
    xtab("bits w+9..w+15", lambda o: (o[9] >> (o[4] + 9)) & 0x7F)

    # stray up fires
    print(f"\nstray up fires (run1==0): {len(stray)}")
    t = defaultdict(int)
    for o in stray:
        mag = o[9]
        w = o[4]
        t[(o[1], o[5], (mag >> (w + 9)) & 7)] += 1
    for k in sorted(t, key=str):
        print(f"  (th, phw, b9..b11)={k}: {t[k]}")


if __name__ == "__main__":
    main()
