#!/usr/bin/env python3
# h965: patch the R94 band arm into the R93 source.  36-entry
# (act, sum8, dist, me2, g) stratum table (h964, blind holdout
# 154/154); on the non-fired default path the terminal sets
# g_r94_adjust; fsin_ref/fcos_ref decrement the architectural
# output by one grid unit before the r84 ledger lookup.
import pickle, sys

SRC = "/root/r59/fsincos_skylake.c"
table = pickle.load(open("h964_table.pkl", "rb"))
rows = sorted(table)
assert len(rows) == 36 and all(table[r] == -1 for r in rows)
tbl = ",\n    ".join("{%d,%d,%d,%d,%d}" % (r[0], r[1], r[2], r[3], r[4])
                     for r in rows)

src = open(SRC, encoding="utf-8").read()
assert "G_R94BAND" not in src

KNOB = """#ifndef G_R94BAND       /* h960-h964 band-stratum arm: 36 zero-
                         * collateral (act,sum8,cell,g) strata where
                         * hw = model - 1 output unit (blind holdout
                         * 154/154).  1 = on. */
#define G_R94BAND 1
#endif
"""
anchor = "#ifndef G_PAYGATE\n"
assert src.count(anchor) == 1
src = src.replace(anchor, KNOB + anchor)

GLOB = """static int g_r94_adjust;
static const short r94_band[][5] = {
    %s
};
""" % tbl
anchor2 = "static const int g_round84_errata = G_ROUND84;\n"
assert src.count(anchor2) == 1
src = src.replace(anchor2, anchor2 + GLOB)

TERM = """    wv_t tc_default = acc_round_bits_mode(
        accumulator, scale, 67, P5_ROUND_CHOP);
"""
assert src.count(TERM) == 1
ARM = TERM + """#if G_R94BAND
    g_r94_adjust = 0;
    if ((payload == 0 || pay_declined) && distance >= 7
        && distance <= 12 && multiplier.e2 >= -75
        && multiplier.e2 <= -71) {
        wv_t w94 = acc_round_bits_mode(
            accumulator, scale, 67 + 60, P5_ROUND_CHOP);
        int top94 = (int)((w94.sig >> 52) & 0xFF);
        int sum94 = top94 + (int)low3;
        u128 rlow94 = right.sig & ((((u128)1) << distance) - 1);
        u128 grl94 = (left.sign != right.sign)
            ? (rlow94 ? rlow94 : (((u128)1) << distance))
            : ((((u128)1) << distance) - rlow94);
        int g94 = grl94 > 64 ? 64 : (int)grl94;
        unsigned bi;
        for (bi = 0; bi < sizeof r94_band / sizeof r94_band[0]; bi++) {
            if (r94_band[bi][0] == (active ? 1 : 0)
                && r94_band[bi][1] == sum94
                && r94_band[bi][2] == distance
                && r94_band[bi][3] == multiplier.e2
                && r94_band[bi][4] == g94) {
                g_r94_adjust = 1;
                break;
            }
        }
    }
#endif
"""
src = src.replace(TERM, ARM)

# Zero the verdict at every producer entry: FSINCOS/FPTAN run the
# terminal with no consumer, and early-exit paths (exact zero, NaN,
# C2) skip the terminal entirely — without this, a stale adjust from
# a prior call would decrement an unrelated early-exit result.
CORE = ("static fsincos_status_t sincos_core"
        "(sf_t x, int n_inc, sf_rc_t rc, sf_t *out)\n{\n")
assert src.count(CORE) == 1
src = src.replace(CORE, CORE + """#if G_R94BAND
    g_r94_adjust = 0;
#endif
""")

def app(fn_anchor):
    global src
    assert src.count(fn_anchor) == 1, fn_anchor
    APPLY = """#if G_R94BAND
    if (g_r94_adjust) {
        g_r94_adjust = 0;
        if (%(out)s->sig == 0x8000000000000000ull) {
            %(out)s->sig = 0xFFFFFFFFFFFFFFFFull;
            %(out)s->se = (%(out)s->se & 0x8000)
                | (((%(out)s->se & 0x7FFF) - 1) & 0x7FFF);
        } else {
            %(out)s->sig -= 1;
        }
    }
#endif
    """ % {"out": fn_anchor.split("r84_lookup(in, ")[1].split(", ")[2].split(")")[0]}
    src = src.replace(fn_anchor, APPLY + fn_anchor)

app("(void)r84_lookup(in, R84_FSIN, rc, sin_out);\n    return FSINCOS_OK;\n}\n\n/* single-output entry point")
app("(void)r84_lookup(in, R84_FCOS, rc, cos_out);\n    return FSINCOS_OK;\n}\n\n/* h251-h258 F2XM1")
open(SRC, "w", encoding="utf-8").write(src)
print("patched; table entries:", len(rows))
