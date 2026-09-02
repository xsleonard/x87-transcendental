#!/usr/bin/env python3
"""h1017: corrected post-gate segmented-carry mechanism search.

The h930/h932 terminal borrow experiments reconstructed their aligned
subtraction with the initial ``payload`` proposal.  On a declined row the
real terminal instead accumulates ``pay2 == 0``.  Rebuild the subtraction in
that actual frame and test bounded carry-select / redundant-adder predictors.

A candidate is useful only when it has no contradiction in the complete
h975 admissible-set census and no BREAK in h1000's silicon neighborhoods.
The known structural direction bit P[cut] is included in every predicate.
"""

import csv
import gzip
import itertools
import os
import re
import subprocess
from collections import Counter


MODES = ("rn", "rd", "ru", "rz")
BASE = "/tmp/x87-r95-check"
FORCE = {"top0": "/tmp/x87-r96-force1",
         "top1": "/tmp/x87-r96-force2",
         "low1": "/tmp/x87-r96-force3"}
WVRE = re.compile(
    r"(mul|lf|rf|f4|mag|left|right)=(\d+):(-?\d+):([0-9a-f]{32})")


def load_tsv(path):
    with open(path) as src:
        header = next(src).rstrip("\n").split("\t")
        index = {name: offset for offset, name in enumerate(header)}
        return index, [line.rstrip("\n").split("\t") for line in src]


def run_model(binary, mode, operands, dump=False, insn="cos"):
    args = [binary, "--batch", "--f%s-standalone" % insn]
    if mode != "rn":
        args.insert(2, "--rc=" + mode)
    if dump:
        args.append("--dump-internals")
    process = subprocess.run(args, input="\n".join(operands) + "\n",
                             capture_output=True, text=True, check=True)
    output = [":".join(line.split()[1:3]).lower()
              for line in process.stdout.splitlines()]
    if len(output) != len(operands):
        raise RuntimeError("model output count mismatch")
    return output, process.stderr


def parse_dumps(text):
    records, current = [], None
    for line in text.splitlines():
        if line.startswith("DI_IN"):
            if current is not None:
                records.append(current)
            current = {}
            continue
        if current is None:
            continue
        if line.startswith("DI_TC ") and "low3" not in current:
            for token in line.split()[1:]:
                if "=" in token:
                    name, value = token.split("=", 1)
                    current[name] = value
            for match in WVRE.finditer(line):
                name, sign, exponent, significand = match.groups()
                current[name] = (int(sign), int(exponent),
                                 int(significand, 16))
        elif line.startswith("DI_TC2"):
            for token in line.split()[1:]:
                if "=" in token:
                    name, value = token.split("=", 1)
                    current[name] = value
    if current is not None:
        records.append(current)
    return records


def terminal_record(record):
    """Return positive magnitude subtraction S-B in the real pay2 frame."""
    left, right = record["left"], record["right"]
    le, re = left[1], right[1]
    payload = int(record.get("pay2", record["payload"]))
    scale = min(le, re, le - 8 if payload else le)
    signed_left = (-1 if left[0] else 1) * (left[2] << (le - scale))
    signed_right = (-1 if right[0] else 1) * (right[2] << (re - scale))
    signed_payload = 0
    if payload:
        psign = left[0] ^ (payload < 0)
        signed_payload = (-1 if psign else 1) * (
            abs(payload) << (le - 8 - scale))
    if signed_left + signed_payload < 0 <= signed_right:
        s_value = -(signed_left + signed_payload)
        b_value = signed_right
        left_row = -signed_left
        payload_row = -signed_payload
    elif signed_right < 0 <= signed_left + signed_payload:
        s_value = -signed_right
        b_value = signed_left + signed_payload
        left_row = s_value
        payload_row = 0
    else:
        raise ValueError("unexpected terminal sign geometry")
    magnitude = s_value - b_value
    if magnitude <= 0:
        raise ValueError("non-positive terminal magnitude")
    cut = magnitude.bit_length() - 67
    return {"S": s_value, "B": b_value, "M": magnitude,
            "L": left_row, "PAY": payload_row,
            "cut": cut, "scale": scale,
            "pcut": (~(s_value ^ b_value) >> cut) & 1}


