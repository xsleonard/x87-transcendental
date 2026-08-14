#!/usr/bin/env python3
"""h662o: decompose the sc gate — deterministic borrow x EU-frame z.

EU = (APf - B_full) >> kf and R = (S - B) >> w differ by a
DETERMINISTIC borrow b = R - EU (the unchopped tail's borrow into
the retained field).  fire_sc was labeled in the standalone-R frame,
so fire_sc(dn) <=> z = b - 1 and fire_sc(up) <=> z = b + 1 where
z = hw_sc - EU.  h662n's single-z scan was ambiguity-contaminated
(rounding cells alias z values 1-3 apart); redo with FULL Z-sets
(h594 discipline).  Census:
  A. b distribution by (sign, th, crit, fire_cos)
  B. Z-set patterns (exact vs ambiguous) by group
  C. exact-z rows: z vs (b, fire_cos) by (sign, crit) — is z
     deterministic given (b, fire_cos)?  If yes the sc lane has NO
     independent coin on these rows.
  D. where z is NOT determined: cross-tab the residual coin vs
     mag_sc law bits (bit kf+8, bit at EU-frame block start).
"""
import os, pickle, sys
from collections import defaultdict
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result

CACHE = "h662n_rows.pkl"
OUT = "h662o_rows.pkl"


def load_sc_hw():
    rows, seen = [], set()
    for lineS in open("ties_comb7.txt"):
        f = lineS.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        rows.append(f)
    inputs = sorted(f[0] for f in rows)
    order = {mm: i for i, mm in enumerate(inputs)}
    st = {md: open(f"comb7_sc_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    hwmap = {}
    for f in rows:
        i = order[f[0]]
        hw, bad = [], False
        for md in ROUNDING_MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[4], 16))
        if not bad:
            hwmap[f[0]] = hw
    return hwmap


def zwork(args):
    mhex, EU, ce, hw = args
    Z = []
    for z in range(-4, 6):
        refs = [final_cosine_result(-(EU + z), ce, md)
                for md in ROUNDING_MODES]
        if hw == refs:
            Z.append(z)
    return (mhex, tuple(Z))


def main():
    rows = pickle.load(open(CACHE, "rb"))
    print(f"{len(rows)} cached rows", flush=True)
    if os.path.exists(OUT):
        zmap = pickle.load(open(OUT, "rb"))
    else:
        hwmap = load_sc_hw()
        jobs = []
        for o in rows:
            (mhex, sign, th, fc, fs, z1, pm, w, phw, scale, S, B, F,
             kf, APf, B_full, ce) = o
            EU = (APf - B_full) >> kf
            jobs.append((mhex, EU, ce, hwmap[mhex]))
        with Pool(8) as pool:
            res = pool.map(zwork, jobs, chunksize=500)
        zmap = dict(res)
        pickle.dump(zmap, open(OUT, "wb"))
    print("z-sets ready", flush=True)

    # assemble per-row records
    rec = []
    for o in rows:
        (mhex, sign, th, fc, fs, z1, pm, w, phw, scale, S, B, F,
         kf, APf, B_full, ce) = o
        mag = S - B
        mag_sc = APf - B_full
        R = mag >> w
        EU = mag_sc >> kf
        b = R - EU
        crit = (pm + phw) % 8 == 7 and pm in (7, 8)
        Z = zmap[mhex]
        bs_rel = 8 + ((8 - phw) % 8)
        bit8 = (mag_sc >> (kf + 8)) & 1
        bitbs = (mag_sc >> (kf + bs_rel)) & 1
        rec.append((sign, th, crit, fc, fs, b, Z, bit8, bitbs, phw))

    print("\n(A) borrow b = R - EU census by (sign, th, crit, fire_cos):")
    t = defaultdict(lambda: defaultdict(int))
    for sign, th, crit, fc, fs, b, Z, b8, bbs, phw in rec:
        t[(sign, th, crit, fc)][b] += 1
    for k in sorted(t, key=str):
        cen = t[k]
        n = sum(cen.values())
        if n < 50:
            continue
        line = "  ".join(f"b={b}:{cen[b]}" for b in sorted(cen))
        print(f"  {k}: n={n}  {line}")

    print("\n(B) Z-set patterns by (sign, crit) [top 8]:")
    t = defaultdict(lambda: defaultdict(int))
    for sign, th, crit, fc, fs, b, Z, b8, bbs, phw in rec:
        t[(sign, crit)][Z] += 1
    for k in sorted(t, key=str):
        cen = t[k]
        n = sum(cen.values())
        tops = sorted(cen.items(), key=lambda kv: -kv[1])[:8]
        print(f"  {k}: n={n}")
        for Z, c in tops:
            print(f"      Z={Z}: {c}")

    print("\n(C) exact-z rows: z by (sign, th, crit, b, fire_cos):")
    t = defaultdict(lambda: defaultdict(int))
    amb = defaultdict(int)
    for sign, th, crit, fc, fs, b, Z, b8, bbs, phw in rec:
        if len(Z) == 1:
            t[(sign, th, crit, b, fc)][Z[0]] += 1
        else:
            amb[(sign, th, crit)] += 1
    for k in sorted(t, key=str):
        cen = t[k]
        n = sum(cen.values())
        if n < 30:
            continue
        line = "  ".join(f"z={z}:{cen[z]}" for z in sorted(cen))
        print(f"  {k}: n={n}  {line}")
    print("  ambiguous rows by (sign, th, crit):")
    for k in sorted(amb, key=str):
        print(f"    {k}: {amb[k]}")

    print("\n(D) cells where z is mixed: split by EU-frame law bits")
    print("    key (sign, th, crit, b, fc, bit8, bitbs, phw) -> z census")
    t = defaultdict(lambda: defaultdict(int))
    for sign, th, crit, fc, fs, b, Z, b8, bbs, phw in rec:
        if len(Z) == 1:
            t[(sign, th, crit, b, fc)][(Z[0], b8, bbs, phw)] += 1
    for k in sorted(t, key=str):
        cen = t[k]
        zs = set(z for z, b8, bbs, phw in cen)
        if len(zs) < 2:
            continue
        n = sum(cen.values())
        if n < 100:
            continue
        print(f"  MIXED {k}: n={n}")
        sub = defaultdict(lambda: defaultdict(int))
        for (z, b8, bbs, phw), c in cen.items():
            sub[(b8, bbs, phw)][z] += c
        for sk in sorted(sub):
            zc = sub[sk]
            nn = sum(zc.values())
            if nn < 30:
                continue
            line = "  ".join(f"z={z}:{zc[z]}" for z in sorted(zc))
            print(f"      (b8,bbs,phw)={sk}: n={nn}  {line}")


if __name__ == "__main__":
    main()
