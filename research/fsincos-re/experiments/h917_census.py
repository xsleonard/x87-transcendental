#!/usr/bin/env python3
# h917: FRAME CENSUS of the 36 post-R89/R90 ledger keys against the
# current model with DI dumps, ledger OFF (-DG_ROUND84=0).  This is
# the census h911 deferred for the non-default-frame family: the 31
# comb "other-path" rows (r59-band strata) + the 5 randv1 keys.
# Output: h917_census.tsv (one row per key, full frame) + a grouped
# summary on stdout.  Read-only w.r.t. banked data; the model binary
# is built by h917_census.sh from the synced repo source.
import subprocess, re, sys, collections

MODEL = sys.argv[1] if len(sys.argv) > 1 else "./model_h917_noled"
KEYS = sys.argv[2] if len(sys.argv) > 2 else "probe_keys.tsv"

def parse_kv(line):
    d = {}
    for m in re.finditer(r"(\w+)=([0-9a-fA-Fx-]+)", line):
        d[m.group(1)] = m.group(2)
    return d

rows = []
for ln in open(KEYS):
    f = ln.split()
    if len(f) != 6:
        continue
    rows.append(dict(instr=f[0], mode=f[1], se=f[2], sig=f[3],
                     hw_se=f[4], hw_sig=f[5]))

def run_one(r):
    args = [MODEL, "--batch",
            "--fcos-standalone" if r["instr"] == "cos"
            else "--fsin-standalone",
            "--dump-internals"]
    if r["mode"] != "rn":
        args.append("--rc=" + r["mode"])
    p = subprocess.run(args, input="%s %s\n" % (r["se"], r["sig"]),
                       capture_output=True, text=True)
    return p.stdout.strip(), p.stderr

out = open("h917_census.tsv", "w")
hdr = ("instr mode se sig hw_se hw_sig mo_se mo_sig delta path nR59 "
       "theta k ce s4 side b1 b2 low3 dist rsh payload fire tie_u0 "
       "band_reg band_uu band_tt band_base crit pm phw bs_bit8 bs_bitbs "
       "tc_elig tc_act b81 corr_via")
out.write("\t".join(hdr.split()) + "\n")

groups = collections.Counter()
detail = []
for r in rows:
    so, se_ = run_one(r)
    m = re.match(r"OK ([0-9a-f]{4}) ([0-9a-f]{16})", so)
    mo_se, mo_sig = (m.group(1), m.group(2)) if m else ("----", "-" * 16)
    if m and mo_se == r["hw_se"]:
        delta = int(mo_sig, 16) - int(r["hw_sig"], 16)
    elif m:
        delta = 999  # exponent differs; inspect manually
    else:
        delta = -999
    r59s = []
    br = crit = bs = tc = b81 = None
    corr_via = []
    for ln in se_.splitlines():
        if ln.startswith("DI_R59"):
            r59s.append(parse_kv(ln))
        elif ln.startswith("DI_BR"):
            br = parse_kv(ln)
            br["br"] = re.search(r"br=(\w+)", ln).group(1)
        elif ln.startswith("DI_CRIT"):
            crit = parse_kv(ln)
        elif ln.startswith("DI_BS"):
            bs = parse_kv(ln)
        elif ln.startswith("DI_TC "):
            tc = parse_kv(ln)
        elif ln.startswith("DI_B81"):
            b81 = parse_kv(ln)
        elif ln.startswith("DI_CORR"):
            corr_via.append(re.search(r"via=(\w+)", ln).group(1))
    d = r59s[-1] if r59s else {}
    path = br["br"] if br else ("+".join(corr_via) if corr_via else "none")
    fire = ""
    if br:
        fire = br.get("fire", br.get("tfire", ""))
    g = lambda k: d.get(k, "")
    vals = [r["instr"], r["mode"], r["se"], r["sig"], r["hw_se"],
            r["hw_sig"], mo_se, mo_sig, str(delta), path, str(len(r59s)),
            g("theta"), g("k"), g("ce"), g("s4"), g("side"), g("b1"),
            g("b2"), g("low3"), g("dist"), g("rsh"), g("payload"), fire,
            br.get("u0", "") if br else "",
            br.get("in_region", "") if br else "",
            br.get("uu", "") if br else "",
            br.get("tt", "") if br else "",
            br.get("base", "") if br else "",
            crit.get("crit", "") if crit else "",
            crit.get("pm", "") if crit else "",
            crit.get("phw", "") if crit else "",
            bs.get("bit8", "") if bs else "",
            bs.get("bitbs", "") if bs else "",
            tc.get("elig", "") if tc else "",
            tc.get("active", "") if tc else "",
            "1" if b81 else "0",
            "+".join(corr_via)]
    out.write("\t".join(vals) + "\n")
    fam = "comb" if r["se"] == "3ffc" and r["instr"] == "cos" else "randv1"
    key = (fam, r["instr"], path,
           "th%s" % g("theta") if g("theta") != "" else "-",
           "s4=%s/%s" % (g("s4"), g("side")) if g("s4") != "" else "-",
           "fire=%s" % fire if fire != "" else "-",
           "d=%+d" % delta if abs(delta) < 10 else "d=?")
    groups[key] += 1
    detail.append((key, r, d, br))
out.close()

print("== h917 census summary (36 keys) ==")
for k, n in sorted(groups.items()):
    print("%3d  %s" % (n, "  ".join(str(x) for x in k)))
print()
print("== per-key one-liners ==")
for key, r, d, br in detail:
    print("%s %s %s%s  path=%-7s th=%-2s s4=%s,%s ce=%-3s d=%-2s low3=%-2s "
          "b1b2=%s%s pay=%-2s fire=%s  delta=%s"
          % (r["instr"], r["mode"], r["se"], r["sig"][:8],
             key[2], d.get("theta", "-"), d.get("s4", "-"),
             d.get("side", "-"), d.get("ce", "-"), d.get("dist", "-"),
             d.get("low3", "-"), d.get("b1", "-"), d.get("b2", "-"),
             d.get("payload", "-"), key[5], key[6]))
