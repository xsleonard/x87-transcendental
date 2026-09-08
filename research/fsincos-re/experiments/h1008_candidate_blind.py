#!/usr/bin/env python3
"""h1008: frozen R96 candidate, fresh silicon neighborhoods.

Run on the authorized i7 from /root/r84 after compiling the frozen source as
model_r96_res1024.  The seeds are all 41 union operands selected by h1006;
none of the neighboring operands contributed to the rule.
"""

import subprocess
from collections import Counter, defaultdict


MODES = ("rn", "rd", "ru", "rz")
RADIUS = 4096
SEEDS = (
    ("cos", "3ffb", "834bc567b2701400"),
    ("cos", "3ffb", "c504fa716d81e2fa"),
    ("cos", "4011", "f8217159750f6800"),
    ("cos", "4030", "a3bcf3b3b1790e00"),
    ("cos", "bffa", "c487210a9abfd700"),
    ("cos", "bffa", "d6b05a389f368540"),
    ("cos", "bffb", "c7180b5b3a180000"),
    ("cos", "3ffb", "b7a3e021b86a2c26"),
    ("cos", "4010", "d79dc27a15070800"),
    ("cos", "4011", "f217c1d920ebcf2e"),
    ("cos", "4020", "86880d1a5bec75a9"),
    ("cos", "bffb", "8190e142e0000000"),
    ("cos", "c01e", "c1ba06751d721211"),
    ("cos", "c029", "82ca6b940977d41d"),
    ("cos", "c038", "c5b6c31baca64e7f"),
    ("cos", "4000", "cdce6262d1000000"),
    ("cos", "400a", "abcd2a72c5e0a077"),
    ("cos", "401d", "8aba754cca800000"),
    ("cos", "4026", "acc1f08cd1eb04cf"),
    ("cos", "403a", "ed693071012e6361"),
    ("cos", "bffb", "b5e64f92d5d0ec68"),
    ("cos", "bffb", "b945f190ecee39df"),
    ("cos", "c00f", "c18bac6fd88da6f6"),
    ("cos", "c022", "e6db5daf71f5de00"),
    ("sin", "c032", "b2d7fb2a1b0b211d"),
    ("sin", "400d", "fac6905b2f577000"),
    ("sin", "401f", "85b3fbc6fa856cbc"),
    ("sin", "c01c", "f4c083adfd655400"),
    ("sin", "c033", "db6accb6b7ac615a"),
    ("sin", "4016", "f01992cddd0fa200"),
    ("sin", "4020", "ffd66a97148e942a"),
    ("sin", "4029", "bd7ef3c439c10fd8"),
    ("sin", "c006", "a4fd2b0bd97697df"),
    ("sin", "c008", "c58d2cfb39437a2c"),
    ("sin", "c00d", "c70fe689352f2f2d"),
    ("sin", "c00d", "e927431cdbe8fb00"),
    ("sin", "c01f", "8f9cd08417e81ca5"),
    ("sin", "c01f", "96e92d16a50ed380"),
    ("sin", "c02b", "cd140fdcb22bdf10"),
    ("sin", "c039", "c8f0e3cb8e0a0000"),
    ("sin", "c03b", "907618f149c6720b"),
)


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


by_insn = defaultdict(list)
for seed_index, (insn, se, sigtext) in enumerate(SEEDS):
    center = int(sigtext, 16)
    for delta in range(-RADIUS, RADIUS + 1):
        sig = center + delta
        if (1 << 63) <= sig < (1 << 64):
            by_insn[insn].append(
                (seed_index, delta, "%s %016x" % (se, sig)))

totals = Counter()
changed = []
for insn, points in sorted(by_insn.items()):
    operands = [point[2] for point in points]
    flag = "--f%s-standalone" % insn
    for mode in MODES:
        capture = run(["/root/x87_capture_x86_64", mode, insn],
                      operands)
        base_args = ["./model_r95", "--batch", flag]
        candidate_args = ["./model_r96_res1024", "--batch", flag]
        if mode != "rn":
            base_args.insert(2, "--rc=" + mode)
            candidate_args.insert(2, "--rc=" + mode)
        baseline = run(base_args, operands)
        candidate = run(candidate_args, operands)
        for point, hardware, before, after in zip(
                points, capture, baseline, candidate):
            if before == after:
                continue
            if after == hardware and before != hardware:
                outcome = "FIX"
            elif before == hardware and after != hardware:
                outcome = "BREAK"
            else:
                outcome = "OTHER"
            totals[outcome] += 1
            changed.append((outcome, insn, mode, point[0], point[1],
                            point[2], hardware, before, after))

with open("h1008_candidate_changes.tsv", "w") as out:
    out.write("outcome\tinsn\tmode\tseed\tdelta\top\thw\tbase\tcandidate\n")
    for row in changed:
        out.write("\t".join(map(str, row)) + "\n")

print("operands", sum(map(len, by_insn.values())),
      "legs", 4 * sum(map(len, by_insn.values())))
print("candidate changes", len(changed), dict(totals))
print("changed operands", len({(row[3], row[4]) for row in changed}))
