#!/usr/bin/env python3
"""h1016: nonlinear residue-ring arms constrained by census + h1000."""

import csv
import gzip
import os
import re
import subprocess
from collections import Counter


SCALE = 66
ONE = 1 << SCALE
MASK = ONE - 1
MODES = ("rn", "rd", "ru", "rz")
BASE = "/tmp/x87-r95-check"
FORCE = {"top0": "/tmp/x87-r96-force1",
         "top1": "/tmp/x87-r96-force2",
         "low1": "/tmp/x87-r96-force3"}
WVRE = re.compile(
    r"(mul|lf|rf|f4|mag|left|right)=(\d+):(-?\d+):([0-9a-f]{32})")


def popcount(value):
    return bin(value).count("1")


def load_tsv(path):
    with open(path) as src:
        header = next(src).rstrip("\n").split("\t")
        index = {name: offset for offset, name in enumerate(header)}
        return index, [line.rstrip("\n").split("\t") for line in src]


def qdiscard(a, b):
    product = a * b
    shift = product.bit_length() - 67
    return (((product & ((1 << shift) - 1)) << SCALE) >> shift
            if shift > 0 else 0)


def terminal_q(record, payload):
    le, re = record["left"][1], record["right"][1]
    left, right = record["left"][2], record["right"][2]
    ls, rs = record["left"][0], record["right"][0]
    scale = min(le, re, le - 8 if payload else le)
    value = ((-1 if ls else 1) * (left << (le - scale))
             + (-1 if rs else 1) * (right << (re - scale)))
    if payload:
        psign = ls ^ (payload < 0)
        value += (-1 if psign else 1) * (
            abs(payload) << (le - 8 - scale))
    magnitude = abs(value)
    cut = magnitude.bit_length() - 67
    residue = magnitude & ((1 << cut) - 1) if cut > 0 else 0
    return (residue << SCALE) >> cut if cut > 0 else 0


def arithmetic_record(record):
    initial_payload = int(record["payload"])
    final_payload = int(record.get("pay2", initial_payload))
    mag = record["mag"][2]
    sq = record["mul"][2]
    fourth = record["f4"][2]
    odd = record["lf"][2]
    even = record["rf"][2]
    full4 = sq * sq
    s4 = full4.bit_length() - 67
    t4 = full4 & ((1 << s4) - 1)
    sqlow = sq - ONE
    mreg = int(record["low3"]) * sqlow - t4
    return {
        "q": {
            "post": terminal_q(record, final_payload),
            "pre": terminal_q(record, initial_payload),
            "sq": qdiscard(mag, mag),
            "f4": qdiscard(sq, sq),
            "left": qdiscard(sq, odd),
            "right": qdiscard(fourth, even),
            # Exact R60 coordinates.  `f4` above is the normalized discard;
            # these retain the raw s4-width residue and signed nonlinear
            # margin in the 66-bit ring used by the proven tie law.
            "sqlow": sqlow & MASK,
            "t4raw": t4 & MASK,
            "r60m": mreg & MASK,
        },
        "s": {
            "low3": int(record["low3"]),
            "dist": int(record["dist"]),
            "payload": initial_payload,
            "pay2": final_payload,
            "ud": int(record["ud"]),
            "u5d": int(record["u5d"]),
            "rud": int(record["rud"]),
        },
    }


def feature_to_record(feature, fix):
    get = lambda name: feature[fix[name]]
    record = {}
    for name in ("mag", "mul", "f4", "lf", "rf", "left", "right"):
        prefix = {"mag": "mag", "mul": "mul", "f4": "f4",
                  "lf": "lf", "rf": "rf",
                  "left": "left", "right": "right"}[name]
        record[name] = (int(get(prefix + "sign"))
                        if prefix in ("left", "right") else 0,
                        int(get(prefix + "e2")),
                        int(get(prefix + "sig"), 16))
    for name in ("payload", "pay2", "low3", "dist", "ud", "u5d", "rud"):
        record[name] = int(get(name)) if get(name) != "-" else 0
    return record


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


