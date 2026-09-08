#!/usr/bin/env python3
"""h997: constraint-aware bit interactions for the remaining integer gate.

Unlike h995, the labels here come from h975's admissible integer sets.  An
operand is positive only when the target correction is allowed and zero is
not; it is negative only when zero is allowed and the target correction is
not.  Ambiguous rows are omitted.  This prevents output-invisible rows from
masquerading as evidence for a terminal decision.

Expose bits in coordinates relative to the terminal 67-bit cut, including
the materialized addends, exact terminal products, and normalized product
discards.  Exhaustively fit every two-bit truth table on FIT and transfer the
unchanged table to HOL.
"""

from collections import Counter

import numpy as np


def load_tsv(path):
    with open(path) as src:
        header = next(src).rstrip("\n").split("\t")
        ix = {name: i for i, name in enumerate(header)}
        return ix, [line.rstrip("\n").split("\t") for line in src]


fix, feature_rows = load_tsv("h970_features.tsv")
nix, nhw_rows = load_tsv("h975_nhw.tsv")
features = {(r[fix["insn"]], r[fix["op"]]): r for r in feature_rows}


def add_bits(output, prefix, value, positions):
    for position in positions:
        output["%s%+03d" % (prefix, position)] = \
            (value >> position) & 1 if position >= 0 else 0


def normalized_discard(output, prefix, product, kept=67, width=64):
    shift = product.bit_length() - kept
    discard = product & ((1 << shift) - 1) if shift > 0 else 0
    for offset in range(width):
        position = shift - 1 - offset
        output["%s_q%02d" % (prefix, offset)] = \
            (discard >> position) & 1 if position >= 0 else 0
    return discard, shift


