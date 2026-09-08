#!/usr/bin/env python3
"""h657b: the theta ladder — is the thinning bit the tie derivative?

Hypothesis (2026-08-13): at offset theta the effective tie sits theta
operand-units from the row's own operand, so the gate's margin is the
theta=0 law evaluated AT THE SHIFTED POINT:

    M_k = L*(sqlow + k*theta) - ((sqlow + k*theta)^2 mod 2^s4)
    fire_dn  <=>  M_k < u_closed * 2^66

i.e. the "thinning bit" h646 localized is no new bit at all but the
derivative term theta*(2*sqlow - L), row-dependent — which the
(L, third)-binned censuses could only register as ~25 percent mixing
(mean shift ~2 lattice units on the lo side, ~1 on the hi side,
variance = the mixing).  Evaluating exactly at the shifted point keeps
the theta^2 and mod-2^s4 wrap terms for free; k=+-1 is the unit-scaled
derivative hypothesis, k=0 the h646 baseline.

Data: the h657 caches (comb7 + comb8 theta!=0, three-way labels
0 clean / 1 fire_dn (R-1) / 2 fire_up (R+1)).  Diagnostic = the full
lattice-slack histogram r = floor(M_k/2^66) - u_closed by label: a
correct k puts every dn-fire at r < 0 and every clean at r >= 0.
theta<0 (where the up-fires live) is censused in the same frame, both
prediction directions.
"""
import pickle
from collections import defaultdict

UNIT = 2**66
X60 = 1 << 60

# h647-h656 closed form: (s4, side 0=lo/1=hi) -> (a, G1, G2, p, Q, K, par, W)
QUAD = {
    (66, 1): (2, 2, 1,  0, 4, 1, 0, lambda d: -5 * (d - 7)),
    (66, 0): (4, 1, 0,  0, 2, 1, 0, lambda d: -9 - 5 * (d - 9)),
    (67, 0): (4, 2, 1, -2, 4, 2, 1, lambda d: -5 * (d - 7)),
    (67, 1): (2, 2, 3, -3, 8, 2, 1, lambda d: -4 - 2 * (d - 7)),
}


