#!/usr/bin/env python3
"""h1033: R60-style coordinates on the actual P[cut] selector problem.

Earlier R60 transfer experiments compared all pinned integer outcomes.  The
new cut-carry invariant shows that P[cut] already separates those outcomes;
the unresolved selector population consists instead of P[cut]-eligible
pinned positives versus rows whose admissible set excludes the target.

Test whether any physically motivated nonlinear coordinate is monotone inside
structural cells on that corrected population.  This is a diagnostic for a
closed-form threshold/floor law, not a fitted rule.
"""

import csv
from collections import Counter, defaultdict


SCALE = 66
ONE = 1 << SCALE
MASK = ONE - 1


def load_tsv(path):
    with open(path) as source:
        return list(csv.DictReader(source, delimiter="\t"))


def qdiscard(first, second):
    product = first * second
    shift = product.bit_length() - 67
    if shift <= 0:
        return 0
    return ((product & ((1 << shift) - 1)) << SCALE) >> shift


def terminal_frame(feature):
    left_exponent = int(feature["lefte2"])
    right_exponent = int(feature["righte2"])
    left = int(feature["leftsig"], 16)
    right = int(feature["rightsig"], 16)
    payload = int(feature["pay2"]) if feature["pay2"] != "-" else 0
    scale = min(left_exponent, right_exponent,
                left_exponent - 8 if payload else left_exponent)
    s_value = left << (left_exponent - scale)
    if payload:
        s_value += payload << (left_exponent - 8 - scale)
    b_value = right << (right_exponent - scale)
    magnitude = s_value - b_value
    if magnitude <= 0:
        raise ValueError("unexpected terminal magnitude")
    cut = magnitude.bit_length() - 67
    residue = magnitude & ((1 << cut) - 1) if cut > 0 else 0
    propagate = ~(s_value ^ b_value)
    pdown = 0
    while cut - pdown >= 0 and ((propagate >> (cut - pdown)) & 1):
        pdown += 1
    pbelow = 0
    while cut - 1 - pbelow >= 0 \
            and ((propagate >> (cut - 1 - pbelow)) & 1):
        pbelow += 1
    return {
        "pcut": (propagate >> cut) & 1,
        "pdown": pdown,
        "pbelow": pbelow,
        "rq": (residue << SCALE) >> cut if cut > 0 else 0,
        "ce8": (scale + cut) & 7,
    }


features = {(row["insn"], row["op"]): row
            for row in load_tsv("h970_features.tsv")}
corr = {(row["insn"], row["op"]): row
        for row in load_tsv("h972_corr.tsv")}

rows = []
for integer in load_tsv("h975_nhw.tsv"):
    key = integer["insn"], integer["op"]
    feature = features[key]
    square = int(feature["mulsig"], 16)
    magnitude = int(feature["magsig"], 16)
    fourth_full = square * square
    s4 = fourth_full.bit_length() - 67
    t4 = fourth_full & ((1 << s4) - 1)
    q4 = (t4 << SCALE) >> s4
    square_low = square - (1 << 66)
    low3 = int(feature["low3"])
    mreg = low3 * square_low - t4
    side = int(magnitude >= 0xB504F333F9DE6800)
    distance = int(feature["dist"])
    right_shift = int(feature["rsh"])
    right_discard = int(corr[key]["rdisc"], 16)
    mexp = right_shift - 16 - (side == 0)
    truncation_mask = (1 << mexp) - 1
    truncated_three = (3 * right_discard
                       - ((2 * right_discard) & truncation_mask)
                       - (right_discard & truncation_mask))
    b1 = int(truncated_three >= (1 << right_shift))
    b2 = int(truncated_three >= (1 << (right_shift + 1)))
    frame = terminal_frame(feature)
    nset = {int(value) for value in integer["nset"].split(",")}
    pinned = integer["pinned"] == "1"
    sum8 = int(integer["sum8"])
    pay2 = int(feature["pay2"]) if feature["pay2"] != "-" else 0
    qsq = qdiscard(magnitude, magnitude)
    qleft = qdiscard(square, int(feature["lfsig"], 16))
    qright = qdiscard(int(feature["f4sig"], 16),
                      int(feature["rfsig"], 16))
    rows.append({
        "line": "TOP" if sum8 >= 128 else "LOW",
        "act": int(integer["act"]), "nset": nset,
        "pinned": pinned,
        "n": int(integer["nset"]) if pinned else None,
        "half": feature["half"], "sum8": sum8,
        "d": int(feature["d"]), "me2": int(feature["me2"]),
        "g": int(feature["g"]), "low3": low3,
        "dist": distance, "payload": pay2, "rud": int(feature["rud"]),
        "s4": s4, "side": side, "b1": b1, "b2": b2,
        "mreg": mreg, "q4": q4, "sqlow": square_low,
        "rq": frame["rq"], "pcut": frame["pcut"],
        "pdown": frame["pdown"],
        "pbelow": frame["pbelow"],
        "ce8": frame["ce8"], "qsq": qsq,
        "qleft": qleft, "qright": qright,
        "rq_plus_q4": (frame["rq"] + q4) & MASK,
        "rq_minus_q4": (frame["rq"] - q4) & MASK,
        "mplusq": mreg + q4, "mminusq": mreg - q4,
        "r60raw": (low3 * square_low - t4),
        "taildiff": (qleft - qright) & MASK,
    })