records = []
all_names = set()
for nrow in nhw_rows:
    key = nrow[nix["insn"]], nrow[nix["op"]]
    f = features[key]
    get = lambda name: f[fix[name]]
    bits = {}
    le, re = int(get("lefte2")), int(get("righte2"))
    left, right = int(get("leftsig"), 16), int(get("rightsig"), 16)
    # `payload` is the pre-gate proposal; `pay2` is the post-gate value
    # actually accumulated.  The earlier search accidentally framed the
    # terminal bits with the proposal, which corrupts every declined row.
    payload = int(get("pay2")) if get("pay2") != "-" else 0
    scale = min(le, re, le - 8 if payload else le)
    s_value = left << (le - scale)
    if payload:
        s_value += payload << (le - 8 - scale)
    b_value = right << (re - scale)
    magnitude = s_value - b_value
    assert magnitude > 0
    cut = magnitude.bit_length() - 67

    # Cut-relative materialized addends and result.
    for offset in range(-24, 49):
        position = cut + offset
        for prefix, value in (("S", s_value), ("B", b_value),
                              ("M", magnitude),
                              ("P", ~(s_value ^ b_value)),
                              ("G", ~s_value & b_value)):
            bits["%s%+03d" % (prefix, offset)] = \
                (value >> position) & 1 if position >= 0 else 0

    mag = int(get("magsig"), 16)
    sq = int(get("mulsig"), 16)
    fourth = int(get("f4sig"), 16)
    odd = int(get("lfsig"), 16)
    even = int(get("rfsig"), 16)
    products = (("sq", mag * mag), ("f4", sq * sq),
                ("left", sq * odd), ("right", fourth * even))
    for prefix, product in products:
        normalized_discard(bits, prefix, product)

    # Exact terminal products aligned to the materialized terminal scale.
    pl, pr = sq * odd, fourth * even
    ple, pre = int(get("mule2")) + int(get("lfe2")), \
        int(get("f4e2")) + int(get("rfe2"))
    exact_scale = min(ple, pre, le - 8 if payload else ple)
    exact_s = pl << (ple - exact_scale)
    if payload:
        exact_s += payload << (le - 8 - exact_scale)
    exact_b = pr << (pre - exact_scale)
    exact_m = exact_s - exact_b
    exact_cut = exact_m.bit_length() - 67
    for offset in range(-24, 49):
        position = exact_cut + offset
        for prefix, value in (("ES", exact_s), ("EB", exact_b),
                              ("EM", exact_m),
                              ("EP", ~(exact_s ^ exact_b)),
                              ("EG", ~exact_s & exact_b)):
            bits["%s%+03d" % (prefix, offset)] = \
                (value >> position) & 1 if position >= 0 else 0

    # Retained-stage bits remain useful interaction inputs, but avoid the
    # thousands of absolute product columns from h995.
    for prefix, value in (("mag", mag), ("sqk", sq),
                          ("f4k", fourth), ("odd", odd),
                          ("even", even)):
        for position in range(67):
            bits["%s_b%02d" % (prefix, position)] = \
                (value >> position) & 1

    # Scalar lane/stratum coordinates were previously used only to define
    # strata.  Expose them here because the perturbation response identifies
    # interactions between the lane difference and cut-relative addend bits.
    for name in ("low3", "dist", "rsh", "payload", "ud", "u5d",
                 "rud", "pay2", "laneb", "lanediff", "lane2", "lane3",
                 "sum8", "d", "me2", "g"):
        text = get(name)
        if text == "-":
            value = 0
        elif name in ("laneb", "lane2", "lane3"):
            value = int(text, 16)
        else:
            value = int(text)
        for position in range(16):
            bits["%s_b%02d" % (name, position)] = \
                (value >> position) & 1

    # Restore the state discarded by h970: original operand bits, reduction
    # quotient/quadrant, and the exact M66 subtraction below the rounded
    # reduced magnitude.  Every h979-h986 reconstruction started at `mag`
    # and therefore could not test these inputs.
    se_text, sig_text = get("op").split()
    se, input_sig = int(se_text, 16), int(sig_text, 16)
    input_sign = (se >> 15) & 1
    input_exp = (se & 0x7FFF) - 16383
    input_scale = input_exp - 63
    reduced = (input_sig, input_scale) != (mag, int(get("mage2")))
    for position in range(64):
        bits["input_b%02d" % position] = (input_sig >> position) & 1
    for position in range(16):
        bits["input_se_b%02d" % position] = (se >> position) & 1
    bits["reduced"] = int(reduced)
    n_inc = 0 if get("insn") == "sin" else 1
    if reduced:
        two_over_pi = ((0xA2F9836E4E441529 << 64)
                       | 0xFC2757D1F534DDC0)
        product_q = input_sig * two_over_pi
        shift_q = 191 - input_exp
        quotient = product_q >> shift_q
        remainder_q = product_q & ((1 << shift_q) - 1)
        half_q = 1 << (shift_q - 1)
        if remainder_q > half_q \
                or (remainder_q == half_q and (quotient & 1)):
            quotient += 1
        m66 = (3 << 64) | 0x243F6A8885A308D3
        a_red = input_sig << (input_exp + 2)
        b_red = quotient * m66
        d_red = abs(a_red - b_red)
        residual_sign = int((a_red < b_red) ^ bool(input_sign))
    else:
        product_q = remainder_q = quotient = d_red = 0
        residual_sign = input_sign
    signed_n = -quotient if input_sign else quotient
    n_quadrant = (signed_n + n_inc) & 3
    bits["red_i1"] = n_quadrant & 1
    bits["red_i0"] = (n_quadrant >> 1) & 1
    bits["red_rsn"] = residual_sign
    for position in range(64):
        bits["red_N_b%02d" % position] = (quotient >> position) & 1
    for position in range(80):
        bits["red_D_b%02d" % position] = (d_red >> position) & 1
    for position in range(128):
        bits["red_Qrem_b%03d" % position] = \
            (remainder_q >> position) & 1
    red_width = d_red.bit_length()
    for offset in range(67):
        position = red_width - 1 - offset
        bits["red_Dq%02d" % offset] = \
            (d_red >> position) & 1 if position >= 0 else 0
    red_residue = 0
    if red_width == 65 and (d_red & 1):
        kept = (1 << 63) | (d_red >> 1)
        red_residue = -1 if (kept & 1) else 1
    bits["red_c_nonzero"] = int(red_residue != 0)
    bits["red_c_sign"] = int((red_residue < 0) ^ bool(residual_sign)) \
        if red_residue else 0

    nset = {int(value) for value in nrow[nix["nset"]].split(",")}
    sum8 = int(nrow[nix["sum8"]])
    records.append({
        "key": key, "half": get("half"), "act": int(get("act")),
        "line": "TOP" if sum8 >= 128 else "LOW", "nset": nset,
        "pinned": nrow[nix["pinned"]] == "1",
        "bits": bits,
    })
    all_names.update(bits)


