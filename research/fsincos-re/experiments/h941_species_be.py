#!/usr/bin/env python3
# h941: classify the h940 in-stratum species (would-be v2 collateral)
# by B_e and full frame features; emit per-row vectors for the
# discriminant search.  Usage: h941_species_be.py
import subprocess, sys
from collections import Counter

# distinct (insn, input) over species rows
seen = {}
for ln in open("h940_species.tsv"):
    t = ln.rstrip("\n").split("\t")
    if len(t) != 9: continue
    seen.setdefault((t[2], t[5]), []).append(t[3])
print("species legs:", sum(len(v) for v in seen.values()),
      "distinct (insn,op):", len(seen), file=sys.stderr)
for insn in ("cos", "sin"):
    inps = [op for (i, op), _ in seen.items() if i == insn]
    with open("h941_%s_inp.txt" % insn, "w") as f:
        f.write("\n".join(inps) + "\n")
    print(insn, len(inps), file=sys.stderr)