def u_closed(dist, s4, side, L, xd60):
    a, G1, G2, p, Q, K, par, W = QUAD[(s4, side)]
    b1 = 1 if 3 * xd60 >= X60 else 0
    b2 = 1 if 3 * xd60 >= 2 * X60 else 0
    return (K * ((a * L + G1 * b1 + G2 * b2 + p * (L % 2) + W(dist)) // Q)
            + par * (L % 2))


def slack(rows, k):
    """per row: (r, label, theta, cell) with r = floor(M_k/U) - u."""
    out = []
    for theta, dist, s4, side, L, xd60, sR, label, M, sqlow in rows:
        u = u_closed(dist, s4, side, L, xd60)
        x = sqlow + k * theta
        Mk = L * x - ((x * x) % (1 << s4))
        out.append((Mk // UNIT - u, label, theta, (dist, s4, side, L)))
    return out


def hist_and_best(sl, fire_label, direction):
    """direction 'lt': fire <=> r < eu;  'ge': fire <=> r >= eu."""
    h = defaultdict(lambda: [0, 0, 0])
    for r, label, theta, cell in sl:
        h[max(-8, min(8, r))][label if label < 3 else 0] += 1
    best = (1 << 62, None)
    for eu in range(-6, 7):
        if direction == "lt":
            e = sum(1 for r, label, _, _ in sl
                    if (r < eu) != (label == fire_label))
        else:
            e = sum(1 for r, label, _, _ in sl
                    if (r >= eu) != (label == fire_label))
        if e < best[0]:
            best = (e, eu)
    return h, best


def show_hist(h, labels=(0, 1, 2)):
    print(f"    {'r':>4} " + " ".join(f"{'lab' + str(x):>9}" for x in labels))
    for r in sorted(h):
        print(f"    {r:>4} " + " ".join(f"{h[r][x]:>9}" for x in labels))


def main():
    for name in ("comb7", "comb8"):
        rows = pickle.load(open(f"h657_{name}.pkl", "rb"))
        cen = defaultdict(lambda: [0, 0, 0])
        for r in rows:
            cen[r[0]][r[7]] += 1
        print(f"\n########## {name}: {len(rows)} rows ##########")
        print(f"{'theta':>6} {'clean':>9} {'fire_dn':>9} {'fire_up':>9}")
        for t in sorted(cen):
            c = cen[t]
            print(f"{t:>+6} {c[0]:>9} {c[1]:>9} {c[2]:>9}")

        pos = [r for r in rows if r[0] > 0]
        neg = [r for r in rows if r[0] < 0]

        # ---- theta>0: dn-fire ladder ----
        print(f"\n[{name}] theta>0 ({len(pos)} rows) — "
              f"fire_dn <=> M_k < (u+eu)*2^66")
        print(f"{'k':>4} {'best eu':>8} {'errs':>9} {'rate':>9}")
        results = {}
        for k in (0, 1, -1, 2, -2, 4, -4):
            sl = slack(pos, k)
            h, (e, eu) = hist_and_best(sl, 1, "lt")
            results[k] = (sl, h, e, eu)
            print(f"{k:>4} {eu:>8} {e:>9} {e/len(pos):>9.5f}", flush=True)
        kbest = min(results, key=lambda k: results[k][2])
        sl, h, e, eu = results[kbest]
        print(f"\n[{name}] BEST k={kbest}, eu={eu}: {e} errs "
              f"({e/len(pos):.5f}).  Slack histogram by label:")
        show_hist(h)
        # per-theta + worst cells at best k
        for th in sorted(set(r[0] for r in pos)):
            sub = [s for s in sl if s[2] == th]
            ee = sum(1 for r, label, _, _ in sub if (r < eu) != (label == 1))
            print(f"    theta=+{th}: {ee} errs / {len(sub)} "
                  f"({ee/len(sub):.5f})")
        bc = defaultdict(lambda: [0, 0])
        for r, label, _, cell in sl:
            bc[cell][0] += int((r < eu) != (label == 1))
            bc[cell][1] += 1
        worst = sorted(bc.items(), key=lambda kv: -kv[1][0])[:10]
        print("    worst cells (dist,s4,side,L):")
        for c, (b, n) in worst:
            if b:
                print(f"      {c}: {b}/{n}")

        # ---- theta<0: up-fire census in the same frame ----
        print(f"\n[{name}] theta<0 ({len(neg)} rows) — up-fire frame scan")
        stray_dn = sum(1 for r in neg if r[7] == 1)
        print(f"    stray dn-fires at theta<0: {stray_dn} (expect 0)")
        for k in (0, 1, -1, 2, -2):
            sl = slack(neg, k)
            hlt, blt = hist_and_best(sl, 2, "lt")
            hge, bge = hist_and_best(sl, 2, "ge")
            print(f"    k={k:>3}: fire_up<=>r<eu best {blt[0]} errs (eu={blt[1]}); "
                  f"fire_up<=>r>=eu best {bge[0]} errs (eu={bge[1]})",
                  flush=True)
        # histogram at the better of the two for the best k found
        best_k, best_e, best_dir, best_eu = None, 1 << 62, None, None
        for k in (0, 1, -1, 2, -2):
            sl = slack(neg, k)
            _, (elt, eult) = hist_and_best(sl, 2, "lt")
            _, (ege, euge) = hist_and_best(sl, 2, "ge")
            if elt < best_e:
                best_k, best_e, best_dir, best_eu = k, elt, "lt", eult
            if ege < best_e:
                best_k, best_e, best_dir, best_eu = k, ege, "ge", euge
        sl = slack(neg, best_k)
        h, _ = hist_and_best(sl, 2, best_dir)
        print(f"\n[{name}] theta<0 BEST: k={best_k} dir={best_dir} "
              f"eu={best_eu}: {best_e} errs ({best_e/len(neg):.5f})")
        show_hist(h)
        print("", flush=True)


if __name__ == "__main__":
    main()
