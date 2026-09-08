#!/usr/bin/env python3
"""h1024: expose Booth-recode and radix-8 redundant-product state.

h994 used unsigned one-bit partial products, while h993 scored only a few
whole carry predictors.  Neither experiment exposed the radix-8 recode digits
or individual bits of the final Booth sum/carry representation.  This pass
builds those features for every multiply in the clean h970/h975 census and
requires discoveries to reproduce in the frozen FIT/HOL split.

The ``patent`` reduction is the concrete odd/even topology described in
US5825679A: the first three products in each thread enter one 3:2 row, one new
product enters each following row, and two final 3:2 rows combine the four
thread outputs.  It is tested as an architectural template, not assumed to be
Skylake's implementation.
"""

import csv
import math
import os
from collections import Counter, defaultdict

from h621_carry_predict import booth8_rows, csa, reduce_rows


WIDTH = 224
MASK = (1 << WIDTH) - 1
OFFSETS = range(-16, 17)


def popcount(value):
    return bin(value).count("1")


def load_tsv(path):
    with open(path) as src:
        header = next(src).rstrip("\n").split("\t")
        index = {name: offset for offset, name in enumerate(header)}
        return index, [line.rstrip("\n").split("\t") for line in src]


def booth_digits(multiplier):
    """Return standard overlapping radix-8 digits, including a top zero."""
    shifted = multiplier << 1
    count = (multiplier.bit_length() + 3) // 3
    digits = []
    for index in range(count):
        value = (shifted >> (3 * index)) & 15
        b0 = value & 1
        b1 = (value >> 1) & 1
        b2 = (value >> 2) & 1
        b3 = (value >> 3) & 1
        digits.append(b0 + b1 + 2 * b2 - 4 * b3)
    return digits


def patent_reduce(rows):
    def thread(items):
        items = list(items)
        items += [0] * max(0, 3 - len(items))
        total = (items[0] + items[1] + items[2]) & MASK
        sum_word, carry_word = csa(items[0], items[1], items[2])
        trace = [(sum_word, carry_word, total)]
        for row in items[3:]:
            total = (total + row) & MASK
            sum_word, carry_word = csa(sum_word, carry_word, row)
            trace.append((sum_word, carry_word, total))
        return sum_word, carry_word, trace

    even_sum, even_carry, even_trace = thread(rows[0::2])
    odd_sum, odd_carry, odd_trace = thread(rows[1::2])
    sum1, carry1 = csa(odd_sum, odd_carry, even_sum)
    sum2, carry2 = csa(sum1, carry1, even_carry)
    return sum2, carry2, even_trace, odd_trace, (sum1, carry1)


def bit_features(a, b, prefix):
    product = a * b
    cut = product.bit_length() - 67
    rows = booth8_rows(a, b)
    digits = booth_digits(b)
    result = {}
    for index, digit in enumerate(digits):
        for candidate in range(-4, 5):
            result["%s_d%02d=%+d" % (prefix, index, candidate)] = \
                int(digit == candidate)
        result["%s_d%02dneg" % (prefix, index)] = int(digit < 0)
        result["%s_d%02dodd" % (prefix, index)] = abs(digit) & 1

    pairs = {"seq": reduce_rows(rows, "seq")}
    ps, pc, even_trace, odd_trace, combine = patent_reduce(rows)
    pairs["patent"] = ps, pc
    for arrangement, (sum_word, carry_word) in pairs.items():
        if (sum_word + carry_word) & MASK != product & MASK:
            raise AssertionError((prefix, arrangement, hex(a), hex(b)))
        words = {
            "s": sum_word,
            "c": carry_word,
            "p": sum_word ^ carry_word,
            "g": sum_word & carry_word,
        }
        for kind, word in words.items():
            for offset in OFFSETS:
                position = cut + offset
                result["%s_%s_%sC%+d" %
                       (prefix, arrangement, kind, offset)] = \
                    (word >> position) & 1 if position >= 0 else 0
        for kind, word in (("p", words["p"]), ("g", words["g"])):
            run = 0
            position = cut - 1
            while position >= 0 and run < 65 and ((word >> position) & 1):
                run += 1
                position -= 1
            for threshold in (1, 2, 3, 4, 6, 8, 10, 12, 16, 20,
                              24, 32, 48, 64):
                result["%s_%s_%srun%d" %
                       (prefix, arrangement, kind, threshold)] = \
                    int(run >= threshold)

    # The two final thread states and first combining row are architecturally
    # distinct in the odd/even array.  Expose their cut-relative P/G state.
    thread_pairs = {
        "pe": even_trace[-1][:2],
        "po": odd_trace[-1][:2],
        "pc1": combine,
    }
    for name, (sum_word, carry_word) in thread_pairs.items():
        for kind, word in (("s", sum_word), ("c", carry_word),
                           ("p", sum_word ^ carry_word),
                           ("g", sum_word & carry_word)):
            for offset in OFFSETS:
                position = cut + offset
                result["%s_%s_%sC%+d" % (prefix, name, kind, offset)] = \
                    (word >> position) & 1 if position >= 0 else 0
    return result


