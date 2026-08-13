#!/usr/bin/env python3
"""h616d: cross-instruction concordance on the SAME terminal
rows — for each h616 locked row whose m has an FCOS capture in
combs 5/6/7/8, classify BOTH hardware outcomes against the
same (off, on) reference pair and compare.  If the 330
anti-rule FSIN rows are anti-rule in FCOS too, the miss is the
rule's residual and the two schedules are row-level IDENTICAL;
discordant rows measure the true FSIN-FCOS schedule delta."""
import json
from collections import defaultdict
from h437_gate_extraction import ROUNDING_MODES

locked = json.load(open("h616_locked.json"))
want = {int(rec["m"], 16): i for i, rec in enumerate(locked)}
print(f"locked rows: {len(locked)}")

fc_out = {}
for comb in ("comb5", "comb6", "comb7", "comb8"):
    try:
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
    except FileNotFoundError as e:
        print(f"  {comb}: missing ({e.filename}), skipped")
        continue
    hit = 0
    for w in raw:
        m = int(w, 16)
        if m not in want or m in fc_out:
            continue
        i = order[w]
        hw = []
        ok = True
        for md in ROUNDING_MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                ok = False
                break
            hw.append(f"{int(t[2], 16):x}")
        if ok:
            fc_out[m] = hw
            hit += 1
    print(f"  {comb}: matched {hit}")

sinst = {md: open(f"h616_{md}_status.txt").read().splitlines()
         for md in ROUNDING_MODES}
conc = defaultdict(int)
detail = defaultdict(int)
for m, i in want.items():
    if m not in fc_out:
        continue
    rec = locked[i]
    hw_sin = []
    ok = True
    for md in ROUNDING_MODES:
        t = sinst[md][i].split()
        if t[0] != "OK":
            ok = False
            break
        hw_sin.append(f"{int(t[2], 16):x}")
    if not ok:
        continue
    def cat(hw):
        if hw == rec["on"]:
            return "rule"
        if hw == rec["off"]:
            return "chop"
        return "other"
    cs, cf = cat(hw_sin), cat(fc_out[m])
    conc[(cs == cf)] += 1
    detail[(cf, cs)] += 1
print(f"\njoined rows: {sum(conc.values())}")
print(f"row-level concordant: {conc[True]}  discordant: "
      f"{conc[False]}")
print("detail (fcos_cat, fsin_cat):",
      dict(sorted(detail.items(), key=str)))
