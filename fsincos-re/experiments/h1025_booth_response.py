#!/usr/bin/env python3
"""h1025: independent response check for h1024's best Booth predicates."""

import csv
import gzip
import os
import re
import subprocess
from collections import Counter, defaultdict

from h621_carry_predict import booth8_rows, csa


WIDTH = 224
MASK = (1 << WIDTH) - 1
MODES = ("rn", "rd", "ru", "rz")
BASE = "/tmp/x87-r95-check"
FORCE = {"top0": "/tmp/x87-r96-force1",
         "top1": "/tmp/x87-r96-force2",
         "low1": "/tmp/x87-r96-force3"}
WVRE = re.compile(
    r"(mul|lf|rf|f4|mag|left|right)=(\d+):(-?\d+):([0-9a-f]{32})")


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


def thread(items):
    items = list(items)
    items += [0] * max(0, 3 - len(items))
    sum_word, carry_word = csa(items[0], items[1], items[2])
    for row in items[3:]:
        sum_word, carry_word = csa(sum_word, carry_word, row)
    return sum_word, carry_word


def patent_state(square):
    product = square * square
    cut = product.bit_length() - 67
    rows = booth8_rows(square, square)
    even_sum, even_carry = thread(rows[0::2])
    odd_sum, odd_carry = thread(rows[1::2])
    sum1, carry1 = csa(odd_sum, odd_carry, even_sum)
    sum2, carry2 = csa(sum1, carry1, even_carry)
    if (sum2 + carry2) & MASK != product & MASK:
        raise AssertionError("patent reduction does not reproduce f4")
    return {
        "po_p+8": ((odd_sum ^ odd_carry) >> (cut + 8)) & 1,
        "pe_c+16": (even_carry >> (cut + 16)) & 1,
        "po_p-8": ((odd_sum ^ odd_carry) >> (cut - 8)) & 1,
        "pe_s+14": (even_sum >> (cut + 14)) & 1,
        "d17neg": int(((square >> 50) & 15) in (8, 9, 10, 11,
                                                    12, 13, 14, 15)),
    }


def terminal_pcut(record):
    left, right = record["left"], record["right"]
    left_exp, right_exp = left[1], right[1]
    payload = int(record.get("pay2", record["payload"]))
    scale = min(left_exp, right_exp,
                left_exp - 8 if payload else left_exp)
    signed_left = (-1 if left[0] else 1) * (
        left[2] << (left_exp - scale))
    signed_right = (-1 if right[0] else 1) * (
        right[2] << (right_exp - scale))
    signed_payload = 0
    if payload:
        payload_sign = left[0] ^ (payload < 0)
        signed_payload = (-1 if payload_sign else 1) * (
            abs(payload) << (left_exp - 8 - scale))
    if signed_left + signed_payload < 0 <= signed_right:
        minuend = -(signed_left + signed_payload)
        subtrahend = signed_right
    else:
        minuend = -signed_right
        subtrahend = signed_left + signed_payload
    magnitude = minuend - subtrahend
    cut = magnitude.bit_length() - 67
    return (~(minuend ^ subtrahend) >> cut) & 1


def predicates(record):
    square = record["mul"][2]
    state = patent_state(square)
    low_digit_three = (square & 7) == 3
    direction = terminal_pcut(record) == 1
    return {
        "d0=3 & po_p+8": direction and low_digit_three
                            and state["po_p+8"],
        "d0=3 & pe_c+16": direction and low_digit_three
                             and state["pe_c+16"],
        "d0=3 & !po_p-8": direction and low_digit_three
                             and not state["po_p-8"],
        "d0=3 & pe_s+14": direction and low_digit_three
                             and state["pe_s+14"],
        "d0=3 & d17neg": direction and low_digit_three
                            and state["d17neg"],
    }


with gzip.open("h1000_sensitive_neighborhoods.tsv.gz", "rt") as src:
    neighborhood = list(csv.DictReader(src, delimiter="\t"))
tests = []
for family, force_binary in FORCE.items():
    selected_rows = [row for row in neighborhood if row["family"] == family]
    operands = [row["op"] for row in selected_rows]
    tags = [set() for _ in selected_rows]
    for mode in MODES:
        candidate, _ = run_model(force_binary, mode, operands)
        for index, (row, value) in enumerate(zip(selected_rows, candidate)):
            baseline, hardware = row["m_" + mode], row["h_" + mode]
            if value == baseline:
                continue
            if value == hardware and baseline != hardware:
                tags[index].add("FIX")
            elif baseline == hardware and value != hardware:
                tags[index].add("BREAK")
            else:
                tags[index].add("OTHER")
    chosen = [(row, next(iter(tag)))
              for row, tag in zip(selected_rows, tags)
              if len(tag) == 1 and tag <= {"FIX", "BREAK"}]
    chosen_operands = [row["op"] for row, _ in chosen]
    _, dump = run_model(BASE, "rn", chosen_operands, dump=True)
    records = parse_dumps(dump)
    if len(records) != len(chosen):
        raise RuntimeError("response dump count mismatch")
    tests.extend((family, "h1000", row["op"], label,
                  "FIT" if int(row["seed"]) % 2 == 0 else "HOL", record)
                 for (row, label), record in zip(chosen, records))

blind_path = "/tmp/h1022_attributed.tsv"
if os.path.exists(blind_path):
    with open(blind_path) as src:
        blind_rows = list(csv.DictReader(src, delimiter="\t"))
    by_family_insn = defaultdict(list)
    arm_family = {"res": "top1", "top": "top0", "low": "low1"}
    for row in blind_rows:
        if row["arm"] in arm_family:
            by_family_insn[(arm_family[row["arm"]], row["insn"])].append(
                row["op"])
    for (family, insn), insn_operands in by_family_insn.items():
        insn_operands = sorted(set(insn_operands))
        _, blind_dump = run_model(BASE, "rn", insn_operands,
                                  dump=True, insn=insn)
        blind_records = parse_dumps(blind_dump)
        tests.extend((family, "h1022", op, "BREAK", "BLIND", record)
                     for op, record in zip(insn_operands, blind_records))

with open("/tmp/h1025_response_records.tsv", "w") as out:
    out.write("family\tsource\top\tlabel\thalf\tsquare\tpcut"
              "\tmag\tmul\tlf\tf4\trf\n")
    for family, source, operand, label, half, record in tests:
        out.write("%s\t%s\t%s\t%s\t%s\t%032x\t%d"
                  "\t%032x\t%032x\t%032x\t%032x\t%032x\n" %
                  (family, source, operand, label, half, record["mul"][2],
                   terminal_pcut(record), record["mag"][2],
                   record["mul"][2], record["lf"][2],
                   record["f4"][2], record["rf"][2]))

print("response rows", Counter((family, source, label)
                               for family, source, _, label, _, _ in tests))
scores = defaultdict(Counter)
selected = defaultdict(list)
for family, source, operand, label, half, record in tests:
    if family != "top1":
        continue
    for name, fired in predicates(record).items():
        if fired:
            scores[name][(source, label)] += 1
            selected[name].append((source, label, operand))
for name in sorted(scores):
    print("\n", name, dict(scores[name]))
    for item in selected[name][:40]:
        print("  ", item)
