#!/usr/bin/env python3
"""h662g: theta ladder — the coin vs the SUM bits (carry-select frame).

h662e/f: the block-edge coin is determined by a <=48-bit (S,B) window
(71/71 identical-window groups agree) yet is neither any affine parity
of the window bits nor depth-6 tree structure.  The canonical deep
functions of (S,B) an adder produces are the sum bits — carry chains,
nonlinear in the inputs, invisible to parity/tree fits over (S,B).

A carry-select block chooses between the two precomputed sums
mag = S-B (carry-in 1 into the block frame) and mag-1 (carry-in 0).
Cross-tab the coin against single bits of mag and mag-1 at positions
w-4 .. j+8, plus the discard value's offset census per theta.
"""
import pickle
from collections import defaultdict

CACHE = "h662e_rows.pkl"


def main():
    out = pickle.load(open(CACHE, "rb"))
    crit = [o for o in out if (o[3] + o[5]) % 8 == 7 and o[3] in (7, 8)]
    print(f"critical rows: {len(crit)}", flush=True)

    # discard-vs-theta sanity census (what exactly is disc at theta?)
    cen = defaultdict(lambda: defaultdict(int))
    for sign, th, fire, pm_up, w, phw, scale, S, B in crit[:50000]:
        mag = S - B
        disc = mag & ((1 << w) - 1)
        off = (1 << w) - disc          # distance below 2^w
        if off > 4 and disc > 4:
            off = -99                  # neither end
        elif disc <= 4:
            off = -disc                # near all-zeros: -disc
        cen[(sign, th)][off] += 1
    print("\ndiscard offset census (off = 2^w - disc if near top, "
          "-disc if near 0):")
    for k in sorted(cen, key=str):
        tot = sum(cen[k].values())
        s = "  ".join(f"{o}:{c/tot:.3f}" for o, c in
                      sorted(cen[k].items()))
        print(f"  {k}: {s}")

    # coin vs mag / mag-1 bits
    for tag, delta in (("mag", 0), ("mag-1", -1)):
        print(f"\n[{tag}] fire by (sign, bitpos-rel-w, bit):")
        flags = 0
        for rel in range(-4, 13):
            t = defaultdict(lambda: [0, 0])
            for sign, th, fire, pm_up, w, phw, scale, S, B in crit:
                v = S - B + delta
                i = w + rel
                if i < 0:
                    continue
                t[(sign, (v >> i) & 1)][fire] += 1
            line = []
            for k in sorted(t, key=str):
                c0, c1 = t[k]
                nn = c0 + c1
                if nn < 500:
                    continue
                r = c1 / nn
                mark = ""
                if r <= 0.1 or r >= 0.9:
                    mark = "*SPLIT*"
                    flags += 1
                elif not 0.45 <= r <= 0.55:
                    mark = "*lean*"
                    flags += 1
                line.append(f"{k}={r:.3f}{mark}(n={nn})")
            print(f"  rel={rel:+d}: " + "  ".join(line), flush=True)
        print(f"  flags: {flags}")


if __name__ == "__main__":
    main()
