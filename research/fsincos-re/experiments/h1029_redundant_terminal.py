#!/usr/bin/env python3
"""h1029: exact radix-8 redundant-product forwarding at the terminal.

h528 tested separate sum/carry truncation with radix-2/radix-4 guessed trees.
h1027/h1028 now provide the exact staged radix-8 lower-array recurrence at
the 67-bit product boundary.  Reconstruct the final product pairs, prove that
their documented lower-wire injections resolve to the exact product, then
test whether forwarding either redundant pair into the terminal explains the
hardware's integer n decision.
"""

import csv
from collections import Counter
from functools import lru_cache
from itertools import permutations, product

from h621_carry_predict import csa


WIDTH = 224
MASK = (1 << WIDTH) - 1
DIGITS = 23
ORIGIN = 3 * (DIGITS - 1)


def load_tsv(path):
    with open(path) as src:
        return list(csv.DictReader(src, delimiter="\t"))


def booth_digits(multiplier):
    shifted = multiplier << 1
    digits = []
    for index in range(DIGITS):
        value = (shifted >> (3 * index)) & 15
        digits.append((value & 1) + ((value >> 1) & 1)
                      + 2 * ((value >> 2) & 1)
                      - 4 * ((value >> 3) & 1))
    return digits


def clear_below(word, boundary):
    return word & (MASK ^ ((1 << boundary) - 1))


def half_add(first, second):
    return (first ^ second) & MASK, ((first & second) << 1) & MASK


def lower_signals(omitted, top_tag):
    lag_tag = "O" if top_tag == "E" else "E"
    priority = {top_tag + "S": 0, top_tag + "C": 1,
                lag_tag + "S": 2, lag_tag + "C": 3}
    ordered = sorted(omitted,
                     key=lambda item: (priority.get(item[3], 4), item[3]))
    incoming = (0, 0, 0, 0)
    result_word = 0
    for column in range(ORIGIN):
        active = [(word >> column) & 1
                  for word, low, high, _ in ordered
                  if low <= column < high]
        if len(active) > 4:
            raise AssertionError((column, len(active)))
        active += [0] * (4 - len(active))
        first, second, third, fourth = active
        ha_in, csa1_in, csa2_in, cpa_in = incoming
        ha_sum = first ^ second
        ha_out = first & second
        csa1_sum = ha_sum ^ third ^ ha_in
        csa1_out = ((ha_sum & third) | (ha_sum & ha_in)
                    | (third & ha_in))
        csa2_sum = csa1_sum ^ fourth ^ csa1_in
        csa2_out = ((csa1_sum & fourth) | (csa1_sum & csa1_in)
                    | (fourth & csa1_in))
        result = csa2_sum ^ csa2_in ^ cpa_in
        cpa_out = ((csa2_sum & csa2_in) | (csa2_sum & cpa_in)
                   | (csa2_in & cpa_in))
        result_word |= result << column
        incoming = ha_out, csa1_out, csa2_out, cpa_out
    omitted_total = sum(word for word, _, _, _ in omitted)
    if result_word != omitted_total & ((1 << ORIGIN) - 1):
        raise AssertionError("lower result mismatch")
    if sum(incoming) != omitted_total >> ORIGIN:
        raise AssertionError("lower carry mismatch")
    return incoming, result_word