def terminal_pcut(feature, fix):
    get = lambda name: feature[fix[name]]
    left = int(get("leftsig"), 16)
    right = int(get("rightsig"), 16)
    left_exp = int(get("lefte2"))
    right_exp = int(get("righte2"))
    payload = int(get("pay2")) if get("pay2") != "-" else 0
    scale = min(left_exp, right_exp,
                left_exp - 8 if payload else left_exp)
    signed_left = (-1 if int(get("leftsign")) else 1) * (
        left << (left_exp - scale))
    signed_right = (-1 if int(get("rightsign")) else 1) * (
        right << (right_exp - scale))
    signed_payload = 0
    if payload:
        payload_sign = int(get("leftsign")) ^ (payload < 0)
        signed_payload = (-1 if payload_sign else 1) * (
            abs(payload) << (left_exp - 8 - scale))
    if signed_left + signed_payload < 0 <= signed_right:
        minuend = -(signed_left + signed_payload)
        subtrahend = signed_right
    elif signed_right < 0 <= signed_left + signed_payload:
        minuend = -signed_right
        subtrahend = signed_left + signed_payload
    else:
        raise AssertionError("unexpected terminal sign geometry")
    magnitude = minuend - subtrahend
    cut = magnitude.bit_length() - 67
    return (~(minuend ^ subtrahend) >> cut) & 1


fix, feature_rows = load_tsv("h970_features.tsv")
nix, nhw_rows = load_tsv("h975_nhw.tsv")
nhw = {(row[nix["insn"]], row[nix["op"]]): row for row in nhw_rows}

data = []
for row_index, feature in enumerate(feature_rows):
    get = lambda name: feature[fix[name]]
    key = get("insn"), get("op")
    nrow = nhw[key]
    nset = {int(value) for value in nrow[nix["nset"]].split(",")}
    pinned = nrow[nix["pinned"]] == "1"
    nvalue = int(nrow[nix["nset"]]) if pinned else None
    line = "TOP" if int(get("sum8")) >= 128 else "LOW"
    values = {
        "mag": int(get("magsig"), 16),
        "sq": int(get("mulsig"), 16),
        "f4": int(get("f4sig"), 16),
        "odd": int(get("lfsig"), 16),
        "even": int(get("rfsig"), 16),
    }
    feats = {}
    # q_f4 was the only strong replicated marginal in h984.  Start with
    # that multiply so this pass remains small enough for rapid iteration;
    # the terminal products can be added only if a real signal survives.
    for name, first, second in (
            ("f4", values["sq"], values["sq"]),):
        feats.update(bit_features(first, second, name))
    stratum = tuple(get(name) for name in ("sum8", "d", "me2", "g"))
    data.append({
        "key": key, "half": get("half"), "line": line,
        "act": int(get("act")), "n": nvalue, "nset": nset,
        "pinned": pinned, "stratum": stratum,
        "pcut": terminal_pcut(feature, fix),
        "features": feats,
    })
    if row_index and row_index % 1000 == 0:
        print("built", row_index, flush=True)


names = sorted(data[0]["features"])
response_rows = []
response_path = "/tmp/h1025_response_records.tsv"
if os.path.exists(response_path):
    with open(response_path) as src:
        for row in csv.DictReader(src, delimiter="\t"):
            response_rows.append({
                **row,
                "pcut": int(row["pcut"]),
                "features": bit_features(int(row["square"], 16),
                                         int(row["square"], 16), "f4"),
            })
families = (("top0", "TOP", 0, -1),
            ("top1", "TOP", 1, -1),
            ("low1", "LOW", 1, 1))
print("census rows", len(data), "pinned",
      sum(row["pinned"] for row in data), "features", len(names), flush=True)
