#!/usr/bin/env python3
# Grand scoring: union of census (band_hits.tsv), phase-3
# (band3_hits_labeled.tsv), and the pool/blind labeled rows.
# DI-extract the cell for every row, print the full cell map and
# score all surviving candidate forms.
import subprocess, re, collections, os, sys

rows = []          # (lab, src, insn, mode, se, sig)
for fn, srcname in (("band_hits.tsv", "census"),
                    ("band3_hits_labeled.tsv", "band3")):
    if not os.path.exists(fn):
        continue
    for l in open(fn):
        t = l.rstrip("\n").split("\t")
        if t[0] not in ("CARRY", "NOCARRY"):
            continue
        se, sig = t[5].split()[:2]
        rows.append((t[0], srcname, t[2], t[3], se, sig))

# pool stragglers (hw carries), the POS/NEG controls, rv5 rows
POOL = [
 ("CARRY","pool","cos","rn","401c","af316268703fc194"),
 ("CARRY","pool","cos","rn","401f","9246de36bed62392"),
 ("CARRY","pool","sin","rn","c028","b9c7aa87ed617ecc"),
 ("CARRY","pool","sin","ru","4005","ac53b9a8eff8f3a7"),
 ("CARRY","pool","sin","ru","402b","b96520948f7a7000"),
 ("CARRY","pool","cos","rn","c014","b17ce8403053ed23"),
 ("CARRY","pool","cos","ru","c02a","d20636b59b05ad28"),
 ("CARRY","pool","sin","rd","401b","a57ad07d247a9800"),
 ("CARRY","pool","cos","rd","4020","9186fa1607c8a800"),
 ("CARRY","pool","sin","rn","401a","8c5bcc66a3c57800"),
 ("CARRY","pool","cos","rn","c02a","b34cbe0072d9947d"),
 ("CARRY","pool","cos","ru","400a","8815a6f089856000"),
 ("CARRY","pool","cos","ru","401d","b5d373d177f1eb43"),
 ("CARRY","pool","sin","ru","c025","c6ad534293ff8800"),
 ("NOCARRY","pool","cos","rn","4008","9eb31894b9f4e0f7"),
]
rows.extend(POOL)

groups = collections.defaultdict(list)
for r in rows:
    groups[(r[2], r[3])].append(r)

recs = []
for (insn, mode), g in groups.items():
    RC = {"rn": [], "rd": ["--rc=rd"], "ru": ["--rc=ru"], "rz": ["--rc=rz"]}[mode]
    FL = ["--fsin-standalone"] if insn == "sin" else ["--fcos-standalone"]
    inp = "".join(r[4] + " " + r[5] + "\n" for r in g)
    p = subprocess.run(["./model_bandA", "--batch"] + RC + FL + ["--dump-internals"],
                       input=inp, capture_output=True, text=True)
    di_rows = []
    cur = None
    for ln in p.stderr.splitlines():
        if ln.startswith("DI_TC "):
            cur = {}
            di_rows.append(cur)
        if cur is not None:
            cur.setdefault(ln.split()[0], ln)
    assert len(di_rows) == len(g), (insn, mode, len(di_rows), len(g))
    for r, di in zip(g, di_rows):
        tc = di.get("DI_TC", "")
        acc = di.get("DI_ACC", "")
        low3 = int(re.search(r"low3=(\d+)", tc).group(1))
        act = int(re.search(r"active=(\d+)", tc).group(1))
        d60 = int(re.search(r"d60=([0-9a-f]{32})", acc).group(1), 16)
        low30 = d60 >> 30
        recs.append(dict(lab=r[0], src=r[1], insn=insn, mode=mode,
                         se=r[4], sig=r[5], low3=low3, active=act,
                         top8=low30 >> 22, b21=(low30 >> 21) & 1,
                         below21=low30 & ((1 << 21) - 1),
                         d60low=d60 & ((1 << 30) - 1)))

PT = [1, 2, 2, 3, 5, 5, 6, 7]
def world_p(h):
    d = 0xFF - h["top8"]
    return 0 <= d <= 7 and h["low3"] >= PT[d]
def world_q(h):
    s = h["top8"] + h["low3"]
    return s >= 0x100 or (s == 0xFF and h["low3"] >= 2 and h["b21"] == 0)
def world_q2(h):   # diagonal for all d>=2 regardless of b21
    s = h["top8"] + h["low3"]
    return s >= 0x100 or (s == 0xFF and h["low3"] >= 2)
def world_qz(h):   # diagonal needs the ENTIRE tail below the field zero
    s = h["top8"] + h["low3"]
    return s >= 0x100 or (s == 0xFF and h["low3"] >= 2 and h["b21"] == 0
                          and h["below21"] == 0 and h["d60low"] == 0)
FORMS = {
    "sumA":    lambda h: h["top8"] + h["low3"] >= 0x100,
    "worldP":  world_p,
    "worldQ":  world_q,
    "worldQ2": world_q2,
    "worldQz": world_qz,
}

cells = collections.defaultdict(collections.Counter)
for h in recs:
    cells[(h["top8"], h["b21"], h["low3"])][h["lab"]] += 1
print("cell map (top8, b21, low3) — only cells with sum >= 0xFE shown:")
for (t8, b21, l3), c in sorted(cells.items()):
    if t8 + l3 < 0xFE:
        continue
    print("  t8=%s b21=%d l3=%d sum=%s  CARRY=%-5d NOCARRY=%d"
          % (hex(t8), b21, l3, hex(t8 + l3), c["CARRY"], c["NOCARRY"]))
print("\nform scores over %d labeled rows:" % len(recs))
for name, f in FORMS.items():
    errs = [h for h in recs if f(h) != (h["lab"] == "CARRY")]
    print("  %-8s: %3d errors" % (name, len(errs)))
    ec = collections.Counter(
        (h["top8"], h["b21"], h["low3"], h["lab"]) for h in errs)
    for (t8, b21, l3, lab), n in sorted(ec.items())[:10]:
        print("      t8=%s b21=%d l3=%d %s: %d" % (hex(t8), b21, l3, lab, n))
