import subprocess, re, collections, os, sys
# Score MODEL BUILDS against hw on every labeled band row.
# Usage: model_score.py ./model_exact ./model_q ...
models = sys.argv[1:]
rows = []
for fn in ("band_hits.tsv", "band3_hits_labeled.tsv"):
    if not os.path.exists(fn):
        continue
    for l in open(fn):
        t = l.rstrip("\n").split("\t")
        if t[0] not in ("CARRY", "NOCARRY"):
            continue
        se, sig = t[5].split()[:2]
        hw = t[8]
        rows.append([t[0], t[2], t[3], se, sig, hw])
POOL = [
 ("cos","rn","401c","af316268703fc194"),
 ("cos","rn","401f","9246de36bed62392"),
 ("sin","rn","c028","b9c7aa87ed617ecc"),
 ("sin","ru","4005","ac53b9a8eff8f3a7"),
 ("sin","ru","402b","b96520948f7a7000"),
 ("cos","rn","c014","b17ce8403053ed23"),
 ("cos","ru","c02a","d20636b59b05ad28"),
 ("sin","rd","401b","a57ad07d247a9800"),
 ("cos","rd","4020","9186fa1607c8a800"),
 ("sin","rn","401a","8c5bcc66a3c57800"),
 ("cos","rn","c02a","b34cbe0072d9947d"),
 ("cos","ru","400a","8815a6f089856000"),
 ("cos","ru","401d","b5d373d177f1eb43"),
 ("sin","ru","c025","c6ad534293ff8800"),
 ("cos","rn","4008","9eb31894b9f4e0f7"),
]
def norm3(line):
    f = line.split()
    return " ".join(f[:3]) if f and f[0] == "OK" else (f[0] if f else "")
# capture hw for pool rows fresh
pg = collections.defaultdict(list)
for insn, mode, se, sig in POOL:
    pg[(insn, mode)].append((se, sig))
for (insn, mode), g in pg.items():
    inp = "".join(se + " " + sig + "\n" for se, sig in g)
    p = subprocess.run(["/root/x87_capture_x86_64", mode, insn],
                       input=inp, capture_output=True, text=True)
    for (se, sig), hwl in zip(g, p.stdout.splitlines()):
        rows.append(["POOL", insn, mode, se, sig, norm3(hwl)])
groups = collections.defaultdict(list)
for r in rows:
    groups[(r[1], r[2])].append(r)
for M in models:
    tot = bad = 0
    badrows = []
    for (insn, mode), g in groups.items():
        RC = {"rn": [], "rd": ["--rc=rd"], "ru": ["--rc=ru"], "rz": ["--rc=rz"]}[mode]
        FL = ["--fsin-standalone"] if insn == "sin" else ["--fcos-standalone"]
        inp = "".join(r[3] + " " + r[4] + "\n" for r in g)
        p = subprocess.run([M, "--batch"] + RC + FL,
                           input=inp, capture_output=True, text=True)
        for r, out in zip(g, p.stdout.splitlines()):
            tot += 1
            if norm3(out) != r[5]:
                bad += 1
                badrows.append((r[1], r[2], r[3], r[4], norm3(out), r[5]))
    print("%s: %d wrong / %d rows" % (M, bad, tot))
    for b in badrows[:12]:
        print("   ", *b)