names = sorted(all_names)
name_index = {name: index for index, name in enumerate(names)}
X = np.zeros((len(records), len(names)), dtype=np.uint8)
for row_index, row in enumerate(records):
    for feature, value in row["bits"].items():
        X[row_index, name_index[feature]] = value


def problem(line, act, correction):
    indexes, labels = [], []
    for index, row in enumerate(records):
        if row["line"] != line or row["act"] != act:
            continue
        posok = correction in row["nset"]
        zerook = 0 in row["nset"]
        if posok == zerook:
            continue
        indexes.append(index)
        labels.append(int(posok))
    indexes = np.asarray(indexes, dtype=np.int32)
    labels = np.asarray(labels, dtype=np.uint8)
    return indexes, labels


def accuracy(table, values, labels):
    return int(np.sum(table[values] == labels))


def search(line, act, correction):
    indexes, labels = problem(line, act, correction)
    fit_mask = np.asarray([records[i]["half"] == "FIT" for i in indexes])
    fi, fy = indexes[fit_mask], labels[fit_mask]
    hi, hy = indexes[~fit_mask], labels[~fit_mask]
    xf, xh = X[fi], X[hi]
    print("\n%s act%d n=%+d: FIT %s HOL %s" %
          (line, act, correction, dict(Counter(fy)), dict(Counter(hy))))

    # Single bits first.
    singles = []
    for first in range(len(names)):
        counts = np.zeros((2, 2), dtype=np.int32)
        np.add.at(counts, (xf[:, first], fy), 1)
        table = np.argmax(counts, axis=1).astype(np.uint8)
        fgood = accuracy(table, xf[:, first], fy)
        hgood = accuracy(table, xh[:, first], hy)
        singles.append((hgood, fgood, names[first], table.tolist()))
    print("  best single bits by HOL:")
    for hgood, fgood, name, table in sorted(singles, reverse=True)[:12]:
        print("    %-12s FIT %d/%d HOL %d/%d map=%s" %
              (name, fgood, len(fy), hgood, len(hy), table))

    # Every two-bit truth table.  The table itself is learned only on FIT.
    best = []
    for first in range(len(names)):
        # Vectorized contingency counts for every possible second bit.
        fc = np.zeros((4, 2, len(names)), dtype=np.int32)
        hc = np.zeros((4, 2, len(names)), dtype=np.int32)
        for one, outcome in ((0, 0), (0, 1), (1, 0), (1, 1)):
            fmask = (xf[:, first] == one) & (fy == outcome)
            hmask = (xh[:, first] == one) & (hy == outcome)
            state0, state1 = one << 1, (one << 1) | 1
            fones = xf[fmask].sum(axis=0, dtype=np.int32)
            hones = xh[hmask].sum(axis=0, dtype=np.int32)
            fc[state1, outcome] = fones
            fc[state0, outcome] = int(fmask.sum()) - fones
            hc[state1, outcome] = hones
            hc[state0, outcome] = int(hmask.sum()) - hones
        tables = np.argmax(fc, axis=1).astype(np.uint8)
        fgood_all = np.max(fc, axis=1).sum(axis=0)
        hgood_all = np.zeros(len(names), dtype=np.int32)
        for state in range(4):
            hgood_all += hc[state, tables[state], np.arange(len(names))]
        for second in range(first + 1, len(names)):
            table = tables[:, second]
            fgood = int(fgood_all[second])
            hgood = int(hgood_all[second])
            candidate = (hgood, fgood, first, second, table.tolist())
            if len(best) < 100:
                best.append(candidate)
                if len(best) == 100:
                    best.sort()
            elif candidate > best[0]:
                best[0] = candidate
                best.sort()
    print("  best two-bit truth tables by HOL:")
    for hgood, fgood, first, second, table in sorted(best, reverse=True)[:20]:
        print("    %-12s %-12s FIT %d/%d HOL %d/%d map=%s" %
              (names[first], names[second], fgood, len(fy),
               hgood, len(hy), table))

    # Exact-cover view: literals must hold on every constrained positive in
    # both banks.  This is deliberately stricter than fitting a majority
    # table and is the relevant test for a proposed closed-form gate.
    positives = indexes[labels == 1]
    negatives = indexes[labels == 0]
    full_mask = (1 << len(negatives)) - 1
    literals = []
    for feature in range(len(names)):
        values = set(int(value) for value in X[positives, feature])
        if len(values) != 1:
            continue
        wanted = next(iter(values))
        mask = 0
        for local, index in enumerate(negatives):
            if int(X[index, feature]) == wanted:
                mask |= 1 << local
        if mask != full_mask:
            literals.append((mask, feature, wanted))
    literals.sort(key=lambda item: (item[0].bit_count(), names[item[1]]))
    print("  common-positive literals:")
    for mask, feature, wanted in literals[:16]:
        print("    %-16s=%d keeps %d/%d negatives" %
              (names[feature], wanted, mask.bit_count(), len(negatives)))
    pairs = []
    for first in range(len(literals)):
        for second in range(first + 1, len(literals)):
            mask = literals[first][0] & literals[second][0]
            pairs.append((mask.bit_count(), first, second, mask))
    pairs.sort()
    print("  common-positive conjunctions:")
    for count, first, second, _ in pairs[:16]:
        a, b = literals[first], literals[second]
        print("    %s=%d && %s=%d keeps %d/%d negatives" %
              (names[a[1]], a[2], names[b[1]], b[2], count,
               len(negatives)))
    triples = []
    for _, first, second, mask in pairs[:100]:
        for third, literal in enumerate(literals):
            if third in (first, second):
                continue
            triples.append(((mask & literal[0]).bit_count(),
                            first, second, third))
    triples.sort()
    for count, first, second, third in triples[:16]:
        values = [literals[index] for index in (first, second, third)]
        print("    %s keeps %d/%d negatives" %
              (" && ".join("%s=%d" % (names[value[1]], value[2])
                            for value in values), count, len(negatives)))


