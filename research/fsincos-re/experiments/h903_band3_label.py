#!/usr/bin/env python3
# Phase 3 labeling: capture hw for every UNLAB hit row, label
# carry/nocarry against the banked A/B outputs, write
# band3_hits_labeled.tsv in the band_hits.tsv format.
import subprocess, collections, os

hits = []
for l in open("band3_hits.tsv"):
    t = l.rstrip("\n").split("\t")
    # UNLAB chunk insn mode line "se sig" A B ?
    hits.append(t)

groups = collections.defaultdict(list)
for t in hits:
    groups[(t[2], t[3])].append(t)

def norm3(line):
    f = line.split()
    return " ".join(f[:3]) if f and f[0] == "OK" else (f[0] if f else "")

out = open("band3_hits_labeled.tsv", "w")
counts = collections.Counter()
for (insn, mode), g in groups.items():
    opf = "band3_ops_%s_%s.txt" % (insn, mode)
    with open(opf, "w") as f:
        for t in g:
            f.write(t[5] + "\n")
    hwf = "band3_hw_%s_%s.txt" % (insn, mode)
    with open(opf) as fi, open(hwf, "w") as fo:
        subprocess.run(["/root/x87_capture_x86_64", mode, insn],
                       stdin=fi, stdout=fo, check=True)
    with open(hwf) as f:
        hwlines = f.read().splitlines()
    assert len(hwlines) == len(g), (insn, mode, len(hwlines), len(g))
    for t, hw in zip(g, hwlines):
        hs = norm3(hw)
        a = norm3(t[6])
        b = norm3(t[7])
        lab = "CARRY" if hs == b else ("NOCARRY" if hs == a else "OTHER")
        counts[lab] += 1
        out.write("\t".join([lab, t[1], t[2], t[3], t[4], t[5], a, b, hs]) + "\n")
    os.remove(opf)
    os.remove(hwf)
out.close()
print("labeled:", dict(counts))
