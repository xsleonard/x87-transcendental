#!/usr/bin/env python3
"""h1001: feature the h1000 perturbation-response selector map.

For each residual family, compare R95 with its absolute-one-quantum force
probe, retain only operands on which the candidate is architecturally
visible, and label those operands from fresh silicon as FIX or BREAK.  Dump
the normal R95 intermediates for that small response set and search for
closed Boolean invariants shared by every seed's FIX but absent from nearby
BREAK counterexamples.
"""

import csv
import gzip
import re
import subprocess
from collections import Counter


DATA = "h1000_sensitive_neighborhoods.tsv.gz"
BASE = "/tmp/x87-r95-check"
FORCE = {"top0": "/tmp/x87-r96-force1",
         "top1": "/tmp/x87-r96-force2",
         "low1": "/tmp/x87-r96-force3"}
MODES = ("rn", "rd", "ru", "rz")
WVRE = re.compile(
    r"(mul|lf|rf|f4|mag|left|right)=(\d+):(-?\d+):([0-9a-f]{32})")


def run_model(binary, mode, operands, dump=False):
    args = [binary, "--batch", "--fcos-standalone"]
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
        elif line.startswith("DI_ACC"):
            current["d60"] = int(line.split("d60=")[1], 16)
        elif line.startswith("DI_B81"):
            for token in line.split()[1:]:
                if "=" in token:
                    name, value = token.split("=", 1)
                    if name not in ("L", "R", "tc"):
                        current["b81_" + name] = value
    if current is not None:
        records.append(current)
    return records


def normalized_discard(bits, numerics, prefix, product, kept=67,
                       width=64):
    shift = product.bit_length() - kept
    discard = product & ((1 << shift) - 1) if shift > 0 else 0
    numerics[prefix + "_q"] = ((discard << 64) >> shift) \
        if shift > 0 else 0
    for offset in range(width):
        position = shift - 1 - offset
        bits["%s_q%02d" % (prefix, offset)] = \
            (discard >> position) & 1 if position >= 0 else 0


def feature_vector(record):
    bits, numerics = {}, {}
    left, right = record["left"], record["right"]
    le, re = left[1], right[1]
    # DI_TC reports the initial payload, while DI_TC2/pay2 is the payload
    # after the micro-rules and is the value actually accumulated.
    payload = int(record.get("pay2", record["payload"]))
    scale = min(le, re, le - 8 if payload else le)
    signed_left = (-1 if left[0] else 1) * (left[2] << (le - scale))
    signed_payload = 0
    if payload:
        payload_sign = left[0] ^ (payload < 0)
        signed_payload = (-1 if payload_sign else 1) * (
            abs(payload) << (le - 8 - scale))
    signed_right = (-1 if right[0] else 1) * (
        right[2] << (re - scale))
    total = signed_left + signed_payload + signed_right
    magnitude = abs(total)
    cut = magnitude.bit_length() - 67
    initial_payload = int(record["payload"])
    pre_scale = min(le, re, le - 8 if initial_payload else le)
    pre_total = ((-1 if left[0] else 1)
                 * (left[2] << (le - pre_scale))
                 + (-1 if right[0] else 1)
                 * (right[2] << (re - pre_scale)))
    if initial_payload:
        pre_payload_sign = left[0] ^ (initial_payload < 0)
        pre_total += (-1 if pre_payload_sign else 1) * (
            abs(initial_payload) << (le - 8 - pre_scale))
    pre_magnitude = abs(pre_total)
    pre_cut = pre_magnitude.bit_length() - 67
    if signed_left + signed_payload < 0 and signed_right >= 0:
        s_value, b_value = -(signed_left + signed_payload), signed_right
    else:
        s_value, b_value = -signed_right, signed_left + signed_payload
    assert s_value - b_value == magnitude
    numerics.update(cut=cut, residue=(magnitude & ((1 << cut) - 1)),
                    sum8=((magnitude >> cut) & 0xFF)
                    + int(record["low3"]),
                    terminal_payload=payload,
                    pre_cut=pre_cut,
                    pre_residue=(pre_magnitude
                                 & ((1 << pre_cut) - 1)),
                    low3=int(record["low3"]),
                    distance=int(record["dist"]),
                    rsh=int(record["rsh"]), rud=int(record["rud"]),
                    payload=payload)

    for offset in range(-24, 49):
        position = cut + offset
        for prefix, value in (("S", s_value), ("B", b_value),
                              ("M", magnitude),
                              ("P", ~(s_value ^ b_value)),
                              ("G", ~s_value & b_value)):
            bits["%s%+03d" % (prefix, offset)] = \
                (value >> position) & 1 if position >= 0 else 0

    mag = record["mag"][2]
    sq = record["mul"][2]
    fourth = record["f4"][2]
    odd = record["lf"][2]
    even = record["rf"][2]
    for prefix, product in (("sq", mag * mag), ("f4", sq * sq),
                            ("left", sq * odd),
                            ("right", fourth * even)):
        normalized_discard(bits, numerics, prefix, product)
    for prefix, value in (("mag", mag), ("sqk", sq),
                          ("f4k", fourth), ("odd", odd),
                          ("even", even)):
        for position in range(67):
            bits["%s_b%02d" % (prefix, position)] = \
                (value >> position) & 1

    # Exact terminal products in their own cut-relative frame.
    pl, pr = sq * odd, fourth * even
    ple = record["mul"][1] + record["lf"][1]
    pre = record["f4"][1] + record["rf"][1]
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

    # Small scalar fields as exact equality literals and ordinary bits.
    scalar_names = ("low3", "dist", "rsh", "rud", "payload", "ud",
                    "u5d", "pay2", "laneb", "diff", "lane2", "lane3")
    for name in scalar_names:
        if name not in record:
            continue
        text = record[name]
        try:
            value = int(text, 16) if name in ("laneb", "lane2", "lane3") \
                else int(text)
        except ValueError:
            continue
        numerics[name] = value
        for position in range(8):
            bits["%s_b%d" % (name, position)] = (value >> position) & 1
    bits["d60_nonzero"] = int(record.get("d60", 0) != 0)
    for position in range(60):
        bits["d60_b%02d" % position] = \
            (record.get("d60", 0) >> position) & 1
    return bits, numerics