@lru_cache(maxsize=None)
def product_representations(multiplicand, multiplier):
    digits = booth_digits(multiplier)
    rows = [((digit * multiplicand) << (3 * index)) & MASK
            for index, digit in enumerate(digits)]

    def thread(indices):
        indices = list(indices)
        first = indices[:3]
        boundary = 3 * first[-1]
        tag = "E" if first[0] == 0 else "O"
        omitted = []
        for index in first:
            row_origin = 3 * index
            if row_origin < boundary:
                omitted.append((rows[index] & ((1 << boundary) - 1),
                                row_origin, boundary, "P%02d" % index))
        initial = [clear_below(rows[index], boundary) for index in first]
        sum_word, carry_word = csa(*initial)
        for index in indices[3:]:
            old_boundary = boundary
            boundary = 3 * index
            low_mask = (1 << boundary) - 1
            omitted.extend(((sum_word & low_mask, old_boundary, boundary,
                             tag + "S"),
                            (carry_word & low_mask, old_boundary, boundary,
                             tag + "C")))
            sum_word = clear_below(sum_word, boundary)
            carry_word = clear_below(carry_word, boundary)
            sum_word, carry_word = csa(
                sum_word, carry_word, clear_below(rows[index], boundary))
        return sum_word, carry_word, boundary, omitted

    even = thread(range(0, DIGITS, 2))
    odd = thread(range(1, DIGITS, 2))
    if even[2] == ORIGIN:
        top, lag, top_tag = even, odd, "E"
    else:
        top, lag, top_tag = odd, even, "O"
    omitted = even[3] + odd[3]
    final_mask = (1 << ORIGIN) - 1
    omitted.extend(((lag[0] & final_mask, lag[2], ORIGIN,
                     ("O" if top_tag == "E" else "E") + "S"),
                    (lag[1] & final_mask, lag[2], ORIGIN,
                     ("O" if top_tag == "E" else "E") + "C")))
    (ha_out, csa1_out, csa2_out, cpa_out), lower_word = lower_signals(
        omitted, top_tag)
    bit = 1 << ORIGIN

    # Figure 8: the first two lower carries occupy the empty LSB of a
    # shifted carry input at CSA71/CSA72.  The third occupies the final
    # carry input to half adder 74; CPA_OUT is the round-adder carry-in.
    top_sum = clear_below(top[0], ORIGIN)
    top_carry = clear_below(top[1], ORIGIN) | (ha_out * bit)
    lag_sum = clear_below(lag[0], ORIGIN)
    lag_carry = clear_below(lag[1], ORIGIN)
    sum1, carry1 = csa(top_sum, top_carry, lag_sum)
    carry1 |= csa1_out * bit
    sum2, carry2 = csa(sum1, carry1, lag_carry)
    carry2 |= csa2_out * bit
    half_sum, half_carry = half_add(sum2, carry2)
    resolved = (lower_word + half_sum + half_carry
                + cpa_out * bit) & MASK
    exact = multiplicand * multiplier
    if (resolved >> ORIGIN) != exact >> ORIGIN:
        raise AssertionError((resolved >> ORIGIN, exact >> ORIGIN,
                              (ha_out, csa1_out, csa2_out, cpa_out)))

    shift = exact.bit_length() - 67
    if shift < 0:
        raise AssertionError("short product")
    exact_chop = exact >> shift

    def pair_value(sum_word, carry_word, extras):
        value = ((lower_word >> shift) + (sum_word >> shift)
                 + (carry_word >> shift))
        for signal in extras:
            if signal and ORIGIN >= shift:
                value += 1 << (ORIGIN - shift)
        # Negative Booth rows are represented modulo WIDTH.  Preserve that
        # modulus after the separate truncations so the sign-extension
        # cancellation cannot masquerade as a gigantic positive product.
        return value & ((1 << (WIDTH - shift)) - 1)

    def normalized_components(sum_word, carry_word, extras):
        components = [((lower_word | sum_word) >> shift),
                      (carry_word >> shift)]
        components.extend(signal << (ORIGIN - shift)
                          for signal in extras)
        components = [value & ((1 << 67) - 1) for value in components]
        if sum(components) & ((1 << 67) - 1) != exact_chop:
            raise AssertionError("normalized component mismatch")
        return tuple(components)

    # Values are intentionally not normalized: terminal alignment uses the
    # product's architectural exponent, so an extra leading bit remains a
    # one-unit representation error at that same scale.
    return {
        "resolved": exact_chop,
        "upper": pair_value(top_sum, clear_below(top[1], ORIGIN),
                            (ha_out, csa1_out, csa2_out, cpa_out)),
        "combine1": pair_value(sum1, carry1,
                               (csa2_out, cpa_out)),
        "combine2": pair_value(sum2, carry2, (cpa_out,)),
        "half": pair_value(half_sum, half_carry, (cpa_out,)),
        "combine2_components": normalized_components(
            sum2, carry2, (cpa_out,)),
        "half_components": normalized_components(
            half_sum, half_carry, (cpa_out,)),
    }


def candidate_n(feature, left_sig, right_sig):
    le = int(feature["lefte2"])
    re = int(feature["righte2"])
    payload = int(feature["pay2"]) if feature["pay2"] != "-" else 0
    left_sign = int(feature["leftsign"])
    right_sign = int(feature["rightsign"])
    scale = min(le, re, le - 8 if payload else le)

    def total(lsig, rsig):
        left = lsig << (le - scale)
        right = rsig << (re - scale)
        pay = abs(payload) << (le - 8 - scale) if payload else 0
        signed_left = -left if left_sign else left
        signed_right = -right if right_sign else right
        payload_sign = left_sign ^ (payload < 0)
        signed_pay = -pay if payload_sign else pay
        return signed_left + signed_pay + signed_right

    baseline_total = total(int(feature["leftsig"], 16),
                           int(feature["rightsig"], 16))
    candidate_total = total(left_sig, right_sig)
    baseline_mag = abs(baseline_total)
    candidate_mag = abs(candidate_total)
    cut = baseline_mag.bit_length() - 67
    baseline_retained = baseline_mag >> cut
    candidate_retained = candidate_mag >> cut
    # The terminal result is negative throughout this census.
    if baseline_total >= 0:
        raise AssertionError("unexpected baseline terminal sign")
    if candidate_total >= 0:
        return 999
    return -(candidate_retained - baseline_retained)


features = load_tsv("h970_features.tsv")
nhw = {(row["insn"], row["op"]): row
       for row in load_tsv("h975_nhw.tsv")}
variants = ("resolved", "combine2", "half")
scores = {pair: Counter() for pair in product(variants, repeat=2)}
product_deltas = {name: Counter() for name in ("left", "right")}
reconstruction = Counter()
component_stages = ("combine2_components", "half_components")
component_orders = tuple(permutations(("A", "N0", "N1", "N2", "K")))
bypass_scores = {(stage, order): Counter()
                 for stage in component_stages for order in component_orders}

