#!/usr/bin/env python3
"""h1028: test exact lower-array carry wires against truth and response.

The h1027 staged-array decomposition proved that the discarded low slices
account exactly for the high contribution omitted by the upper product array.
This experiment preserves the four HA/CSA1/CSA2/CPA carry channels and tests
their states on two independent axes:

* the h975 pinned/admissible terminal-integer census; and
* h1000 force-response neighborhoods plus h1022 blind false positives.

Patterns are learned only as conjunctions of architectural wire values.  The
FIT/HOL label is used solely for reporting and is never available to a rule.
"""

import csv
from collections import Counter
from functools import lru_cache
from itertools import combinations

from h621_carry_predict import csa


WIDTH = 224
MASK = (1 << WIDTH) - 1
DIGITS = 23
FINAL_ORIGIN = 3 * (DIGITS - 1)
PRODUCTS = ("sq", "f4", "left", "right")
FAMILIES = {
    "top0": ("TOP", 0, -1),
    "top1": ("TOP", 1, -1),
    "low1": ("LOW", 1, 1),
}


def load_tsv(path):
    with open(path) as src:
        return list(csv.DictReader(src, delimiter="\t"))


def booth_digits(multiplier):
    shifted = multiplier << 1
    result = []
    for index in range(DIGITS):
        value = (shifted >> (3 * index)) & 15
        result.append((value & 1) + ((value >> 1) & 1)
                      + 2 * ((value >> 2) & 1)
                      - 4 * ((value >> 3) & 1))
    return result


def clear_below(word, boundary):
    return word & (MASK ^ ((1 << boundary) - 1))


def omitted_slices(multiplicand, multiplier):
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
            origin = 3 * index
            if origin < boundary:
                omitted.append((rows[index] & ((1 << boundary) - 1),
                                origin, boundary, "P%02d" % index))
        inputs = [clear_below(rows[index], boundary) for index in first]
        sum_word, carry_word = csa(*inputs)
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

    even_sum, even_carry, even_boundary, even_omitted = \
        thread(range(0, DIGITS, 2))
    odd_sum, odd_carry, odd_boundary, odd_omitted = \
        thread(range(1, DIGITS, 2))
    final_mask = (1 << FINAL_ORIGIN) - 1
    if even_boundary == FINAL_ORIGIN:
        lag_sum, lag_carry, lag_boundary, lag_tag = (
            odd_sum, odd_carry, odd_boundary, "O")
    else:
        lag_sum, lag_carry, lag_boundary, lag_tag = (
            even_sum, even_carry, even_boundary, "E")
    return even_omitted + odd_omitted + [
        (lag_sum & final_mask, lag_boundary, FINAL_ORIGIN, lag_tag + "S"),
        (lag_carry & final_mask, lag_boundary, FINAL_ORIGIN, lag_tag + "C"),
    ]


@lru_cache(maxsize=None)
def lower_state(multiplicand, multiplier):
    omitted = omitted_slices(multiplicand, multiplier)
    # The thread containing the final recode digit enters the HA first;
    # the lagging thread is shifted into the two following CSA levels.
    top_tag = "E" if (DIGITS - 1) % 2 == 0 else "O"
    lag_tag = "O" if top_tag == "E" else "E"
    priority = {top_tag + "S": 0, top_tag + "C": 1,
                lag_tag + "S": 2, lag_tag + "C": 3}
    ordered = sorted(omitted,
                     key=lambda item: (priority.get(item[3], 4), item[3]))
    incoming = (0, 0, 0, 0)
    result_word = 0
    for column in range(FINAL_ORIGIN):
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
    low_mask = (1 << FINAL_ORIGIN) - 1
    if result_word != (omitted_total & low_mask):
        raise AssertionError("lower-array conservation failure")
    if sum(incoming) != omitted_total >> FINAL_ORIGIN:
        raise AssertionError("lower-array carry failure")
    state = sum(bit << index for index, bit in enumerate(incoming))
    return state


def terminal_frame(feature):
    le = int(feature["lefte2"])
    re = int(feature["righte2"])
    left = int(feature["leftsig"], 16)
    right = int(feature["rightsig"], 16)
    payload = int(feature["pay2"]) if feature["pay2"] != "-" else 0
    left_sign = int(feature["leftsign"])
    right_sign = int(feature["rightsign"])
    scale = min(le, re, le - 8 if payload else le)
    left_input = left << (le - scale)
    payload_input = abs(payload) << (le - 8 - scale) if payload else 0
    signed_left = -left_input if left_sign else left_input
    payload_sign = left_sign ^ (payload < 0)
    signed_payload = -payload_input if payload_sign else payload_input
    signed_right = -(right << (re - scale)) if right_sign \
        else right << (re - scale)
    magnitude = abs(signed_left + signed_payload + signed_right)
    cut = magnitude.bit_length() - 67
    if signed_left + signed_payload < 0 <= signed_right:
        minuend = -(signed_left + signed_payload)
        subtrahend = signed_right
    elif signed_right < 0 <= signed_left + signed_payload:
        minuend = -signed_right
        subtrahend = signed_left + signed_payload
    else:
        raise ValueError("unexpected terminal sign geometry")
    return (~(minuend ^ subtrahend) >> cut) & 1