def descriptors():
    bases = ("f4", "left", "post", "pre", "right", "r60m", "sq",
             "sqlow", "t4raw")
    for base in bases:
        yield ("base", base)
    for first_index, first in enumerate(bases):
        for second in bases[first_index:]:
            yield ("product", "ring", first, second)
            yield ("product", "fixed", first, second)
    multiplier_names = tuple(map(str, (2, 3, 4, 5, 6, 7, 8,
                                       16, 32, 64))) + (
        "dist", "low3", "pay2", "payload", "rud", "u5d", "ud")
    for aname in bases:
        for bname in bases:
            for multiplier in multiplier_names:
                for operation in ("+", "-"):
                    yield ("word", multiplier, aname, operation, bname)


def value(record, descriptor):
    if descriptor[0] == "base":
        return record["q"][descriptor[1]]
    if descriptor[0] == "product":
        _, kind, first, second = descriptor
        product = record["q"][first] * record["q"][second]
        return product & MASK if kind == "ring" else (product >> SCALE) & MASK
    _, multiplier, aname, operation, bname = descriptor
    m = (int(multiplier) if multiplier[0].isdigit()
         else record["s"][multiplier])
    a, b = record["q"][aname], record["q"][bname]
    return (m * a + b if operation == "+" else m * a - b) & MASK


def name(descriptor):
    if descriptor[0] == "base":
        return descriptor[1]
    if descriptor[0] == "product":
        return "%s(%s*%s)" % descriptor[1:]
    return "%s*%s%s%s" % descriptor[1:]


# Complete census constraints.
fix, feature_rows = load_tsv("h970_features.tsv")
nix, nhw_rows = load_tsv("h975_nhw.tsv")
features = {(row[fix["insn"]], row[fix["op"]]): row
            for row in feature_rows}
census = []
for nrow in nhw_rows:
    key = nrow[nix["insn"]], nrow[nix["op"]]
    feature = features[key]
    census.append({
        "line": "TOP" if int(nrow[nix["sum8"]]) >= 128 else "LOW",
        "act": int(nrow[nix["act"]]),
        "nset": {int(item) for item in nrow[nix["nset"]].split(",")},
        "pinned": nrow[nix["pinned"]] == "1",
        "half": feature[fix["half"]],
        **arithmetic_record(feature_to_record(feature, fix)),
    })

# Fresh perturbation response constraints.
with gzip.open("h1000_sensitive_neighborhoods.tsv.gz", "rt") as src:
    neighborhood = list(csv.DictReader(src, delimiter="\t"))
responses = {}
for family, force_binary in FORCE.items():
    selected = [row for row in neighborhood if row["family"] == family]
    operands = [row["op"] for row in selected]
    tags = [set() for _ in selected]
    for mode in MODES:
        candidate, _ = run_model(force_binary, mode, operands)
        for index, (row, result) in enumerate(zip(selected, candidate)):
            baseline, hardware = row["m_" + mode], row["h_" + mode]
            if result == baseline:
                continue
            if result == hardware and baseline != hardware:
                tags[index].add("FIX")
            elif baseline == hardware and result != hardware:
                tags[index].add("BREAK")
            else:
                tags[index].add("OTHER")
    chosen = [(row, next(iter(tag))) for row, tag in zip(selected, tags)
              if len(tag) == 1 and tag <= {"FIX", "BREAK"}]
    operands = [row["op"] for row, _ in chosen]
    _, dump = run_model(BASE, "rn", operands, dump=True)
    parsed = parse_dumps(dump)
    responses[family] = [
        {"label": label, "op": row["op"], "seed": row["seed"],
         **arithmetic_record(record)}
        for ((row, label), record) in zip(chosen, parsed)
    ]

