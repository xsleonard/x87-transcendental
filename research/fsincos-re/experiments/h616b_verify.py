#!/usr/bin/env python3
"""h616b: local model verification of the h616 lock — run the C
model over the constructed FSIN inputs, flag off and on, and
compare against the locked off/on predictions per mode.
Mismatching rows are dropped from scoring (frame/reduction
surprises); expect ~0."""
import json
import subprocess
from collections import defaultdict
from h437_gate_extraction import ROUNDING_MODES

CBIN = "/tmp/stageA/fsincos_skylake_r57"
FSIN = ("--fsin-standalone --round18-poly --round21-table-bias "
        "--round23-narrow-coefficient --round24-table-delta-rn67 "
        "--round29-p5-fmul-route --round30-fsin-cosine-square "
        "--round31-fsin-cosine-tail --round32-fsin-cosine-horner "
        "--round33-fsin-cosine-product --round34-table-lookup-firc "
        "--round35-table-p-terminal "
        "--round36-table-fadd-microcontrol --round37-p6-four-term "
        "--round41-fsin-cosine-split --round42-p6-sine-split "
        "--round43-p6-sine-bias --round44-p6-sine-bias "
        "--round45-p6-sine-fraction "
        "--round46-p6-narrow-sine-fraction "
        "--round47-p6-narrow-sine-fraction "
        "--round48-p6-narrow-sine-fraction "
        "--round49-p6-carrier-interval "
        "--round50-fsin-operation-classes "
        "--round51-fsin-fadd-signature "
        "--round56-fsin-cosine-carrier").split()

locked = json.load(open("h616_locked.json"))
inp = "".join(rec["x"] + "\n" for rec in locked)
res = {}
for tag, extra in (("off", []), ("on", ["--round57-fsin-test"])):
    for md in ROUNDING_MODES:
        args = [CBIN, "--batch"] + FSIN + extra
        if md != "rn":
            args.append(f"--rc={md}")
        r = subprocess.run(args, input=inp, capture_output=True,
                           text=True)
        res[(tag, md)] = r.stdout.splitlines()
ok_off = ok_on = bad_off = bad_on = 0
badrows = []
for i, rec in enumerate(locked):
    coff = []
    con = []
    good = True
    for md in ROUNDING_MODES:
        t1 = res[("off", md)][i].split()
        t2 = res[("on", md)][i].split()
        if t1[0] != "OK" or t2[0] != "OK":
            good = False
            break
        coff.append(t1[2])
        con.append(t2[2])
    if not good:
        badrows.append(i)
        continue
    mo = [f"{int(s, 16):x}" for s in coff]
    mn = [f"{int(s, 16):x}" for s in con]
    if mo == rec["off"]:
        ok_off += 1
    else:
        bad_off += 1
        if bad_off <= 5:
            print(f"OFF mismatch row {i}: {rec['x']} "
                  f"model={mo} locked={rec['off']}")
    if mn == rec["on"]:
        ok_on += 1
    else:
        bad_on += 1
        if bad_on <= 5:
            print(f"ON mismatch row {i}: {rec['x']} "
                  f"model={mn} locked={rec['on']}")
print(f"off: {ok_off} ok / {bad_off} mismatch; "
      f"on: {ok_on} ok / {bad_on} mismatch; "
      f"badstat {len(badrows)}")
json.dump(badrows, open("h616_badrows.json", "w"))
