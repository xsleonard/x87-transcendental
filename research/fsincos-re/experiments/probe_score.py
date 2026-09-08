import sys, collections
ts, tag = sys.argv[1:3]
keys = collections.defaultdict(list)
for line in open("/root/r84/probe_keys.tsv"):
    insn, mode, se, mant, hse, hsig = line.split()
    keys[(insn, mode)].append((se, mant, hse, hsig))
tot = match = 0
flips = []
for (insn, mode), rows in keys.items():
    cap = open(f"/root/r84/probe_out_{insn}_{mode}.txt").read().splitlines()
    assert len(cap) == len(rows)
    for (se, mant, hse, hsig), line in zip(rows, cap):
        t = line.split()
        tot += 1
        if t[0] == "OK" and t[1] == hse and t[2] == hsig: match += 1
        else: flips.append(f"{insn}/{mode}/{se}:{mant}->{line.strip()}")
print(f"{ts} {tag} ledger-keys match={match}/{tot}" + (" FLIPS: " + "; ".join(flips) if flips else ""))