def product_states(values):
    pairs = {
        "sq": (values["mag"], values["mag"]),
        "f4": (values["mul"], values["mul"]),
        "left": (values["mul"], values["lf"]),
        "right": (values["f4"], values["rf"]),
    }
    return {name: lower_state(*pair) for name, pair in pairs.items()}


def rule_features(states, pcut):
    result = {name: state for name, state in states.items()}
    result["pcut"] = pcut
    for name, state in states.items():
        for wire in range(4):
            result["%s.b%d" % (name, wire)] = (state >> wire) & 1
    for first, second in combinations(PRODUCTS, 2):
        result[first + "^" + second] = states[first] ^ states[second]
    return result


print("building census states")
feature_rows = load_tsv("h970_features.tsv")
nhw_rows = load_tsv("h975_nhw.tsv")
features = {(row["insn"], row["op"]): row for row in feature_rows}
census = []
for nrow in nhw_rows:
    feature = features[nrow["insn"], nrow["op"]]
    values = {
        "mag": int(feature["magsig"], 16),
        "mul": int(feature["mulsig"], 16),
        "lf": int(feature["lfsig"], 16),
        "f4": int(feature["f4sig"], 16),
        "rf": int(feature["rfsig"], 16),
    }
    states = product_states(values)
    nset = {int(value) for value in nrow["nset"].split(",")}
    line = "TOP" if int(nrow["sum8"]) >= 128 else "LOW"
    census.append({
        "source": "census", "half": feature["half"], "line": line,
        "act": int(nrow["act"]), "nset": nset,
        "pinned": nrow["pinned"] == "1",
        "n": int(nrow["nset"]) if nrow["pinned"] == "1" else None,
        "features": rule_features(states, terminal_frame(feature)),
    })

print("building response states")
response = []
for row in load_tsv("/tmp/h1025_response_records.tsv"):
    values = {name: int(row[name], 16)
              for name in ("mag", "mul", "lf", "f4", "rf")}
    response.append({
        "family": row["family"], "source": row["source"],
        "half": row["half"], "label": row["label"], "op": row["op"],
        "features": rule_features(product_states(values), int(row["pcut"])),
    })


def fires(row, pattern):
    return all(row["features"][name] == value for name, value in pattern)


base_names = (["pcut"] + list(PRODUCTS)
              + ["%s.b%d" % (name, wire)
                 for name in PRODUCTS for wire in range(4)]
              + [first + "^" + second
                 for first, second in combinations(PRODUCTS, 2)])

for family, (line, act, target) in FAMILIES.items():
    print("\n===", family, "===")
    family_response = [row for row in response if row["family"] == family]
    fixes = [row for row in family_response if row["label"] == "FIX"]
    candidates = set()
    for row in fixes:
        for size in (1, 2, 3):
            for names in combinations(base_names, size):
                candidates.add(tuple((name, row["features"][name])
                                     for name in names))

    response_safe = []
    for pattern in candidates:
        fired = [row for row in family_response if fires(row, pattern)]
        if any(row["label"] == "BREAK" for row in fired):
            continue
        fix_count = sum(row["label"] == "FIX" for row in fired)
        if fix_count:
            response_safe.append((pattern, fired))

    eligible = [row for row in census
                if row["line"] == line and row["act"] == act]
    ranked = []
    for pattern, response_fired in response_safe:
        census_fired = [row for row in eligible if fires(row, pattern)]
        contradictions = sum(target not in row["nset"]
                             for row in census_fired)
        if contradictions:
            continue
        pinned_positive = sum(row["pinned"] and row["n"] == target
                              for row in census_fired)
        if not pinned_positive:
            continue
        response_counts = Counter((row["source"], row["label"], row["half"])
                                  for row in response_fired)
        census_halves = Counter(row["half"] for row in census_fired
                                if row["pinned"] and row["n"] == target)
        robustness = (len(response_fired),
                      min(census_halves.get("FIT", 0),
                          census_halves.get("HOL", 0)),
                      pinned_positive, len(census_fired))
        ranked.append((robustness, pattern, response_counts, census_halves))

    ranked.sort(reverse=True)
    print("patterns", len(candidates), "response-safe", len(response_safe),
          "fully admissible", len(ranked))
    for robustness, pattern, response_counts, census_halves in ranked[:30]:
        print(" ", robustness, pattern,
              "response", dict(sorted(response_counts.items())),
              "census", dict(sorted(census_halves.items())))
