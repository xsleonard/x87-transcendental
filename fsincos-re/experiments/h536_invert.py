#!/usr/bin/env python3
"""h536: INVERSION — let the data specify the resolver.

Per comb-7 row (all theta): build the terminal low fields under the
verified iterative pair (h534 simulate_pair), compress the addend set
(APf, ~S, ~C, ~ret, +3) to (ps, pc) under parameterized orders, and
extract the REQUIRED borrow from the hardware label.

FRAME (corrected from first run): the unchopped-redundant terminal's
exact value is EU = (APf - B_full) >> kf, NOT the chopped model's R
— at a tie with Bdisc = B_full mod 2^rsh > 0, EU is already R-1.
The required resolver error is req2 = result_hw - EU, config-
independent.  Decomposition: cin = extra + crun, extra = compression
carry-outs at/above column kf (exact wires), crun = ripple carry of
(ps&lowm)+(pc&lowm) into kf, read off the propagate-run terminator:
scan p = ps^pc from kf-1 down; run length L; terminator column t
(g: both bits set -> crun=1; k: both clear -> crun=0; e: run reaches
column 0 -> crun=0).

SHARP TEST per pair form: req2 = -1 REQUIRES crun=1 (generate-
terminated run the resolver missed); req2 = +1 REQUIRES crun=0
(kill/edge run the resolver resolved as carry); |req2| > 1 is
impossible.  A correct operand form must satisfy this with zero
exceptions; then t measures the resolver's cut column per row and
the below-cut structure is the resolver's input.

Output: h536_rows.tsv (one line per labeled row: geometry + per-
config crun/term/t/L) and a census on stdout.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h528_structural import row_features
from h534_bitlevel_seam import simulate_pair

PAIRS = [(27, "rf"), (27, "f4")]
# 5-addend orders (a=APf, s=~S, c=~C, r=~ret, K=+3) folded seq 3:2;
# E/F: ret resolved exactly into APf first (v = APf - ret), K2=+2.
ORDERS = {
    "A": ("a", "s", "c", "r", "K"),
    "B": ("s", "c", "r", "K", "a"),
    "C": ("r", "a", "s", "c", "K"),
    "D": ("a", "s", "K", "c", "r"),
    "E": ("v", "s", "c", "K2"),
    "F": ("s", "c", "K2", "v"),
}
CONFIGS = [(pb, mult, o) for (pb, mult) in PAIRS for o in ORDERS]


def csa_full(a, b, c):
    return a ^ b ^ c, ((a & b) | (a & c) | (b & c)) << 1


def run_read(ps, pc, kf):
    """(crun, term, t, L) from the compressed pair's low field."""
    lowm = (1 << kf) - 1
    ps &= lowm
    pc &= lowm
    p = ps ^ pc
    g = ps & pc
    t = kf - 1
    while t >= 0 and (p >> t) & 1:
        t -= 1
    if t < 0:
        return 0, "e", -1, kf
    crun = (g >> t) & 1
    return crun, ("g" if crun else "k"), t, kf - 1 - t


def analyze(addmap, order, kf):
    """Fold addends in order with 3:2 CSAs (full ints); return
    (extra, crun, term, t, L)."""
    vals = [addmap[n] for n in order]
    s, c = vals[0], 0
    for v in vals[1:]:
        s, c = csa_full(s, c, v)
    extra = (s >> kf) + (c >> kf)
    crun, term, t, L = run_read(s, c, kf)
    return extra, crun, term, t, L


