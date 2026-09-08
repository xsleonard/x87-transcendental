#!/usr/bin/env python3
"""Regenerate the R59 feature bank for the current ledger-free residual.

The h1095 bank labeled all 29 residuals that existed at that checkpoint.
Later arithmetic recurrences derived twenty of them and can also change their
internal traces.  This experiment therefore starts from the current full-suite
miss list, keeps only the still-open R59 operands, and re-dumps every row from
the current ledger-free executable.  Rows intercepted by an earlier derived
recurrence are outside the R59 selector's support and are reported/skipped.
"""

import argparse
import csv
import os
import re
import subprocess


def parse_tokens(line):
    values = {}
    for match in re.finditer(r"(\w+)=([0-9a-fA-F,-]+)", line):
        values[match.group(1)] = match.group(2)
    return values


def parse_wide_values(line):
    values = {}
    for match in re.finditer(
            r"(mul|lf|rf|f4|mag|left|right)=([01]):(-?\d+):([0-9a-fA-F]+)",
            line):
        name, sign, exponent, significand = match.groups()
        values["tc_" + name + "_sign"] = sign
        values["tc_" + name + "_exp"] = exponent
        values["tc_" + name + "_sig"] = significand.lower()
    return values


def dump(binary, mode, operands):
    command = [binary, "--batch", "--fcos-standalone", "--dump-internals"]
    if mode != "rn":
        command.insert(2, "--rc=" + mode)
    process = subprocess.run(
        command, input="\n".join(operands) + "\n",
        capture_output=True, text=True, check=True)
    outputs = [line.strip() for line in process.stdout.splitlines()
               if line.startswith(("OK ", "UNSUPPORTED "))]
    if len(outputs) != len(operands):
        raise RuntimeError("output count mismatch %d != %d in %s" %
                           (len(outputs), len(operands), mode))

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
    if len(records) != len(operands):
        raise RuntimeError("dump count mismatch %d != %d in %s" %
                           (len(records), len(operands), mode))
    for record, output in zip(records, outputs):
        record["model"] = output.replace("OK ", "", 1).replace(" ", ":", 1)
    return records


def current_r59_operands(path):
    operands = set()
    with open(path) as source:
        for line in source:
            fields = line.split()
            if len(fields) < 10 or fields[1] != "cos":
                continue
            operand = (fields[4] + " " + fields[5]).lower()
            # d0d0 is the independently tracked s4=66 R1270 merge miss.
            if operand == "3ffc d0d000000cc0b3f8":
                continue
            operands.add(operand)
    return operands


def positive_rows(score_path, targets):
    selected = {}
    with open(score_path) as source:
        for row in csv.DictReader(source, delimiter="\t"):
            if row["op"] not in targets or row["hw"] == row["f0"]:
                continue
            endpoints = []
            if row["hw"] == row["f1"]:
                endpoints.append("minus2")
            if row["hw"] == row["f4"]:
                endpoints.append("plus1")
            if len(endpoints) != 1:
                raise RuntimeError("ambiguous endpoint for " + row["op"])
            prior = selected.setdefault(row["op"], {
                "label": "POS", "desired": endpoints[0],
                "mode": row["mode"], "op": row["op"], "hw": row["hw"]})
            if prior["desired"] != endpoints[0]:
                raise RuntimeError("mode-dependent endpoint for " + row["op"])
    missing = targets - set(selected)
    if missing:
        raise RuntimeError("current misses absent from endpoint score: " +
                           ", ".join(sorted(missing)))
    return selected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("controls")
    parser.add_argument("positive_allmode_score")
    parser.add_argument("current_misses")
    parser.add_argument("model")
    parser.add_argument("output")
    args = parser.parse_args()
    if os.path.exists(args.output):
        raise SystemExit("refusing to overwrite " + args.output)

    targets = current_r59_operands(args.current_misses)
    selected = positive_rows(args.positive_allmode_score, targets)
    with open(args.controls) as source:
        for row in csv.DictReader(source, delimiter="\t"):
            if row["op"] in selected:
                continue
            endpoint_matches = []
            if row["hw"] == row["fminus2"]:
                endpoint_matches.append("minus2")
            if row["hw"] == row["fplus1"]:
                endpoint_matches.append("plus1")
            if len(endpoint_matches) != 1:
                raise RuntimeError("ambiguous control endpoint for " + row["op"])
            selected[row["op"]] = {
                "label": "NEG", "desired": endpoint_matches[0],
                "mode": row["mode"], "op": row["op"], "hw": row["hw"]}

    for mode in ("rn", "rd", "ru", "rz"):
        operands = sorted(operand for operand, row in selected.items()
                          if row["mode"] == mode)
        for start in range(0, len(operands), 2000):
            chunk = operands[start:start + 2000]
            records = dump(args.model, mode, chunk)
            for operand, record in zip(chunk, records):
                if record["op"] != operand:
                    raise RuntimeError("dump desynchronization")
                selected[operand].update(record)

    required = ("theta", "k", "ce", "s4", "side", "b1", "b2", "low3",
                "dist", "rsh", "payload", "rscale", "dl", "dr", "dp",
                "umag", "S", "B", "Mreg", "t4", "sqlow", "rd3", "disc",
                "branch")
    kept = []
    skipped = []
    wrong = []
    for row in selected.values():
        if row["model"].lower() != row["hw"].lower():
            wrong.append(row["op"])
        if all(name in row for name in required):
            kept.append(row)
        else:
            skipped.append(row)
    target_kept = {row["op"] for row in kept if row["label"] == "POS"}
    if target_kept != targets:
        raise RuntimeError("current R59 targets did not all reach R59")
    if set(wrong) != targets:
        raise RuntimeError("current model mismatch set differs from targets: " +
                           ", ".join(sorted(set(wrong) ^ targets)))

    metadata = ("label", "desired", "mode", "op", "hw", "model")
    extras = sorted({key for row in kept for key in row}
                    - set(metadata) - set(required))
    columns = metadata + required + tuple(extras)
    with open(args.output, "w", newline="") as target:
        writer = csv.DictWriter(target, columns, delimiter="\t",
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sorted(kept, key=lambda row: (
            row["label"], row["branch"], row["op"])))
    print("rows", len(kept), "positive", len(target_kept),
          "negative", len(kept) - len(target_kept),
          "skipped_before_r59", len(skipped), "columns", len(columns))


if __name__ == "__main__":
    main()
