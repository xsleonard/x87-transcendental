#!/usr/bin/env python3
"""h1000: balanced dense neighborhoods around three R95 residual arms.

Run on the i7 in /root/r84.  The seeds are hardware-verified R95 misses from
distinct h975 cells.  A smaller neighborhood than h998 is sufficient once
many seeds are sampled.  All modes are retained so default-off force probes
can identify visible candidate corrections without re-capturing silicon.
"""

import subprocess


MODES = ("rn", "rd", "ru", "rz")
RADIUS = 4096
SEEDS = (
    # Upper ladder, inactive, required value-frame n=-1.
    ("top0", "c03c", "efefc12969ab67c3"),
    ("top0", "c03b", "e7ec944d39789826"),
    ("top0", "c030", "e1d17778aa7b8c00"),
    ("top0", "c02e", "ec243027816f6f64"),
    ("top0", "c029", "f426cb0b03b3ec00"),
    ("top0", "c026", "85522fe25ef73dd0"),
    ("top0", "c022", "e7d457b32e276a78"),
    ("top0", "c01e", "baa6bac843169129"),
    ("top0", "c01c", "97f6c7a0b60571c0"),
    ("top0", "c01b", "d7f76a523515f853"),
    ("top0", "c01a", "bf13525bb9c39624"),
    ("top0", "c015", "ca646001d145e540"),

    # Upper ladder, active, required value-frame n=-1.
    ("top1", "c03d", "f2c2f46ae23a6694"),
    ("top1", "c03d", "d729e6a9105c4e80"),
    ("top1", "c03d", "9bcd835df57792c3"),
    ("top1", "c032", "f2d715b39f800000"),
    ("top1", "c031", "ea6e24d420e25c32"),
    ("top1", "c02f", "e0fd4bb0d01245f4"),
    ("top1", "c02e", "8409b1ba049c2dc0"),
    ("top1", "c029", "ef7d95f051f00000"),
    ("top1", "c027", "ed1ce212a1bdb800"),
    ("top1", "c027", "b3412100d2f2eeb9"),
    ("top1", "c027", "84721d6190b9fc00"),
    ("top1", "c023", "c44091a2c203be9d"),

    # Lower ladder, active, required value-frame n=+1.
    ("low1", "c038", "9aa33e791b211680"),
    ("low1", "c037", "f78c70d8153ecc00"),
    ("low1", "c02a", "cc6d3eb72512db27"),
    ("low1", "c025", "c77ff079c044d200"),
    ("low1", "c024", "d1bab6fbebfd8000"),
    ("low1", "c023", "fb1d18d0099b3000"),
    ("low1", "c002", "fdbddd6fa1a4f4bb"),
    ("low1", "bffb", "fa9a43ba38161290"),
    ("low1", "bffb", "8f2042c45171bcf1"),
)


def run(args, operands):
    process = subprocess.run(args, input="\n".join(operands) + "\n",
                             capture_output=True, text=True, check=True)
    rows = []
    for line in process.stdout.splitlines():
        fields = line.split()
        rows.append((fields[1].lower(), fields[2].lower()))
    if len(rows) != len(operands):
        raise RuntimeError("output length mismatch: %d != %d for %r" %
                           (len(rows), len(operands), args))
    return rows


operands = []
coordinates = []
for seed_index, (family, se, sigtext) in enumerate(SEEDS):
    seed = int(sigtext, 16)
    for delta in range(-RADIUS, RADIUS + 1):
        sig = seed + delta
        if not (1 << 63) <= sig < (1 << 64):
            continue
        operands.append("%s %016x" % (se, sig))
        coordinates.append((seed_index, family, delta))

hardware = {}
model = {}
for mode in MODES:
    hardware[mode] = run(
        ["/root/x87_capture_x86_64", mode, "cos"], operands)
    args = ["./model_r95", "--batch", "--fcos-standalone"]
    if mode != "rn":
        args.insert(2, "--rc=" + mode)
    model[mode] = run(args, operands)


with open("h1000_sensitive_neighborhoods.tsv", "w") as out:
    out.write("seed\tfamily\tdelta\top\t" + "\t".join(
        "m_%s\th_%s" % (mode, mode) for mode in MODES) + "\n")
    for index, operand in enumerate(operands):
        values = []
        for mode in MODES:
            values.extend(("%s:%s" % model[mode][index],
                           "%s:%s" % hardware[mode][index]))
        out.write("%d\t%s\t%d\t%s\t%s\n" %
                  (*coordinates[index], operand, "\t".join(values)))

print("wrote", len(operands), "operands")
