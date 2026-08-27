#!/usr/bin/env python3
# h920b: the corner-family u-floor boundary probe.  h920 found the
# three theta!=0 corner POS at mfrac=1.000 (Mreg just below a 2^66
# u-grid line; md=-1/1/4 — three DIFFERENT lines) and the th=0 pair
# at 0.501/0.088.  Measure: exact boundary distances for POS, and
# the NEG mass in the same tails (per theta class), plus secondary
# coordinates of the tail NEGs.
# usage: h920b_boundary.py h918_corner_comb15.txt [...]
import subprocess, re, sys, collections

MODEL = "./model_h917_noled"
T66 = 1 << 66


def parse_kv(line):
    d = {}
    for m in re.finditer(r"(\w+)=([0-9a-fA-F-]+)", line):
        d[m.group(1)] = m.group(2)
    return d


def s128(h):
    v = int(h, 16)
    return v - (1 << 128) if v >= (1 << 127) else v


def coords(rec):
    Mreg = s128(rec["Mreg"])
    md = Mreg >> 66
    up_gap = (md + 1) * T66 - Mreg          # distance to line above
    dn_gap = Mreg - md * T66                # distance to line below
    return dict(theta=int(rec["theta"]), low3=int(rec["low3"]),
                b1=int(rec["b1"]), b2=int(rec["b2"]), md=md,
                up_gap=up_gap, dn_gap=dn_gap,
                dist=int(rec["dist"]), pay=int(rec.get("payload", "0")))


pos = []
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
    r59 = None; isc = False
    for ln in p.stderr.splitlines():
        if ln.startswith("DI_R59"):
            r59 = parse_kv(ln)
        elif ln.startswith("DI_BR br=corner"):
            isc = True
    if isc and r59:
        C = coords(r59)
        C["op"] = sig[:10]
        pos.append(C)

print("== POS boundary gaps (units of 2^66; ug=to line above) ==")
for C in pos:
    print("%-12s th=%d dd=%d md=%2d  ug=%.3e  dg=%.3e  (raw ug=%d)"
          % (C["op"], C["theta"], C["low3"] + C["b1"] + C["b2"],
             C["md"], C["up_gap"] / T66, C["dn_gap"] / T66, C["up_gap"]))

ledger_ops = set()
for l in open("probe_keys.tsv"):
    f = l.split()
    if len(f) == 6:
        ledger_ops.add((f[2], f[3]))

# NEG tails
TH = [1 << 40, 1 << 46, 1 << 52, 1 << 58, 1 << 62]
tail = collections.Counter()      # (theta_cls, thresh_idx) -> count
tail_rows = collections.defaultdict(list)
n = 0
for fn in sys.argv[1:]:
    for ln in open(fn):
        if "|" not in ln:
            continue
        parts = ln.split("|")
        mi = re.match(r"DI_IN ([0-9a-f]{4}) ([0-9a-f]{16})", parts[0])
        if not mi or (mi.group(1), mi.group(2)) in ledger_ops:
            continue
        rec = parse_kv(parts[1])
        try:
            C = coords(rec)
        except (KeyError, ValueError):
            continue
        n += 1
        for i, t in enumerate(TH):
            if C["up_gap"] < t:
                tail[(C["theta"], i)] += 1
                if i <= 1 and len(tail_rows[C["theta"]]) < 12:
                    C2 = dict(C); C2["op"] = mi.group(2)[:10]
                    tail_rows[C["theta"]].append(C2)

print("\n== NEG rows %d; up_gap tail counts ==" % n)
print("thresholds:", ["2^%d" % t.bit_length() for t in TH])
for kk in sorted(tail):
    print("  th=%-3d gap<2^%d : %d"
          % (kk[0], TH[kk[1]].bit_length(), tail[kk]))
print("\n== closest NEG rows per theta (gap<2^47) ==")
for t in sorted(tail_rows):
    for C in tail_rows[t]:
        print("  th=%-3d %-12s dd=%d md=%2d ug=%.3e pay=%d"
              % (C["theta"], C["op"], C["low3"] + C["b1"] + C["b2"],
                 C["md"], C["up_gap"] / T66, C["pay"]))