def feature_to_record(feature, fix):
    get = lambda name: feature[fix[name]]
    record = {}
    for name in ("left", "right"):
        record[name] = (int(get(name + "sign")), int(get(name + "e2")),
                        int(get(name + "sig"), 16))
    for name in ("payload", "pay2"):
        record[name] = int(get(name)) if get(name) != "-" else 0
    return record


def response_records():
    with gzip.open("h1000_sensitive_neighborhoods.tsv.gz", "rt") as src:
        neighborhood = list(csv.DictReader(src, delimiter="\t"))
    result = {}
    for family, force_binary in FORCE.items():
        selected = [row for row in neighborhood if row["family"] == family]
        operands = [row["op"] for row in selected]
        tags = [set() for _ in selected]
        for mode in MODES:
            candidate, _ = run_model(force_binary, mode, operands)
            for index, (row, value) in enumerate(zip(selected, candidate)):
                baseline, hardware = row["m_" + mode], row["h_" + mode]
                if value == baseline:
                    continue
                if value == hardware and baseline != hardware:
                    tags[index].add("FIX")
                elif baseline == hardware and value != hardware:
                    tags[index].add("BREAK")
                else:
                    tags[index].add("OTHER")
        chosen = [(row, next(iter(tag))) for row, tag in zip(selected, tags)
                  if len(tag) == 1 and tag <= {"FIX", "BREAK"}]
        operands = [row["op"] for row, _ in chosen]
        _, dump = run_model(BASE, "rn", operands, dump=True)
        parsed = parse_dumps(dump)
        if len(parsed) != len(chosen):
            raise RuntimeError("response dump count mismatch")
        result[family] = [
            {"label": label, **terminal_record(record)}
            for (_, label), record in zip(chosen, parsed)]
    return result


def window_carry_dev(row, width, default):
    """Carry into cut from a bounded low window instead of the full field."""
    cut = row["cut"]
    if cut <= 0:
        return 0
    width = min(width, cut)
    low = cut - width
    mask = (1 << width) - 1
    x = (row["S"] >> low) & mask
    y = ((~row["B"]) >> low) & mask
    true_low = ((row["S"] & ((1 << cut) - 1))
                + ((~row["B"]) & ((1 << cut) - 1)) + 1)
    true_carry = true_low >> cut
    if default == "zero":
        cin = 0
    elif default == "one":
        cin = 1
    elif default == "sticky":
        below = low and ((row["S"] ^ ~row["B"]) & ((1 << low) - 1))
        cin = int(bool(below))
    elif default == "exact1":
        if low == 0:
            cin = 1
        else:
            below = ((row["S"] & ((1 << low) - 1))
                     + ((~row["B"]) & ((1 << low) - 1)) + 1)
            cin = below >> low
    else:
        raise ValueError(default)
    predicted = (x + y + cin) >> width
    return int(predicted) - int(true_carry)


def segmented_dev(row, block, depth, phase, default):
    """Bounded carry-select into the physical block below the output cut."""
    cut = row["cut"]
    edge = cut - ((cut - phase) % block)
    low = edge - depth * block
    if edge <= 0 or low <= 0:
        return 0
    mask_edge = (1 << edge) - 1
    true = ((row["S"] & mask_edge)
            + ((~row["B"]) & mask_edge) + 1) >> edge
    width = edge - low
    mask = (1 << width) - 1
    x = (row["S"] >> low) & mask
    y = ((~row["B"]) >> low) & mask
    if default == 0:
        cin = 0
    elif default == 1:
        cin = 1
    else:
        below = ((row["S"] & ((1 << low) - 1))
                 + ((~row["B"]) & ((1 << low) - 1)) + 1)
        cin = below >> low
    predicted = (x + y + cin) >> width
    if edge == cut:
        return int(predicted) - int(true)
    upper_width = cut - edge
    upper_mask = (1 << upper_width) - 1
    ux = (row["S"] >> edge) & upper_mask
    uy = ((~row["B"]) >> edge) & upper_mask
    with_true = (ux + uy + int(true)) >> upper_width
    with_predicted = (ux + uy + int(predicted)) >> upper_width
    return int(with_predicted) - int(with_true)


