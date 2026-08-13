#!/usr/bin/env python3
"""h459: controlled-predecessor capture — is the borrow bit carried in
from the PREVIOUS operation?

h457's fresh i7 capture flipped 15 corpus fires OFF and 9 corpus
controls ON (same machine, same inputs, different surrounding input
stream).  The one uncontrolled variable between runs is the execution
context: the capture runner streams inputs through the FPU
back-to-back, so each input executes with datapath state left by its
predecessor.  Stale cross-instruction state would explain at a stroke
why every per-input basis (h429-h458) failed while within-run behavior
looked deterministic (h413).

Design: for each probe input X (all 24 flipped rows + stable-fire and
stable-control samples), emit blocks [N, N, P, X] where N is a fixed
neutral flush input and P sweeps a predecessor panel:
  N itself (baseline), X (self), X's corpus2-run predecessor (when X
  came from corpus2), X's h457-run predecessor (the preceding manifest
  line), and samples of fire / control / plain inputs.
Only X's line (block offset 3) is read at analysis time.  If fire-ness
of X varies with P, cross-instruction state is PROVEN and the panel
begins mapping which property of P matters.

Outputs in h459_package/: probes.tsv, blocks.txt (capture stdin),
manifest.tsv (block -> probe id, predecessor id), run_h459.sh.

Run from /tmp/stageA (after h457's analysis artifacts exist).
"""
import os
import random

from multiprocessing import Pool
from h457_analyze_capture import (
    load_manifest, load_captures, model_terminal, MODES)

PKG = "h459_package"
NEUTRAL = (0x3FFC, 0x8000000000000000)      # x = 0.125, fixed flush value


def base_fire_states():
    """h457 capture: per base target -> (role, se, sig, fired_now)."""
    roles = {}
    with open("h456_package/targets.tsv") as fh:
        fh.readline()
        for line in fh:
            c = line.split()
            roles[c[0]] = c[1]
    entries = load_manifest()
    hw = load_captures(False, entries)
    out = {}
    prev_input = {}
    last = None
    for i, (n, target, bit, se, sig) in enumerate(entries):
        if bit == -1:
            prev_input[target] = last
        last = (se, sig)
        if bit != -1:
            continue
        _, res = model_terminal(se, sig)
        fired = 0 if all(res[0][m] == hw[i][m] for m in MODES) else 1
        out[target] = (roles[target], se, sig, fired)
    return out, prev_input


def corpus2_predecessors():
    """input -> its immediate predecessor in the corpus2 capture order."""
    lines = [l.split() for l in open("corpus2/selected_inputs.txt")]
    pred = {}
    for i in range(1, len(lines)):
        key = (int(lines[i][0], 16) & 0x7FFF, int(lines[i][1], 16))
        pred[key] = (int(lines[i - 1][0], 16) & 0x7FFF,
                     int(lines[i - 1][1], 16))
    return pred


def main():
    states, prev_input = base_fire_states()
    c2pred = corpus2_predecessors()
    rng = random.Random(459)

    flipped_fire = [(t, se, sig) for t, (r, se, sig, f) in states.items()
                    if r == "fire" and not f]
    flipped_ctrl = [(t, se, sig) for t, (r, se, sig, f) in states.items()
                    if r == "control" and f]
    stable_fire = [(t, se, sig) for t, (r, se, sig, f) in states.items()
                   if r == "fire" and f]
    stable_ctrl = [(t, se, sig) for t, (r, se, sig, f) in states.items()
                   if r == "control" and not f]
    probes = (flipped_fire + flipped_ctrl
              + rng.sample(stable_fire, 12) + rng.sample(stable_ctrl, 12))
    print(f"probes: {len(flipped_fire)} flipped-fire, "
          f"{len(flipped_ctrl)} flipped-control, 12+12 stable")

    fire_pool = rng.sample(stable_fire, 12)
    ctrl_pool = rng.sample(stable_ctrl, 8)
    plain_pool = [(f"R{i}", 0x3FFC, rng.getrandbits(63) | (1 << 63))
                  for i in range(8)]

    blocks = []
    manifest = []
    os.makedirs(PKG, exist_ok=True)
    with open(f"{PKG}/probes.tsv", "w") as fh:
        fh.write("target\tclass\tse\tsig\n")
        for group, name in ((flipped_fire, "flipped_fire"),
                            (flipped_ctrl, "flipped_control"),
                            (probes[len(flipped_fire) + len(flipped_ctrl):
                                    len(flipped_fire) + len(flipped_ctrl) + 12],
                             "stable_fire"),
                            (probes[-12:], "stable_control")):
            for t, se, sig in group:
                fh.write(f"{t}\t{name}\t{se:x}\t{sig:016x}\n")

    for t, se, sig in probes:
        panel = [("N", NEUTRAL), ("self", (se, sig))]
        key = (se, sig)
        if key in c2pred:
            panel.append(("c2pred", c2pred[key]))
        if prev_input.get(t):
            panel.append(("h457pred", prev_input[t]))
        for i, (pt, pse, psig) in enumerate(fire_pool):
            panel.append((f"fire{i}", (pse, psig)))
        for i, (pt, pse, psig) in enumerate(ctrl_pool):
            panel.append((f"ctrl{i}", (pse, psig)))
        for name, pse, psig in plain_pool:
            panel.append((name, (pse, psig)))
        for pname, (pse, psig) in panel:
            block_no = len(manifest)
            manifest.append((block_no, t, pname))
            blocks.append(f"{NEUTRAL[0]:x} {NEUTRAL[1]:016x}")
            blocks.append(f"{NEUTRAL[0]:x} {NEUTRAL[1]:016x}")
            blocks.append(f"{pse:x} {psig:016x}")
            blocks.append(f"{se:x} {sig:016x}")

    with open(f"{PKG}/blocks.txt", "w") as fh:
        fh.write("\n".join(blocks) + "\n")
    with open(f"{PKG}/manifest.tsv", "w") as fh:
        fh.write("block\ttarget\tpredecessor\n")
        for block_no, t, pname in manifest:
            fh.write(f"{block_no}\t{t}\t{pname}\n")
    n = len(blocks)
    with open(f"{PKG}/run_h459.sh", "w") as fh:
        fh.write(f"""#!/bin/sh
# h459 controlled-predecessor capture: {n} lines x rn/rd/ru.
cd "$(dirname "$0")"
RUNNER=/root/x87_capture_x86_64
for mode in rn rd ru; do
    taskset -c 2 "$RUNNER" cos "$mode" --status \\
        < blocks.txt > "cos_${{mode}}_status.txt" || exit 1
    lines=$(wc -l < "cos_${{mode}}_status.txt")
    [ "$lines" -eq {n} ] || {{ echo "BAD count $mode: $lines"; exit 1; }}
done
echo DONE > h459.done
""")
    os.chmod(f"{PKG}/run_h459.sh", 0o755)
    print(f"blocks: {len(manifest)}, capture lines: {n}")


if __name__ == "__main__":
    main()