for feature in features:
    key = feature["insn"], feature["op"]
    nrow = nhw[key]
    left_reps = product_representations(
        int(feature["mulsig"], 16), int(feature["lfsig"], 16))
    right_reps = product_representations(
        int(feature["f4sig"], 16), int(feature["rfsig"], 16))
    if left_reps["resolved"] != int(feature["leftsig"], 16):
        reconstruction["left_chop_mismatch"] += 1
    if right_reps["resolved"] != int(feature["rightsig"], 16):
        reconstruction["right_chop_mismatch"] += 1
    for name in variants[1:]:
        product_deltas["left"][name, left_reps[name]
                               - left_reps["resolved"]] += 1
        product_deltas["right"][name, right_reps[name]
                                - right_reps["resolved"]] += 1
    nset = {int(value) for value in nrow["nset"].split(",")}
    pinned = nrow["pinned"] == "1"
    truth = int(nrow["nset"]) if pinned else None
    half = feature["half"]
    for left_name, right_name in product(variants, repeat=2):
        value = candidate_n(feature, left_reps[left_name],
                            right_reps[right_name])
        score = scores[left_name, right_name]
        score["admissible"] += value in nset
        score["total"] += 1
        if pinned:
            score["pinned"] += 1
            score["pinned_exact"] += value == truth
            score[half + "_exact"] += value == truth
            score[half + "_total"] += 1

    # Model the right product as bypassing materialization before
    # the terminal subtraction. Its three final multiplier components enter
    # the subtract's CSA, while the left product and its retained payload
    # are already materialized in this asymmetric numerical hypothesis.
    le = int(feature["lefte2"])
    re = int(feature["righte2"])
    payload = int(feature["pay2"]) if feature["pay2"] != "-" else 0
    term_scale = min(le, re, le - 8 if payload else le)
    minuend = int(feature["leftsig"], 16) << (le - term_scale)
    if payload:
        minuend += payload << (le - 8 - term_scale)
    subtrahend = int(feature["rightsig"], 16) << (re - term_scale)
    baseline_mag = minuend - subtrahend
    if baseline_mag <= 0:
        raise AssertionError("unexpected terminal ordering")
    cut = baseline_mag.bit_length() - 67
    baseline_retained = baseline_mag >> cut
    term_width = 128
    term_mask = (1 << term_width) - 1
    for stage in component_stages:
        components = right_reps[stage]
        if len(components) != 3:
            raise AssertionError((stage, len(components)))
        right_alignment = re - term_scale
        overflow = sum(components) >> 67
        terms = {
            "A": minuend & term_mask,
            "N0": (~(components[0] << right_alignment)) & term_mask,
            "N1": (~(components[1] << right_alignment)) & term_mask,
            "N2": (~(components[2] << right_alignment)) & term_mask,
            "K": (3 + (overflow << (67 + right_alignment))) & term_mask,
        }
        for order in component_orders:
            sum_word, carry_word = csa(*(terms[name] for name in order[:3]))
            for name in order[3:]:
                sum_word, carry_word = csa(
                    sum_word, carry_word, terms[name])
            candidate = ((sum_word >> cut) + (carry_word >> cut)) \
                & ((1 << (term_width - cut)) - 1)
            value = -(candidate - baseline_retained)
            score = bypass_scores[stage, order]
            score["admissible"] += value in nset
            score["total"] += 1
            if pinned:
                score["pinned"] += 1
                score["pinned_exact"] += value == truth
                score[half + "_exact"] += value == truth
                score[half + "_total"] += 1

print("digits", DIGITS, "origin", ORIGIN,
      "reconstruction", dict(reconstruction))
for side in ("left", "right"):
    print("\n", side, "separate-pair delta from resolved chop")
    for cell, count in sorted(product_deltas[side].items()):
        print(" ", cell, count)

print("\nterminal forwarding scores")
ranked = sorted(scores.items(),
                key=lambda item: (item[1]["pinned_exact"],
                                  item[1]["admissible"]), reverse=True)
for pair, score in ranked:
    print(" %-22s pin %4d/%4d FIT %4d/%4d HOL %4d/%4d adm %4d/%4d" %
          ((pair[0] + "/" + pair[1]), score["pinned_exact"],
           score["pinned"], score["FIT_exact"], score["FIT_total"],
           score["HOL_exact"], score["HOL_total"], score["admissible"],
           score["total"]))

print("\nhot-right redundant bypass scores")
ranked = sorted(bypass_scores.items(),
                key=lambda item: (item[1]["pinned_exact"],
                                  item[1]["admissible"]), reverse=True)
for (stage, order), score in ranked[:40]:
    print(" %-19s %-18s pin %4d/%4d FIT %4d/%4d HOL %4d/%4d "
          "adm %4d/%4d" %
          (stage.replace("_components", ""), "/".join(order),
           score["pinned_exact"], score["pinned"],
           score["FIT_exact"], score["FIT_total"],
           score["HOL_exact"], score["HOL_total"],
           score["admissible"], score["total"]))
