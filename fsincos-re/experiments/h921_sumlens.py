#!/usr/bin/env python3
# h921: THE ADDER LENS ON THE r59 FAMILIES.  ~24 of the 36 ledger
# keys are "+1 uplift" rows (hw one retained unit ABOVE the model's
# baseline on down/tie rows) — the same direction as the act1
# guard-carry adder.  Test: run every ledger key through a probe
# build with g_round59_fcos_theta_band=0 (all four r59 sub-branches
# fall through to the default terminal), dump DI_TC/DI_ACC/DI_B81,
# and compute the R88/h914 sum coordinates (top8 = bits 52-59 of
# DI_ACC d60; sum = top8 + low3).  If the uplift rows sit in the
# adder boundary band [0xFD,0x106], the r59 families unify with the
# parked act1/act0 band object.
import subprocess, re, sys

MODEL = sys.argv[1] if len(sys.argv) > 1 else "./model_h921_nor59"

print("op\tinstr\tmode\tbranch\tdelta\ttc_act\ttop8\tlow3\tsum\t"
      "b81act\tb81pay\tinband")
for l in open("probe_keys.tsv"):
    f = l.split()
    if len(f) != 6:
        continue
    instr, mode, se, sig, hse, hsig = f
    args = [MODEL, "--batch",
            "--fcos-standalone" if instr == "cos" else "--fsin-standalone",
            "--dump-internals"]
    if mode != "rn":
        args.append("--rc=" + mode)
    p = subprocess.run(args, input="%s %s\n" % (se, sig),
                       capture_output=True, text=True)
    di = {}
    for ln in p.stderr.splitlines():
        di.setdefault(ln.split()[0], ln)
    tc = di.get("DI_TC", "")
    acc = di.get("DI_ACC", "")
    b81 = di.get("DI_B81", "")
    m = re.search(r"low3=(\d+)", tc)
    low3 = int(m.group(1)) if m else -1
    m = re.search(r"active=(\d+)", tc)
    act = int(m.group(1)) if m else -1
    top8 = -1
    m = re.search(r"d60=([0-9a-f]{32})", acc)
    if m:
        d60 = int(m.group(1), 16)
        top8 = (d60 >> 52) & 0xFF
    s = top8 + low3 if top8 >= 0 else -1
    b81act = b81pay = "-"
    if b81:
        b81act = re.search(r"act=(\d+)", b81).group(1)
        b81pay = re.search(r"pay=(-?\d+)", b81).group(1)
    inband = int(0xFD <= s <= 0x106) if s >= 0 else "-"
    print("%s%s\t%s\t%s\t%s\t%s\t%d\t%s\t%d\t%s\t%s\t%s\t%s"
          % (se, sig[:10], instr, mode, "-", "-", act,
             hex(top8) if top8 >= 0 else "-", low3,
             hex(s) if s >= 0 else "-", b81act, b81pay, inband))
