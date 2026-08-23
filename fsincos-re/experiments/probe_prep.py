import collections
groups = collections.defaultdict(list)
for line in open("/root/r84/probe_keys.tsv"):
    insn, mode, se, mant, hse, hsig = line.split()
    groups[(insn, mode)].append((se, mant))
for (insn, mode), ops in groups.items():
    with open(f"/root/r84/probe_in_{insn}_{mode}.txt", "w") as f:
        for se, mant in ops:
            f.write(f"{se} {mant}\n")
