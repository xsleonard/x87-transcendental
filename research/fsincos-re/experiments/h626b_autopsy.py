#!/usr/bin/env python3
"""h626b: direct autopsy of a few mismatch rows — where does
the replica diverge from the trace (f4? lf? rf?), and what do
the traced values look like?"""
from h437_gate_extraction import load_labeled_rows
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5,
                                 C6_6, build_chain, mul_round,
                                 recover_m)

rows = load_labeled_rows()
shown = 0
census = {}
for fields, hw in rows:
    if fields.get("active") != "1" or fields["lsign"] != "1" \
            or fields["rsign"] != "0":
        continue
    le2, re2 = int(fields["le2"]), int(fields["re2"])
    ls, rs = int(fields["ls"], 16), int(fields["rs"], 16)
    dist, low3 = int(fields["dist"]), int(fields["low3"])
    prepay = low3 + 8 - dist
    scale = min(le2, re2, le2 - 8)
    M = (ls << (le2 - scale)) - (rs << (re2 - scale)) \
        + (prepay << (le2 - 8 - scale))
    if M <= 0:
        continue
    k = max(M.bit_length() - 67, 0)
    if k < 3:
        continue
    disc = M & ((1 << k) - 1)
    if disc > 2 and disc < (1 << k) - 2:
        continue
    mul = int(fields["mul"], 16)
    m = recover_m(mul)
    if m is None:
        continue
    while m.bit_length() > 64:
        m >>= 1
    while 0 < m.bit_length() < 64:
        m <<= 1
    mag = (0, -66, m)
    sq = mul_round(mag, mag, 67, "chop")
    f4 = mul_round(sq, sq, 67, "chop")
    neg = build_chain(f4, C6_5, C6_3, C6_1, 67, 64, "rn",
                      False, False, False)
    pos = build_chain(f4, C6_6, C6_4, C6_2, 67, 64, "rn",
                      False, False, False)
    ok_f4 = f4[2] == int(fields["f4"], 16)
    ok_lf = neg[2] == int(fields["lf"], 16)
    ok_rf = pos[2] == int(fields["rf"], 16)
    ok_sq = sq[2] == mul
    if ok_f4 and ok_lf and ok_rf:
        continue
    key = (ok_sq, ok_f4, ok_lf, ok_rf)
    census[key] = census.get(key, 0) + 1
    if shown < 4:
        shown += 1
        print(f"row: dist={dist} low3={low3} le2={le2} "
              f"re2={re2}")
        print(f"  mul(trace)={mul:x}  sq(repl)={sq[2]:x} "
              f"ok={ok_sq}")
        print(f"  f4 (trace)={int(fields['f4'],16):x}")
        print(f"  f4 (repl) ={f4[2]:x} ok={ok_f4}")
        print(f"  lf (trace)={int(fields['lf'],16):x}")
        print(f"  lf (repl) ={neg[2]:x} ok={ok_lf}")
        print(f"  rf (trace)={int(fields['rf'],16):x}")
        print(f"  rf (repl) ={pos[2]:x} ok={ok_rf}")
print("\ncensus (ok_sq, ok_f4, ok_lf, ok_rf):", census)
