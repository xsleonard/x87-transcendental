#!/usr/bin/env python3
"""h519b: reverse the family-2 (P5C4) carrier structure from traces.

Constants known (p5_rom_constants.h).  For family-2 corpus tie rows
(NOEXPONENT under the C6 chains), test structural hypotheses for the
lf/rf chain values and report which reproduces the traces:
  H_A: 2-term chains over f4:  neg = rn64(C1 + chop67(f4*C3)),
       pos = rn64(C2 + chop67(f4*C4))          (mirror of C6 family)
  H_B: same but chains over sq
  H_C: 3+1 Horner split over f4: neg = rn64(C1 + chop67(f4*C3)),
       pos = rn64(C2 + chop67(f4*rn64(C4... )))
Each at exponents e2m in -63..-69."""
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import load_labeled_rows
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round, add_round,
                                 recover_m)

C4_1 = (1, -68, (0x7 << 64) | 0xfffffffffffffa28)
C4_2 = (0, -71, (0x5 << 64) | 0x55555555539cfae6)
C4_3 = (1, -76, (0x5 << 64) | 0xb05b050f31b2e713)
C4_4 = (0, -82, (0x6 << 64) | 0x803988d56e3bff10)


def two_term(base, lead, last):
    prod = mul_round(base, lead, 67, "chop")
    return add_round(last, prod, 64, "rn")


def hypos(sq, f4):
    yield "A_f4", two_term(f4, C4_3, C4_1), two_term(f4, C4_4, C4_2)
    yield "B_sq", two_term(sq, C4_3, C4_1), two_term(sq, C4_4, C4_2)
    yield "C_swap", two_term(f4, C4_4, C4_2), two_term(f4, C4_3, C4_1)
    # C6-style 3-term chains but with C4 constants padded by C6 tails
    yield "D_mix", build_chain(f4, C6_5, C4_3, C4_1, 67, 64, "rn",
                               False, False, False), \
        build_chain(f4, C6_6, C4_4, C4_2, 67, 64, "rn",
                    False, False, False)


def probe(job):
    fields, hw = job
    if fields.get("active") != "1":
        return None
    m = recover_m(int(fields["mul"], 16))
    if m is None:
        return None
    lf_t, rf_t = int(fields["lf"], 16), int(fields["rf"], 16)
    sq_t, f4_t = int(fields["mul"], 16), int(fields["f4"], 16)
    # C6 first: skip family-1 rows
    if mul_round((0, -66, m), (0, -66, m), 67, "chop")[2] != sq_t:
        return ("sqmismatch",)
    all_hits = []
    for e2m in (-63, -64, -65, -66, -67, -68, -69, -70):
        mag = (0, e2m, m)
        sq = mul_round(mag, mag, 67, "chop")
        f4 = mul_round(sq, sq, 67, "chop")
        neg = build_chain(f4, C6_5, C6_3, C6_1, 67, 64, "rn",
                          False, False, False)
        pos = build_chain(f4, C6_6, C6_4, C6_2, 67, 64, "rn",
                          False, False, False)
        if neg[2] == lf_t and pos[2] == rf_t:
            return ("family1", e2m)
        for name, lneg, lpos in hypos(sq, f4):
            lmatch = lneg[2] == lf_t
            rmatch = lpos[2] == rf_t
            if lmatch or rmatch:
                all_hits.append((name, lmatch, rmatch, e2m))
    if all_hits:
        return ("hit", tuple(all_hits))
    return ("nohit", f"lf={lf_t:x}", f"rf={rf_t:x}")


def main():
    rows = load_labeled_rows()
    with Pool(8) as pool:
        out = [o for o in pool.map(probe, rows, chunksize=500) if o]
    tab = defaultdict(int)
    samples = defaultdict(list)
    for o in out:
        tab[o[0]] += 1
        if o[0] in ("hit", "nohit") and len(samples[o[0]]) < 6:
            samples[o[0]].append(o[1:])
    print("census:", dict(tab))
    for k, v in samples.items():
        print(f"\n{k} samples:")
        for s in v:
            print("  ", s)


if __name__ == "__main__":
    main()
