#!/usr/bin/env python3
"""Localize the 29 upper FCOS residuals by causal stage perturbation.

This is a software-only inverse-response experiment.  For each reconstructed
producer (square, fourth power, odd/even Horner factor, terminal magnitude,
and retained terminal integer), nudge the significand by -4..+4 units and
score the resulting architectural outputs against the already cached four-
rounding-mode hardware truth.  A common response identifies an arithmetic
stage worth reconstructing; it is not itself a correction rule.
"""

import argparse
import csv
import os
import subprocess
from collections import defaultdict


MODES = ("rn", "rd", "ru", "rz")
TARGETS = ("odd", "even", "sq", "f4", "mag", "umag")


def read_truth(path):
    truth = {}
    with open(path) as source:
        for row in csv.DictReader(source, delimiter="\t"):
            key = (row["mode"], row["op"].lower())
            if key in truth and truth[key] != row["hw"].lower():
                raise AssertionError("conflicting cached truth for %r" %
                                     (key,))
            truth[key] = row["hw"].lower()
    operands = sorted({operand for _, operand in truth})
    for operand in operands:
        missing = [mode for mode in MODES if (mode, operand) not in truth]
        if missing:
            raise AssertionError("missing modes for %s: %s" %
                                 (operand, ",".join(missing)))
    return truth, operands


def run(binary, mode, operands, target, delta):
    command = [binary, "--batch", "--fcos-standalone",
               "--perturb=%s:%d" % (target, delta)]
    if mode != "rn":
        command.insert(2, "--rc=" + mode)
    process = subprocess.run(command, input="\n".join(operands) + "\n",
                             capture_output=True, text=True, check=True)
    outputs = []
    for line in process.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[0] == "OK":
            outputs.append(fields[1].lower() + ":" + fields[2].lower())
    if len(outputs) != len(operands):
        raise RuntimeError("output count mismatch for %s/%s/%d" %
                           (mode, target, delta))
    return outputs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("model")
    parser.add_argument("allmode_truth")
    parser.add_argument("output")
    args = parser.parse_args()
    if os.path.exists(args.output):
        raise SystemExit("refusing to overwrite " + args.output)

    truth, operands = read_truth(args.allmode_truth)
    matches = defaultdict(set)
    scores = []
    for target in TARGETS:
        for delta in range(-4, 5):
            exact_legs = 0
            exact_by_operand = defaultdict(int)
            for mode in MODES:
                outputs = run(args.model, mode, operands, target, delta)
                for operand, output in zip(operands, outputs):
                    if output == truth[mode, operand]:
                        exact_legs += 1
                        exact_by_operand[operand] += 1
            exact_operands = sum(value == len(MODES)
                                 for value in exact_by_operand.values())
            scores.append((exact_operands, exact_legs, target, delta))
            for operand, count in exact_by_operand.items():
                if count == len(MODES):
                    matches[operand].add((target, delta))
            print(target, delta, "exact", exact_operands, "/", len(operands),
                  "operands", exact_legs, "/", len(operands) * len(MODES),
                  "legs", flush=True)

    scores.sort(key=lambda item: (-item[0], -item[1], item[2],
                                  abs(item[3]), item[3]))
    with open(args.output, "x") as target:
        target.write("operands\t%d\nlegs\t%d\ntargets\t%d\n" %
                     (len(operands), len(operands) * len(MODES),
                      len(TARGETS) * 9))
        target.write("\n[variant ranking]\n")
        target.write("exact_operands\texact_legs\ttarget\tdelta\n")
        for score in scores:
            target.write("%d\t%d\t%s\t%d\n" % score)
        target.write("\n[all-mode exact variants per operand]\n")
        target.write("op\tcount\tvariants\n")
        for operand in operands:
            variants = sorted(matches[operand],
                              key=lambda item: (item[0], abs(item[1]), item[1]))
            rendered = ",".join("%s:%+d" % variant for variant in variants)
            target.write("%s\t%d\t%s\n" %
                         (operand, len(variants), rendered or "-"))
    print("wrote", args.output, "best", scores[0], flush=True)


if __name__ == "__main__":
    main()
