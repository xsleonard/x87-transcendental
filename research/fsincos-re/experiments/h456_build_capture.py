#!/usr/bin/env python3
"""h456: build the single-bit-flip truth-table capture package.

For every target input from h455 (fire rows + matched near-boundary
controls), emit the base input and its 63 single-bit-flip neighbors
(significand bits 0..62; bit 63 is the explicit x87 integer bit —
flipping it produces an unnormal encoding that takes a different
hardware path and would pollute the truth table, so it is excluded and
the exclusion is part of the experiment's definition).  The exponent
stays fixed, so every neighbor remains a normalized in-range FCOS
input.

Outputs in h456_package/ (all plain text, no pickle):
  inputs.txt    one "se sig" pair per line, in manifest order, the
                exact stdin format of capture-kit/x87_capture
                ("%x %llx", cos --status).
  manifest.tsv  capture line number (0-based) -> target id, flipped
                bit (-1 = base), se, sig.
  run_h456.sh   remote-side script: three mode passes (rn/rd/ru) into
                cos_{mode}_status.txt next to itself, then a DONE
                marker with wc -l checks.  Designed for one detached
                setsid nohup launch.

Run from /tmp/stageA.
"""
import os

PKG = "h456_package"


def main():
    targets = []
    with open(f"{PKG}/targets.tsv") as fh:
        header = fh.readline()
        for line in fh:
            tid, role, se, sig, *_ = line.rstrip("\n").split("\t")
            targets.append((tid, int(se, 16), int(sig, 16)))

    lines = []
    manifest = []
    for tid, se, sig in targets:
        manifest.append((tid, -1, se, sig))
        lines.append(f"{se:x} {sig:016x}")
        for bit in range(63):
            flipped = sig ^ (1 << bit)
            manifest.append((tid, bit, se, flipped))
            lines.append(f"{se:x} {flipped:016x}")

    with open(f"{PKG}/inputs.txt", "w") as fh:
        fh.write("\n".join(lines) + "\n")
    with open(f"{PKG}/manifest.tsv", "w") as fh:
        fh.write("line\ttarget\tbit\tse\tsig\n")
        for i, (tid, bit, se, sig) in enumerate(manifest):
            fh.write(f"{i}\t{tid}\t{bit}\t{se:x}\t{sig:016x}\n")

    n = len(lines)
    with open(f"{PKG}/run_h456.sh", "w") as fh:
        fh.write(f"""#!/bin/sh
# h456 truth-table capture: {n} FCOS inputs x rn/rd/ru, --status.
# Launch detached:  setsid nohup sh run_h456.sh > run.log 2>&1 &
cd "$(dirname "$0")"
RUNNER=/root/x87_capture_x86_64
for mode in rn rd ru; do
    taskset -c 2 "$RUNNER" cos "$mode" --status \\
        < inputs.txt > "cos_${{mode}}_status.txt" || exit 1
done
for mode in rn rd ru; do
    lines=$(wc -l < "cos_${{mode}}_status.txt")
    [ "$lines" -eq {n} ] || {{ echo "BAD count $mode: $lines"; exit 1; }}
done
echo DONE > h456.done
""")
    os.chmod(f"{PKG}/run_h456.sh", 0o755)
    print(f"targets: {len(targets)}, capture lines: {n} "
          f"(x3 modes = {3 * n} executions)")
    print(f"wrote {PKG}/inputs.txt, manifest.tsv, run_h456.sh")


if __name__ == "__main__":
    main()
