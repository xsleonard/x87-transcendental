#!/usr/bin/env python3
"""h462 analysis: fire outcome per probe per context condition.

Conditions per probe (see h462_context_replay.py): selfp/selfn (current
sign, neutral context), p1/p1f (exact signed immediate predecessor and
its sign-flip), w8/w32 (8- and 32-deep exact corpus replays).  A probe
is scored FIRE when the hardware result at its line differs from the
bit-exact model in any mode.  The corpus outcome (fires) and the h456
bases-run outcome (no fire, for flipped probes) bracket the conditions:
the shallowest condition that reproduces the corpus outcome measures
the carried state's depth.

Run from /tmp/stageA.
"""
from collections import defaultdict

from h457_analyze_capture import model_terminal, MODES

PKG = "h462_package"


def main():
    probes = {}
    with open(f"{PKG}/probes.tsv") as fh:
        fh.readline()
        for line in fh:
            name, kind, idx, se, sig = line.split()
            probes[name] = (kind, int(se, 16), int(sig, 16))
    manifest = []
    with open(f"{PKG}/manifest.tsv") as fh:
        fh.readline()
        for line in fh:
            line_no, probe, cond = line.split()
            manifest.append((int(line_no), probe, cond))
    captures = {m: open(f"{PKG}/cos_{m}.txt").read().splitlines()
                for m in MODES}

    model_cache = {}
    table = defaultdict(dict)
    for line_no, probe, cond in manifest:
        kind, se, sig = probes[probe]
        key = (se & 0x7FFF, sig)          # model is sign-blind (cos even)
        if key not in model_cache:
            _, res = model_terminal(*key)
            model_cache[key] = {m: res[0][m] for m in MODES}
        fired = 0
        for m in MODES:
            tokens = captures[m][line_no].split()
            hw_sig = int(tokens[2], 16) if tokens[0] == "OK" else -1
            if hw_sig != model_cache[key][m]:
                fired = 1
        table[probe][cond] = fired

    conds = ["selfp", "selfn", "p1", "p1f", "w8", "w32"]
    print(f"{'probe':12s} {'kind':13s} " + "  ".join(f"{c:5s}" for c in conds))
    for probe in sorted(table, key=lambda p: (probes[p][0], p)):
        kind = probes[probe][0]
        row = "  ".join(f"{table[probe].get(c, '?')!s:5s}" for c in conds)
        print(f"{probe:12s} {kind:13s} {row}")


if __name__ == "__main__":
    main()
