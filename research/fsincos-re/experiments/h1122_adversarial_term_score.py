#!/usr/bin/env python3
"""Score structural DNF terms on the already-captured h1097 adversaries.

Only model internals are regenerated.  Hardware outputs and admissible
endpoint sets come from the cached h1098 score, so this script performs no
hardware capture.
"""

import argparse
import csv
import re
import subprocess

from h1101_p5_tree_mine import row_features as product_features
from h1106_terminal_prefix_mine import terminal_features


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


def dump(binary, mode, operands):
    command = [binary, "--batch", "--fcos-standalone", "--dump-internals"]
    if mode != "rn":
        command.insert(2, "--rc=" + mode)
    process = subprocess.run(command, input="\n".join(operands) + "\n",
                             capture_output=True, text=True, check=True)
    records = []
    current = None
    for line in process.stderr.splitlines():
        if line.startswith("DI_IN "):
            if current is not None:
                records.append(current)
            current = {"op": " ".join(line.split()[1:3]).lower()}
        elif current is not None and line.startswith("DI_R59 "):
            current.update(parse_tokens(line))
        elif current is not None and line.startswith("DI_TC "):
            current.update({"tc_" + key: value
                            for key, value in parse_tokens(line).items()})
            current.update(parse_wide_values(line))
        elif current is not None and line.startswith("DI_BR "):
            current["branch"] = line.split()[1].split("=", 1)[1]
            current.update({"br_" + key: value
                            for key, value in parse_tokens(line).items()
                            if key != "br"})
    if current is not None:
        records.append(current)
    if len(records) != len(operands):
        raise RuntimeError("dump count mismatch")
    return records


def parse_terms(path):
    terms = []
    section = None
    with open(path) as source:
        for line in source:
            line = line.rstrip("\n")
            if line == "[best zero-forbidden terms]":
                section = "all"
                continue
            if line == "[greedy cover]":
                section = "greedy"
                continue
            if line.startswith("["):
                section = None
                continue
            if section not in ("all", "greedy") or "=" not in line:
                continue
            fields = line.split("\t")
            expression = fields[-1]
            literals = []
            for clause in expression.split(" & "):
                name, value = clause.rsplit("=", 1)
                literals.append((name, int(value)))
            terms.append((section, expression, tuple(literals)))
    return terms


def carry_state(row):
    cut = int(row["k"])
    mask = (1 << cut) - 1
    borrow = int((int(row["S"], 16) & mask)
                 < (int(row["B"], 16) & mask))
    current_delta = (int(row["br_r"], 16)
                     - (int(row["umag"], 16) >> cut))
    current_carry = current_delta - borrow + 1
    return borrow, current_delta, current_carry


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("bank")
    parser.add_argument("model")
    parser.add_argument("term_report")
    parser.add_argument("output")
    args = parser.parse_args()

    with open(args.bank) as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    groups = {}
    for mode in sorted({row["mode"] for row in rows}):
        group = [row for row in rows if row["mode"] == mode]
        records = dump(args.model, mode, [row["op"] for row in group])
        groups.update({row["op"]: record
                       for row, record in zip(group, records)})

    terms = parse_terms(args.term_report)
    scores = []
    row_values = []
    for row in rows:
        record = groups[row["op"]]
        values = {"terminal." + name: value
                  for name, value in terminal_features(record).items()}
        values.update({"product." + name: value
                       for name, value in product_features(record).items()})
        borrow, current_delta, current_carry = carry_state(record)
        values["state.current_carry"] = current_carry
        values["state.borrow"] = borrow
        allowed_delta = {int(value) for value in row["matches"].split(",")}
        flipped_delta = borrow - 1 + (1 - current_carry)
        row_values.append((row, values, current_delta, flipped_delta,
                           allowed_delta))

    for section, expression, literals in terms:
        triggered = breaks = fixes = neutral = 0
        triggered_ops = []
        for row, values, current_delta, flipped_delta, allowed in row_values:
            if not all(int(values[name]) == value
                       for name, value in literals):
                continue
            triggered += 1
            triggered_ops.append(row["op"])
            current_ok = current_delta in allowed
            flipped_ok = flipped_delta in allowed
            if current_ok and not flipped_ok:
                breaks += 1
            elif not current_ok and flipped_ok:
                fixes += 1
            else:
                neutral += 1
        scores.append((breaks, -fixes, -triggered, section, expression,
                       neutral, tuple(triggered_ops)))
    scores.sort()

    greedy_terms = [term for term in terms if term[0] == "greedy"]
    greedy_triggered = greedy_breaks = greedy_fixes = greedy_neutral = 0
    for row, values, current_delta, flipped_delta, allowed in row_values:
        trigger = any(all(int(values[name]) == value
                          for name, value in literals)
                      for _, _, literals in greedy_terms)
        if not trigger:
            continue
        greedy_triggered += 1
        current_ok = current_delta in allowed
        flipped_ok = flipped_delta in allowed
        if current_ok and not flipped_ok:
            greedy_breaks += 1
        elif not current_ok and flipped_ok:
            greedy_fixes += 1
        else:
            greedy_neutral += 1

    with open(args.output, "w") as target:
        target.write("rows\t%d\nterms\t%d\n" % (len(rows), len(terms)))
        target.write("greedy_triggered\t%d\ngreedy_breaks\t%d\n"
                     "greedy_fixes\t%d\ngreedy_neutral\t%d\n" %
                     (greedy_triggered, greedy_breaks, greedy_fixes,
                      greedy_neutral))
        target.write("\n[term scores]\n")
        target.write("breaks\tfixes\ttriggered\tsection\tneutral"
                     "\texpression\toperands\n")
        for breaks, minus_fixes, minus_triggered, section, expression, \
                neutral, operands in scores:
            target.write("%d\t%d\t%d\t%s\t%d\t%s\t%s\n" %
                         (breaks, -minus_fixes, -minus_triggered, section,
                          neutral, expression, ",".join(operands)))
    print("wrote", args.output, "rows", len(rows), "terms", len(terms),
          "greedy", greedy_triggered, greedy_breaks, greedy_fixes,
          greedy_neutral)


if __name__ == "__main__":
    main()
