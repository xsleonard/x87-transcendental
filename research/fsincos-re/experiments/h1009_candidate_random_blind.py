#!/usr/bin/env python3
"""h1009: model-filtered blind random validation of frozen R96.

Generate deterministic ordinary in-range operands that were not used during
discovery.  Filter only on candidate-vs-R95 output differences, then ask the
Skylake hardware for all four legs of every selected operand.
"""

import random
import subprocess
from collections import Counter


MODES = ("rn", "rd", "ru", "rz")
COUNT_PER_INSN = 1000000
CHUNK = 100000
SEED = 0x1009A5EED


def run(args, operands):
    process = subprocess.run(args, input="\n".join(operands) + "\n",
                             capture_output=True, text=True, check=True)
    output = []
    for line in process.stdout.splitlines():
        fields = line.split()
        output.append("%s:%s" % (fields[1].lower(), fields[2].lower()))
    if len(output) != len(operands):
        raise RuntimeError("output length mismatch")
    return output


generator = random.Random(SEED)
selected = {}
for insn in ("cos", "sin"):
    flag = "--f%s-standalone" % insn
    for start in range(0, COUNT_PER_INSN, CHUNK):
        count = min(CHUNK, COUNT_PER_INSN - start)
        operands = []
        for _ in range(count):
            sign = generator.getrandbits(1)
            exponent = generator.randrange(0x3FFF, 0x403E)
            significand = (1 << 63) | generator.getrandbits(63)
            operands.append("%04x %016x" %
                            ((sign << 15) | exponent, significand))
        mode_outputs = {}
        for mode in MODES:
            base_args = ["./model_r95", "--batch", flag]
            candidate_args = ["./model_r96_res1024", "--batch", flag]
            if mode != "rn":
                base_args.insert(2, "--rc=" + mode)
                candidate_args.insert(2, "--rc=" + mode)
            mode_outputs[mode] = (
                run(base_args, operands), run(candidate_args, operands))
        for index, operand in enumerate(operands):
            if any(mode_outputs[mode][0][index]
                   != mode_outputs[mode][1][index] for mode in MODES):
                selected[(insn, operand)] = {
                    mode: (mode_outputs[mode][0][index],
                           mode_outputs[mode][1][index])
                    for mode in MODES
                }
        print(insn, start + count, "selected", len(selected), flush=True)

totals = Counter()
rows = []
for insn in ("cos", "sin"):
    keys = sorted(key for key in selected if key[0] == insn)
    operands = [key[1] for key in keys]
    hardware = {
        mode: run(["/root/x87_capture_x86_64", mode, insn], operands)
        for mode in MODES
    }
    for index, key in enumerate(keys):
        for mode in MODES:
            before, after = selected[key][mode]
            if before == after:
                continue
            actual = hardware[mode][index]
            if after == actual and before != actual:
                outcome = "FIX"
            elif before == actual and after != actual:
                outcome = "BREAK"
            else:
                outcome = "OTHER"
            totals[outcome] += 1
            rows.append((outcome, key[0], mode, key[1],
                         actual, before, after))

with open("h1009_candidate_random_changes.tsv", "w") as out:
    out.write("outcome\tinsn\tmode\top\thw\tbase\tcandidate\n")
    for row in rows:
        out.write("\t".join(row) + "\n")

print("generated", 2 * COUNT_PER_INSN,
      "selected operands", len(selected),
      "changed legs", len(rows), dict(totals))
