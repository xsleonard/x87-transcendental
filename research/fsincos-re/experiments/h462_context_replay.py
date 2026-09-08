#!/usr/bin/env python3
"""h462: context-replay capture — how deep is the carried state?

Established so far (h457-h461): the machine is byte-for-byte
deterministic when the FULL corpus2 input stream is replayed (h461),
yet 15 corpus fires vanish and 9 new ones appear when the same inputs
are captured in a different order (h456/h460), and a depth-1
predecessor restoration with sign-stripped inputs does not bring them
back (h459).  Therefore the borrow bit at collision states reads
execution context — deeper than one instruction and/or sign-sensitive
(h459 stripped signs; corpus inputs carry random signs).

Design: for every corpus2-sourced flipped probe X at corpus index i
(plus stable anchors), capture blocks:

  selfp / selfn : [N N N +X], [N N N -X]     current-sign dependence
  p1            : [N N P X]   exact signed immediate predecessor
  p1f           : [N N P' X]  predecessor with its sign flipped
  w8            : [N c2[i-8..i-1] X]         8-deep exact replay
  w32           : [c2[i-32..i-1] X]          32-deep exact replay

X always in its TRUE corpus sign (except selfp/selfn).  Blocks are
separated by 4 neutral flushes to decouple conditions; only X's line is
read.  The condition at which the corpus outcome returns measures the
state's depth; selfp-vs-selfn measures current-sign sensitivity.

Outputs in h462_package/: stream.txt, manifest.tsv (line -> probe,
condition), run_h462.sh.

Run from /tmp/stageA.
"""
import os

from h455_select_targets import analyze_row
from h437_gate_extraction import parse_trace_line

PKG = "h462_package"
NEUTRAL = "3ffc 8000000000000000"
FLIPPED_FIRE_SIGS = {
    0xde42ab34615412ce, 0xaa1f77b854d56233, 0xaf698fd8eab38c12,
    0xacac532b465d2534, 0x805344e197d38148, 0xd7c6da8419ab87d7,
    0xd117f47e1d9db29b, 0xda1f16bbf007c83e, 0x8672d9bcb999eb5a,
    0x8694cfa7f1f787d4, 0xb05f6aa4cfc72554, 0xab7a34bf1860fdd4,
    0xadc4198821f84510, 0xd14900f0d8ae62fc, 0xaca6da1b404e1985}


def main():
    inputs2 = [l.strip() for l in open("corpus2/selected_inputs.txt")]
    traces2 = open("corpus2/selected_traces.txt").read().splitlines()
    hw2 = {m: [l.split() for l in open(f"corpus2/hw_{m}.txt")]
           for m in ("rn", "rd", "ru")}

    # corpus2-sourced probes: flipped fires found in corpus2, the 9
    # flipped controls (identified by h457 behavior: corpus label
    # no-fire; today-fire — here we just take every corpus2 constrained
    # row whose sig matches the h459 flipped-control list is not
    # available locally, so probes = flipped fires + stable anchors)
    probes = []       # (name, corpus_index, signed_input_line, kind)
    n_anchor = 0
    for i, line in enumerate(traces2):
        row = (parse_trace_line(line),
               {m: int(hw2[m][i][2], 16) for m in ("rn", "rd", "ru")})
        r = analyze_row(row)
        if r in (None, "NOEXPONENT"):
            continue
        if r[7] in FLIPPED_FIRE_SIGS:
            probes.append((f"flip{i}", i, inputs2[i], "flipped_fire"))
        elif r[2] == 1 and n_anchor < 10:
            probes.append((f"anchor{i}", i, inputs2[i], "stable_fire"))
            n_anchor += 1
    print(f"probes: {len(probes)} "
          f"({sum(1 for p in probes if p[3] == 'flipped_fire')} flipped)")

    def flip_sign(line):
        se, sig = line.split()
        return f"{int(se, 16) ^ 0x8000:04x} {sig}"

    def force_sign(line, neg):
        se, sig = line.split()
        return f"{(int(se, 16) & 0x7FFF) | (0x8000 if neg else 0):04x} {sig}"

    stream = []
    manifest = []      # (x_line_number, probe, condition)

    def emit_block(prefix_lines, x_line, probe, condition):
        stream.extend([NEUTRAL] * 4)
        stream.extend(prefix_lines)
        manifest.append((len(stream), probe, condition))
        stream.append(x_line)

    for name, i, x_line, kind in probes:
        pred = inputs2[i - 1]
        emit_block([NEUTRAL] * 3, force_sign(x_line, 0), name, "selfp")
        emit_block([NEUTRAL] * 3, force_sign(x_line, 1), name, "selfn")
        emit_block([NEUTRAL, NEUTRAL, pred], x_line, name, "p1")
        emit_block([NEUTRAL, NEUTRAL, flip_sign(pred)], x_line, name, "p1f")
        emit_block(inputs2[i - 8:i], x_line, name, "w8")
        emit_block(inputs2[i - 32:i], x_line, name, "w32")

    os.makedirs(PKG, exist_ok=True)
    with open(f"{PKG}/stream.txt", "w") as fh:
        fh.write("\n".join(stream) + "\n")
    with open(f"{PKG}/manifest.tsv", "w") as fh:
        fh.write("line\tprobe\tcondition\n")
        for line_no, probe, condition in manifest:
            fh.write(f"{line_no}\t{probe}\t{condition}\n")
    with open(f"{PKG}/probes.tsv", "w") as fh:
        fh.write("probe\tkind\tcorpus_index\tinput\n")
        for name, i, x_line, kind in probes:
            fh.write(f"{name}\t{kind}\t{i}\t{x_line}\n")
    n = len(stream)
    with open(f"{PKG}/run_h462.sh", "w") as fh:
        fh.write(f"""#!/bin/sh
# h462 context-replay capture: {n} lines x rn/rd/ru.
cd "$(dirname "$0")"
for mode in rn rd ru; do
    taskset -c 2 /root/x87_capture_x86_64 cos "$mode" --status \\
        < stream.txt > "cos_${{mode}}.txt" || exit 1
    lines=$(wc -l < "cos_${{mode}}.txt")
    [ "$lines" -eq {n} ] || {{ echo "BAD $mode: $lines"; exit 1; }}
done
echo DONE > h462.done
""")
    os.chmod(f"{PKG}/run_h462.sh", 0o755)
    print(f"stream lines: {n}")


if __name__ == "__main__":
    main()
