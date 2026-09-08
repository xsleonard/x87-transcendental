#!/usr/bin/env python3
"""h459 analysis: fire-ness of each probe input as a function of its
controlled predecessor.

Reads h459_package/{manifest.tsv,probes.tsv,cos_*_status.txt}; each
block is [N, N, P, X] so X's hardware result is the block's 4th line.
For each probe X: compute the bit-exact model result once, then print
the fire/no-fire outcome per predecessor.  A probe whose outcome varies
across predecessors proves cross-instruction state; the pattern over
the panel (which predecessors induce the fire) is the first map of what
the stale state is.

Run from /tmp/stageA.
"""
from collections import defaultdict

from h457_analyze_capture import model_terminal, MODES

PKG = "h459_package"


def main():
    manifest = []
    with open(f"{PKG}/manifest.tsv") as fh:
        fh.readline()
        for line in fh:
            block, target, pred = line.split()
            manifest.append((int(block), target, pred))
    probes = {}
    with open(f"{PKG}/probes.tsv") as fh:
        fh.readline()
        for line in fh:
            t, cls, se, sig = line.split()
            probes[t] = (cls, int(se, 16), int(sig, 16))
    captures = {}
    for mode in MODES:
        captures[mode] = open(f"{PKG}/cos_{mode}_status.txt").read().splitlines()

    model_cache = {}
    outcomes = defaultdict(dict)
    for block, target, pred in manifest:
        cls, se, sig = probes[target]
        if target not in model_cache:
            _, res = model_terminal(se, sig)
            model_cache[target] = {m: res[0][m] for m in MODES}
        line_no = block * 4 + 3
        fired = 0
        for m in MODES:
            tokens = captures[m][line_no].split()
            hw_sig = int(tokens[2], 16) if tokens[0] == "OK" else -1
            if hw_sig != model_cache[target][m]:
                fired = 1
        outcomes[target][pred] = fired

    print("probe            class            fires-as: "
          "(predecessors -> outcome)")
    n_varying = 0
    for target, preds in outcomes.items():
        cls = probes[target][0]
        values = set(preds.values())
        varying = len(values) > 1
        n_varying += varying
        fire_preds = sorted(p for p, f in preds.items() if f)
        nofire_preds = sorted(p for p, f in preds.items() if not f)
        tag = "VARIES" if varying else ("always-FIRE" if 1 in values
                                        else "never-fires")
        print(f"{target}  {cls:16s} {tag}")
        if varying:
            print(f"    fire under   : {' '.join(fire_preds)}")
            print(f"    no fire under: {' '.join(nofire_preds)}")
    print(f"\nprobes with predecessor-dependent outcome: "
          f"{n_varying}/{len(outcomes)}")


if __name__ == "__main__":
    main()
