#!/usr/bin/env python3
"""h998: dense i7 perturbation capture around surviving R95 misses.

Run this script in /root/r84 on the hardware host.  Neighboring 80-bit input
significands are captured in all four rounding modes and compared with R95.
The dense delta coordinate is retained so periodic selector structure is not
destroyed by corpus sampling.
"""

import subprocess


MODES = ("rn", "rd", "ru", "rz")
RADIUS = 8192
SEEDS = (
    ("3ff9", "f7437a29cc70e000"),
    ("3ffc", "8879c27dc768d240"),
    ("4005", "8a84264a7624864c"),
    ("4008", "840130665ed728a9"),
)


def run(args, operands):
    process = subprocess.run(args, input="\n".join(operands) + "\n",
                             capture_output=True, text=True, check=True)
    rows = []
    for line in process.stdout.splitlines():
        fields = line.split()
        if fields[0] == "OK":
            rows.append((fields[1].lower(), fields[2].lower()))
        else:
            # Model batch output has no OK prefix.
            rows.append((fields[1].lower(), fields[2].lower()))
    if len(rows) != len(operands):
        raise RuntimeError("output length mismatch: %d != %d for %r" %
                           (len(rows), len(operands), args))
    return rows


operands = []
coordinates = []
for seed_index, (se, sigtext) in enumerate(SEEDS):
    seed = int(sigtext, 16)
    for delta in range(-RADIUS, RADIUS + 1):
        sig = seed + delta
        if not (1 << 63) <= sig < (1 << 64):
            continue
        operands.append("%s %016x" % (se, sig))
        coordinates.append((seed_index, delta))

hardware = {}
model = {}
for mode in MODES:
    hardware[mode] = run(
        ["/root/x87_capture_x86_64", mode, "cos"], operands)
    args = ["./model_r95", "--batch", "--fcos-standalone"]
    if mode != "rn":
        args.insert(2, "--rc=" + mode)
    model[mode] = run(args, operands)


with open("h998_neighborhood.tsv", "w") as out:
    out.write("seed\tdelta\top\t" + "\t".join(
        "m_%s\th_%s" % (mode, mode) for mode in MODES) + "\n")
    for index, operand in enumerate(operands):
        values = []
        for mode in MODES:
            values.extend(("%s:%s" % model[mode][index],
                           "%s:%s" % hardware[mode][index]))
        out.write("%d\t%d\t%s\t%s\n" %
                  (*coordinates[index], operand, "\t".join(values)))

print("wrote", len(operands), "operands")