# Fresh h1022 annulus negatives are outside both discovery corpora.  Fold
# them into the response BREAK bank when the attribution artifact is present,
# so every subsequent safe arm is constrained by the first true blind test.
blind_path = "/tmp/h1022_attributed.tsv"
if os.path.exists(blind_path):
    with open(blind_path) as src:
        blind_rows = list(csv.DictReader(src, delimiter="\t"))
    arm_family = {"res": "top1", "top": "top0", "low": "low1"}
    unique_blind = sorted({(arm_family[row["arm"]], row["insn"], row["op"])
                           for row in blind_rows if row["arm"] in arm_family})
    for family in FORCE:
        for insn in ("cos", "sin"):
            selected = [(op, insn) for row_family, row_insn, op in unique_blind
                        if row_family == family and row_insn == insn]
            if not selected:
                continue
            operands = [op for op, _ in selected]
            _, dump = run_model(BASE, "rn", operands, dump=True, insn=insn)
            parsed = parse_dumps(dump)
            responses[family].extend(
                {"label": "BREAK", "op": op, "seed": "blind",
                 **arithmetic_record(record)}
                for op, record in zip(operands, parsed))


families = (("top0", "TOP", 0, -1),
            ("top1", "TOP", 1, -1),
            ("low1", "LOW", 1, 1))
