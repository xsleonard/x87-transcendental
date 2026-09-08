#!/usr/bin/env python3
"""h494b: fresh-data EXACTNESS validation of the locked tables.
Reads ties_fresh.txt (never seen by any fit), applies
h494_locked_tables.json, captures predictions vs hardware:
per claimed stratum, count exceptions.  Verdict per stratum:
EXACT / near / broken."""
import json
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h493_curvefit import build
SC = 60
ONE = 1 << SC
MODES = ("rn", "rd", "ru")

def main():
    tables = json.load(open("h494_locked_tables.json"))
    fresh = []
    seen = set()
    for line in open("ties_fresh.txt"):
        f = line.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        fresh.append((f[0], int(f[7], 16), int(f[8])))
    print(f"fresh unique ties: {len(fresh)}")
    with Pool(8) as pool:
        states = pool.map(build, [(m, False) for m, R, ce in fresh],
                          chunksize=500)
    # keep only claimed strata; build prediction + expected tuples
    keep = []
    for (m, R, ce), (cell, XT, XD, XP, XE, _f) in zip(fresh, states):
        key = "|".join(str(x) for x in cell)
        if key not in tables:
            continue
        t = tables[key]
        tw = [i * ONE // 12 for i in range(13)] + [ONE * 2]
        r = 0 if XT < tw[t["b1"]] else (1 if XT < tw[t["b2"]] else 2)
        lv = tw[t["levels"][r]] if t["levels"][r] < 13 else ONE * 2
        pred = XD >= lv
        clean = [f"{final_cosine_result(-R, ce, md):016x}"
                 for md in ROUNDING_MODES]
        fired = [f"{final_cosine_result(-(R-1), ce, md):016x}"
                 for md in ROUNDING_MODES]
        keep.append((m, key, pred, clean, fired))
    print(f"in claimed strata: {len(keep)}")
    with open("h494_pred.json", "w") as fh:
        json.dump([{"m": m, "s": k, "pred": int(p), "clean": c,
                    "fired": fdd} for m, k, p, c, fdd in keep], fh)
    with open("h494_inputs.txt", "w") as fh:
        for m, k, p, c, fdd in keep:
            fh.write(f"3ffc {m}\n")
    n = len(keep)
    with open("run_h494cap.sh", "w") as fh:
        fh.write(f"""#!/bin/sh
cd "$(dirname "$0")"
RUNNER=/root/x87_capture_x86_64
for mode in rn rd ru; do
    taskset -c 2 "$RUNNER" cos "$mode" --status \\
        < h494_inputs.txt > "vcos_${{mode}}_status.txt" || exit 1
    lines=$(wc -l < "vcos_${{mode}}_status.txt")
    [ "$lines" -eq {n} ] || {{ echo "BAD $mode: $lines"; exit 1; }}
done
echo DONE > h494cap.done
""")
    print("wrote h494_pred.json, h494_inputs.txt, run_h494cap.sh")

if __name__ == "__main__":
    main()
