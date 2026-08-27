#!/usr/bin/env python3
# h918b: fine-grain contrast for the q67th2 family.  The u-floor
# vocabulary fails (h918: POS inside the NEG bulk at every vector).
# Three deeper lenses, each with campaign precedent:
#   L1 scalar concentrations: low3 (7/9 POS at low3=5), payload, k.
#   L2 the adder-boundary lens (h914 precedent): the byte of Mreg
#      just below the u-floor's 2^66 granularity line, POS vs NEG —
#      boundary-band clustering = the h486 species signature.
#   L3 the R64 killed-column lens: the comparator reads 3*rd with
#      addend columns below bit 47 killed; rows where the kill
#      swallows a real carry are candidate anomaly sites.
# usage: h918b_fine.py NEG1.txt [NEG2.txt ...]
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


def fine(rec):
    k = int(rec["k"]); ce = int(rec["ce"])
    low3 = int(rec["low3"]); dist = int(rec["dist"])
    rsh = int(rec["rsh"])
    Mreg = s128(rec["Mreg"])
    rd = int(rec["disc"], 16)          # right_discarded
    sq = int(rec["sqlow"], 16)
    t4 = int(rec["t4"], 16)
    umag = int(rec["umag"], 16)
    md = Mreg >> 66
    mfine = (Mreg >> 58) & 0xFF        # byte below the 2^66 line
    mfrac = (Mreg - (md << 66)) / (1 << 66)  # position inside the cell
    # R64 comparator object: rd3 = 3*rd - (2*rd mod 2^47) - (rd mod 2^47)
    m47 = (1 << 47) - 1
    kill = ((2 * rd) & m47) + (rd & m47)
    kcarry = kill >> 47                # 0/1/2: carries the kill swallowed
    kfrac = kill / (1 << 47)
    b1 = int(rec["b1"]); b2 = int(rec["b2"])
    return dict(k=k, ce=ce, low3=low3, dist=dist, rsh=rsh, md=md,
                mfine=mfine, mfrac=mfrac, kcarry=kcarry, kfrac=kfrac,
                b1=b1, b2=b2, pay=int(rec.get("payload", "0")),
                umag_low=umag & 0xFFFF, rd_top=rd >> max(0, k - 8))


POS_KEYS = [l.split() for l in open("probe_keys.tsv") if len(l.split()) == 6]
pos = []
for instr, mode, se, sig, hse, hsig in POS_KEYS:
    args = [MODEL, "--batch",
            "--fcos-standalone" if instr == "cos" else "--fsin-standalone",
            "--dump-internals"]
    if mode != "rn":
        args.append("--rc=" + mode)
    p = subprocess.run(args, input="%s %s\n" % (se, sig),
                       capture_output=True, text=True)
    r59 = None; isq = False
    for l in p.stderr.splitlines():
        if l.startswith("DI_R59"):
            r59 = parse_kv(l)
        elif l.startswith("DI_BR br=q67th2"):
            isq = True
    if isq and r59:
        F = fine(r59)
        F["op"] = "%s/%s/%s%s" % (instr, mode, se, sig[:8])
        pos.append(F)

print("== POS fine coordinates ==")
for F in pos:
    print("%-22s ce=%d d=%d rsh=%d low3=%d b1b2=%d%d pay=%d  md=%d "
          "mfine=%02x mfrac=%.4f  kcarry=%d kfrac=%.4f"
          % (F["op"], F["ce"], F["dist"], F["rsh"], F["low3"], F["b1"],
             F["b2"], F["pay"], F["md"], F["mfine"], F["mfrac"],
             F["kcarry"], F["kfrac"]))

h_low3 = collections.Counter(); h_pay = collections.Counter()
h_mfine = collections.Counter(); h_kc = collections.Counter()
h_mfrac = collections.Counter(); h_kfrac = collections.Counter()
h_low3_cell = collections.Counter()
n = 0
for fn in sys.argv[1:]:
    for ln in open(fn):
        if "|" not in ln:
            continue
        rec = parse_kv(ln.split("|", 1)[1])
        try:
            F = fine(rec)
        except (KeyError, ValueError):
            continue
        n += 1
        h_low3[F["low3"]] += 1
        h_pay[F["pay"]] += 1
        h_mfine[F["mfine"] >> 4] += 1
        h_kc[F["kcarry"]] += 1
        h_mfrac[int(F["mfrac"] * 10)] += 1
        h_kfrac[int(F["kfrac"] * 10)] += 1
        h_low3_cell[(F["dist"], F["rsh"], F["low3"])] += 1

print("\n== NEG n=%d ==" % n)
print("low3 NEG:", sorted(h_low3.items()))
print("low3 POS:", sorted(collections.Counter(F["low3"] for F in pos).items()))
print("pay NEG:", sorted(h_pay.items()))
print("pay POS:", sorted(collections.Counter(F["pay"] for F in pos).items()))
print("mfine>>4 NEG:", sorted(h_mfine.items()))
print("mfine>>4 POS:",
      sorted(collections.Counter(F["mfine"] >> 4 for F in pos).items()))
print("mfrac decile NEG:", sorted(h_mfrac.items()))
print("mfrac decile POS:",
      sorted(collections.Counter(int(F["mfrac"] * 10) for F in pos).items()))
print("kcarry NEG:", sorted(h_kc.items()))
print("kcarry POS:",
      sorted(collections.Counter(F["kcarry"] for F in pos).items()))
print("kfrac decile NEG:", sorted(h_kfrac.items()))
print("kfrac decile POS:",
      sorted(collections.Counter(int(F["kfrac"] * 10) for F in pos).items()))
print("\nlow3 by cell NEG (d,rsh,low3):",
      sorted(h_low3_cell.items())[:40])