def conservative_pairs(line, act, correction):
    """Find partial two-literal arms with zero census contradictions."""
    scope = [index for index, row in enumerate(records)
             if row["line"] == line and row["act"] == act]
    full = (1 << len(scope)) - 1
    bad = fit_positive = hol_positive = 0
    for local, index in enumerate(scope):
        row = records[index]
        bit = 1 << local
        if correction not in row["nset"]:
            bad |= bit
        if row["pinned"] and row["nset"] == {correction}:
            if row["half"] == "FIT":
                fit_positive |= bit
            else:
                hol_positive |= bit

    literals = []
    for feature in range(len(names)):
        ones = 0
        for local, index in enumerate(scope):
            if int(X[index, feature]):
                ones |= 1 << local
        literals.append((feature, 0, full ^ ones))
        literals.append((feature, 1, ones))

    singles = []
    for feature, wanted, mask in literals:
        if mask and not (mask & bad):
            fit = (mask & fit_positive).bit_count()
            hol = (mask & hol_positive).bit_count()
            if fit and hol:
                singles.append((fit + hol, min(fit, hol),
                                mask.bit_count(), feature, wanted))
    print("  zero-contradiction partial literals:")
    for total, minimum, fires, feature, wanted in sorted(
            singles, reverse=True)[:20]:
        print("    %-16s=%d pinned=%d (%d bank-min) fires=%d" %
              (names[feature], wanted, total, minimum, fires))

    best = []
    for first in range(len(literals)):
        ffeature, fwanted, fmask = literals[first]
        for second in range(first + 1, len(literals)):
            sfeature, swanted, smask = literals[second]
            if ffeature == sfeature:
                continue
            mask = fmask & smask
            if not mask or mask & bad:
                continue
            fit = (mask & fit_positive).bit_count()
            hol = (mask & hol_positive).bit_count()
            if not fit or not hol:
                continue
            candidate = (fit + hol, min(fit, hol), mask.bit_count(),
                         first, second)
            if len(best) < 100:
                best.append(candidate)
                if len(best) == 100:
                    best.sort()
            elif candidate > best[0]:
                best[0] = candidate
                best.sort()
    print("  zero-contradiction partial conjunctions:")
    for total, minimum, fires, first, second in sorted(
            best, reverse=True)[:30]:
        a, b = literals[first], literals[second]
        print("    %s=%d && %s=%d pinned=%d (%d bank-min) fires=%d" %
              (names[a[0]], a[1], names[b[0]], b[1], total, minimum,
               fires))

    # The corrected terminal frame proves P[cut] is the direction bit on
    # every pinned decision: one for upper magnitude-up, zero for lower
    # magnitude-down.  Hold that structural literal fixed and search the
    # remaining two-literal qualifier exactly.
    direction = 1 if correction == -1 else 0
    pcut_feature = name_index["P+00"]
    anchor = literals[2 * pcut_feature + direction][2]
    anchored = []
    for first in range(len(literals)):
        ffeature, _, fmask = literals[first]
        if ffeature == pcut_feature:
            continue
        for second in range(first + 1, len(literals)):
            sfeature, _, smask = literals[second]
            if sfeature in (pcut_feature, ffeature):
                continue
            mask = anchor & fmask & smask
            if not mask or mask & bad:
                continue
            fit = (mask & fit_positive).bit_count()
            hol = (mask & hol_positive).bit_count()
            if not fit or not hol:
                continue
            candidate = (fit + hol, min(fit, hol), mask.bit_count(),
                         first, second)
            if len(anchored) < 100:
                anchored.append(candidate)
                if len(anchored) == 100:
                    anchored.sort()
            elif candidate > anchored[0]:
                anchored[0] = candidate
                anchored.sort()
    print("  P[cut]-anchored zero-contradiction triples:")
    for total, minimum, fires, first, second in sorted(
            anchored, reverse=True)[:30]:
        a, b = literals[first], literals[second]
        print("    P+00=%d && %s=%d && %s=%d "
              "pinned=%d (%d bank-min) fires=%d" %
              (direction, names[a[0]], a[1], names[b[0]], b[1],
               total, minimum, fires))