families = (
    ("top0", "TOP", 0, -1),
    ("top1", "TOP", 1, -1),
    ("low1", "LOW", 1, 1),
)
coordinates = (
    "mreg", "q4", "sqlow", "rq", "qsq", "qleft", "qright",
    "rq_plus_q4", "rq_minus_q4", "mplusq", "mminusq", "taildiff",
)
cell_specs = (
    ("s4", "side"),
    ("s4", "side", "dist"),
    ("s4", "side", "dist", "low3"),
    ("s4", "side", "dist", "low3", "b1", "b2"),
    ("sum8", "s4", "side", "dist", "low3"),
    ("sum8", "s4", "side", "dist", "low3", "b1", "b2"),
    ("sum8", "d", "me2", "g", "low3"),
)


def evaluate(sample, target, coordinate, fields):
    cells = defaultdict(lambda: [[], []])
    for row in sample:
        positive = row["pinned"] and row["n"] == target
        negative = target not in row["nset"]
        if positive == negative:
            continue
        state = tuple(row[field] for field in fields)
        cells[state][positive].append(row[coordinate])
    counts = Counter()
    conflicts = []
    for state, (negatives, positives) in cells.items():
        counts["positive"] += len(positives)
        counts["negative"] += len(negatives)
        if not positives:
            continue
        if not negatives:
            counts["pure_positive"] += len(positives)
            counts["pure_cells"] += 1
            continue
        counts["mixed_positive"] += len(positives)
        counts["mixed_negative"] += len(negatives)
        counts["mixed_cells"] += 1
        if max(positives) < min(negatives):
            counts["separable_positive"] += len(positives)
            counts["separable_negative"] += len(negatives)
            counts["lt_cells"] += 1
        elif min(positives) > max(negatives):
            counts["separable_positive"] += len(positives)
            counts["separable_negative"] += len(negatives)
            counts["gt_cells"] += 1
        else:
            counts["conflict_positive"] += len(positives)
            counts["conflict_negative"] += len(negatives)
            counts["conflict_cells"] += 1
            conflicts.append((len(positives) + len(negatives), state,
                              min(positives), max(positives),
                              min(negatives), max(negatives)))
    return counts, sorted(conflicts, reverse=True)


print("rows", len(rows))
for family, line, act, target in families:
    direction = 1 if line == "TOP" else 0
    sample = [row for row in rows if row["line"] == line
              and row["act"] == act and row["pcut"] == direction]
    labels = Counter("positive" if row["pinned"] and row["n"] == target
                     else "negative" if target not in row["nset"]
                     else "ambiguous" for row in sample)
    print("\n%s rows=%d labels=%s" % (family, len(sample), dict(labels)))
    ranked = []
    for fields in cell_specs:
        for coordinate in coordinates:
            counts, conflicts = evaluate(sample, target, coordinate, fields)
            ranked.append((counts["conflict_positive"],
                           counts["conflict_cells"],
                           -counts["separable_positive"],
                           coordinate, fields, counts, conflicts))
    for _, _, _, coordinate, fields, counts, conflicts in sorted(ranked)[:24]:
        print("  %-12s cells=%-42s sep+=%3d conflict+=%3d/%3d "
              "mixed=%3d pure+=%3d dirs=%d/%d" % (
                  coordinate, ",".join(fields),
                  counts["separable_positive"],
                  counts["conflict_positive"], counts["positive"],
                  counts["mixed_cells"], counts["pure_positive"],
                  counts["lt_cells"], counts["gt_cells"]))
    best = sorted(ranked)[0]
    print("  largest conflicts for", best[3], best[4])
    for conflict in best[6][:12]:
        print("   ", conflict)
