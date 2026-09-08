#!/usr/bin/env python3
# h987: patch the R95 exact-support gate into the R93 source.
# When a fitted post-chop terminal adjustment (fire71/73/75, R81
# narrow) contradicts the EXACT terminal composition's chop67, the
# hardware follows the exact chop (h975/h986 census on 8,315
# fresh-captured band-strata ops: 616-vs-19, breaks clustering in
# two families).  Two carve families keep their fitted form (the
# act1-fired-path-only form; act0 and the declined path are never
# touched (corpus-wide 45/52 of act0 suppressions were breaks —
# the R73-R79 cancellation-borrow cells are hardware-verified).
import sys

SRC = "/root/r59/fsincos_skylake.c"
src = open(SRC, encoding="utf-8").read()
assert "G_R95XSUP" not in src

KNOB = """#ifndef G_R95XSUP       /* h975-h986 exact-support gate: fitted
                         * post-chop terminal adjustments are
                         * suppressed when the exact terminal
                         * composition's chop67 contradicts them
                         * (census 616-vs-19; two carve familes
                         * kept).  1 = on. */
#define G_R95XSUP 1
#endif
"""
anchor = "#ifndef G_PAYGATE\n"
assert src.count(anchor) == 1
src = src.replace(anchor, KNOB + anchor)

TERM = """    wv_t tc_default = acc_round_bits_mode(
        accumulator, scale, 67, P5_ROUND_CHOP);
"""
assert src.count(TERM) == 1
src = src.replace(TERM, TERM + """#if G_R95XSUP
    wv_t tc_pre95 = tc_default;
#endif
""")

RET = """    if (g_dump_internals)
        fprintf(stderr, "DI_CORR via=default payload=%d out=" DIWF "\\n",
            payload, DIW(tc_default));
    return tc_default;
"""
assert src.count(RET) == 1
ARM = """#if G_R95XSUP
    /* Round 95: the exact-support gate, ACT1 FIRED PATH ONLY.
     * When a fitted post-chop adjustment (fire75/R81 narrow) on
     * the payload-fired path contradicts the EXACT terminal
     * composition's chop67, the hardware follows the exact chop
     * (h988/h989 fresh-silicon value gate over the 5.09M-op scope
     * corpus + the 8,315-op h968 census: 1,259 fixes / ZERO
     * breaks / 59 unfixed with the carves below; act0's fitted
     * carry/borrow rules and the declined path are hardware-
     * verified and never touched).
     * Carves (fitted kept): five mag-down low-ladder strata
     * (h975 census breaks) and the mag-up d12/me2-75/g7 deep-
     * fringe cell. */
    if ((tc_default.sig != tc_pre95.sig
         || tc_default.e2 != tc_pre95.e2)
        && active && payload != 0 && !pay_declined) {
        int32_t fu_l95 = multiplier.e2 + left_factor.e2;
        int32_t fu_r95 = fourth.e2 + right_factor.e2;
        int32_t sc95 = fu_l95 < fu_r95 ? fu_l95 : fu_r95;
        if (left.e2 - 8 < sc95)
            sc95 = left.e2 - 8;
        u256 af95 = { 0, 0 };
        acc_add_product(&af95, left.sign, multiplier.sig,
                        left_factor.sig, fu_l95, sc95);
        acc_add_product(&af95, right.sign, fourth.sig,
                        right_factor.sig, fu_r95, sc95);
        acc_add_product(&af95, left.sign ^ (payload < 0),
                        (u128)(payload < 0 ? -payload : payload),
                        1, left.e2 - 8, sc95);
        wv_t tful95 = acc_round_bits_mode(af95, sc95, 67,
                                          P5_ROUND_CHOP);
        if (tful95.sig != tc_default.sig
            || tful95.e2 != tc_default.e2
            || tful95.sign != tc_default.sign) {
            int magdown95 = (tc_default.e2 < tc_pre95.e2)
                || (tc_default.e2 == tc_pre95.e2
                    && tc_default.sig < tc_pre95.sig);
            wv_t w95 = acc_round_bits_mode(
                accumulator, scale, 67 + 8, P5_ROUND_CHOP);
            int sum95 = (int)(w95.sig & 0xFF) + (int)low3;
            u128 rlow95 = right.sig
                & ((((u128)1) << distance) - 1);
            u128 grl95 = (left.sign != right.sign)
                ? (rlow95 ? rlow95 : (((u128)1) << distance))
                : ((((u128)1) << distance) - rlow95);
            int g95 = grl95 > 64 ? 64 : (int)grl95;
            int keep95 = 0;
            if (distance == 12 && multiplier.e2 == -75
                && g95 == 7) {
                /* deep-fringe g7 cell, SIDE-AGNOSTIC (h988/h989:
                 * the magdown mirror held the only 3 breaks and
                 * zero fixes -> widened; zero collateral on all
                 * 8,518 hw-verified union ops). */
                keep95 = 1;
            } else if (magdown95) {
                if ((sum95 == 9 && distance == 9
                     && multiplier.e2 == -72 && g95 == 7)
                    || (sum95 == 9 && distance == 9
                        && multiplier.e2 == -73 && g95 == 4)
                    || (sum95 == 10 && distance == 9
                        && multiplier.e2 == -72 && g95 == 6)
                    || (sum95 == 5 && distance == 12
                        && multiplier.e2 == -75 && g95 == 5)
                    || (sum95 == 7 && distance == 10
                        && multiplier.e2 == -74 && g95 == 3))
                    keep95 = 1;
            }
            if (!keep95)
                tc_default = tc_pre95;
        }
    }
#endif
"""
src = src.replace(RET, ARM + RET)
open(SRC, "w", encoding="utf-8").write(src)
print("patched")