def work(rows):
    out_lines = []
    census = defaultdict(int)
    for mhex, theta, lab in rows:
        (f4s, poss, B_full, rsh, A, P, M, k, R, bshift,
         dist, low3) = row_features(mhex)
        F = rsh - bshift
        if F < 0:
            census["skipF"] += 1
            continue
        kf = k + F
        lowm = (1 << kf) - 1
        APf = (A + P) << F
        a_lo = APf & lowm
        EU = (APf - B_full) >> kf
        res_hw = R + {"clean": 0, "down": -1, "up": 1}[lab]
        req2 = res_hw - EU
        census[("req2", theta, req2)] += 1
        rec = [mhex, str(theta), lab, str(req2), str(dist),
               str(low3), str(k), str(kf)]
        for pb, mult in PAIRS:
            S, C, ret = simulate_pair(f4s, poss, (pb, mult))
            s_lo = (~S) & lowm
            c_lo = (~C) & lowm
            r_lo = (~ret) & lowm
            V = a_lo + ((~ret) & lowm) + 1
            addmap = {"a": a_lo, "s": s_lo, "c": c_lo, "r": r_lo,
                      "K": 3, "v": V & lowm, "K2": 2}
            v_extra = V >> kf
            tot = a_lo + s_lo + c_lo + r_lo + 3
            true_cin = tot >> kf
            for oname in ORDERS:
                order = ORDERS[oname]
                extra, crun, term, t, L = analyze(addmap, order, kf)
                if "v" in order:
                    extra += v_extra
                    tc = (addmap["v"] + s_lo + c_lo + 2) >> kf
                    tc += v_extra
                else:
                    tc = true_cin
                if extra + crun != tc:
                    census[("decomp_bad", pb, mult, oname)] += 1
                key = (pb, mult, oname)
                census[(key, req2, term)] += 1
                if (req2 == -1 and crun == 0) or \
                   (req2 == 1 and crun == 1) or abs(req2) > 1:
                    census[(key, "impossible")] += 1
                rec.append(f"{term}{t}")
        out_lines.append("\t".join(rec))
    return out_lines, census


def main():
    rows = []
    seen = set()
    raw = []
    for line in open("ties_comb7.txt"):
        f = line.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        raw.append(f)
    inputs = sorted(f[0] for f in raw)
    order = {m: i for i, m in enumerate(inputs)}
    st = {md: open(f"comb7_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    stride = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    labeled = []
    census = defaultdict(int)
    for j, f in enumerate(raw):
        if j % stride:
            continue
        R, ce, theta = int(f[7], 16), int(f[8]), int(f[9])
        i = order[f[0]]
        hw, bad = [], False
        for md in ROUNDING_MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[2], 16))
        if bad:
            census["badstat"] += 1
            continue
        refs = {name: [final_cosine_result(-(R + d), ce, md)
                       for md in ROUNDING_MODES]
                for name, d in (("clean", 0), ("down", -1),
                                ("up", 1))}
        lab = None
        for name in ("clean", "down", "up"):
            if hw == refs[name]:
                lab = name
                break
        if lab is None:
            census["other"] += 1
            continue
        labeled.append((f[0], theta, lab))
    print(f"labeled {len(labeled)} rows "
          f"(badstat {census['badstat']}, other {census['other']})",
          flush=True)
    chunks = [labeled[i::8] for i in range(8)]
    with Pool(8) as pool:
        parts = pool.map(work, chunks)
    agg = defaultdict(int)
    with open("h536_rows.tsv", "w") as fh:
        fh.write("# mhex theta lab dist low3 k kf | per-config "
                 "term+t for " + " ".join(map(str, CONFIGS)) + "\n")
        for lines, cen in parts:
            for ln in lines:
                fh.write(ln + "\n")
            for kk, v in cen.items():
                agg[kk] += v
    if agg.get("skipF"):
        print("skipF:", agg["skipF"])
    bad_dec = {kk: v for kk, v in agg.items()
               if isinstance(kk, tuple) and kk[0] == "decomp_bad"}
    if bad_dec:
        print("DECOMP BAD:", bad_dec)
    print("\nreq2 census by theta (theta, req2): count")
    for kk in sorted(k2 for k2 in agg if isinstance(k2, tuple)
                     and k2[0] == "req2"):
        print(f"  theta={kk[1]:+d} req2={kk[2]:+d}: {agg[kk]}")
    print(f"\n{'config':22s} {'req2':>4s}       g       k       e")
    for cfg in CONFIGS:
        for req2 in (-2, -1, 0, 1, 2):
            g = agg.get((cfg, req2, "g"), 0)
            kk = agg.get((cfg, req2, "k"), 0)
            e = agg.get((cfg, req2, "e"), 0)
            if g + kk + e:
                print(f"{str(cfg):22s} {req2:+4d} {g:7d} {kk:7d} "
                      f"{e:7d}")
        print(f"{str(cfg):22s} impossible: "
              f"{agg.get((cfg, 'impossible'), 0)}")


if __name__ == "__main__":
    main()
