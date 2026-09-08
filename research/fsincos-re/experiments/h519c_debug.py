#!/usr/bin/env python3
"""h519c: single-row bitwise debug of the family-2 chain structure.
Take one NOEXPONENT row, print traced lf/rf and every candidate chain
value (C6 and C4 constant sets, 2-term and 3-term forms, chains over
sq and f4, e2m in -63..-70) with bit-diff annotations."""
from h437_gate_extraction import load_labeled_rows
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round, add_round,
                                 recover_m)
from h519b_family2 import C4_1, C4_2, C4_3, C4_4, two_term


def main():
    target = None
    for fields, hw in load_labeled_rows():
        if fields.get("active") != "1":
            continue
        if int(fields["lf"], 16) == 0x8000487045418fac:
            target = fields
            break
    f = target
    print({k: f[k] for k in ("mul", "f4", "lf", "rf", "le2", "re2",
                             "dist", "low3", "lsign", "rsign",
                             "payload")})
    m = recover_m(int(f["mul"], 16))
    lf_t, rf_t = int(f["lf"], 16), int(f["rf"], 16)
    print(f"m = {m:x} ({m.bit_length()} bits)")
    print(f"traced lf={lf_t:016x} rf={rf_t:016x}")
    for e2m in range(-70, -62):
        mag = (0, e2m, m)
        sq = mul_round(mag, mag, 67, "chop")
        f4 = mul_round(sq, sq, 67, "chop")
        cands = {
            "C6neg3(f4)": build_chain(f4, C6_5, C6_3, C6_1, 67, 64,
                                      "rn", False, False, False),
            "C6pos3(f4)": build_chain(f4, C6_6, C6_4, C6_2, 67, 64,
                                      "rn", False, False, False),
            "C4neg2(f4)": two_term(f4, C4_3, C4_1),
            "C4pos2(f4)": two_term(f4, C4_4, C4_2),
            "C4neg2(sq)": two_term(sq, C4_3, C4_1),
            "C4pos2(sq)": two_term(sq, C4_4, C4_2),
            "C4neg3(f4)": build_chain(f4, C6_5, C4_3, C4_1, 67, 64,
                                      "rn", False, False, False),
            "C4pos3(f4)": build_chain(f4, C6_6, C4_4, C4_2, 67, 64,
                                      "rn", False, False, False),
        }
        for name, v in cands.items():
            for tgt, tname in ((lf_t, "lf"), (rf_t, "rf")):
                x = v[2] ^ tgt
                if x == 0:
                    print(f"e2m={e2m} {name} == {tname}  EXACT")
                elif x < (1 << 20):
                    print(f"e2m={e2m} {name} ~ {tname}: "
                          f"{v[2]:016x} xor={x:x}")


if __name__ == "__main__":
    main()
