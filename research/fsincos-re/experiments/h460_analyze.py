#!/usr/bin/env python3
"""h460 analysis: does the fire set depend on core or frequency?

For each condition (core0..core3 default, core2 at 800 MHz, core2 at
4.0 GHz, core2 default repeated), compute the fire set over the 3,455
base inputs (hardware vs bit-exact model, any mode) and compare:

  - identical fire sets across all conditions => the day-scale drift is
    not core- or frequency-linked (points at temperature/aging/
    microcode-era state);
  - per-core differences => physical per-core variation of the marginal
    path;
  - frequency-linked differences => timing-marginal carry path PROVEN
    (the boundary-confined fires are the adder's longest borrow
    propagations, i.e. its critical path).

Run from /tmp/stageA.
"""
from h457_analyze_capture import model_terminal, MODES

PKG = "h460_package"
CONDITIONS = ["core0", "core1", "core2", "core3",
              "freq800", "freq4000", "core2rep"]


def main():
    bases = []
    for line in open(f"{PKG}/bases.txt"):
        se, sig = line.split()
        bases.append((int(se, 16), int(sig, 16)))
    model = []
    for se, sig in bases:
        _, res = model_terminal(se, sig)
        model.append({m: res[0][m] for m in MODES})

    fire_sets = {}
    for cond in CONDITIONS:
        captures = {m: open(f"{PKG}/cos_{cond}_{m}.txt").read().splitlines()
                    for m in MODES}
        fires = set()
        for i in range(len(bases)):
            for m in MODES:
                tokens = captures[m][i].split()
                hw_sig = int(tokens[2], 16) if tokens[0] == "OK" else -1
                if hw_sig != model[i][m]:
                    fires.add(i)
                    break
        fire_sets[cond] = fires
        print(f"{cond:9s}: {len(fires)} fires")

    reference = fire_sets["core2"]
    print("\npairwise differences vs core2 (default):")
    for cond in CONDITIONS:
        if cond == "core2":
            continue
        gained = fire_sets[cond] - reference
        lost = reference - fire_sets[cond]
        print(f"  {cond:9s}: +{len(gained)} fires, -{len(lost)} fires")
        for i in sorted(gained)[:6]:
            print(f"      gained: line {i} "
                  f"{bases[i][0]:x}:{bases[i][1]:016x}")
        for i in sorted(lost)[:6]:
            print(f"      lost:   line {i} "
                  f"{bases[i][0]:x}:{bases[i][1]:016x}")


if __name__ == "__main__":
    main()