def redundant_dev(row, width, mode):
    """Resolve a two-row redundant subtraction through a bounded window."""
    mask = (1 << 192) - 1
    x, y = row["S"], (~row["B"]) & mask
    sum_word = x ^ y
    carry_word = ((x & y) << 1) | 1
    cut = row["cut"]
    exact = (sum_word + carry_word) >> cut
    if mode == "drop":
        predicted = (sum_word >> cut) + (carry_word >> cut)
    else:
        width = min(width, cut)
        low = cut - width
        field_mask = (1 << width) - 1
        sw = (sum_word >> low) & field_mask
        cw = (carry_word >> low) & field_mask
        cin = 0
        if mode == "one":
            cin = 1
        elif mode == "sticky" and low:
            cin = int(bool((sum_word | carry_word) & ((1 << low) - 1)))
        predicted = ((sum_word >> cut) + (carry_word >> cut)
                     + ((sw + cw + cin) >> width))
    return int(predicted - exact)


def csa(first, second, third, mask):
    return ((first ^ second ^ third) & mask,
            (((first & second) | (first & third)
              | (second & third)) << 1) & mask)


def terminal_csa_dev(row, order, width, mode):
    """Resolve the real L, payload, ~R, +1 rows through a bounded window."""
    mask = (1 << 192) - 1
    input_rows = (row["L"], row["PAY"], (~row["B"]) & mask, 1)
    sum_word = carry_word = 0
    for index in order:
        sum_word, carry_word = csa(
            sum_word, carry_word, input_rows[index], mask)
    if (sum_word + carry_word) & mask != row["M"] & mask:
        raise AssertionError((order, row["M"], sum_word, carry_word))
    cut = row["cut"]
    exact = (sum_word + carry_word) >> cut
    if mode == "drop":
        predicted = (sum_word >> cut) + (carry_word >> cut)
    else:
        width = min(width, cut)
        low = cut - width
        field_mask = (1 << width) - 1
        sw = (sum_word >> low) & field_mask
        cw = (carry_word >> low) & field_mask
        cin = 0
        if mode == "one":
            cin = 1
        elif mode == "sticky" and low:
            cin = int(bool((sum_word | carry_word) & ((1 << low) - 1)))
        predicted = ((sum_word >> cut) + (carry_word >> cut)
                     + ((sw + cw + cin) >> width))
    return int(predicted - exact)


fix, feature_rows = load_tsv("h970_features.tsv")
nix, nhw_rows = load_tsv("h975_nhw.tsv")
features = {(row[fix["insn"]], row[fix["op"]]): row
            for row in feature_rows}
census = []
for nrow in nhw_rows:
    key = nrow[nix["insn"]], nrow[nix["op"]]
    frame = terminal_record(feature_to_record(features[key], fix))
    census.append({
        "line": "TOP" if int(nrow[nix["sum8"]]) >= 128 else "LOW",
        "act": int(nrow[nix["act"]]),
        "nset": {int(item) for item in nrow[nix["nset"]].split(",")},
        "pinned": nrow[nix["pinned"]] == "1",
        "half": features[key][fix["half"]],
        **frame,
    })
responses = response_records()

