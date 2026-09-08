#!/usr/bin/env python3
# h959: patch the R93 clean-label override table into the R92
# source (G_R93OVR, default ON).  Table from h959_table.txt (143
# entries: dl_g, mule2, g, pay -> fire).  Inserted ahead of the
# existing payload==0 / staircase logic; decline semantics
# identical (payload=0 + pay_declined=1); fire bypasses both.
import sys

SRC = "/root/r59/fsincos_skylake.c"
rows = []
for ln in open("h959_table.txt"):
    if not ln.startswith("OV "): continue
    w = ln.split()
    rows.append((int(w[1]), int(w[2]), int(w[3]), int(w[4]), int(w[5])))
assert len(rows) == 143, len(rows)
tbl = ",\n            ".join("{%d,%d,%d,%d,%d}" % r for r in rows)

src = open(SRC, encoding="utf-8").read()
assert "G_R93OVR" not in src

KNOB = """#ifndef G_R93OVR        /* h956/h959 clean-label (cell,g,pay) gate
                         * override table: 143 tuples where the
                         * value-level majority at 34k-op power
                         * contradicts the h913 staircase (blind
                         * holdout 266-vs-536).  1 = on. */
#define G_R93OVR 1
#endif
"""
anchor = "#ifndef G_PAYGATE\n"
assert src.count(anchor) == 1
src = src.replace(anchor, KNOB + anchor)

ANCH = """        if (payload == 0) {
            if (deep_g)
                pay_declined = 1;
        } else {"""
assert src.count(ANCH) == 1
BLOCK = """#if G_R93OVR
        /* R93: value-level clean-label overrides (h956b half-grid
         * relabel; h959 table).  An entry hit decides fire/decline
         * outright; no entry falls through to the R89/R90 logic. */
        int ovr_g = -1;
        if (dl_g >= 9 && dl_g <= 14) {
            u128 rlow93 = right.sig & ((((u128)1) << dl_g) - 1);
            u128 grl93 = (left.sign != right.sign)
                ? (rlow93 ? rlow93 : (((u128)1) << dl_g))
                : ((((u128)1) << dl_g) - rlow93);
            int g93 = grl93 > 64 ? 64 : (int)grl93;
            static const short r93_ovr[][5] = {
            %s
            };
            unsigned oi;
            for (oi = 0;
                 oi < sizeof(r93_ovr) / sizeof(r93_ovr[0]); oi++) {
                if (r93_ovr[oi][0] == dl_g
                    && r93_ovr[oi][1] == multiplier.e2
                    && r93_ovr[oi][2] == g93
                    && r93_ovr[oi][3] == payload) {
                    ovr_g = r93_ovr[oi][4];
                    break;
                }
            }
        }
        if (ovr_g == 0) {
            payload = 0;
            pay_declined = 1;
        } else if (ovr_g == 1) {
            /* fire: keep the payload; R75/R81 stay eligible */
        } else
#endif
""" % tbl
src = src.replace(ANCH, BLOCK + ANCH)
open(SRC, "w", encoding="utf-8").write(src)
print("patched", SRC, "entries:", len(rows))
