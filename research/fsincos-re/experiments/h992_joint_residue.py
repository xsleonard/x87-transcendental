#!/usr/bin/env python3
"""h992: joint terminal-margin / fourth-power-residue search.

The h984 q_f4 marginal need not act by changing the retained f4 word (the
h985 experiment).  A redundant squarer state can instead meet the terminal
window only when that window is close to a carry boundary.  Test that
specific possibility with exact integer coordinates and the banked FIT/HOL
split.  No hardware labels are fit outside FIT.
"""

from collections import Counter, defaultdict
from fractions import Fraction


def load_tsv(path):
    with open(path) as src:
        head = next(src).rstrip("\n").split("\t")
        ix = {name: i for i, name in enumerate(head)}
        return ix, [line.rstrip("\n").split("\t") for line in src]


fix, feature_rows = load_tsv("h970_features.tsv")
nix, nhw_rows = load_tsv("h975_nhw.tsv")
uix, union_rows = load_tsv("h989_union_legs.tsv")
cix, corr_rows = load_tsv("h972_corr.tsv")

nhw = {(r[nix["insn"]], r[nix["op"]]): r for r in nhw_rows
       if r[nix["pinned"]] == "1"}
corr = {(r[cix["insn"]], r[cix["op"]]): r for r in corr_rows}


def outword(text):
    return text.lower().replace(":", " ")


union = defaultdict(list)
for row in union_rows:
    key = row[uix["insn"]], row[uix["op"]]
    union[key].append(row)


SCALE = 66
ONE = 1 << SCALE
B2 = -1400


def chopw(value, bits):
    mag = abs(value)
    width = mag.bit_length()
    if width <= bits:
        return value, 0
    shift = width - bits
    kept = (mag >> shift) << shift
    return (-kept if value < 0 else kept), shift