with gzip.open(DATA, "rt") as src:
    rows = list(csv.DictReader(src, delimiter="\t"))


for family, force_binary in FORCE.items():
    selected = [row for row in rows if row["family"] == family]
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
    response = [(row, next(iter(tag))) for row, tag in zip(selected, tags)
                if len(tag) == 1 and tag <= {"FIX", "BREAK"}]
    response_operands = [row["op"] for row, _ in response]
    _, dump_text = run_model(BASE, "rn", response_operands, dump=True)
    dumps = parse_dumps(dump_text)
    if len(dumps) != len(response):
        raise RuntimeError("dump count mismatch for " + family)
    featured = []
    for (row, label), dump in zip(response, dumps):
        bits, numerics = feature_vector(dump)
        featured.append((row, label, bits, numerics))

    positives = [item for item in featured if item[1] == "FIX"]
    negatives = [item for item in featured if item[1] == "BREAK"]
    print("\n==", family, "response map ==")
    print("FIX", len(positives), "BREAK", len(negatives),
          "seeds", len({item[0]["seed"] for item in positives}))
    print("positive deltas:", Counter(int(item[0]["delta"])
                                      for item in positives))
    print("cut propagate:",
          Counter((item[1], item[2]["P+00"]) for item in featured))
    if family == "top0":
        print("Pcut && !M-5 && f4q56:", Counter(
            (item[1], item[2]["P+00"] == 1
             and item[2]["M-05"] == 0
             and item[2]["f4_q56"] == 1)
            for item in featured))
    if family == "top1":
        print("M[cut-12]:",
              Counter((item[1], item[2]["M-12"]) for item in featured))
        print("M[cut-13]:",
              Counter((item[1], item[2]["M-13"]) for item in featured))
        print("M[cut-14]:",
              Counter((item[1], item[2]["M-14"]) for item in featured))
        print("dist.bit2 && right_q19:", Counter(
            (item[1], item[2]["dist_b2"] == 1
             and item[2]["right_q19"] == 1)
            for item in featured))
    if family == "top1":
        def residue_1024(item):
            numerics = item[3]
            cut = numerics["pre_cut"]
            return (cut > 0 and numerics["sum8"] >= 0xF0
                    and numerics["pre_residue"] * 1024
                    > 1023 * (1 << cut))

        print("top pre-gate residue > 1023/1024:",
              Counter((item[1], residue_1024(item))
                      for item in featured))
        def residue_2045(item):
            numerics = item[3]
            cut = numerics["pre_cut"]
            return (cut > 0 and numerics["sum8"] >= 0xF0
                    and numerics["pre_residue"] * 2048
                    > 2045 * (1 << cut))

        print("top pre-gate residue > 2045/2048:",
              Counter((item[1], residue_2045(item))
                      for item in featured))
        def post_residue_2047(item):
            numerics = item[3]
            cut = numerics["cut"]
            return (cut > 0 and numerics["sum8"] >= 0xF0
                    and numerics["residue"] * 2048
                    > 2047 * (1 << cut))

        print("top post-gate residue > 2047/2048:",
              Counter((item[1], post_residue_2047(item))
                      for item in featured))
        def wrapped_residue(item):
            numerics = item[3]
            post_cut, pre_cut = numerics["cut"], numerics["pre_cut"]
            if post_cut <= 0 or pre_cut <= 0 or numerics["sum8"] < 0xF0:
                return False
            post_q = (numerics["residue"] << 66) >> post_cut
            pre_q = (numerics["pre_residue"] << 66) >> pre_cut
            word = (8 * post_q + pre_q) & ((1 << 66) - 1)
            return word * 2048 > 2023 * (1 << 66)

        print("(8*post+pre) mod 1 > 2023/2048:",
              Counter((item[1], wrapped_residue(item))
                      for item in featured))
        def wrapped_family(item, form):
            numerics = item[3]
            post_cut, pre_cut = numerics["cut"], numerics["pre_cut"]
            if post_cut <= 0 or pre_cut <= 0 or numerics["sum8"] < 0xF0:
                return False
            unit = 1 << 66
            mask = unit - 1
            post_q = (numerics["residue"] << 66) >> post_cut
            pre_q = (numerics["pre_residue"] << 66) >> pre_cut
            if form == "w7":
                return ((7 * post_q + pre_q) & mask) * 256 > 253 * unit
            if form == "dpost":
                return ((numerics["dist"] * post_q + pre_q) & mask) \
                    * 512 > 505 * unit
            if form == "dpre_minus":
                return ((numerics["dist"] * pre_q - pre_q) & mask) \
                    * 2048 > 2015 * unit
            if form == "dpre_plus":
                return ((numerics["dist"] * pre_q + pre_q) & mask) \
                    * 2048 > 2009 * unit
            word = ((numerics["payload"] * post_q - post_q) & mask)
            return word * 2048 < 3 * unit

        for form in ("w7", "dpost", "dpre_minus", "dpre_plus",
                     "payload_post_minus"):
            print("wrapped", form + ":", Counter(
                (item[1], wrapped_family(item, form))
                for item in featured))
        def six_pre_bit55(item):
            numerics = item[3]
            cut = numerics["pre_cut"]
            if cut <= 0 or numerics["sum8"] < 0xF0:
                return False
            pre_q = (numerics["pre_residue"] << 66) >> cut
            return (((6 * pre_q) & ((1 << 66) - 1)) >> 55) & 1

        print("bit55((6*pre) mod 1):", Counter(
            (item[1], bool(six_pre_bit55(item))) for item in featured))

    # A literal is eligible only if every independent positive seed has the
    # same value.  Rank literal conjunctions by surviving local negatives.
    names = sorted(set.intersection(*(set(item[2]) for item in featured)))
    literals = []
    full_negative_mask = (1 << len(negatives)) - 1
    for name in names:
        values = {item[2][name] for item in positives}
        if len(values) != 1:
            continue
        wanted = next(iter(values))
        mask = 0
        for index, item in enumerate(negatives):
            if item[2][name] == wanted:
                mask |= 1 << index
        if mask != full_negative_mask:
            literals.append((mask, name, wanted))
    literals.sort(key=lambda item: (bin(item[0]).count("1"), item[1]))
    print("best common literals:")
    for mask, name, wanted in literals[:20]:
        print("  %s=%d keeps %d/%d BREAK" %
              (name, wanted, bin(mask).count("1"), len(negatives)))

    pairs = []
    for first in range(len(literals)):
        for second in range(first + 1, len(literals)):
            mask = literals[first][0] & literals[second][0]
            pairs.append((bin(mask).count("1"), first, second, mask))
    pairs.sort()
    print("best two-literal conjunctions:")
    for count, first, second, _ in pairs[:20]:
        a, b = literals[first], literals[second]
        print("  %s=%d && %s=%d keeps %d/%d BREAK" %
              (a[1], a[2], b[1], b[2], count, len(negatives)))

    triples = []
    for _, first, second, pair_mask in pairs[:200]:
        for third, literal in enumerate(literals):
            if third in (first, second):
                continue
            count = bin(pair_mask & literal[0]).count("1")
            triples.append((count, first, second, third))
    triples.sort()
    print("best three-literal conjunctions:")
    for count, first, second, third in triples[:20]:
        values = [literals[index] for index in (first, second, third)]
        print("  %s keeps %d/%d BREAK" %
              (" && ".join("%s=%d" % (value[1], value[2])
                            for value in values), count, len(negatives)))

    print("numeric positive envelopes:")
    numeric_names = sorted(set.intersection(
        *(set(item[3]) for item in featured)))
    envelopes = []
    for name in numeric_names:
        lo = min(item[3][name] for item in positives)
        hi = max(item[3][name] for item in positives)
        inside = sum(lo <= item[3][name] <= hi for item in negatives)
        envelopes.append((inside, name, lo, hi))
    for inside, name, lo, hi in sorted(envelopes)[:20]:
        print("  %-12s [%d,%d] keeps %d/%d BREAK" %
              (name, lo, hi, inside, len(negatives)))