for family, line, act, target in families:
    sample = [row for row in census
              if row["line"] == line and row["act"] == act]
    bad = [row for row in sample if target not in row["nset"]]
    fit = [row for row in sample if row["pinned"]
           and row["nset"] == {target} and row["half"] == "FIT"]
    hol = [row for row in sample if row["pinned"]
           and row["nset"] == {target} and row["half"] == "HOL"]
    breaks = [row for row in responses[family] if row["label"] == "BREAK"]
    fixes = [row for row in responses[family] if row["label"] == "FIX"]
    bits, tails, dyadic, pair_predicates = [], [], [], []
    for descriptor in descriptors():
        bad_values = [value(row, descriptor) for row in bad + breaks]
        fit_values = [value(row, descriptor) for row in fit]
        hol_values = [value(row, descriptor) for row in hol]
        fix_values = [value(row, descriptor) for row in fixes]
        all_values = [value(row, descriptor) for row in sample]
        if True:
            local_predicates = []
            for fix_value in set(fix_values):
                for sense, boundary in (("lt", fix_value + 1),
                                        ("gt", fix_value - 1)):
                    predicate = ((lambda item, b=boundary: item < b)
                                 if sense == "lt" else
                                 (lambda item, b=boundary: item > b))
                    def bitmask(values):
                        result = 0
                        for index, item in enumerate(values):
                            if predicate(item):
                                result |= 1 << index
                        return result
                    bm = bitmask(bad_values)
                    fm = bitmask(fit_values)
                    hm = bitmask(hol_values)
                    rm = bitmask(fix_values)
                    am = bitmask(all_values)
                    if fm and hm and rm and popcount(bm) <= 128:
                        local_predicates.append((popcount(bm),
                            -(popcount(fm) + popcount(hm)),
                            name(descriptor), sense, boundary,
                            bm, fm, hm, rm, am))
            pair_predicates.extend(sorted(local_predicates)[:4])
        bad_or, bad_and = 0, MASK
        for item in bad_values:
            bad_or |= item
            bad_and &= item
        for bit in range(SCALE):
            for wanted in (0, 1):
                safe = not ((bad_or >> bit) & 1) if wanted else (
                    (bad_and >> bit) & 1)
                if not safe:
                    continue
                nf = sum(((item >> bit) & 1) == wanted
                         for item in fit_values)
                nh = sum(((item >> bit) & 1) == wanted
                         for item in hol_values)
                nr = sum(((item >> bit) & 1) == wanted
                         for item in fix_values)
                if nf and nh and nr:
                    fires = sum(((item >> bit) & 1) == wanted
                                for item in all_values)
                    bits.append((nr, nf + nh, min(nf, nh), fires,
                                 name(descriptor), bit, wanted, nf, nh))
        for sense, boundary in (("gt", max(bad_values)),
                                ("lt", min(bad_values))):
            predicate = ((lambda item, b=boundary: item > b)
                         if sense == "gt" else
                         (lambda item, b=boundary: item < b))
            nf, nh = sum(map(predicate, fit_values)), \
                sum(map(predicate, hol_values))
            nr = sum(map(predicate, fix_values))
            if nf and nh and nr:
                tails.append((nr, nf + nh, min(nf, nh),
                              sum(map(predicate, all_values)),
                              name(descriptor), sense, boundary, nf, nh))
            for denominator_bits in range(4, 21):
                step = 1 << (SCALE - denominator_bits)
                if sense == "gt":
                    simple_boundary = ((boundary + step - 1) // step) * step
                    simple_boundary = min(simple_boundary, MASK)
                    simple_predicate = lambda item, b=simple_boundary: item > b
                else:
                    simple_boundary = (boundary // step) * step
                    simple_predicate = lambda item, b=simple_boundary: item < b
                sf = sum(map(simple_predicate, fit_values))
                sh = sum(map(simple_predicate, hol_values))
                sr = sum(map(simple_predicate, fix_values))
                if sf and sh and sr:
                    dyadic.append((sr, sf + sh, min(sf, sh),
                                   sum(map(simple_predicate, all_values)),
                                   name(descriptor), sense,
                                   simple_boundary >> (SCALE-denominator_bits),
                                   denominator_bits, sf, sh))
    print("\n", family, "joint-safe word bits:")
    for row in sorted(bits, reverse=True)[:80]:
        nr, total, minimum, fires, word, bit, wanted, nf, nh = row
        print("  bit%d(%s)=%d response=%d pinned=%d FIT/HOL=%d/%d "
              "fires=%d" %
              (bit, word, wanted, nr, total, nf, nh, fires))
    print(" ", family, "joint-safe word tails:")
    for row in sorted(tails, reverse=True)[:80]:
        nr, total, minimum, fires, word, sense, boundary, nf, nh = row
        print("  %s %s %d response=%d pinned=%d FIT/HOL=%d/%d "
              "fires=%d" %
              (word, sense, boundary, nr, total, nf, nh, fires))
    print(" ", family, "joint-safe dyadic tails:")
    seen = set()
    shown = 0
    for row in sorted(dyadic, reverse=True):
        nr, total, minimum, fires, word, sense, numerator, dbits, nf, nh = row
        signature = word, sense, numerator, dbits
        if signature in seen:
            continue
        seen.add(signature)
        print("  %s %s %d/2^%d response=%d pinned=%d FIT/HOL=%d/%d "
              "fires=%d" %
              (word, sense, numerator, dbits, nr, total, nf, nh, fires))
        shown += 1
        if shown == 80:
            break
    if pair_predicates:
        unique = {}
        for row in pair_predicates:
            _, _, word, sense, boundary, bm, fm, hm, rm, am = row
            signature = bm, fm, hm, rm
            old = unique.get(signature)
            candidate = (word, sense, boundary, bm, fm, hm, rm, am)
            if old is None or (len(word), word, sense, boundary) < (
                    len(old[0]), old[0], old[1], old[2]):
                unique[signature] = candidate
        candidates = sorted(unique.values(),
                            key=lambda row: (popcount(row[3]),
                                             len(row[0]), row[:3]))[:5000]
        pairs = []
        for first_index, first in enumerate(candidates):
            for second in candidates[first_index + 1:]:
                if first[3] & second[3]:
                    continue
                fm, hm = first[4] & second[4], first[5] & second[5]
                rm = first[6] & second[6]
                if not fm or not hm or not rm:
                    continue
                am = first[7] & second[7]
                pairs.append((popcount(rm), popcount(fm)+popcount(hm),
                              min(popcount(fm), popcount(hm)),
                              popcount(am), first[:3], second[:3], rm))
        print(" ", family, "zero-contradiction numeric tail pairs:")
        for row in sorted(pairs, reverse=True)[:80]:
            nr, total, minimum, fires, first, second, rm = row
            print("  (%s %s %d) && (%s %s %d) response=%d pinned=%d "
                  "fires=%d rmask=%x" %
                  (*first, *second, nr, total, fires, rm))
        best_response_sets = {}
        for row in pairs:
            old = best_response_sets.get(row[6])
            if old is None or row[1:4] > old[1:4]:
                best_response_sets[row[6]] = row
        print(" ", family, "best pair per response set:")
        for row in sorted(best_response_sets.values(), reverse=True)[:80]:
            nr, total, minimum, fires, first, second, rm = row
            selected = ["%s:%s" % (fixes[index]["seed"], fixes[index]["op"])
                        for index in range(len(fixes)) if (rm >> index) & 1]
            print("  (%s %s %d) && (%s %s %d) response=%d pinned=%d "
                  "fires=%d selected=%s" %
                  (*first, *second, nr, total, fires, ",".join(selected)))

        # Search the full dyadic grid around every observed response value
        # for the strongest exact-boundary pair in each ladder.  This asks
        # whether the exact-looking cutoffs are merely samples inside wider
        # binary comparator laws that the hardware can implement.
        focused_descriptors = {
            "top0": (
                ("word", "64", "pre", "-", "right"),
                ("base", "sqlow"),
            ),
            "top1": (
                ("word", "6", "post", "+", "pre"),
                ("word", "dist", "post", "+", "pre"),
            ),
            "low1": (
                ("word", "low3", "sq", "+", "sqlow"),
                ("word", "5", "t4raw", "-", "right"),
            ),
        }[family]

        def focused_predicates(descriptor):
            bv = [value(row, descriptor) for row in bad + breaks]
            fv = [value(row, descriptor) for row in fit]
            hv = [value(row, descriptor) for row in hol]
            rv = [value(row, descriptor) for row in fixes]
            av = [value(row, descriptor) for row in sample]
            result = {}
            for response_value in set(rv):
                for sense in ("lt", "gt"):
                    for denominator_bits in range(4, 25):
                        step = 1 << (SCALE - denominator_bits)
                        if sense == "gt":
                            boundary = ((response_value - 1) // step) * step
                            predicate = lambda item, b=boundary: item > b
                        else:
                            boundary = ((response_value // step) + 1) * step
                            predicate = lambda item, b=boundary: item < b

                        def mask(values):
                            answer = 0
                            for index, item in enumerate(values):
                                if predicate(item):
                                    answer |= 1 << index
                            return answer

                        masks = tuple(mask(values)
                                      for values in (bv, fv, hv, rv, av))
                        if masks[1] and masks[2] and masks[3]:
                            numerator = boundary >> (SCALE-denominator_bits)
                            signature = sense, numerator, denominator_bits
                            result[signature] = masks
            return result

        first_grid = focused_predicates(focused_descriptors[0])
        second_grid = focused_predicates(focused_descriptors[1])
        focused_pairs = []
        for first_signature, first_masks in first_grid.items():
            for second_signature, second_masks in second_grid.items():
                if first_masks[0] & second_masks[0]:
                    continue
                fm = first_masks[1] & second_masks[1]
                hm = first_masks[2] & second_masks[2]
                rm = first_masks[3] & second_masks[3]
                if not fm or not hm or not rm:
                    continue
                am = first_masks[4] & second_masks[4]
                focused_pairs.append((
                    popcount(rm), popcount(fm) + popcount(hm),
                    min(popcount(fm), popcount(hm)), popcount(am),
                    first_signature, second_signature))
        focused_pairs.sort(key=lambda row: (
            -row[0], -row[1], -row[2],
            max(row[4][2], row[5][2]), row[4][2] + row[5][2],
            row[3], row[4], row[5]))
        print(" ", family, "focused dyadic R60 pairs:")
        for row in focused_pairs[:80]:
            nr, total, minimum, fires, first, second = row
            print("  (%s %s %d/2^%d) && (%s %s %d/2^%d) "
                  "response=%d pinned=%d FIT/HOL-min=%d fires=%d" % (
                      name(focused_descriptors[0]), *first,
                      name(focused_descriptors[1]), *second,
                      nr, total, minimum, fires))
