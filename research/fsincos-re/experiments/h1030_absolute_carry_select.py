#!/usr/bin/env python3
"""h1030: absolute-exponent carry-select search for the R95 residue.

h1017 tested bounded terminal carries with block boundaries anchored to the
integer representation used by the reconstruction.  The already-solved
standalone-FCOS carry-select law instead keys its block phase by the absolute
exponent of the retained cut.  Search that missing geometry against h975's
complete admissible integer sets, keeping the FIT/HOL split frozen.

The predicted integer is the carry deviation of a bounded lower window from
the exact two's-complement subtraction.  A useful arm must have no census
contradictions and must cover pinned positives in both banks.
"""

import sys
from collections import Counter


def load_tsv(path):
    with open(path) as source:
        header = next(source).rstrip("\n").split("\t")
        index = {name: offset for offset, name in enumerate(header)}
        return index, [line.rstrip("\n").split("\t") for line in source]


def terminal_frame(feature, fix):
    get = lambda name: feature[fix[name]]
    left = int(get("leftsig"), 16)
    right = int(get("rightsig"), 16)
    left_exponent = int(get("lefte2"))
    right_exponent = int(get("righte2"))
    payload = int(get("pay2")) if get("pay2") != "-" else 0
    scale = min(left_exponent, right_exponent,
                left_exponent - 8 if payload else left_exponent)
    signed_left = (-1 if int(get("leftsign")) else 1) * (
        left << (left_exponent - scale))
    signed_right = (-1 if int(get("rightsign")) else 1) * (
        right << (right_exponent - scale))
    signed_payload = 0
    if payload:
        payload_sign = int(get("leftsign")) ^ (payload < 0)
        signed_payload = (-1 if payload_sign else 1) * (
            abs(payload) << (left_exponent - 8 - scale))
    if signed_left + signed_payload < 0 <= signed_right:
        minuend = -(signed_left + signed_payload)
        subtrahend = signed_right
    elif signed_right < 0 <= signed_left + signed_payload:
        minuend = -signed_right
        subtrahend = signed_left + signed_payload
    else:
        raise ValueError("unexpected terminal sign geometry")
    magnitude = minuend - subtrahend
    if magnitude <= 0:
        raise ValueError("non-positive terminal magnitude")
    cut = magnitude.bit_length() - 67
    return {
        "S": minuend, "B": subtrahend, "M": magnitude,
        "cut": cut, "scale": scale, "ce": scale + cut,
        "pcut": (~(minuend ^ subtrahend) >> cut) & 1,
    }


def carry_into(row, edge):
    """Exact carry into edge for S + ~B + 1."""
    if edge <= 0:
        return 1
    mask = (1 << edge) - 1
    return ((row["S"] & mask) + ((~row["B"]) & mask) + 1) >> edge


def bounded_carry(row, lower, edge, default):
    """Carry into edge seen through [lower, edge) and a guessed carry-in."""
    if lower <= 0:
        return carry_into(row, edge)
    width = edge - lower
    if width <= 0:
        return default
    mask = (1 << width) - 1
    first = (row["S"] >> lower) & mask
    second = ((~row["B"]) >> lower) & mask
    return (first + second + default) >> width


def propagate_deviation(row, edge, true_carry, predicted_carry):
    """Propagate a carry-selection difference from edge to the output cut."""
    cut = row["cut"]
    if true_carry == predicted_carry:
        return 0
    if edge == cut:
        return int(predicted_carry) - int(true_carry)
    if edge > cut:
        raise ValueError("edge above output cut")
    width = cut - edge
    mask = (1 << width) - 1
    first = (row["S"] >> edge) & mask
    second = ((~row["B"]) >> edge) & mask
    exact = (first + second + int(true_carry)) >> width
    predicted = (first + second + int(predicted_carry)) >> width
    return int(predicted) - int(exact)


def uniform_deviation(row, block, depth, phase, default):
    """Uniform blocks whose edges satisfy scale+edge == phase (mod block)."""
    cut = row["cut"]
    edge = cut - ((row["scale"] + cut - phase) % block)
    if edge <= 0:
        return 0
    lower = edge - depth * block
    true_carry = carry_into(row, edge)
    predicted_carry = bounded_carry(row, lower, edge, default)
    return propagate_deviation(row, edge, true_carry, predicted_carry)


def scheduled_deviation(row, widths, starts, period, anchor, blocks_back,
                        default):
    """Nonuniform blocks on the absolute-exponent axis."""
    cut_exponent = row["ce"]
    relative = cut_exponent - anchor
    cycle, offset = divmod(relative, period)
    start_index = max(index for index, start in enumerate(starts)
                      if start <= offset)
    edge_exponent = anchor + cycle * period + starts[start_index]
    edge_index = row["cut"] + edge_exponent - cut_exponent
    lower_exponent = edge_exponent
    for step in range(blocks_back):
        lower_exponent -= widths[(start_index - 1 - step) % len(widths)]
    lower_index = row["cut"] + lower_exponent - cut_exponent
    if edge_index <= 0:
        return 0
    true_carry = carry_into(row, edge_index)
    predicted_carry = bounded_carry(
        row, lower_index, edge_index, default)
    return propagate_deviation(
        row, edge_index, true_carry, predicted_carry)


