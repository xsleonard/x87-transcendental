#!/usr/bin/env python3
"""h488a: build the FSINCOS cross-context capture package.
All unique constructed tie inputs (h479+h480+h482) with their known
FCOS outcomes and clean/fired tuples -> capture via `sincos` mode,
score the COS lane: does the same input fire under the paired
schedule?  Identical fire-ness => gate is kernel-internal;
asymmetric flips => microcode operand schedule participates.
NOTE: paired-vs-standalone polynomial differences are a known class
(~3k silicon points, lead 3); OTHER outcomes are reported separately
from clean R/R-1 flips."""
import json
MODES = ("rn", "rd", "ru")

def sig(line):
    t = line.split()
    return f"{int(t[2],16):016x}" if t[0] == "OK" else "BAD"

entries = {}
d479 = json.load(open("h479_locked.json"))
order = []
for p in d479["pairs"]:
    order += [p["g0"], p["g1"]]
order += d479["controls"]
st = {m: open(f"h479_cos_{m}_status.txt").read().splitlines()
      for m in MODES}
for i, e in enumerate(order):
    hw = [sig(st[m][i]) for m in MODES]
    o = 1 if hw == e["fired"] else (0 if hw == e["clean"] else 2)
    entries[e["m"]] = {"clean": e["clean"], "fired": e["fired"],
                       "fcos": o}
for fn, pref in (("h480_locked.json", None),):
    d = json.load(open(fn))
    for line in open("h480_outcomes.tsv").read().splitlines()[1:]:
        f = line.split("\t")
        pass
d480 = json.load(open("h480_locked.json"))
out480 = {}
for line in open("h480_outcomes.tsv").read().splitlines()[1:]:
    f = line.split("\t")
    out480[f[0]] = {"CLEAN": 0, "FIRE": 1}.get(f[6], 2)
for e in d480["inputs"]:
    entries[e["m"]] = {"clean": e["clean"], "fired": e["fired"],
                       "fcos": out480[e["m"]]}
d482 = json.load(open("h482_locked.json"))
st = {m: open(f"cos_{m}_status.txt").read().splitlines()
      for m in MODES}
for i, e in enumerate(d482["inputs"]):
    hw = [sig(st[m][i]) for m in MODES]
    o = 1 if hw == e["fired"] else (0 if hw == e["clean"] else 2)
    entries[e["m"]] = {"clean": e["clean"], "fired": e["fired"],
                       "fcos": o}

ms = sorted(m for m, v in entries.items() if v["fcos"] != 2)
print(f"unique labeled inputs: {len(ms)}, fires: "
      f"{sum(1 for m in ms if entries[m]['fcos'])}")
with open("h488_locked.json", "w") as fh:
    json.dump({"inputs": [{"m": m, **entries[m]} for m in ms]}, fh,
              indent=1)
with open("h488_inputs.txt", "w") as fh:
    for m in ms:
        fh.write(f"3ffc {m}\n")
with open("run_h488.sh", "w") as fh:
    fh.write(f"""#!/bin/sh
cd "$(dirname "$0")"
RUNNER=/root/x87_capture_x86_64
for mode in rn rd ru; do
    taskset -c 2 "$RUNNER" sincos "$mode" --status \\
        < h488_inputs.txt > "sincos_${{mode}}_status.txt" || exit 1
done
for mode in rn rd ru; do
    lines=$(wc -l < "sincos_${{mode}}_status.txt")
    [ "$lines" -eq {len(ms)} ] || {{ echo "BAD count $mode: $lines"; exit 1; }}
done
echo DONE > h488.done
""")
print("wrote h488_locked.json, h488_inputs.txt, run_h488.sh")
