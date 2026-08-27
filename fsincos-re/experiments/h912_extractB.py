#!/usr/bin/env python3
# B-side extractor: d60 + terminal frame from model_payB (payload
# declined) — the no-payload sum's own below-terminal field.
import subprocess, re, sys, collections
inf, outf = sys.argv[1], sys.argv[2]
rows = []
for l in open(inf):
    t = l.rstrip("\n").split("\t")
    if len(t) < 9 or t[0] == "WEIRD":
        continue
    rows.append((t[0], t[1], t[2], t[3], t[5]))
groups = collections.defaultdict(list)
for r in rows:
    groups[(r[2], r[3])].append(r)
WV = re.compile(r"(\w+)=(\d+):(-?\d+):([0-9a-f]{32})")
out = open(outf, "w")
out.write("insn\tmode\tse\tsig\td60B\ttcBsig\ttcBe2\tleB\treB\tpayB\n")
for (insn, mode), g in groups.items():
    RC = {"rn": [], "rd": ["--rc=rd"], "ru": ["--rc=ru"], "rz": ["--rc=rz"]}[mode]
    FL = ["--fsin-standalone"] if insn == "sin" else ["--fcos-standalone"]
    inp = "".join(r[4] + "\n" for r in g)
    p = subprocess.run(["./model_payB", "--batch"] + RC + FL + ["--dump-internals"],
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
        acc = di.get("DI_ACC", "")
        wv = {m[0]: m for m in WV.findall(tc)}
        d60 = re.search(r"d60=([0-9a-f]{32})", acc)
        f = dict(re.findall(r"(\w+)=(-?\w+)", tc))
        se, sig = r[4].split()
        out.write("\t".join((insn, mode, se, sig,
            d60.group(1) if d60 else "",
            wv["left"][2] if "left" in wv else "", wv["right"][2] if "right" in wv else "",
            f.get("payload",""))) + "\n")
out.close()
print("wrote", outf, len(rows))
