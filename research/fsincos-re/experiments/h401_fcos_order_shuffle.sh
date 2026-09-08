#!/bin/bash
# Preserved verbatim from the 2026-08-07 Round-54 pass; ran in
# /home/coduoserver/fsincos-residual-20260807-1 on the Skylake capture host.
# See notes/skylake-comparison.md (Round 54) and notes/residual-ideas.md.
# Idea 1: order/history dependence test on the FCOS terminal-adder sets.
# Capture identical inputs in original, reversed, and two shuffled orders;
# any per-input output difference proves predecessor dependence.
set -e
cd /home/coduoserver/fsincos-residual-20260807-1
CAPBIN=src/x87_capture
mkdir -p shuffle
python3 - <<'PYEOF'
import random
sets = {
  "h363": "capture-kit/inputs/constraint_fcos_terminal_neighbors_h363.txt",
  "h372": "capture-kit/inputs/constraint_fcos_scaled_tail_h372.txt",
  "h380": "capture-kit/inputs/constraint_fcos_payload_h380.txt",
  "h384": "capture-kit/inputs/constraint_fcos_payload_h384.txt",
}
for name, path in sets.items():
    lines = [l for l in open(path) if l.strip()]
    n = len(lines)
    with open(f"shuffle/{name}_orig.txt","w") as f: f.writelines(lines)
    with open(f"shuffle/{name}_rev.txt","w") as f: f.writelines(lines[::-1])
    for seed in (1,2):
        rng = random.Random(0xA5A5 + seed)
        perm = list(range(n)); rng.shuffle(perm)
        with open(f"shuffle/{name}_shuf{seed}.txt","w") as f:
            f.writelines(lines[p] for p in perm)
        with open(f"shuffle/{name}_shuf{seed}.perm","w") as f:
            f.write("\n".join(map(str,perm)))
    print(name, n)
PYEOF
for s in h363 h372 h380 h384; do
  for mode in rn rd ru; do
    for order in orig rev shuf1 shuf2; do
      $CAPBIN $mode cos --status < shuffle/${s}_${order}.txt > shuffle/${s}_${order}_${mode}.out
    done
  done
done
python3 - <<'PYEOF'
sets = ["h363","h372","h380","h384"]
total = 0
for s in sets:
    for mode in ("rn","rd","ru"):
        orig = open(f"shuffle/{s}_orig_{mode}.out").read().splitlines()
        n = len(orig)
        rev = open(f"shuffle/{s}_rev_{mode}.out").read().splitlines()[::-1]
        d_rev = sum(1 for a,b in zip(orig,rev) if a!=b)
        d_sh = []
        for seed in (1,2):
            perm = [int(x) for x in open(f"shuffle/{s}_shuf{seed}.perm")]
            sh = open(f"shuffle/{s}_shuf{seed}_{mode}.out").read().splitlines()
            un = [None]*n
            for pos, src in enumerate(perm): un[src] = sh[pos]
            d_sh.append(sum(1 for a,b in zip(orig,un) if a!=b))
        total += d_rev + sum(d_sh)
        print(s, mode, "n",n, "rev_diffs",d_rev, "shuf_diffs",d_sh)
print("TOTAL order-dependent differences:", total)
PYEOF
