#!/usr/bin/env python3
"""h1035: score every exact h1034 TOP/act0 floor law on response rows.

The h975 census constrains admissibility but cannot distinguish equivalent
tap vectors inside its finite cells.  The dense h1000 neighborhoods provide
the independent test: FIX is a required selector firing and BREAK is a
nearby operand on which firing is forbidden.  This script reconstructs the
same integer coordinates from a normal R95 dump and ranks only formulas that
were already exact on the complete h975 selector population.
"""

import csv
import re
import subprocess
from collections import Counter, defaultdict

import h1034_top0_tap_solver as tap_solver


BASE = "/tmp/x87-r95-check"
WVRE = re.compile(
    r"(mul|lf|rf|f4|mag|left|right)=(\d+):(-?\d+):([0-9a-f]{32})")


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
            for token in line.split()[1:]:
                if "=" in token:
                    name, value = token.split("=", 1)
                    current[name] = value
    if current is not None:
        records.append(current)
    return records


def run_dumps(operands):
    process = subprocess.run(
        [BASE, "--batch", "--fcos-standalone", "--dump-internals"],
        input="\n".join(operands) + "\n", capture_output=True, text=True,
        check=True)
    records = parse_dumps(process.stderr)
    if len(records) != len(operands):
        raise RuntimeError("dump count mismatch")
    return records


def reconstructed(record):
    square = record["mul"][2]
    magnitude_sig = record["mag"][2]
    low3 = int(record["low3"])
    distance = int(record["dist"])
    right_shift = int(record["rsh"])
    right_discard = int(record["rdisc"], 16)
    full = square * square
    s4 = full.bit_length() - 67
    t4 = full & ((1 << s4) - 1)
    sqlow = square - (1 << 66)
    side = int(magnitude_sig >= 0xB504F333F9DE6800)
    mexp = right_shift - 16 - (side == 0)
    mask = (1 << mexp) - 1
    truncated_three = (3 * right_discard
                       - ((2 * right_discard) & mask)
                       - (right_discard & mask))
    b1 = int(truncated_three >= (1 << right_shift))
    b2 = int(truncated_three >= (1 << (right_shift + 1)))

    left, right = record["left"], record["right"]
    payload = int(record.get("pay2", record["payload"]))
    scale = min(left[1], right[1], left[1] - 8 if payload else left[1])
    s_value = left[2] << (left[1] - scale)
    if payload:
        s_value += payload << (left[1] - 8 - scale)
    b_value = right[2] << (right[1] - scale)
    magnitude = s_value - b_value
    cut = magnitude.bit_length() - 67
    sum8 = ((magnitude >> cut) & 0xff) + low3
    propagate = ~(s_value ^ b_value)
    pdown = 0
    while cut - pdown >= 0 and ((propagate >> (cut - pdown)) & 1):
        pdown += 1
    pbelow = 0
    while cut - 1 - pbelow >= 0 \
            and ((propagate >> (cut - 1 - pbelow)) & 1):
        pbelow += 1
    return {
        "sum8": sum8, "s4": s4, "side": side, "dist": distance,
        "low3": low3, "b1": b1, "b2": b2,
        "mreg": low3 * sqlow - t4, "sqlow": sqlow,
        "pcut": (propagate >> cut) & 1, "pdown": pdown,
        "pbelow": pbelow,
    }


def fires(row, coeff):
    c0, cL, cb1, cb2, clp, cd = coeff
    tap = (c0 + cL * row["low3"] + cb1 * row["b1"]
           + cb2 * row["b2"] + clp * (row["low3"] & 1)
           + cd * (row["dist"] - 7))
    _, u = tap_solver.base_and_u(row, tap)
    return row["pcut"] == 1 and row["mreg"] >= u * tap_solver.ONE


def q66_piecewise(row):
    if (row["dist"] in (8, 9) and row["low3"] == 1
            and row["b1"] == 0):
        tap = 3 + 5 * (row["dist"] - 8)
    elif (row["dist"] == 9 and row["low3"] == 3
          and row["b1"] == 1 and row["b2"] == 0):
        tap = 1
    else:
        return False
    _, u = tap_solver.base_and_u(row, tap)
    return row["pcut"] == 1 and row["mreg"] >= u * tap_solver.ONE


def main():
    with open("/tmp/h1025_response_records.tsv") as source:
        all_response = list(csv.DictReader(source, delimiter="\t"))
    response = [row for row in all_response
                if row["family"] == "top0" and row["source"] == "h1000"]
    records = run_dumps([row["op"] for row in response])
    tests = [(raw["label"], reconstructed(record), raw["op"])
             for raw, record in zip(response, records)]
    print("response", Counter(label for label, _, _ in tests))
    print("groups", Counter((256 - row["sum8"], row["s4"], row["side"],
                             label) for label, row, _ in tests))

    census = tap_solver.load_h1033_rows()
    eligible = [row for row in census if row["line"] == "TOP"
                and row["act"] == 0 and row["pcut"] == 1]
    groups = defaultdict(list)
    for row in eligible:
        groups[(256 - row["sum8"], row["s4"], row["side"])].append(row)

    for key in sorted(groups):
        positives = sum(tap_solver.label(row) == 1 for row in groups[key])
        if positives == 0:
            continue
        subset = [(label, row, op) for label, row, op in tests
                  if (256 - row["sum8"], row["s4"], row["side"]) == key]
        print(f"\n{key}: census positives={positives}; response="
              f"{Counter(label for label, _, _ in subset)}")
        _, intervals = tap_solver.cell_intervals(groups[key])
        solutions = tap_solver.fit_intervals(intervals)
        if solutions:
            ranked = []
            for weight, nonzero, coeff in solutions:
                score = Counter(label for label, row, _ in subset
                                if fires(row, coeff))
                ranked.append((score["BREAK"], -score["FIX"], weight,
                               nonzero, coeff, score))
            for item in sorted(ranked)[:20]:
                print(" ", item[4], dict(item[5]), "weight", item[2])
        elif key == (1, 66, 1):
            score = Counter(label for label, row, _ in subset
                            if q66_piecewise(row))
            print("  q66 piecewise", dict(score))


if __name__ == "__main__":
    main()
