#!/usr/bin/env python3
"""h622: build the cross-generation capture bundle.

capture-kit/crossgen/: the 56,190 doubly-validated adversarial
FCOS operands as (3ffc, m) inputs, their Skylake reference
outputs (extracted from the comb captures), a per-row category
file (rule/chop/other under the Round-57 model), and a
self-contained check script.  Run on ANY x86 with x87 to test
the heritage assumption: identical => the borrow gate predates
that microarchitecture; different => the gate is
generation-local silicon behavior.
"""
import json
import os
from h437_gate_extraction import ROUNDING_MODES

OUT = ("/Users/steve/llm/x87-transcendental/fsincos-re/"
       "capture-kit/crossgen")
os.makedirs(OUT, exist_ok=True)

locked = json.load(open("h616_locked.json"))
want = {int(rec["m"], 16): i for i, rec in enumerate(locked)}
fc_out = {}
for comb in ("comb5", "comb6", "comb7", "comb8"):
    seen = set()
    raw = []
    for line in open(f"ties_{comb}.txt"):
        w = line.split()[0]
        if w in seen:
            continue
        seen.add(w)
        raw.append(w)
    inputs = sorted(raw)
    order = {m: i for i, m in enumerate(inputs)}
    st = {md: open(f"{comb}_{md}_status.txt").read()
          .splitlines() for md in ROUNDING_MODES}
    for w in raw:
        m = int(w, 16)
        if m not in want or m in fc_out:
            continue
        i = order[w]
        rows = {md: st[md][i].split() for md in ROUNDING_MODES}
        if all(r[0] == "OK" for r in rows.values()):
            fc_out[m] = {md: (rows[md][1], rows[md][2])
                         for md in ROUNDING_MODES}
print(f"reference rows: {len(fc_out)}")

ms = [int(rec["m"], 16) for rec in locked
      if int(rec["m"], 16) in fc_out]
with open(f"{OUT}/inputs.txt", "w") as f:
    for m in ms:
        f.write(f"3ffc {m:016x}\n")
for md in ROUNDING_MODES:
    with open(f"{OUT}/skylake_{md}.txt", "w") as f:
        for m in ms:
            e, s = fc_out[m][md]
            f.write(f"OK {e} {s}\n")
sin_st = {md: open(f"h616_{md}_status.txt").read()
          .splitlines() for md in ROUNDING_MODES}
with open(f"{OUT}/categories.tsv", "w") as f:
    f.write("m\tcategory\tkey\n")
    for m in ms:
        i = want[m]
        rec = locked[i]
        hw = [f"{int(sin_st[md][i].split()[2], 16):x}"
              for md in ROUNDING_MODES]
        cat = ("rule" if hw == rec["on"] else
               "chop" if hw == rec["off"] else "other")
        f.write(f"{m:016x}\t{cat}\t"
                f"{','.join(map(str, rec['key']))}\n")
print(f"bundle inputs: {len(ms)}")
