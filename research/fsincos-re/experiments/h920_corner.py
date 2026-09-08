#!/usr/bin/env python3
# h920: the corner family (R67/68 D-ladder residuals).  The 5 ledger
# keys in the corner cell (s4=67, side=1, d=8, rsh=64) are UNIFORM:
# hw = model + 1 output ulp (4 no-fire rows where hw did +1, and 1
# model-fire where hw stayed) — unlike every other r59 family, one
# direction only, all at the extreme near-0.5 edge (comb16/17/18).
# Contrast the 5 POS against corner-branch NEG rows harvested from
# the same corpora: D-ladder coordinates (dd, lane0-drop), crit
# lattice (pm, phw, block-start bits), payload/disc structure, and
# the leading-ones count of the operand (edge proximity).
# usage: h920_corner.py h918_corner_comb15.txt [...]
import subprocess, re, sys, collections

MODEL = "./model_h917_noled"


def parse_kv(line):
    d = {}
    for m in re.finditer(r"(\w+)=([0-9a-fA-F-]+)", line):
        d[m.group(1)] = m.group(2)
    return d


def s128(h):
    v = int(h, 16)
    return v - (1 << 128) if v >= (1 << 127) else v


def obj(rec, sig_hex):
    k = int(rec["k"]); ce = int(rec["ce"])
    low3 = int(rec["low3"]); dist = int(rec["dist"])
    b1 = int(rec["b1"]); b2 = int(rec["b2"])
    S = int(rec["S"], 16); B = int(rec["B"], 16)
    umag = int(rec["umag"], 16)
    rd = int(rec["disc"], 16)
    theta = int(rec["theta"])
    pmask = ~(S ^ B) & ((1 << 128) - 1)
    pm = 0; j = k
    while pm < 32 and ((pmask >> j) & 1):
        pm += 1; j += 1
    phw = ((ce % 8) + 8) % 8 if ce >= 0 else ((ce - 8 * int(ce / 8)) + 8) % 8
    dd = low3 + b1 + b2
    lane0 = 1 if 3 * rd < (1 << 47) else 0   # R68 lane0-drop reads 3*rd
    ddx = dd - lane0
    sig = int(sig_hex, 16)
    lead1 = 0
    for i in range(63, -1, -1):
        if (sig >> i) & 1:
            lead1 += 1
        else:
            break
    bit8 = (umag >> (k + 8)) & 1
    bsrel = 8 + ((8 - phw) % 8)
    bitbs = (umag >> (k + bsrel)) & 1
    Mreg = s128(rec["Mreg"])
    return dict(k=k, ce=ce, low3=low3, dist=dist, b1=b1, b2=b2,
                theta=theta, pm=pm, phw=phw, dd=dd, lane0=lane0, ddx=ddx,
                lead1=lead1, bit8=bit8, bitbs=bitbs,
                pay=int(rec.get("payload", "0")), md=Mreg >> 66,
                mfrac=(Mreg - ((Mreg >> 66) << 66)) / (1 << 66))


# POS: the 5 corner ledger keys
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
    r59 = None; isc = False; fire = ""
    for ln in p.stderr.splitlines():
        if ln.startswith("DI_R59"):
            r59 = parse_kv(ln)
        elif ln.startswith("DI_BR br=corner"):
            isc = True
            fire = re.search(r"fire=(\d)", ln).group(1)
    if isc and r59:
        O = obj(r59, sig)
        O["op"] = "%s/%s/%s" % (instr, mode, sig[:10])
        O["fire"] = fire
        pos.append(O)

print("== %d POS (corner ledger keys) ==" % len(pos))
for O in pos:
    print("%-24s th=%d low3=%d b1=%d b2=%d dd=%d lane0=%d ddx=%d "
          "fire=%s pay=%d lead1=%d pm=%d phw=%d b8=%d bbs=%d md=%d "
          "mfrac=%.3f"
          % (O["op"], O["theta"], O["low3"], O["b1"], O["b2"], O["dd"],
             O["lane0"], O["ddx"], O["fire"], O["pay"], O["lead1"],
             O["pm"], O["phw"], O["bit8"], O["bitbs"], O["md"],
             O["mfrac"]))

ledger_ops = set()
for l in open("probe_keys.tsv"):
    f = l.split()
    if len(f) == 6:
        ledger_ops.add((f[2], f[3]))

# NEG: corner-branch rows from the harvest
n = 0
th_dd = collections.Counter()          # (theta_class, dd, fire) counts
lead_h = collections.Counter()
fire_h = collections.Counter()
neg_at_pos = collections.defaultdict(int)   # POS-matching coords
pos_coords = set((O["theta"], O["dd"], O["low3"], O["b1"], O["b2"],
                  O["lane0"]) for O in pos)
pos_near = collections.defaultdict(int)
for fn in sys.argv[1:]:
    for ln in open(fn):
        if "|" not in ln:
            continue
        parts = ln.split("|")
        mi = re.match(r"DI_IN ([0-9a-f]{4}) ([0-9a-f]{16})", parts[0])
        if not mi:
            continue
        if (mi.group(1), mi.group(2)) in ledger_ops:
            continue
        rec = parse_kv(parts[1])
        brline = parts[-1]
        mfire = re.search(r"fire=(\d)", brline)
        try:
            O = obj(rec, mi.group(2))
        except (KeyError, ValueError):
            continue
        n += 1
        f = mfire.group(1) if mfire else "?"
        thc = 0 if O["theta"] == 0 else (1 if abs(O["theta"]) == 1 else 2)
        th_dd[(O["theta"], O["dd"], f)] += 1
        lead_h[O["lead1"]] += 1
        fire_h[f] += 1
        c = (O["theta"], O["dd"], O["low3"], O["b1"], O["b2"], O["lane0"])
        if c in pos_coords:
            neg_at_pos[c] += 1

print("\n== NEG corner rows: %d ==" % n)
print("fire dist:", sorted(fire_h.items()))
print("lead1 hist:", sorted(lead_h.items()))
print("\n(theta, dd, fire) census:")
for kk in sorted(th_dd):
    print("  th=%-3d dd=%-2d fire=%s  %8d" % (kk[0], kk[1], kk[2],
                                              th_dd[kk]))
print("\nNEG at exact POS coords (theta,dd,low3,b1,b2,lane0):")
for c in sorted(pos_coords):
    print("  %s  NEG=%d" % (str(c), neg_at_pos.get(c, 0)))
