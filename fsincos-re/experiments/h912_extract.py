#!/usr/bin/env python3
# h912 DI extractor: labeled hit rows (act_census.tsv / act_fresh.tsv
# format: lab corp/seed insn mode row op A B hw) -> full DI frame TSV.
# Dumps from model_payA (--dump-internals): DI_TC (payload frame),
# DI_B81 (act1 gate frame), DI_ACC (d60), DI_RED (i1 i0 rsn).
import subprocess, re, sys, collections
inf, outf = sys.argv[1], sys.argv[2]
rows = []
for l in open(inf):
    t = l.rstrip("\n").split("\t")
    if len(t) < 9 or t[0] == "WEIRD":
        continue
    rows.append((t[0], t[1], t[2], t[3], t[5]))   # lab src insn mode op
print("rows in:", len(rows))
groups = collections.defaultdict(list)
for r in rows:
    groups[(r[2], r[3])].append(r)
WV = re.compile(r"(\w+)=(\d+):(-?\d+):([0-9a-f]{32})")
out = open(outf, "w")
hdr = ("lab","src","insn","mode","se","sig","act","pay","low3","dist","rsh","ud","u5d","rud",
       "mule2","neg","lb","df","top","rem","dspan","wk","pm","phw","th","at","b8","bbs",
       "i1","i0","rsn","d60","lsig","le2","lsign","rsig","re2","rsign","tcsig","tce2",
       "mulsig","lfsig","lfe2","f4sig","f4e2","rfsig","rfe2","mage2")
out.write("\t".join(hdr) + "\n")
for (insn, mode), g in groups.items():
    RC = {"rn": [], "rd": ["--rc=rd"], "ru": ["--rc=ru"], "rz": ["--rc=rz"]}[mode]
    FL = ["--fsin-standalone"] if insn == "sin" else ["--fcos-standalone"]
    inp = "".join(r[4] + "\n" for r in g)
    p = subprocess.run(["./model_payA", "--batch"] + RC + FL + ["--dump-internals"],
                       input=inp, capture_output=True, text=True)
    di_rows = []
    cur = None
    for ln in p.stderr.splitlines():
        if ln.startswith("DI_IN "):
            cur = {}
            di_rows.append(cur)
        if cur is not None:
            cur.setdefault(ln.split()[0], ln)
    assert len(di_rows) == len(g), (insn, mode, len(di_rows), len(g))
    for r, di in zip(g, di_rows):
        tc = di.get("DI_TC", "")
        b81 = di.get("DI_B81", "")
        acc = di.get("DI_ACC", "")
        red = di.get("DI_RED", "")
        f = dict(re.findall(r"(\w+)=(-?\w+)", tc))
        fb = dict(re.findall(r"(\w+)=(-?\w+)", b81)) if b81 else {}
        wv = {m[0]: m for m in WV.findall(tc)}
        wb = {m[0]: m for m in WV.findall(b81)} if b81 else {}
        d60 = re.search(r"d60=([0-9a-f]{32})", acc)
        fr = dict(re.findall(r"(\w+)=(-?\w+)", red)) if red else {}
        se, sig = r[4].split()
        out.write("\t".join(str(x) for x in (
            r[0], r[1], insn, mode, se, sig,
            f.get("active",""), f.get("payload",""), f.get("low3",""),
            f.get("dist",""), f.get("rsh",""), f.get("ud",""),
            f.get("u5d",""), f.get("rud",""), wv["mul"][2] if "mul" in wv else "",
            fb.get("neg",""), fb.get("lb",""), fb.get("df",""),
            fb.get("top",""), fb.get("rem",""), fb.get("dspan",""),
            fb.get("wk",""), fb.get("pm",""), fb.get("phw",""),
            fb.get("th",""), fb.get("at",""), fb.get("b8",""), fb.get("bbs",""),
            fr.get("i1",""), fr.get("i0",""), fr.get("rsn",""),
            d60.group(1) if d60 else "",
            wb["L"][3] if "L" in wb else "", wb["L"][2] if "L" in wb else "",
            wb["L"][1] if "L" in wb else "",
            wb["R"][3] if "R" in wb else "", wb["R"][2] if "R" in wb else "",
            wb["R"][1] if "R" in wb else "",
            wb["tc"][3] if "tc" in wb else "", wb["tc"][2] if "tc" in wb else "",
            wv["mul"][3] if "mul" in wv else "",
            wv["lf"][3] if "lf" in wv else "", wv["lf"][2] if "lf" in wv else "",
            wv["f4"][3] if "f4" in wv else "", wv["f4"][2] if "f4" in wv else "",
            wv["rf"][3] if "rf" in wv else "", wv["rf"][2] if "rf" in wv else "",
            wv["mag"][2] if "mag" in wv else "",
            )) + "\n")
out.close()
print("wrote", outf)
