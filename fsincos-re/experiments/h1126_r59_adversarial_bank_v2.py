#!/usr/bin/env python3
"""Build a label-blind, no-repeat adversarial bank for the R59 selector.

This is a software-only selection pass.  It never executes x87 hardware and
never consults an unseen hardware label.  The two absolute endpoint models
identify architecturally visible rows; the standing candidate supplies the
internal state used for selection.  Every output operand is excluded from all
supplied inventories before it is considered.

The selected rows attack three distinct generalization risks:

* exact-input and continuous-coordinate brackets around each known residual;
* same-cell/same-leaf rows whose literal multiplier/terminal netlist state is
  as different as possible from the residual anchor; and
* discrete siblings across b1/b2, prefix-run, and incumbent branch decisions.

The result is a one-shot capture manifest: each (rounding mode, operand) pair
occurs once.  Different rounding modes are distinct architectural inputs, not
repeat observations.
"""

import argparse
import csv
import glob
import hashlib
import os
import random
import re
import subprocess
from collections import Counter, defaultdict

from h1100_p5_multiplier_tree import (
    PRODUCT_MASK, TREE_MASK, csa3, multiplier_tree,
)


MODES = ("rn", "rd", "ru", "rz")
CORE_FIELDS = ("branch", "theta", "ce", "s4", "side", "low3",
               "dist", "rsh")
STRICT_FIELDS = CORE_FIELDS + ("b1", "b2")
HEX_OPERAND = re.compile(r"^[0-9a-f]{4} [0-9a-f]{16}$")


def signed128(text):
    value = int(text, 16)
    return value - (1 << 128) if value >> 127 else value


def parse_tokens(line):
    return {match.group(1): match.group(2)
            for match in re.finditer(r"(\w+)=([0-9a-fA-F,-]+)", line)}


def parse_wide_values(line):
    values = {}
    pattern = (r"(mul|lf|rf|f4|mag|left|right)="
               r"([01]):(-?\d+):([0-9a-fA-F]+)")
    for match in re.finditer(pattern, line):
        name, sign, exponent, significand = match.groups()
        values["tc_" + name + "_sign"] = sign
        values["tc_" + name + "_exp"] = exponent
        values["tc_" + name + "_sig"] = significand.lower()
    return values


def run_model(binary, mode, operands, dump=False):
    command = [binary, "--batch", "--fcos-standalone"]
    if mode != "rn":
        command.insert(2, "--rc=" + mode)
    if dump:
        command.append("--dump-internals")
    process = subprocess.run(
        command, input="\n".join(operands) + "\n",
        capture_output=True, text=True, check=True)
    outputs = []
    for line in process.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[0] == "OK":
            outputs.append(fields[1].lower() + ":" + fields[2].lower())
    if len(outputs) != len(operands):
        raise RuntimeError("output count mismatch for " + binary)
    return outputs, process.stderr


def parse_dump(text):
    records = []
    current = None
    for line in text.splitlines():
        if line.startswith("DI_IN "):
            if current is not None:
                records.append(current)
            fields = line.split()
            current = {"op": (fields[1] + " " + fields[2]).lower()}
        elif current is not None and line.startswith("DI_R59 "):
            current.update(parse_tokens(line))
        elif current is not None and line.startswith("DI_TC "):
            current.update({"tc_" + key: value
                            for key, value in parse_tokens(line).items()})
            current.update(parse_wide_values(line))
        elif current is not None and line.startswith("DI_CRIT "):
            current.update({"crit_" + key: value
                            for key, value in parse_tokens(line).items()})
        elif current is not None and line.startswith("DI_BS "):
            current.update({"bs_" + key: value
                            for key, value in parse_tokens(line).items()})
        elif current is not None and line.startswith("DI_BR "):
            current["branch"] = line.split()[1].split("=", 1)[1]
            current.update({"br_" + key: value
                            for key, value in parse_tokens(line).items()
                            if key != "br"})
    if current is not None:
        records.append(current)
    return records


