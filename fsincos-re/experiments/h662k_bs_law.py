#!/usr/bin/env python3
"""h662k: theta ladder — the block-start law, exact score + autopsy.

h662j: at phw=7 up rows always have b8=0 and fire <=> b9 exactly; at
phw=0 up fire <=> b8.  Define bs = next block-start above w+7 (w+8 at
phw=0, w+9 at phw=7).  Candidate final law on the critical set:
  up: fire <=> mag bit(bs) = 1
  dn: fire <=> mag bit(w+8) = 1 AND mag bit(bs) = 1
Score exactly on the critical set and the full h658 region (pred=1 on
non-critical rows), and autopsy every exception in full detail.
"""
import pickle
from collections import defaultdict

CACHE = "h662e_rows.pkl"


def main():
    out = pickle.load(open(CACHE, "rb"))
    print(f"region rows: {len(out)}")

    err = defaultdict(int)
    bad = []
    for o in out:
        sign, th, fire, pm_up, w, phw, scale, S, B = o
        critical = (pm_up + phw) % 8 == 7 and pm_up in (7, 8)
        if critical:
            mag = S - B
            bs = w + 8 + ((8 - phw) % 8)
            b8 = (mag >> (w + 8)) & 1
            bbs = (mag >> bs) & 1
            pred = bbs if sign == "up" else (b8 & bbs)
        else:
            pred = 1
        if pred != fire:
            err[(sign, th, "crit" if critical else "pure")] += 1
            bad.append(o)
    print(f"\nblock-start law total errors: {sum(err.values())} / {len(out)}")
    for k in sorted(err, key=str):
        print(f"  {k}: {err[k]}")

    for o in bad:
        sign, th, fire, pm_up, w, phw, scale, S, B = o
        mag = S - B
        bs = w + 8 + ((8 - phw) % 8)
        print(f"\nexception: sign={sign} th={th} fire={fire} pm_up={pm_up} "
              f"w={w} phw={phw} scale={scale}")
        print(f"  S    = {S:#x}")
        print(f"  B    = {B:#x}")
        print(f"  mag  = {mag:#x}")
        print(f"  mag bits w-4..w+24 (lsb first): "
              + "".join(str((mag >> (w + i)) & 1) for i in range(-4, 25)))
        print(f"  bs=w+{bs-w}, bit(bs)={(mag >> bs) & 1}, "
              f"b8={(mag >> (w + 8)) & 1}, run1="
              f"{next(i for i in range(64) if not (mag >> (w + 8 + i)) & 1)}")


if __name__ == "__main__":
    main()
