#!/usr/bin/env python3
"""h610b: autopsy of the out-of-zone baseline mismatches — are
they exactly the Round-52 patch-active rows (traced payload !=
pre-patch payload), i.e. rows the shipped patches already fix?"""
from collections import defaultdict
from h437_gate_extraction import (ROUNDING_MODES, load_labeled_rows,
                                  final_cosine_result)

rows = load_labeled_rows()
tab = defaultdict(int)
detail = []
for fields, hw_sigs in rows:
    if fields.get("active") != "1" or fields["lsign"] != "1" \
            or fields["rsign"] != "0":
        continue
    le2, re2 = int(fields["le2"]), int(fields["re2"])
    ls, rs = int(fields["ls"], 16), int(fields["rs"], 16)
    dist, low3 = int(fields["dist"]), int(fields["low3"])
    prepay = low3 + 8 - dist
    tpay = int(fields["payload"])
    scale = min(le2, re2, le2 - 8)
    A = ls << (le2 - scale)
    B = rs << (re2 - scale)
    unit = le2 - 8 - scale
    M = A - B + (prepay << unit)
    if M <= 0:
        continue
    k = max(M.bit_length() - 67, 0)
    if k < 3:
        continue
    disc = M & ((1 << k) - 1)
    if disc <= 2 or disc >= (1 << k) - 2:
        continue  # in-zone: not this autopsy
    R = M >> k
    ce = scale + k
    hw = [hw_sigs[md] for md in ROUNDING_MODES]
    base_ref = [final_cosine_result(-R, ce, md)
                for md in ROUNDING_MODES]
    if hw == base_ref:
        continue
    patch_active = tpay != prepay
    tab[("outzone_mismatch", "patch_active" if patch_active
         else "NOT_patched")] += 1
    # patched coordinates: rebuild M with traced payload
    M2 = A - B + (tpay << unit)
    k2 = max(M2.bit_length() - 67, 0)
    R2 = M2 >> k2
    ce2 = scale + k2
    ref2 = [final_cosine_result(-R2, ce2, md)
            for md in ROUNDING_MODES]
    tab[("patched_ref", "match" if hw == ref2 else
         "MISMATCH")] += 1
    d2 = M2 & ((1 << k2) - 1) if k2 else 0
    zone2 = d2 <= 2 or (k2 and d2 >= (1 << k2) - 2)
    detail.append((dist, low3, prepay, tpay,
                   "inzone2" if zone2 else "outzone2",
                   "hw==ref2" if hw == ref2 else "hw!=ref2"))
print(dict(tab))
for d in detail:
    print(d)
