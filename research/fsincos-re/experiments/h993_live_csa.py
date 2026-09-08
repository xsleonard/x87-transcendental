#!/usr/bin/env python3
"""h993: live-FMUL carry-save pairs consumed by the terminal subtract.

The direct cosine numerical model combines two terminal products with a
subtraction.  h930 encoded the subtraction of the *materialized* 67-bit
products, while h980 altered resolved exact products.  This experiment tests
the remaining structural case: radix-8 FMUL outputs arrive as (S,C) pairs,
the terminal combines both pairs with payload, and a bounded predictor supplies
the carry from the discarded field.

Every Booth/reduction pair is first required to reproduce the exact product
modulo WIDTH.  Predictions are scored as the integer magnitude adjustment
relative to the same chop67 baseline used by h975.
"""

from collections import Counter

from h621_carry_predict import booth8_rows, reduce_rows, csa


WIDTH = 224
MASK = (1 << WIDTH) - 1
PREDICTORS = []
for width in (4, 6, 8, 10, 12, 16, 20, 24, 32):
    for kind in ("z", "o", "sticky", "adjS", "adjC"):
        PREDICTORS.append((kind, width))


def load_tsv(path):
    with open(path) as src:
        head = next(src).rstrip("\n").split("\t")
        ix = {name: i for i, name in enumerate(head)}
        return ix, [line.rstrip("\n").split("\t") for line in src]


fix, features = load_tsv("h970_features.tsv")
nix, nhw_rows = load_tsv("h975_nhw.tsv")
nhw = {(r[nix["insn"]], r[nix["op"]]): r for r in nhw_rows
       if r[nix["pinned"]] == "1"}


def product_pair(a, b, arrangement):
    reverse_role = arrangement.endswith("_rf")
    base = arrangement.replace("_rf", "")
    mcand, mplier = (b, a) if reverse_role else (a, b)
    rows = booth8_rows(mcand, mplier)
    if base == "patent":
        # US5825679A's array is not the generic ``eo`` reduction used by
        # h621.  Each odd/even thread reduces its first three products in
        # one row, consumes one new product in each following row, and the
        # four final vectors are combined in two more 3:2 stages.
        def thread(items):
            items = list(items)
            items += [0] * max(0, 3 - len(items))
            s, c = csa(items[0], items[1], items[2])
            for row in items[3:]:
                s, c = csa(s, c, row)
            return s, c

        es, ec = thread(rows[0::2])
        os, oc = thread(rows[1::2])
        s1, c1 = csa(os, oc, es)
        pair = csa(s1, c1, ec)
    else:
        pair = reduce_rows(rows, base)
    if (pair[0] + pair[1]) & MASK != (a * b) & MASK:
        raise AssertionError((arrangement, hex(a), hex(b)))
    return pair


def terminal_pair(rows, arrangement):
    return reduce_rows([row & MASK for row in rows], arrangement)


def predicted_carry(sum_word, carry_word, cut, kind, width):
    if cut <= 0:
        return 0
    low_mask = (1 << cut) - 1
    sl = sum_word & low_mask
    cl = carry_word & low_mask
    width = min(width, cut)
    shift = cut - width
    base = (sl >> shift) + (cl >> shift)
    if kind == "o":
        base += 1
    elif kind == "sticky" and shift and ((sl | cl) & ((1 << shift) - 1)):
        base += 1
    elif kind == "adjS" and shift:
        base += (sl >> (shift - 1)) & 1
    elif kind == "adjC" and shift:
        base += (cl >> (shift - 1)) & 1
    return base >> width


