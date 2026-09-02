#!/usr/bin/env python3
"""h1027: model the staged low-column loss of an odd/even radix-8 array.

The full-width ``patent`` pair in h993 was only a different exact CSA tree.
The architectural distinction in US5825679A is that each thread advances six
columns per row and exports the discarded columns to a separate lower-product
network.  Reconstruct that upper array in global coordinates.  If the model
is coherent, its high result must differ from the exact product by only the
small carry contribution injected at the final guard column.
"""

from collections import Counter, defaultdict

from h621_carry_predict import csa


WIDTH = 224
MASK = (1 << WIDTH) - 1
DIGITS = 24                 # pad a 67-bit multiplier to two 12-row threads
FINAL_ORIGIN = 3 * (DIGITS - 1)


def load_tsv(path):
    with open(path) as src:
        header = next(src).rstrip("\n").split("\t")
        index = {name: offset for offset, name in enumerate(header)}
        return index, [line.rstrip("\n").split("\t") for line in src]


def booth_digits(multiplier):
    shifted = multiplier << 1
    result = []
    for index in range(DIGITS):
        value = (shifted >> (3 * index)) & 15
        b0 = value & 1
        b1 = (value >> 1) & 1
        b2 = (value >> 2) & 1
        b3 = (value >> 3) & 1
        result.append(b0 + b1 + 2 * b2 - 4 * b3)
    return result


def clear_below(word, boundary):
    return word & (MASK ^ ((1 << boundary) - 1))


def upper_product_pair(multiplicand, multiplier):
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
        trace = [(boundary, sum_word, carry_word)]
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
            row = clear_below(rows[index], boundary)
            sum_word, carry_word = csa(sum_word, carry_word, row)
            trace.append((boundary, sum_word, carry_word))
        return sum_word, carry_word, trace, omitted

    even_sum, even_carry, even_trace, even_omitted = \
        thread(range(0, DIGITS, 2))
    odd_sum, odd_carry, odd_trace, odd_omitted = \
        thread(range(1, DIGITS, 2))
    # Final odd origin is three columns above the final even origin.  The
    # patent's two combining rows receive O-sum/O-carry/E-sum, then the first
    # pair plus E-carry.  All lower inputs are absent in this upper-only pass.
    rows1 = [clear_below(word, FINAL_ORIGIN)
             for word in (odd_sum, odd_carry, even_sum)]
    sum1, carry1 = csa(*rows1)
    rows2 = [clear_below(word, FINAL_ORIGIN)
             for word in (sum1, carry1, even_carry)]
    final_low_mask = (1 << FINAL_ORIGIN) - 1
    combine_omitted = [
        (even_sum & final_low_mask, even_trace[-1][0], FINAL_ORIGIN, "ES"),
        (even_carry & final_low_mask, even_trace[-1][0], FINAL_ORIGIN, "EC"),
    ]
    sum2, carry2 = csa(*rows2)
    omitted = even_omitted + odd_omitted + combine_omitted
    return (sum2, carry2, even_trace, odd_trace, (sum1, carry1), rows,
            omitted)


def lower_product_signals(omitted):
    """Reduce discarded slices with the four-channel lower-array recurrence.

    For an ordinary six-bit group, the four new inputs are odd sum, odd carry,
    even sum, and even carry.  The initial partial-product groups have fewer
    inputs and use their natural partial-product order.  Each carry channel is
    injected one reduction level below the level that produced it.
    """
    priority = {"OS": 0, "OC": 1, "ES": 2, "EC": 3}
    incoming = (0, 0, 0, 0)
    result_word = 0
    max_inputs = 0
    for column in range(FINAL_ORIGIN):
        active = [(word >> column) & 1
                  for word, low, high, tag in sorted(
                      omitted,
                      key=lambda item: (priority.get(item[3], 4), item[3]))
                  if low <= column < high]
        max_inputs = max(max_inputs, len(active))
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
    return incoming, result_word, max_inputs


def analyze_product(first, second):
    sum_word, carry_word, even_trace, odd_trace, combine, rows, omitted = \
        upper_product_pair(first, second)
    upper = ((sum_word + carry_word) & MASK) >> FINAL_ORIGIN
    exact = (first * second) >> FINAL_ORIGIN
    signals, lower_word, max_inputs = lower_product_signals(omitted)
    omitted_carry = sum(word for word, _, _, _ in omitted) >> FINAL_ORIGIN
    omitted_low = sum(word for word, _, _, _ in omitted) \
        & ((1 << FINAL_ORIGIN) - 1)
    if lower_word != omitted_low:
        raise AssertionError((lower_word, omitted_low))
    return (exact - upper, signals, omitted_carry, max_inputs, sum_word,
            carry_word)


fix, rows = load_tsv("h970_features.tsv")
nhix, nhw_rows = load_tsv("h975_nhw.tsv")
nhw = {(row[nhix["insn"]], row[nhix["op"]]): row for row in nhw_rows}

counts = defaultdict(Counter)
samples = defaultdict(list)
decisions = Counter()
signal_decisions = Counter()
for row in rows:
    get = lambda name: row[fix[name]]
    key = get("insn"), get("op")
    products = {
        "sq": (int(get("magsig"), 16), int(get("magsig"), 16)),
        "f4": (int(get("mulsig"), 16), int(get("mulsig"), 16)),
        "left": (int(get("mulsig"), 16), int(get("lfsig"), 16)),
        "right": (int(get("f4sig"), 16), int(get("rfsig"), 16)),
    }
    nrow = nhw[key]
    nvalue = (int(nrow[nhix["nset"]])
              if nrow[nhix["pinned"]] == "1" else None)
    line = "TOP" if int(get("sum8")) >= 128 else "LOW"
    act = int(get("act"))
    for name, operands in products.items():
        need, signals, omitted_carry, max_inputs, _, _ = \
            analyze_product(*operands)
        counts[name][need] += 1
        counts[name + "_signals"][signals] += 1
        if omitted_carry != need:
            counts[name + "_omitted_mismatch"][need, omitted_carry] += 1
        counts[name + "_max_inputs"][max_inputs] += 1
        if sum(signals) != need:
            counts[name + "_signal_mismatch"][need, signals] += 1
        if nvalue is not None:
            decisions[line, act, nvalue, name, need] += 1
            signal_decisions[line, act, nvalue, name, signals] += 1
        if len(samples[name, need]) < 4:
            samples[name, need].append((key, nvalue, operands))

print("digits", DIGITS, "final origin", FINAL_ORIGIN)
for name in ("sq", "f4", "left", "right"):
    print("\n", name, "missing high contribution:")
    for need, count in sorted(counts[name].items()):
        print("  need=%+d count=%d" % (need, count))
        if need < 0 or need > 4:
            for sample in samples[name, need]:
                print("    ", sample[:2])
    print("  signal tuples:", dict(sorted(counts[name + "_signals"].items())))
    print("  signal-sum mismatches:",
          sum(counts[name + "_signal_mismatch"].values()))
    print("  omitted-carry mismatches:",
          sum(counts[name + "_omitted_mismatch"].values()))
    print("  maximum simultaneous inputs:",
          dict(sorted(counts[name + "_max_inputs"].items())))

print("\nPinned terminal decisions by lower-product contribution:")
for cell, count in sorted(decisions.items()):
    print(" ", cell, count)

print("\nPinned terminal decisions by four-wire state:")
for cell, count in sorted(signal_decisions.items()):
    print(" ", cell, count)