def add_inventory(path, known):
    """Add operands from either a TSV or a plain operand/key file."""
    with open(path, errors="replace") as source:
        first = source.readline()
        source.seek(0)
        if "\t" in first:
            reader = csv.DictReader(source, delimiter="\t")
            if reader.fieldnames and "op" in reader.fieldnames:
                for row in reader:
                    operand = (row.get("op") or "").lower()
                    if HEX_OPERAND.fullmatch(operand):
                        known.add(operand)
                return
            if reader.fieldnames and {"se", "sig"}.issubset(reader.fieldnames):
                for row in reader:
                    operand = ((row.get("se") or "") + " "
                               + (row.get("sig") or "")).lower()
                    if HEX_OPERAND.fullmatch(operand):
                        known.add(operand)
                return
        for line in source:
            fields = line.lower().split()
            for start in range(max(1, len(fields) - 1)):
                operand = " ".join(fields[start:start + 2])
                if HEX_OPERAND.fullmatch(operand):
                    known.add(operand)
                    break


def generated_operands(anchor, count, generator):
    se_text, sig_text = anchor.split()
    anchor_sig = int(sig_text, 16)
    result = set()

    # Deterministic near neighbors and single-bit challenges are always
    # present, even when the stochastic tail budget is small.
    for magnitude in list(range(1, 257)) + [1 << bit for bit in range(8, 56)]:
        for sign in (-1, 1):
            sig = anchor_sig + sign * magnitude
            if (1 << 63) <= sig < (1 << 64):
                result.add(se_text + " " + ("%016x" % sig))
    for bit in range(56):
        sig = anchor_sig ^ (1 << bit)
        if (1 << 63) <= sig < (1 << 64):
            result.add(se_text + " " + ("%016x" % sig))

    widths = (8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56)
    attempt = 0
    while len(result) < count:
        width = widths[attempt % len(widths)]
        style = (attempt // len(widths)) % 4
        attempt += 1
        mask = (1 << width) - 1
        if style == 0:
            sig = (anchor_sig & ~mask) | generator.getrandbits(width)
        elif style == 1:
            sig = anchor_sig
            flips = 1 + generator.randrange(min(8, width))
            for bit in generator.sample(range(width), flips):
                sig ^= 1 << bit
        elif style == 2:
            delta = generator.randrange(1, 1 << width)
            sig = anchor_sig + (delta if generator.getrandbits(1) else -delta)
        else:
            # Long all-zero/all-one runs attack propagate-chain boundaries.
            run = 1 + generator.randrange(width)
            low_mask = (1 << run) - 1
            fill = low_mask if generator.getrandbits(1) else 0
            sig = (anchor_sig & ~low_mask) | fill
            if run < width:
                sig ^= 1 << run
        if (1 << 63) <= sig < (1 << 64):
            result.add(se_text + " " + ("%016x" % sig))
    result.discard(anchor)
    return sorted(result)


def bit(value, position):
    return (value >> position) & 1 if position >= 0 else 0


def popcount(value):
    return bin(value).count("1")


def append_product_signature(bits, multiplicand, multiplier, square=False):
    state = multiplier_tree(multiplicand, multiplier)
    exact = multiplicand * multiplier
    cut = exact.bit_length() - 67
    sum_vector = state["sum"]
    carry_vector = state["carry"]
    if square:
        sum_vector, carry_vector = csa3(
            (sum_vector << 3) & TREE_MASK,
            (carry_vector << 3) & TREE_MASK,
            multiplicand * (multiplicand & 7))
        exact = multiplicand * multiplicand
        cut = exact.bit_length() - 67
        if ((sum_vector + carry_vector) & ((1 << 134) - 1)) != exact:
            raise AssertionError("square reconstruction mismatch")
    elif ((sum_vector + carry_vector) & PRODUCT_MASK) != exact:
        raise AssertionError("product reconstruction mismatch")
    for offset in range(-16, 9):
        position = cut + offset
        bits.extend((bit(sum_vector, position), bit(carry_vector, position)))
    for digit in state["digits"]:
        bits.extend((digit < 0, digit == 0, abs(digit) == 3))


def structural_signature(row):
    bits = []
    multiplier = int(row["tc_mul_sig"], 16)
    append_product_signature(
        bits, multiplier, int(row["tc_lf_sig"], 16))
    append_product_signature(
        bits, int(row["tc_f4_sig"], 16), int(row["tc_rf_sig"], 16))
    append_product_signature(bits, multiplier, multiplier >> 3, square=True)
    s_value = int(row["S"], 16)
    b_value = int(row["B"], 16)
    cut = int(row["k"])
    for offset in range(-16, 9):
        position = cut + offset
        a = bit(s_value, position)
        b = bit(b_value, position)
        bits.extend((a, b, a == b))
    packed = 0
    for index, value in enumerate(bits):
        packed |= int(value) << index
    return packed, len(bits)


def decorate(row, anchor, mode, base, minus, plus):
    row = dict(row)
    row["mode"] = mode
    row["anchor"] = anchor["op"]
    row["anchor_mode"] = anchor["mode"]
    row["anchor_desired"] = anchor["desired"]
    row["base"] = base
    row["force_minus2"] = minus
    row["force_plus1"] = plus
    row["base_choice"] = (
        "minus2" if base == minus else "plus1" if base == plus else "other")
    sig = int(row["op"].split()[1], 16)
    anchor_sig = int(anchor["op"].split()[1], 16)
    row["offset"] = str(sig - anchor_sig)
    row["mreg_signed"] = str(signed128(row["Mreg"]))
    row["anchor_mreg_signed"] = str(signed128(anchor["Mreg"]))
    row["mreg_delta"] = str(
        int(row["mreg_signed"]) - int(row["anchor_mreg_signed"]))
    cut = int(row["k"])
    disc = int(row["disc"], 16)
    row["q11"] = str((disc << 11) >> cut)
    anchor_cut = int(anchor["k"])
    row["anchor_q11"] = str(
        (int(anchor["disc"], 16) << 11) >> anchor_cut)
    row["q11_delta"] = str(int(row["q11"]) - int(row["anchor_q11"]))
    s_value = int(row["S"], 16)
    b_value = int(row["B"], 16)
    equality = ~(s_value ^ b_value)
    row["pcut"] = str((equality >> cut) & 1)
    below = 0
    while cut - 1 - below >= 0 and ((equality >> (cut - 1 - below)) & 1):
        below += 1
    above = 0
    while above < 32 and ((equality >> (cut + above)) & 1):
        above += 1
    row["pbelow"] = str(below)
    row["pabove"] = str(above)
    row["retained_byte"] = str((int(row["umag"], 16) >> cut) & 255)
    if row.get("br_uu", "") not in ("", None):
        row["u_margin"] = str(
            int(row["mreg_signed"]) - (int(row["br_uu"]) << 66))
    else:
        row["u_margin"] = ""
    signature, signature_bits = structural_signature(row)
    row["structural_signature"] = "%0*x" % (
        (signature_bits + 3) // 4, signature)
    anchor_signature = anchor["_structural_signature"]
    row["structural_hamming"] = str(
        popcount(signature ^ anchor_signature))
    leaf_fields = (
        "branch", "br_in_region", "br_fire", "br_tfire", "crit_crit",
        "crit_crit9", "bs_fire", "retained_byte", "pcut",
        "pbelow", "pabove",
    )
    row["leaf_signature"] = "/".join(row.get(name, "-")
                                       for name in leaf_fields)
    return row


def same_fields(left, right, fields):
    return all(left.get(name) == right.get(name) for name in fields)


def choose_group(anchor, rows, limit):
    """Choose paired boundary and structural challenges without labels."""
    if not rows:
        return []
    strict = [row for row in rows if same_fields(row, anchor, STRICT_FIELDS)]
    core = [row for row in rows if same_fields(row, anchor, CORE_FIELDS)]
    primary = strict or core or rows
    chosen = {}

    def add(category, candidates, count=1):
        added = 0
        for row in candidates:
            entry = chosen.setdefault(row["op"], (row, set()))
            entry[1].add(category)
            if len(entry[1]) == 1:
                added += 1
            if added >= count:
                break

    def sides(category, key, target, population, count=2):
        lower = sorted((row for row in population if key(row) < target),
                       key=lambda row: (target - key(row), row["op"]))
        upper = sorted((row for row in population if key(row) > target),
                       key=lambda row: (key(row) - target, row["op"]))
        add(category + "_below", lower, count)
        add(category + "_above", upper, count)

    sides("input", lambda row: int(row["offset"]), 0, primary)
    sides("M", lambda row: int(row["mreg_signed"]),
          int(primary[0]["anchor_mreg_signed"]), primary)
    sides("q11", lambda row: int(row["q11"]),
          int(primary[0]["anchor_q11"]), primary)

    # Rows closest to an actual incumbent M threshold attack an open/closed
    # comparator mistake rather than merely clustering around the anchor.
    margins = [row for row in core if row.get("u_margin", "") != ""]
    add("u_wall", sorted(margins, key=lambda row: (
        abs(int(row["u_margin"])), row["op"])), 4)

    anchor_leaf = anchor.get("_leaf_signature", "")
    same_leaf = [row for row in primary
                 if row["leaf_signature"] == anchor_leaf]
    add("same_leaf_far_netlist", sorted(
        same_leaf, key=lambda row: (-int(row["structural_hamming"]),
                                    abs(int(row["offset"])), row["op"])), 4)
    far_category = ("same_strict_cell_far_netlist" if strict
                    else "same_core_cell_far_netlist" if core
                    else "near_cell_far_netlist")
    add(far_category, sorted(
        primary, key=lambda row: (-int(row["structural_hamming"]),
                                  abs(int(row["offset"])), row["op"])), 4)

    # Force discrete siblings into the manifest when the generator reaches
    # them, even though they are intentionally outside the strict cell.
    for b1 in ("0", "1"):
        for b2 in ("0", "1"):
            siblings = [row for row in core
                        if row.get("b1") == b1 and row.get("b2") == b2]
            add("b_sibling_" + b1 + b2, sorted(
                siblings, key=lambda row: (abs(int(row["mreg_delta"])),
                                            row["op"])), 1)
    prefix_bins = {}
    for row in primary:
        key = (min(int(row["pbelow"]), 16),
               min(int(row["pabove"]), 16), row["pcut"])
        candidate = (abs(int(row["offset"])), row["op"], row)
        if key not in prefix_bins or candidate[:2] < prefix_bins[key][:2]:
            prefix_bins[key] = candidate
    add("prefix_sibling", [value[2] for _, value in sorted(prefix_bins.items())],
        min(6, len(prefix_bins)))

    ranked = sorted(chosen.values(), key=lambda item: (
        -len(item[1]), abs(int(item[0]["offset"])),
        -int(item[0]["structural_hamming"]), item[0]["op"]))
    result = []
    for row, categories in ranked[:limit]:
        row = dict(row)
        row["selection"] = ",".join(sorted(categories))
        result.append(row)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("features")
    parser.add_argument("baseline")
    parser.add_argument("force_minus2")
    parser.add_argument("force_plus1")
    parser.add_argument("output_prefix")
    parser.add_argument("--known", action="append", default=[])
    parser.add_argument("--known-glob", action="append", default=[])
    parser.add_argument("--samples-per-anchor", type=int, default=100000)
    parser.add_argument("--limit-per-anchor-mode", type=int, default=24)
    parser.add_argument("--seed", type=lambda value: int(value, 0),
                        default=0x1126A6B3)
    parser.add_argument("--chunk", type=int, default=20000)
    args = parser.parse_args()

    output_paths = [args.output_prefix + "_features.tsv",
                    args.output_prefix + "_manifest.tsv"] + [
        args.output_prefix + "_" + mode + "_ops.txt" for mode in MODES]
    for path in output_paths:
        if os.path.exists(path):
            raise SystemExit("refusing to overwrite " + path)

    with open(args.features) as source:
        feature_rows = list(csv.DictReader(source, delimiter="\t"))
    anchors = [dict(row) for row in feature_rows if row["label"] == "POS"]
    known = set()
    inventory_paths = list(args.known)
    for pattern in args.known_glob:
        inventory_paths.extend(glob.glob(pattern))
    for path in sorted(set(inventory_paths)):
        add_inventory(path, known)
    known.update(row["op"].lower() for row in feature_rows)

    for anchor in anchors:
        signature, _ = structural_signature(anchor)
        anchor["_structural_signature"] = signature
        # Anchor leaf signatures use the same derived fields as candidates.
        anchor_copy = decorate(
            anchor, anchor, anchor["mode"], "", "minus", "plus")
        anchor["_leaf_signature"] = anchor_copy["leaf_signature"]

    generator = random.Random(args.seed)
    selected = {}
    eligible_counts = Counter()
    for anchor_index, anchor in enumerate(anchors, 1):
        candidates = [operand for operand in generated_operands(
            anchor["op"], args.samples_per_anchor, generator)
            if operand not in known]
        for mode in MODES:
            visible = []
            endpoint_outputs = {}
            for start in range(0, len(candidates), args.chunk):
                chunk = candidates[start:start + args.chunk]
                minus, _ = run_model(args.force_minus2, mode, chunk)
                plus, _ = run_model(args.force_plus1, mode, chunk)
                for operand, first, second in zip(chunk, minus, plus):
                    if first != second:
                        visible.append(operand)
                        endpoint_outputs[operand] = (first, second)
            records = []
            for start in range(0, len(visible), min(args.chunk, 4000)):
                chunk = visible[start:start + min(args.chunk, 4000)]
                base, stderr = run_model(args.baseline, mode, chunk, dump=True)
                parsed = parse_dump(stderr)
                if len(parsed) != len(chunk):
                    raise RuntimeError("dump count mismatch at " + anchor["op"])
                for operand, output, record in zip(chunk, base, parsed):
                    if record["op"] != operand:
                        raise RuntimeError("dump desynchronization")
                    required = set(STRICT_FIELDS) | {
                        "Mreg", "S", "B", "k", "umag", "disc",
                        "tc_mul_sig", "tc_lf_sig", "tc_f4_sig", "tc_rf_sig",
                    }
                    if not required.issubset(record):
                        continue
                    minus, plus = endpoint_outputs[operand]
                    records.append(decorate(
                        record, anchor, mode, output, minus, plus))
            eligible_counts[mode] += len(records)
            for row in choose_group(
                    anchor, records, args.limit_per_anchor_mode):
                key = (mode, row["op"])
                if key not in selected:
                    selected[key] = row
                else:
                    categories = set(selected[key]["selection"].split(","))
                    categories.update(row["selection"].split(","))
                    selected[key]["selection"] = ",".join(sorted(categories))
            print("anchor", anchor_index, "of", len(anchors), anchor["op"],
                  "mode", mode, "generated", len(candidates),
                  "visible", len(visible), "eligible", len(records),
                  "selected-total", len(selected), flush=True)

    if not selected:
        raise RuntimeError("no fresh adversarial rows selected")
    rows = [selected[key] for key in sorted(selected)]
    metadata = (
        "mode", "op", "anchor", "anchor_mode", "anchor_desired",
        "selection", "base", "force_minus2", "force_plus1", "base_choice",
        "offset", "mreg_signed", "anchor_mreg_signed", "mreg_delta",
        "q11", "anchor_q11", "q11_delta", "u_margin", "pcut", "pbelow",
        "pabove", "retained_byte", "structural_hamming",
        "structural_signature",
    )
    columns = metadata + tuple(sorted(
        {name for row in rows for name in row}
        - set(metadata) - {"_structural_signature", "_leaf_signature"}))
    feature_path = args.output_prefix + "_features.tsv"
    with open(feature_path, "w", newline="") as target:
        writer = csv.DictWriter(target, columns, delimiter="\t",
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    manifest_path = args.output_prefix + "_manifest.tsv"
    with open(manifest_path, "w", newline="") as target:
        writer = csv.DictWriter(
            target, ("insn", "mode", "op", "anchor", "selection"),
            delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({"insn": "cos", "mode": row["mode"],
                             "op": row["op"], "anchor": row["anchor"],
                             "selection": row["selection"]})
    for mode in MODES:
        with open(args.output_prefix + "_" + mode + "_ops.txt", "w") as target:
            for row in rows:
                if row["mode"] == mode:
                    target.write(row["op"] + "\n")

    digest = hashlib.sha256()
    with open(manifest_path, "rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    print("anchors", len(anchors), "known", len(known),
          "eligible", dict(eligible_counts), "selected", len(rows),
          "modes", dict(Counter(row["mode"] for row in rows)))
    print("manifest_sha256", digest.hexdigest())


if __name__ == "__main__":
    main()