def r60_u0(s4, side, distance, low3, b1, b2):
    if s4 == 66 and side == 1:
        qa, qg1, qg2, qp, qq, qk, qpar = 2, 2, 1, 0, 4, 1, 0
        wd = -5 * (distance - 7)
    elif s4 == 66 and side == 0:
        qa, qg1, qg2, qp, qq, qk, qpar = 4, 1, 0, 0, 2, 1, 0
        wd = -9 - 5 * (distance - 9)
    elif s4 == 67 and side == 0:
        qa, qg1, qg2, qp, qq, qk, qpar = 4, 2, 1, -2, 4, 2, 1
        wd = -5 * (distance - 7)
    else:
        qa, qg1, qg2, qp, qq, qk, qpar = 2, 2, 3, -3, 8, 2, 1
        wd = -4 - 2 * (distance - 7)
    lp = low3 & 1
    base = qa * low3 + qg1 * b1 + qg2 * b2 + qp * lp + wd
    return qk * (base // qq) + qpar * lp


rows = []
for feature in feature_rows:
    key = feature[fix["insn"]], feature[fix["op"]]
    if key not in nhw:
        continue
    get = lambda name: feature[fix[name]]
    n = nhw[key]
    sq = int(get("mulsig"), 16)
    full4 = sq * sq
    s4 = full4.bit_length() - 67
    t4 = full4 & ((1 << s4) - 1)
    q4 = (t4 << SCALE) >> s4
    sqlow = sq - (1 << 66)
    low3 = int(get("low3"))
    mreg = low3 * sqlow - t4
    side = int(int(get("magsig"), 16) >= 0xB504F333F9DE6800)
    distance = int(get("dist"))
    right_shift = int(get("rsh"))
    rdisc = int(corr[key][cix["rdisc"]], 16)
    mexp = right_shift - 16 - (side == 0)
    mask = (1 << mexp) - 1
    rd3 = 3 * rdisc - ((2 * rdisc) & mask) - (rdisc & mask)
    b1 = int(rd3 >= (1 << right_shift))
    b2 = int(rd3 >= (1 << (right_shift + 1)))
    u0 = r60_u0(s4, side, distance, low3, b1, b2)
    mcenter = mreg - u0 * ONE

    ls, rs = int(get("leftsign")), int(get("rightsign"))
    le2, re2 = int(get("lefte2")), int(get("righte2"))
    pay = int(get("pay2")) if get("pay2") != "-" else 0
    acc = ((-1) ** ls * (int(get("leftsig"), 16) << (le2 - B2))
           + (-1) ** rs * (int(get("rightsig"), 16) << (re2 - B2)))
    if pay:
        acc += (-1) ** (ls ^ (pay < 0)) * (
            abs(pay) << (le2 - 8 - B2))
    chopped, ushift = chopw(acc, 67)
    residue = acc - chopped if acc > 0 else chopped - acc
    rq = (residue << SCALE) >> ushift

    nm = -int(n[nix["nset"]]) if acc < 0 else int(n[nix["nset"]])
    sum8 = int(get("sum8"))
    line = "TOP" if sum8 >= 0xF0 else "LOW"
    model95_bad = None
    if key in union:
        legs = union[key]
        model95_bad = sum(outword(r[uix["hw"]]) != outword(r[uix["m95"]])
                          for r in legs)
    rows.append({
        "key": key, "half": get("half"), "nm": nm,
        "line": line, "act": int(get("act")), "sum8": sum8,
        "d": distance, "me2": int(get("me2")),
        "g": int(get("g")), "low3": low3, "s4": s4,
        "side": side, "b1": b1, "b2": b2, "u0": u0,
        "rq": rq, "q4": q4, "sqlow": sqlow, "mreg": mreg,
        "mcenter": mcenter,
        "m95bad": model95_bad,
    })


def fit_cut(values):
    """Fit pred=(score < cut) or pred=(score >= cut), no tie split."""
    grouped = defaultdict(lambda: [0, 0])
    for score, positive in values:
        grouped[score][positive] += 1
    points = sorted(grouped.items())
    total_neg = sum(counts[0] for _, counts in points)
    total_pos = sum(counts[1] for _, counts in points)
    below_neg = below_pos = 0
    candidates = []
    for index in range(len(points) + 1):
        if index == 0:
            cut = points[0][0]
        elif index == len(points):
            cut = points[-1][0] + 1
        else:
            cut = (points[index - 1][0] + points[index][0] + 1) // 2
        good_lt = below_pos + total_neg - below_neg
        good_ge = total_pos - below_pos + below_neg
        candidates.append((good_lt, "lt", cut))
        candidates.append((good_ge, "ge", cut))
        if index < len(points):
            below_neg += points[index][1][0]
            below_pos += points[index][1][1]
    return max(candidates)


def apply_cut(sample, positive, score_fn, sense, cut):
    good = 0
    total = 0
    for row in sample:
        if row["nm"] not in (0, positive):
            continue
        predicted = score_fn(row) < cut if sense == "lt" \
            else score_fn(row) >= cut
        good += predicted == (row["nm"] == positive)
        total += 1
    return good, total


def coefficient_grid():
    values = {Fraction(0)}
    for denominator in (1, 2, 4, 8, 16, 32, 64, 128, 256):
        for numerator in range(-64, 65):
            values.add(Fraction(numerator, denominator))
    return sorted(values)


print("pinned rows:", len(rows))
print("post-R95 residual legs on pinned rows:",
      sum(r["m95bad"] or 0 for r in rows))

families = (("TOP", 0, 1), ("TOP", 1, 1), ("LOW", 1, -1))
for line, act, positive in families:
    fit = [r for r in rows if r["line"] == line and r["act"] == act
           and r["half"] == "FIT" and r["nm"] in (0, positive)]
    hol = [r for r in rows if r["line"] == line and r["act"] == act
           and r["half"] == "HOL" and r["nm"] in (0, positive)]
    print("\n%s act%d nm%+d: FIT %s HOL %s" % (
        line, act, positive,
        dict(Counter(r["nm"] for r in fit)),
        dict(Counter(r["nm"] for r in hol))))
    forms = [
        ("terminal rq", lambda r: r["rq"]),
        ("q_f4", lambda r: r["q4"]),
        ("R60 M", lambda r: r["mreg"]),
        ("R60 M-u", lambda r: r["mcenter"]),
    ]
    for name, score_fn in forms:
        good, sense, cut = fit_cut(
            [(score_fn(r), r["nm"] == positive) for r in fit])
        hgood, htotal = apply_cut(hol, positive, score_fn, sense, cut)
        print("  %-16s FIT %4d/%-4d HOL %4d/%-4d %s %d" % (
            name, good, len(fit), hgood, htotal, sense, cut))

    # score = rq + a*q_f4 and rq + a*M.  Fractions are evaluated
    # exactly by clearing the denominator before threshold fitting.
    joint = []
    for source in ("q4", "mreg", "mcenter"):
        for coeff in coefficient_grid():
            num, den = coeff.numerator, coeff.denominator
            score_fn = lambda r, s=source, n=num, d=den: d * r["rq"] \
                + n * r[s]
            good, sense, cut = fit_cut(
                [(score_fn(r), r["nm"] == positive) for r in fit])
            hgood, htotal = apply_cut(hol, positive, score_fn, sense, cut)
            joint.append((hgood, good, source, coeff, sense, cut, htotal,
                          score_fn))
    joint.sort(key=lambda item: (item[0], item[1]), reverse=True)
    print("  best joint forms by untouched HOL:")
    seen = set()
    shown = 0
    for hgood, good, source, coeff, sense, cut, htotal, _ in joint:
        signature = (source, round(float(coeff), 3))
        if signature in seen:
            continue
        seen.add(signature)
        print("    rq %s%-7s FIT %4d/%-4d HOL %4d/%-4d %s %d" % (
            ("+" if coeff >= 0 else "") + str(coeff) + "*",
            source, good, len(fit), hgood, htotal, sense, cut))
        shown += 1
        if shown == 8:
            break

    print("  fixed architectural boundary, coefficient selected on FIT:")
    fixed = []
    boundary = ONE if line == "TOP" else ONE >> 5
    for source in ("q4", "mreg", "mcenter"):
        for coeff in coefficient_grid():
            num, den = coeff.numerator, coeff.denominator
            def predicted(row, n=num, d=den, s=source):
                score = d * row["rq"] + n * row[s]
                return score >= d * boundary if line == "TOP" \
                    else score < d * boundary
            fgood = sum(predicted(r) == (r["nm"] == positive)
                        for r in fit)
            hgood = sum(predicted(r) == (r["nm"] == positive)
                        for r in hol)
            fixed.append((fgood, hgood, source, coeff))
    fixed.sort(reverse=True)
    for fgood, hgood, source, coeff in fixed[:5]:
        print("    rq %s%s*%s vs %s: FIT %d/%d HOL %d/%d" % (
            "+" if coeff >= 0 else "", coeff, source,
            "1" if line == "TOP" else "1/32",
            fgood, len(fit), hgood, len(hol)))

    print("  fixed boundary per (s4,side), selected on FIT:")
    for quadrant in ((66, 0), (66, 1), (67, 0), (67, 1)):
        qfit = [r for r in fit if (r["s4"], r["side"]) == quadrant]
        qhol = [r for r in hol if (r["s4"], r["side"]) == quadrant]
        if not qfit or not qhol:
            continue
        choices = []
        for coeff in coefficient_grid():
            num, den = coeff.numerator, coeff.denominator
            def predicted(row, n=num, d=den):
                score = d * row["rq"] + n * row["mcenter"]
                return score >= d * boundary if line == "TOP" \
                    else score < d * boundary
            fgood = sum(predicted(r) == (r["nm"] == positive)
                        for r in qfit)
            hgood = sum(predicted(r) == (r["nm"] == positive)
                        for r in qhol)
            choices.append((fgood, hgood, coeff))
        fgood, hgood, coeff = max(choices)
        print("    q%s rq %+s*Mcenter: FIT %d/%d HOL %d/%d" % (
            quadrant, coeff, fgood, len(qfit), hgood, len(qhol)))


print("\nPost-R95 pinned residual by line/act/nm:")
for key, count in sorted(Counter(
        (r["line"], r["act"], r["nm"], r["m95bad"])
        for r in rows if r["m95bad"]).items()):
    print("  %s act%d nm%+d badlegs%d: %d ops" % (*key, count))
