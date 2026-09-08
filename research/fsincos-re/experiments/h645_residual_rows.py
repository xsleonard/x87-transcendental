#!/usr/bin/env python3
"""h645: autopsy of the residual rows under the exact lattice law.

Assign each stratum (dist, side, low3, third) its lattice threshold
u*2^66 (the unique multiple inside the separation interval; strata whose
census showed errs use the lattice point at the best-T).  Predict
fire <=> M < u*2^66 strictly.  Print every mismatching row with its
margin offset from the lattice and its XD distance to the 1/3, 2/3
comparator constants.
"""
import pickle, sys
from collections import defaultdict

sys.path.insert(0, "/Users/steve/llm/x87-transcendental/fsincos-re/experiments")
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result

TIES = "ties_comb4.txt"
PREFIX = "comb4"
FEATCACHE = "h628_feats.pkl"
PIV = 0.70710678118654752
UNIT = 2**66


def load():
    rows, seen = [], set()
    for lineS in open(TIES):
        f = lineS.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        rows.append(f)
    inputs = sorted(f[0] for f in rows)
    order = {mm: i for i, mm in enumerate(inputs)}
    st = {md: open(f"{PREFIX}_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    out = []
    for f in rows:
        R, ce, i = int(f[7], 16), int(f[8]), order[f[0]]
        hw, bad = [], False
        for md in ROUNDING_MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[2], 16))
        if bad:
            continue
        clean = [final_cosine_result(-R, ce, md) for md in ROUNDING_MODES]
        fired = [final_cosine_result(-(R - 1), ce, md) for md in ROUNDING_MODES]
        if hw == clean:
            out.append((f[0], False))
        elif hw == fired:
            out.append((f[0], True))
    return out


def main():
    labeled = load()
    feats = pickle.load(open(FEATCACHE, "rb"))
    rows = []
    strata = defaultdict(lambda: [[], []])
    for (mhex, fire), (dist, low3, s4, XT, XTabs, XD, mf, cfire) in zip(
            labeled, feats):
        m = int(mhex, 16)
        m2 = m * m
        sq = m2 >> (m2.bit_length() - 67)
        f4 = sq * sq
        t4 = f4 & ((1 << s4) - 1)
        sqlow = sq - (1 << 66)
        M = low3 * sqlow - t4
        side = "lo" if mf < PIV else "hi"
        third = 0 if XD < 1 / 3 else (1 if XD < 2 / 3 else 2)
        key = (dist, s4, side, low3, third)
        strata[key][int(fire)].append(M)
        rows.append((key, mhex, M, XD, int(fire)))

    # lattice threshold per stratum
    TH = {}
    for key, (cleans, fires) in strata.items():
        if not fires:
            # never-fire: T = smallest lattice value <= min clean
            TH[key] = None if not cleans else \
                (min(cleans) // UNIT) * UNIT  # any T at/below works; use floor
            continue
        if not cleans:
            hi = max(fires)
            TH[key] = (hi // UNIT + 1) * UNIT
            continue
        hi_f, lo_c = max(fires), min(cleans)
        # lattice points in (hi_f, lo_c] — or nearest to the best split
        cands = [k * UNIT for k in range(hi_f // UNIT - 1, lo_c // UNIT + 2)
                 if hi_f < k * UNIT <= lo_c]
        if len(cands) == 1:
            TH[key] = cands[0]
        elif cands:
            TH[key] = cands[0]
            print(f"NOTE {key}: multiple lattice points {len(cands)}")
        else:
            # no clean separation: pick lattice point minimizing errors
            best = (1 << 60, None)
            for k in range((min(hi_f, lo_c)) // UNIT - 1,
                           (max(hi_f, lo_c)) // UNIT + 2):
                T = k * UNIT
                e = sum(1 for mm in fires if mm >= T) + \
                    sum(1 for mm in cleans if mm < T)
                if e < best[0]:
                    best = (e, T)
            TH[key] = best[1]
            print(f"NOTE {key}: no separating lattice point; "
                  f"best lattice T={best[1]//UNIT} errs={best[0]}")

    print("\nmismatching rows under strict fire <=> M < u*2^66:")
    print(f"{'key':>24} {'mhex':>18} {'fire':>4} {'(M-T)/2^66':>12} "
          f"{'3*XD-1':>12} {'3*XD-2':>12}")
    nbad = tot = 0
    for key, mhex, M, XD, fire in rows:
        T = TH[key]
        if T is None:
            pred = 0
        else:
            pred = int(M < T)
        tot += 1
        if pred != fire:
            nbad += 1
            off = (M - (T or 0)) / UNIT
            print(f"{str(key):>24} {mhex:>18} {fire:>4} {off:>12.2e} "
                  f"{3*XD-1:>12.2e} {3*XD-2:>12.2e}")
    print(f"\ntotal mismatches: {nbad} / {tot}")


if __name__ == "__main__":
    main()