for family, line, act, positive in families:
    direction_bit = 1 if line == "TOP" else 0
    sample = [row for row in data
              if row["line"] == line and row["act"] == act
              and row["pcut"] == direction_bit
              and ((row["pinned"] and row["n"] == positive)
                   or positive not in row["nset"])]
    strata = defaultdict(list)
    for row in sample:
        strata[row["stratum"]].append(row)
    scores = []
    for name in names:
        zscores = {}
        for half in ("FIT", "HOL"):
            numerator = denominator = 0.0
            for rows in strata.values():
                a = b = c = d = 0
                for row in rows:
                    if row["half"] != half:
                        continue
                    value = row["features"][name]
                    is_positive = row["pinned"] and row["n"] == positive
                    if is_positive:
                        a += value
                        b += 1 - value
                    else:
                        c += value
                        d += 1 - value
                n1, n0 = a + b, c + d
                if not n1 or not n0:
                    continue
                probability = (a + c) / (n1 + n0)
                if probability <= 0 or probability >= 1:
                    continue
                numerator += a - n1 * probability
                denominator += (n1 * n0 * probability
                                * (1 - probability) / (n1 + n0))
            zscores[half] = numerator / math.sqrt(denominator) \
                if denominator else 0.0
        fit, holdout = zscores["FIT"], zscores["HOL"]
        if fit * holdout > 0:
            scores.append((min(abs(fit), abs(holdout)),
                           abs(fit) + abs(holdout), fit, holdout, name))
    scores.sort(reverse=True)
    print("\n%s positives %d/%d; reproduced Booth-state features:" %
          (family, sum(row["pinned"] and row["n"] == positive
                       for row in sample),
           len(sample)))
    for _, _, fit, holdout, name in scores[:60]:
        print("  %-45s FIT %+7.2f HOL %+7.2f" %
              (name, fit, holdout))

    # Exact admissibility screen: target-absent rows are hard negatives;
    # target-containing unpinned rows are don't-cares.  Search two-literal
    # Booth predicates with no census contradiction and positive examples in
    # both frozen banks.  Python integers make the exhaustive pair scan cheap.
    bad_mask = fit_mask = holdout_mask = 0
    for index, row in enumerate(sample):
        bit = 1 << index
        if positive not in row["nset"]:
            bad_mask |= bit
        elif row["pinned"] and row["n"] == positive:
            if row["half"] == "FIT":
                fit_mask |= bit
            else:
                holdout_mask |= bit
    all_mask = (1 << len(sample)) - 1
    unique = {}
    for feature_name in names:
        one_mask = 0
        for index, row in enumerate(sample):
            one_mask |= row["features"][feature_name] << index
        for wanted, literal_mask in ((1, one_mask),
                                     (0, all_mask ^ one_mask)):
            if not (literal_mask & fit_mask and literal_mask & holdout_mask):
                continue
            unique.setdefault(literal_mask, (feature_name, wanted))
    literals = [(mask, description) for mask, description in unique.items()]
    response = [row for row in response_rows
                if row["family"] == family
                and row["pcut"] == direction_bit]
    response_all_mask = (1 << len(response)) - 1
    response_break_mask = response_fix_mask = 0
    response_fit_mask = response_holdout_mask = 0
    for index, row in enumerate(response):
        if row["label"] == "BREAK":
            response_break_mask |= 1 << index
        elif row["label"] == "FIX":
            response_fix_mask |= 1 << index
            if row["half"] == "FIT":
                response_fit_mask |= 1 << index
            elif row["half"] == "HOL":
                response_holdout_mask |= 1 << index
    response_feature_masks = {}
    for feature_name in names:
        mask = 0
        for index, row in enumerate(response):
            mask |= row["features"][feature_name] << index
        response_feature_masks[feature_name] = mask

    def response_literal(description):
        feature_name, wanted = description
        mask = response_feature_masks[feature_name]
        return mask if wanted else response_all_mask ^ mask

    safe_pairs = []
    for first_index, (first_mask, first_desc) in enumerate(literals):
        for second_mask, second_desc in literals[first_index:]:
            fired = first_mask & second_mask
            if fired & bad_mask:
                continue
            response_fired = (response_literal(first_desc)
                              & response_literal(second_desc))
            if response_fired & response_break_mask:
                continue
            response_fixes = popcount(response_fired & response_fix_mask)
            if response_rows and not response_fixes:
                continue
            response_fit = popcount(response_fired & response_fit_mask)
            response_holdout = popcount(
                response_fired & response_holdout_mask)
            if response_rows and (not response_fit or not response_holdout):
                continue
            fit_count = popcount(fired & fit_mask)
            holdout_count = popcount(fired & holdout_mask)
            if not fit_count or not holdout_count:
                continue
            safe_pairs.append((min(response_fit, response_holdout),
                               response_fixes, fit_count + holdout_count,
                               min(fit_count, holdout_count),
                               popcount(fired), first_desc, second_desc,
                               fit_count, holdout_count,
                               response_fit, response_holdout))
    safe_pairs.sort(reverse=True)
    print("  zero-contradiction Booth literal pairs:")
    for _, response_fixes, total, minimum, fires, first, second, fit_count, holdout_count, response_fit, response_holdout \
            in safe_pairs[:40]:
        print("    (%s==%d) && (%s==%d): pinned=%d FIT/HOL=%d/%d "
              "fires=%d response=%d(%d/%d)" %
              (*first, *second, total, fit_count, holdout_count, fires,
               response_fixes, response_fit, response_holdout))