OPS = []
for f in features:
    key = f[fix["insn"]], f[fix["op"]]
    if key not in nhw:
        continue
    get = lambda name: f[fix[name]]
    sq = int(get("mulsig"), 16)
    odd = int(get("lfsig"), 16)
    fourth = int(get("f4sig"), 16)
    even = int(get("rfsig"), 16)
    lbase = int(get("mule2")) + int(get("lfe2"))
    rbase = int(get("f4e2")) + int(get("rfe2"))
    payload = int(get("pay2")) if get("pay2") != "-" else 0
    paybase = int(get("lefte2")) - 8
    fine = min(lbase, rbase, paybase)
    left_full = sq * odd
    right_full = fourth * even
    exact_mag = ((left_full << (lbase - fine))
                 - (right_full << (rbase - fine))
                 + (payload << (paybase - fine)))
    if exact_mag <= 0:
        raise AssertionError((key, "non-positive exact magnitude"))

    # Materialized-product baseline used by h975.
    left_sig = int(get("leftsig"), 16)
    right_sig = int(get("rightsig"), 16)
    le2, re2 = int(get("lefte2")), int(get("righte2"))
    coarse = min(le2, re2, paybase)
    base_mag = ((left_sig << (le2 - coarse))
                - (right_sig << (re2 - coarse))
                + (payload << (paybase - coarse)))
    base_cut = base_mag.bit_length() - 67
    base_retained = base_mag >> base_cut
    retained_e2 = coarse + base_cut
    fine_cut = retained_e2 - fine
    if fine_cut <= 0:
        raise AssertionError((key, fine_cut))
    exact_retained = exact_mag >> fine_cut
    n_value = int(nhw[key][nix["nset"]])
    n_magnitude = -n_value
    OPS.append({
        "key": key, "half": get("half"), "target": n_magnitude,
        "sq": sq, "odd": odd, "fourth": fourth, "even": even,
        "lshift": lbase - fine, "rshift": rbase - fine,
        "payload": payload << (paybase - fine), "cut": fine_cut,
        "base": base_retained, "exact": exact_retained,
        "line": "TOP" if int(get("sum8")) >= 0xF0 else "LOW",
        "act": int(get("act")),
    })


ARRANGEMENTS = ("seq", "eo", "tree", "patent",
                "seq_rf", "tree_rf", "patent_rf")
TERMINALS = ("seq", "eo", "tree")


PAIR_CACHE = {}


def terminal_words(op, arrangement, terminal):
    cache_key = (op["key"], arrangement, terminal)
    if cache_key not in PAIR_CACHE:
        ls, lc = product_pair(op["sq"], op["odd"], arrangement)
        rs, rc = product_pair(op["fourth"], op["even"], arrangement)
        rows = [
            ls << op["lshift"], lc << op["lshift"], op["payload"],
            (~(rs << op["rshift"])) & MASK,
            (~(rc << op["rshift"])) & MASK,
            2,
        ]
        ss, cc = terminal_pair(rows, terminal)
        if (ss + cc) & MASK != (
                (op["sq"] * op["odd"] << op["lshift"])
                - (op["fourth"] * op["even"] << op["rshift"])
                + op["payload"]) & MASK:
            raise AssertionError((op["key"], arrangement, terminal))
        PAIR_CACHE[cache_key] = ss, cc
    return PAIR_CACHE[cache_key]


def classify(op, arrangement, terminal, predictor):
    ss, cc = terminal_words(op, arrangement, terminal)
    kind, width = predictor
    carry = predicted_carry(ss, cc, op["cut"], kind, width)
    high_mask = (1 << (WIDTH - op["cut"])) - 1
    retained = ((ss >> op["cut"]) + (cc >> op["cut"]) + carry) \
        & high_mask
    return retained - op["base"]


def score(config, half):
    arrangement, terminal, predictor = config
    right = total = 0
    classes = Counter()
    for op in OPS:
        if op["half"] != half:
            continue
        pred = classify(op, arrangement, terminal, predictor)
        target = op["target"]
        right += pred == target
        total += 1
        classes[(op["line"], op["act"], target, pred)] += 1
    return right, total, classes


print("pinned ops:", len(OPS), "targets:",
      dict(sorted(Counter(op["target"] for op in OPS).items())))
print("exact full-products control:",
      sum(op["exact"] - op["base"] == op["target"] for op in OPS),
      "/", len(OPS))

configs = [(arr, term, pred) for arr in ARRANGEMENTS
           for term in TERMINALS for pred in PREDICTORS]
ranked = []
for i, config in enumerate(configs):
    fit, nf, _ = score(config, "FIT")
    hol, nh, _ = score(config, "HOL")
    ranked.append((hol, fit, config, nf, nh))
ranked.sort(reverse=True)

print("\nTop live-CSA forms (ranked by untouched HOL):")
for hol, fit, config, nf, nh in ranked[:20]:
    print("  %-38s FIT %d/%d HOL %d/%d" %
          (str(config), fit, nf, hol, nh))

best = ranked[0][2]
_, _, detail = score(best, "HOL")
print("\nBest HOL confusion by (line, act, target, prediction):")
for key, count in sorted(detail.items()):
    print("  %-24s %d" % (str(key), count))