blind_path = "/tmp/h1022_attributed.tsv"
if os.path.exists(blind_path):
    with open(blind_path) as src:
        blind_rows = list(csv.DictReader(src, delimiter="\t"))
    arm_family = {"res": "top1", "top": "top0", "low": "low1"}
    unique_blind = sorted({(arm_family[row["arm"]], row["insn"], row["op"])
                           for row in blind_rows if row["arm"] in arm_family})
    for family in FORCE:
        for insn in ("cos", "sin"):
            operands = [op for row_family, row_insn, op in unique_blind
                        if row_family == family and row_insn == insn]
            if not operands:
                continue
            _, dump = run_model(BASE, "rn", operands, dump=True, insn=insn)
            parsed = parse_dumps(dump)
            responses[family].extend(
                {"label": "BREAK", **terminal_record(record)}
                for record in parsed)


mechanisms = []
for width in range(1, 65):
    for default in ("zero", "one", "sticky"):
        mechanisms.append(("window w%d %s" % (width, default),
                           lambda row, w=width, d=default:
                           window_carry_dev(row, w, d)))
for block in range(2, 33):
    for depth in range(1, 17):
        for phase in range(block):
            for default in (0, 1):
                mechanisms.append((
                    "segment b%d d%d p%d c%d" %
                    (block, depth, phase, default),
                    lambda row, b=block, d=depth, p=phase, c=default:
                    segmented_dev(row, b, d, p, c)))
for width in range(1, 65):
    for mode in ("drop", "zero", "one", "sticky"):
        mechanisms.append(("redundant w%d %s" % (width, mode),
                           lambda row, w=width, m=mode:
                           redundant_dev(row, w, m)))
for order in itertools.permutations(range(4)):
    for width in range(1, 65):
        for mode in ("drop", "zero", "one", "sticky"):
            mechanisms.append((
                "terminal-csa %s w%d %s" %
                ("".join(map(str, order)), width, mode),
                lambda row, o=order, w=width, m=mode:
                terminal_csa_dev(row, o, w, m)))


families = (("top0", "TOP", 0, -1, 1, 1),
            ("top1", "TOP", 1, -1, 1, 1),
            ("low1", "LOW", 1, 1, -1, 0))
print("census", len(census), "mechanisms", len(mechanisms))
for family, line, act, target, magnitude_target, direction_bit in families:
    sample = [row for row in census
              if row["line"] == line and row["act"] == act]
    bad = [row for row in sample if target not in row["nset"]]
    fit = [row for row in sample if row["pinned"]
           and row["nset"] == {target} and row["half"] == "FIT"]
    hol = [row for row in sample if row["pinned"]
           and row["nset"] == {target} and row["half"] == "HOL"]
    rfix = [row for row in responses[family] if row["label"] == "FIX"]
    rbreak = [row for row in responses[family] if row["label"] == "BREAK"]
    ranked, near = [], []
    for name, mechanism in mechanisms:
        choose = lambda row, fn=mechanism: (
            row["pcut"] == direction_bit
            and fn(row) == magnitude_target)
        nb = sum(choose(row) for row in bad)
        rb = sum(choose(row) for row in rbreak)
        nf = sum(choose(row) for row in fit)
        nh = sum(choose(row) for row in hol)
        nr = sum(choose(row) for row in rfix)
        fires = sum(choose(row) for row in sample)
        row = (nr, nf + nh, min(nf, nh), fires, name,
               nf, nh, nb, rb)
        if not nb and not rb and nr and nf and nh:
            ranked.append(row)
        elif nr and (nb + rb) <= 4:
            near.append((-(nb + rb),) + row)
    print("\n", family, "joint-safe mechanisms:")
    for row in sorted(ranked, reverse=True)[:80]:
        nr, total, minimum, fires, name, nf, nh, nb, rb = row
        print("  %s response=%d pinned=%d FIT/HOL=%d/%d fires=%d" %
              (name, nr, total, nf, nh, fires))
    if not ranked:
        print("  none")
    print(" ", family, "closest response-catching mechanisms:")
    for row in sorted(near, reverse=True)[:30]:
        negbad, nr, total, minimum, fires, name, nf, nh, nb, rb = row
        print("  %s response=%d pinned=%d FIT/HOL=%d/%d fires=%d "
              "census_bad=%d response_break=%d" %
              (name, nr, total, nf, nh, fires, nb, rb))
