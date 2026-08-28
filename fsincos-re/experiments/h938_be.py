#!/usr/bin/env python3
# h938: the exact-borrow discriminant.  For each frame row compute the
# terminal-window geometry and the exact below-window borrow
#   B_e = 1 iff lowX < belowAR   (exact subtraction borrows into window)
# Jam-law prediction: hardware terminal = chopX - chopAR - 1 whenever
# belowAR != 0, so a VISIBLE -1 deficit iff B_e == 0, and the v2
# unconditional probe over-fires exactly on B_e == 1 rows.
# Usage: h938_be.py <frames.tsv> [--census] > per-row tsv; summary on stderr
# --census: input is h931_frames.tsv (has lab column; group by operand).
import sys
from collections import Counter

path = sys.argv[1]
census = "--census" in sys.argv[2:]
f = open(path)
hdr = f.readline().rstrip("\n").split("\t")
col = {c: i for i, c in enumerate(hdr)}

print("\t".join(("key", "lab", "act", "pay", "kk", "belownz", "B_e",
                 "rtop_off", "rbot_off", "lowx_top_off", "chop_min",
                 "sum")))
cnt = Counter()
for ln in f:
    t = ln.rstrip("\n").split("\t")
    if len(t) != len(hdr):
        continue
    try:
        le2 = int(t[col["lefte2"]]); re2 = int(t[col["righte2"]])
        L = int(t[col["leftsig"]], 16); R = int(t[col["rightsig"]], 16)
        pay = int(t[col["payload"]])
    except (ValueError, KeyError):
        continue
    act = t[col["active"]]
    lab = t[col["lab"]] if census else "?"
    key = (t[col["seed"]] + ":" + t[col["insn"]] + ":" + t[col["se"]]
           + ":" + t[col["sig"]]) if census else \
          (t[col["idx"]] + ":" + t[col["insn"]])
    scale = min(le2, re2)
    if pay and le2 - 8 < scale:
        scale = le2 - 8
    X = L << (le2 - scale)
    if pay >= 0:
        X += pay << max(0, le2 - 8 - scale)
    else:
        X -= (-pay) << max(0, le2 - 8 - scale)
    AR = R << (re2 - scale)
    M = X - AR
    if M <= 0:
        cnt[("skip_neg", lab)] += 1
        continue
    kk = M.bit_length() - 67
    if kk < 1:
        cnt[("skip_kk", lab)] += 1
        continue
    mask = (1 << kk) - 1
    below = AR & mask
    lowX = X & mask
    be = 1 if lowX < below else 0
    # offsets from the window lsb (bit kk): 1 = the round-bit position
    rtop = kk - below.bit_length() + 1 if below else 0
    rbot = kk - ((below & -below).bit_length() - 1) if below else 0
    xtop = kk - lowX.bit_length() + 1 if lowX else 0
    chop_min = 1 if (M >> kk) == (1 << 66) else 0
    summ = ((M >> kk) >> 58) & 0x1FF        # top9 of the 67-bit chop
    print("\t".join(str(x) for x in (
        key, lab, act, pay, kk, 1 if below else 0, be,
        rtop, rbot, xtop, chop_min, "%#x" % summ)))
    cnt[(lab, "act%s" % act, "pay%d" % (1 if pay > 0 else 0),
         "bz%d" % (1 if below else 0), "B%d" % be)] += 1
for k in sorted(cnt):
    print(k, cnt[k], file=sys.stderr)
