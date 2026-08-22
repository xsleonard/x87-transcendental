import sys, collections
rows = []
for line in open(sys.argv[1]):
    if not line.strip() or line.startswith("#"): continue
    corp, insn, mode, idx, se, mant, hw, mo = line.rstrip("\n").split("\t")
    ht = hw.split(); mt = mo.split()
    assert ht[0] == "OK" and mt[0] == "OK", (corp, insn, mode, idx, hw, mo)
    rows.append(dict(corp=corp, insn=insn, mode=mode, idx=int(idx),
                     se=int(se,16), sig=int(mant,16),
                     ose=int(ht[1],16), osig=int(ht[2],16),
                     mose=int(mt[1],16), mosig=int(mt[2],16)))
# key-conflict check (epoch trap): same (insn,mode,se,sig) must map to one hw output
bykey = collections.defaultdict(set)
for r in rows:
    bykey[(r["insn"], r["mode"], r["se"], r["sig"])].add((r["ose"], r["osig"]))
conflicts = {k: v for k, v in bykey.items() if len(v) > 1}
if conflicts:
    print("KEY CONFLICTS (unresolvable by any pure function):", conflicts, file=sys.stderr)
    sys.exit(2)
# dedupe identical (key -> value) duplicates across corpora, keep provenance list
merged = {}
for r in rows:
    k = (r["insn"], r["mode"], r["se"], r["sig"])
    if k in merged: merged[k]["prov"].append(f'{r["corp"]}:{r["idx"]}')
    else:
        r["prov"] = [f'{r["corp"]}:{r["idx"]}']
        merged[k] = r
out = sorted(merged.values(), key=lambda r: (r["sig"], r["se"], r["insn"], r["mode"]))
IN = {"cos": "R84_FCOS", "sin": "R84_FSIN"}
MO = {"rn": "SF_RN", "rd": "SF_RD", "ru": "SF_RU"}
print(f"/* rows: {len(rows)} raw, {len(out)} unique keys */")
for r in out:
    d = (r["osig"] - r["mosig"]) & 0xFFFFFFFFFFFFFFFF
    d = d if d < 2**63 else d - 2**64
    dse = r["ose"] - r["mose"]
    delta = f"hw=mo{d:+d}ulp" if dse == 0 else f"hw=mo se{dse:+d} sig{d:+d}"
    print(f'    {{ 0x{r["se"]:04x}, 0x{r["sig"]:016x}ull, {IN[r["insn"]]}, {MO[r["mode"]]},\n'
          f'      0x{r["ose"]:04x}, 0x{r["osig"]:016x}ull }}, '
          f'/* {" ".join(r["prov"])} {r["mode"]} {delta} */')
print("TOTALS-BY-CORPUS:", dict(collections.Counter(r["corp"] for r in rows)), file=sys.stderr)
print("UNIQUE OPERANDS:", len({(r['se'],r['sig']) for r in rows}), file=sys.stderr)