fix, feature_rows = load_tsv("h970_features.tsv")
nix, integer_rows = load_tsv("h975_nhw.tsv")
features = {(row[fix["insn"]], row[fix["op"]]): row
            for row in feature_rows}

rows = []
for integer_row in integer_rows:
    key = integer_row[nix["insn"]], integer_row[nix["op"]]
    feature = features[key]
    sum8 = int(integer_row[nix["sum8"]])
    nset = {int(value) for value in
            integer_row[nix["nset"]].split(",")}
    rows.append({
        "key": key,
        "line": "TOP" if sum8 >= 128 else "LOW",
        "act": int(integer_row[nix["act"]]),
        "half": feature[fix["half"]],
        "pinned": integer_row[nix["pinned"]] == "1",
        "nset": nset,
        **terminal_frame(feature, fix),
    })


families = (
    ("top0", "TOP", 0, -1, 1),
    ("top1", "TOP", 1, -1, 1),
    ("low1", "LOW", 1, 1, 0),
)


def evaluate(name, mechanism, sample, target, direction):
    fired = []
    for row in sample:
        # The exact P[cut] polarity is independently pinned on all positives.
        if row["pcut"] == direction and mechanism(row) == target:
            fired.append(row)
    contradictions = sum(target not in row["nset"] for row in fired)
    fit = sum(row["pinned"] and row["nset"] == {target}
              and row["half"] == "FIT" for row in fired)
    holdout = sum(row["pinned"] and row["nset"] == {target}
                  and row["half"] == "HOL" for row in fired)
    unpinned = sum(not row["pinned"] and target in row["nset"]
                   for row in fired)
    return (contradictions, -(fit + holdout), -min(fit, holdout),
            -unpinned, len(fired), name, fit, holdout, unpinned)


mode = sys.argv[1] if len(sys.argv) > 1 else "all"
mechanisms = []
if mode in ("all", "uniform"):
    for block in range(2, 33):
        for depth in range(1, 17):
            for phase in range(block):
                for default in (0, 1):
                    name = "uniform b%d d%d absphase%d c%d" % (
                        block, depth, phase, default)
                    mechanisms.append((
                        name,
                        lambda row, b=block, d=depth, p=phase, c=default:
                        uniform_deviation(row, b, d, p, c)))

# Published grouping examples are architecture priors only.  Include the
# 56-bit [5,6,8,8,7,8,8,6] carry-select schedule and rotations/reversals,
# plus simple alternating schedules, without attributing any one to Skylake.
schedules = {
    (5, 6, 8, 8, 7, 8, 8, 6),
    (6, 8, 8, 7, 8, 8, 6, 5),
    (6, 8, 8, 7, 8, 8, 6),
    (8, 7), (7, 8), (8, 6), (6, 8), (8, 5), (5, 8),
}
if mode in ("all", "schedule"):
    for widths in sorted(schedules):
        period = sum(widths)
        starts = [0]
        for width in widths[:-1]:
            starts.append(starts[-1] + width)
        starts = tuple(starts)
        for anchor in range(period):
            for blocks_back in range(1, min(17, len(widths) * 2 + 1)):
                for default in (0, 1):
                    label = "schedule %s anchor%d back%d c%d" % (
                        "/".join(map(str, widths)), anchor,
                        blocks_back, default)
                    mechanisms.append((
                        label,
                        lambda row, w=widths, s=starts, p=period,
                        a=anchor, b=blocks_back, c=default:
                        scheduled_deviation(row, w, s, p, a, b, c)))


print("rows", len(rows), "mechanisms", len(mechanisms))
for family, line, act, target, direction in families:
    sample = [row for row in rows
              if row["line"] == line and row["act"] == act]
    positives = Counter(
        row["half"] for row in sample
        if row["pinned"] and row["nset"] == {target})
    scores = [evaluate(name, mechanism, sample, target, direction)
              for name, mechanism in mechanisms]
    safe = [score for score in scores
            if score[0] == 0 and score[6] and score[7]]
    print("\n%s sample=%d positives=%s" %
          (family, len(sample), dict(positives)))
    print("  zero-contradiction mechanisms", len(safe))
    for score in sorted(safe, key=lambda item: item[1:])[:40]:
        bad, negative_total, negative_minimum, negative_unpinned, fires, \
            name, fit, holdout, unpinned = score
        print("    %-48s pin=%d FIT/HOL=%d/%d unpinned=%d fires=%d" %
              (name, fit + holdout, fit, holdout, unpinned, fires))
    print("  best by contradictions then pinned coverage")
    for score in sorted(scores, key=lambda item: item[:5])[:30]:
        bad, negative_total, negative_minimum, negative_unpinned, fires, \
            name, fit, holdout, unpinned = score
        print("    %-48s bad=%d pin=%d FIT/HOL=%d/%d unpinned=%d fires=%d" %
              (name, bad, fit + holdout, fit, holdout, unpinned, fires))
    print("  best coverage allowing contradictions")
    for score in sorted(scores, key=lambda item: (item[1], item[0],
                                                   item[2:5]))[:20]:
        bad, negative_total, negative_minimum, negative_unpinned, fires, \
            name, fit, holdout, unpinned = score
        print("    %-48s bad=%d pin=%d FIT/HOL=%d/%d unpinned=%d fires=%d" %
              (name, bad, fit + holdout, fit, holdout, unpinned, fires))
