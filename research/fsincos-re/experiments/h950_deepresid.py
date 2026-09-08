#!/usr/bin/env python3
# h950: identify the 1,160-leg deep residual (invisible-C: hw !=
# model where the payload decision cannot matter) against the
# parked adder-band signature (h914/h916: top8 = bits 52-59 of
# DI_ACC d60, sum = top8 + low3, band = [0xFD, 0x106]; act1
# over-side 0x100-0x106 graded, act0 under-side 0xFD-0xFF).
# Background: random sample of AGREE legs in the same deep zone.
# Run on i7 in /root/r84.
import random, re, subprocess, sys
from collections import Counter, defaultdict

# --- labels: all C legs + AGREE sample pool ---
c_legs = {}      # (insn, mode, op) -> (hw_se, hw_sig, mo_se, mo_sig, seed)
agree_pool = []
for ln in open("h931_labels.tsv"):
    t = ln.rstrip("\n").split("\t")
    if len(t) != 9: continue
    k = (t[1], t[2], t[3])
    if t[8] == "C":
        c_legs[k] = (t[4], t[5], t[6], t[7], int(t[0]))
    elif t[8] == "AGREE":
        agree_pool.append(k)

# --- subtract the visible (payload-decisive) C legs ---
visible = set()
f = open("h948_gate_corpus.tsv"); f.readline()
for ln in f:
    t = ln.rstrip("\n").split("\t")
    if len(t) == 6: visible.add((t[0], t[1], t[2]))
resid = {k: v for k, v in c_legs.items() if k not in visible}
print("C legs total:", len(c_legs), "visible:",
      sum(1 for k in c_legs if k in visible), "residual:", len(resid))

random.seed(950)
bg = random.sample(agree_pool, min(12000, len(agree_pool)))

def dump(keys):
    """keys: list of (insn, mode, op) -> dict key -> coords"""
    out = {}
    grp = defaultdict(list)
    for k in keys: grp[(k[0], k[1])].append(k[2])
    for (insn, mode), opsl in sorted(grp.items()):
        fl = "--fsin-standalone" if insn == "sin" else "--fcos-standalone"
        args = ["./model_r92", "--batch", fl, "--dump-internals"]
        if mode != "rn": args.insert(2, "--rc=" + mode)
        p = subprocess.run(args, input="\n".join(opsl) + "\n",
                           capture_output=True, text=True)
        rows, cur = [], None
        for ln in p.stderr.splitlines():
            tag = ln.split(" ", 1)[0]
            if tag == "DI_IN":
                if cur is not None: rows.append(cur)
                cur = {"_tags": set()}
                continue
            if cur is None: continue
            if tag in cur["_tags"]: continue
            cur["_tags"].add(tag)
            if tag == "DI_TC":
                for f_ in ("active", "low3", "dist", "ud", "rud",
                           "payload", "rsh"):
                    m = re.search(f_ + r"=(-?\d+)", ln)
                    if m: cur[f_] = int(m.group(1))
                m = re.search(r"mul=\d+:(-?\d+):", ln)
                if m: cur["mule2"] = int(m.group(1))
            elif tag == "DI_ACC":
                m = re.search(r"d60=([0-9a-f]{32})", ln)
                if m: cur["top8"] = (int(m.group(1), 16) >> 52) & 0xFF
            elif tag == "DI_B81":
                m = re.search(r"act=(\d+)", ln)
                if m: cur["b81act"] = int(m.group(1))
            elif tag == "DI_CORR":
                m = re.search(r"via=(\w+)", ln)
                if m: cur["via"] = m.group(1)
        if cur is not None: rows.append(cur)
        assert len(rows) == len(opsl), (insn, mode, len(rows), len(opsl))
        for op, r in zip(opsl, rows):
            del r["_tags"]
            out[(insn, mode, op)] = r
    return out

resid_d = dump(list(resid))
bg_d = dump(bg)

def delta(hw_se, hw_sig, mo_se, mo_sig):
    if hw_se != mo_se: return "SE"
    d = int(hw_sig, 16) - int(mo_sig, 16)
    return d if abs(d) <= 2 else "BIG"

def coords(r):
    t8 = r.get("top8", -1); l3 = r.get("low3", -1)
    s = t8 + l3 if t8 >= 0 and l3 >= 0 else -1
    return s, r.get("active", -1), r.get("dist", -1), r.get("mule2", 0)

print("\n=== RESIDUAL (n=%d) ===" % len(resid))
cnt = Counter(); sums = Counter(); dists = Counter(); via = Counter()
for k, v in resid.items():
    r = resid_d[k]
    s, act, dist, me2 = coords(r)
    dl = delta(*v[:4])
    inb = 0xFD <= s <= 0x106 if s >= 0 else False
    cnt[(dl, act, inb)] += 1
    sums[s if inb else ("lo" if s < 0xFD else "hi")] += 1
    dists[(dist, me2)] += 1
    via[r.get("via", "?")] += 1
for k in sorted(cnt, key=str): print("delta/act/inband", k, cnt[k])
print("sum histogram:", dict(sorted(sums.items(), key=str)))
print("via:", dict(via))
print("(dist,mule2) top:", dists.most_common(12))

print("\n=== BACKGROUND deep AGREE (dist 11-14) ===")
bcnt = Counter(); bsums = Counter(); nb = 0
for k in bg:
    r = bg_d[k]
    s, act, dist, me2 = coords(r)
    if not (11 <= dist <= 14): continue
    nb += 1
    inb = 0xFD <= s <= 0x106 if s >= 0 else False
    bcnt[(act, inb)] += 1
    if inb: bsums[s] += 1
print("deep AGREE legs sampled:", nb)
for k in sorted(bcnt, key=str): print("act/inband", k, bcnt[k])
print("in-band sums:", dict(sorted(bsums.items())))
