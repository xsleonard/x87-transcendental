#!/usr/bin/env python3
"""h491b: turn the scanner's tie list into a dual-instruction capture
package.  Reads ties_all.txt (m dist low3 k rud t4hi12 rdhi12 R_hex
corr_e), computes each tie's clean (R) and fired (R-1) architectural
tuples, writes h491_inputs.txt + run_h491cap.sh (cos and sincos, 3
modes) + h491_ties.tsv for the mapper.  Run from /tmp/stageA."""
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result

rows = []
seen = set()
for line in open("ties_all.txt"):
    f = line.split()
    m = f[0]
    if m in seen:
        continue
    seen.add(m)
    R = int(f[7], 16)
    corr_e = int(f[8])
    clean = [f"{final_cosine_result(-R, corr_e, md):016x}"
             for md in ROUNDING_MODES]
    fired = [f"{final_cosine_result(-(R - 1), corr_e, md):016x}"
             for md in ROUNDING_MODES]
    rows.append((m, f[1], f[2], f[3], f[4], f[5], f[6],
                 ",".join(clean), ",".join(fired)))
print(f"unique ties: {len(rows)}")
with open("h491_ties.tsv", "w") as fh:
    fh.write("m\tdist\tlow3\tk\trud\tt4hi12\trdhi12\tclean\tfired\n")
    for r in rows:
        fh.write("\t".join(r) + "\n")
with open("h491_inputs.txt", "w") as fh:
    for r in rows:
        fh.write(f"3ffc {r[0]}\n")
n = len(rows)
with open("run_h491cap.sh", "w") as fh:
    fh.write(f"""#!/bin/sh
cd "$(dirname "$0")"
RUNNER=/root/x87_capture_x86_64
for insn in cos sincos; do
  for mode in rn rd ru; do
    taskset -c 2 "$RUNNER" "$insn" "$mode" --status \\
        < h491_inputs.txt > "${{insn}}_${{mode}}_status.txt" || exit 1
    lines=$(wc -l < "${{insn}}_${{mode}}_status.txt")
    [ "$lines" -eq {n} ] || {{ echo "BAD $insn $mode: $lines"; exit 1; }}
  done
done
echo DONE > h491cap.done
""")
print(f"wrote h491_ties.tsv, h491_inputs.txt, run_h491cap.sh ({n})")
