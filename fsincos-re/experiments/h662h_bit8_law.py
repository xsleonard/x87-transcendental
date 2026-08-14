#!/usr/bin/env python3
"""h662h: theta ladder — pin the bit-(w+8) law exactly.

h662g: in the block-edge-critical set, up-fires follow bit(w+8) of
mag = S-B almost exactly (0.005/1.000), dn-fires require it (bit=0 ->
0.000 exact) with a second condition splitting on bit(w+9).  The shape
suggests run conditions at the next block level: count exact
exceptions, take dn joint tables over (bit8..bit12, pm_up, phw, theta),
and test the natural candidate: the fire condition is a SECOND
propagate-run condition in the retained field — run of ones in mag
starting at w+8 (dn) vs single bit (up).
"""
import pickle
from collections import defaultdict

CACHE = "h662e_rows.pkl"


def main():
    out = pickle.load(open(CACHE, "rb"))
    crit = [o for o in out if (o[3] + o[5]) % 8 == 7 and o[3] in (7, 8)]
    print(f"critical rows: {len(crit)}")

    # exact exception counts for the bit8 law
    cnt = defaultdict(lambda: [0, 0])
    for sign, th, fire, pm_up, w, phw, scale, S, B in crit:
        b8 = ((S - B) >> (w + 8)) & 1
        cnt[(sign, b8)][fire] += 1
    print("\nexact (sign, bit8) counts [clean, fire]:")
    for k in sorted(cnt, key=str):
        print(f"  {k}: {cnt[k]}")

    # dn: joint over (b8, b9, b10, b11) and run-of-ones from w+8
    print("\ndn rows, fire by (b8..b11):")
    t = defaultdict(lambda: [0, 0])
    runt = defaultdict(lambda: [0, 0])
    upt = defaultdict(lambda: [0, 0])
    for sign, th, fire, pm_up, w, phw, scale, S, B in crit:
        mag = S - B
        bits = tuple((mag >> (w + 8 + i)) & 1 for i in range(4))
        run = 0
        while (mag >> (w + 8 + run)) & 1:
            run += 1
        if sign == "dn":
            t[bits][fire] += 1
            runt[min(run, 12)][fire] += 1
        else:
            upt[min(run, 12)][fire] += 1
    for k in sorted(t):
        c0, c1 = t[k]
        n = c0 + c1
        if n >= 100:
            print(f"  b8..b11={k}: n={n} rate={c1/n:.4f}")
    print("\ndn fire by run-of-ones in mag from w+8:")
    for k in sorted(runt):
        c0, c1 = runt[k]
        n = c0 + c1
        if n >= 50:
            print(f"  run={k}: n={n} rate={c1/n:.4f}")
    print("up fire by same run:")
    for k in sorted(upt):
        c0, c1 = upt[k]
        n = c0 + c1
        if n >= 50:
            print(f"  run={k}: n={n} rate={c1/n:.4f}")

    # candidate laws, exact global scoring on ALL region rows
    # (non-critical region rows must stay fire=1 regardless)
    print("\n=== candidate full laws over the whole h658 region ===")
    laws = {
        "up: b8; dn: b8": lambda sign, mag, w: (mag >> (w + 8)) & 1,
        "up: b8; dn: b8&b9": lambda sign, mag, w:
            ((mag >> (w + 8)) & 1) if sign == "up"
            else ((mag >> (w + 8)) & 1) & ((mag >> (w + 9)) & 1),
        "up: b8; dn: run>=8": lambda sign, mag, w:
            ((mag >> (w + 8)) & 1) if sign == "up"
            else int(((mag >> (w + 8)) & 0xFF) == 0xFF),
    }
    for name, fn in laws.items():
        err = defaultdict(int)
        tot = 0
        for sign, th, fire, pm_up, w, phw, scale, S, B in out:
            critical = (pm_up + phw) % 8 == 7 and pm_up in (7, 8)
            mag = S - B
            pred = fn(sign, mag, w) if critical else 1
            tot += 1
            if pred != fire:
                err[(sign, th, "crit" if critical else "pure")] += 1
        e = sum(err.values())
        print(f"\n  [{name}] total errors {e} / {tot}")
        for k in sorted(err, key=str):
            print(f"    {k}: {err[k]}")


if __name__ == "__main__":
    main()