def lower_response_core():
    """Qualify h1000's exact 9-fix/0-break lower response core."""
    scope = [index for index, row in enumerate(records)
             if row["line"] == "LOW" and row["act"] == 1]
    full = (1 << len(scope)) - 1
    bad = fit_positive = hol_positive = 0
    for local, index in enumerate(scope):
        row = records[index]
        bit = 1 << local
        if 1 not in row["nset"]:
            bad |= bit
        if row["pinned"] and row["nset"] == {1}:
            if row["half"] == "FIT":
                fit_positive |= bit
            else:
                hol_positive |= bit

    masks = []
    for feature in range(len(names)):
        ones = 0
        for local, index in enumerate(scope):
            if int(X[index, feature]):
                ones |= 1 << local
        masks.append((full ^ ones, ones))
    core = (masks[name_index["P+00"]][0]
            & masks[name_index["B-01"]][0]
            & masks[name_index["P-08"]][0])
    print("\n  h1000 lower response core "
          "P+00=0 && B-01=0 && P-08=0:")
    print("    fires=%d bad=%d pinned=%d FIT/HOL=%d/%d" %
          (core.bit_count(), (core & bad).bit_count(),
           (core & (fit_positive | hol_positive)).bit_count(),
           (core & fit_positive).bit_count(),
           (core & hol_positive).bit_count()))
    candidates = []
    for feature in range(len(names)):
        for wanted in (0, 1):
            mask = core & masks[feature][wanted]
            if not mask or mask & bad:
                continue
            fit = (mask & fit_positive).bit_count()
            hol = (mask & hol_positive).bit_count()
            if not fit or not hol:
                continue
            candidates.append((fit + hol, min(fit, hol),
                               mask.bit_count(), feature, wanted))
    print("    zero-contradiction one-literal qualifiers:")
    for total, minimum, fires, feature, wanted in sorted(
            candidates, reverse=True)[:40]:
        print("      %-16s=%d pinned=%d (%d bank-min) fires=%d" %
              (names[feature], wanted, total, minimum, fires))


print("records:", len(records), "features:", len(names))
search("TOP", 0, -1)
search("TOP", 1, -1)
search("LOW", 1, 1)
print("\n== conservative zero-contradiction partial arms ==")
conservative_pairs("TOP", 0, -1)
conservative_pairs("TOP", 1, -1)
conservative_pairs("LOW", 1, 1)
lower_response_core()
