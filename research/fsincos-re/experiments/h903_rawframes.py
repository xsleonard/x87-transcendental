#!/usr/bin/env python3
# Dump RAW datapath components for every labeled band row:
# census + phase3/4 + ALL pool default-terminal rows (labeled by
# capture hw vs bandA/bandB outputs).  Output: one TSV with full
# 128-bit sigs so the exact tail composition can be fit offline.
import subprocess, re, collections, os

def norm3(line):
    f = line.split()
    return " ".join(f[:3]) if f and f[0] == "OK" else (f[0] if f else "")

rows = []   # (lab, src, insn, mode, se, sig)
for fn, srcname in (("band_hits.tsv", "census"),
                    ("band3_hits_labeled_p3.tsv", "band3"),
                    ("band3_hits_labeled.tsv", "band4")):
    if not os.path.exists(fn):
        continue
    for l in open(fn):
        t = l.rstrip("\n").split("\t")
        if t[0] not in ("CARRY", "NOCARRY"):
            continue
        se, sig = t[5].split()[:2]
        rows.append((t[0], srcname, t[2], t[3], se, sig))

# pool rows: label via capture vs bandA/bandB
prows = []
seen = set()
for f in ("/root/r59/h753_allvotes.txt", "/root/r59/h759_miner2_votes.txt",
          "/root/r59/h780_votes.txt"):
    for l in open(f):
        t = l.split()
        if len(t) < 7:
            continue
        k = (t[1], t[2], t[3], t[4])
        if k in seen:
            continue
        seen.add(k)
        prows.append(k)
pg = collections.defaultdict(list)
for insn, mode, se, sig in prows:
    pg[(insn, mode)].append((se, sig))
for (insn, mode), g in pg.items():
    RC = {"rn": [], "rd": ["--rc=rd"], "ru": ["--rc=ru"], "rz": ["--rc=rz"]}[mode]
    FL = ["--fsin-standalone"] if insn == "sin" else ["--fcos-standalone"]
    inp = "".join(se + " " + sig + "\n" for se, sig in g)
    pa = subprocess.run(["./model_bandA", "--batch"] + RC + FL,
                        input=inp, capture_output=True, text=True).stdout.splitlines()
    pb = subprocess.run(["./model_bandB", "--batch"] + RC + FL,
                        input=inp, capture_output=True, text=True).stdout.splitlines()
    ph = subprocess.run(["/root/x87_capture_x86_64", mode, insn],
                        input=inp, capture_output=True, text=True).stdout.splitlines()
    for (se, sig), a, b, h in zip(g, pa, pb, ph):
        na, nb, nh = norm3(a), norm3(b), norm3(h)
        if na == nb:
            continue          # invisible: no label
        lab = "CARRY" if nh == nb else ("NOCARRY" if nh == na else "OTHER")
        if lab == "OTHER":
            continue
        rows.append((lab, "pool", insn, mode, se, sig))

groups = collections.defaultdict(list)
for r in rows:
    groups[(r[2], r[3])].append(r)
out = open("band_raw_frames.tsv", "w")
out.write("lab\tsrc\tinsn\tmode\tse\tsig\tactive\tpayload\tlow3\tdist\trsh\tud\tu5d\trud\t"
          "mule2\tmulsig\tlfe2\tlfsig\trfe2\trfsig\tf4e2\tf4sig\t"
          "lefte2\tleftsig\tleftsign\trighte2\trightsig\trightsign\td60\n")
for (insn, mode), g in groups.items():
    RC = {"rn": [], "rd": ["--rc=rd"], "ru": ["--rc=ru"], "rz": ["--rc=rz"]}[mode]
    FL = ["--fsin-standalone"] if insn == "sin" else ["--fcos-standalone"]
    for r in g:
        p = subprocess.run(["./model_bandA", "--batch"] + RC + FL + ["--dump-internals"],
                           input=r[4] + " " + r[5] + "\n",
                           capture_output=True, text=True)
        di = {}
        for ln in p.stderr.splitlines():
            di.setdefault(ln.split()[0], ln)
        tc = di.get("DI_TC", "")
        acc = di.get("DI_ACC", "")
        if "DI_ACC" not in di or "DI_TC" not in di:
            continue
        f = dict(re.findall(r"(\w+)=(-?\w+)", tc))
        wv = {}
        for name in ("mul", "lf", "rf", "f4", "left", "right"):
            m = re.search(name + r"=(\d+):(-?\d+):([0-9a-f]{32})", tc)
            wv[name] = (int(m.group(1)), int(m.group(2)), m.group(3))
        d60 = re.search(r"d60=([0-9a-f]{32})", acc).group(1)
        out.write("\t".join(str(x) for x in (
            r[0], r[1], insn, mode, r[4], r[5],
            f["active"], f["payload"], f["low3"], f["dist"], f["rsh"],
            f["ud"], f["u5d"], f["rud"],
            wv["mul"][1], wv["mul"][2], wv["lf"][1], wv["lf"][2],
            wv["rf"][1], wv["rf"][2], wv["f4"][1], wv["f4"][2],
            wv["left"][1], wv["left"][2], wv["left"][0],
            wv["right"][1], wv["right"][2], wv["right"][0],
            d60)) + "\n")
out.close()
print("rows labeled:", len(rows),
      dict(collections.Counter(r[0] for r in rows)),
      dict(collections.Counter(r[1] for r in rows)))
