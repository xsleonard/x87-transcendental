#!/usr/bin/env python3
# h738: default-stratum predicate hunt.  Positives = the h733+randv1
# default-branch votes (chip corr differs by +-1 corr-lsb).  Field
# candidates per row: the S-B discarded low field ((-B) mod 2^dl),
# left/right product discard fractions, low bits of every dumped
# value.  Negatives = clean default rows from a regenerated chunk.
import subprocess, re, random, collections

def parse_wv(s):
    sg, e2, hx = s.split(":")
    return (int(sg), int(e2), int(hx, 16))

def dump_rows(pairs, flag):
    """run model_h235 --dump-internals over ops; return list of DI dicts"""
    inp = "\n".join("%s %s" % p for p in pairs) + "\n"
    p = subprocess.run(["./model_h235","--batch",flag,"--dump-internals"],
                       input=inp, capture_output=True, text=True)
    out = []
    d = None
    for L in p.stderr.splitlines():
        t = L.split()
        if not t: continue
        if t[0] == "DI_IN":
            if d is not None: out.append(d)
            d = {}
        elif d is not None and t[0].startswith("DI_"):
            dd = d.setdefault(t[0], {})
            for kv in t[1:]:
                k, v = kv.split("=", 1)
                dd[k] = v
    if d is not None: out.append(d)
    return out

def feats(d):
    tc = d.get("DI_TC"); corr = d.get("DI_CORR", {})
    if not tc or corr.get("via") != "default": return None
    left = parse_wv(tc["left"]); right = parse_wv(tc["right"])
    dl = left[1] - right[1]
    if dl <= 0 or dl > 30: return None
    B_low = right[2] & ((1 << dl) - 1)
    disc = ((1 << dl) - B_low) & ((1 << dl) - 1)   # (S-B) discarded field
    mul = parse_wv(tc["mul"]); lf = parse_wv(tc["lf"])
    rf = parse_wv(tc["rf"]); f4 = parse_wv(tc["f4"])
    lfull = mul[2] * lf[2]; shL = lfull.bit_length() - 67
    fracL = (lfull & ((1 << shL) - 1)) / float(1 << shL)
    rfull = f4[2] * rf[2]; shR = rfull.bit_length() - 67
    fracR = (rfull & ((1 << shR) - 1)) / float(1 << shR)
    return dict(dl=dl, disc_frac=disc / float(1 << dl),
                B_low=B_low, fracL=fracL, fracR=fracR,
                low3=int(tc["low3"]), active=int(tc["active"]),
                lsig_low=left[2] & 0xf, rsig_low=right[2] & 0xf)

# positives from votes
votes = collections.defaultdict(dict)
for l in open("h733_votes.txt"):
    t = l.split()
    votes[(t[3], t[4], t[1])][t[2]] = (t[5].split("=")[1], t[6].split("=")[1])
pos = {"cos": [], "sin": []}
for (se, sig, insn) in votes:
    pos[insn].append((se, sig))
P = []
for insn in ("cos","sin"):
    flag = "--fcos-standalone" if insn=="cos" else "--fsin-standalone"
    for d in dump_rows(pos[insn], flag):
        f = feats(d)
        if f: P.append(f)
print("default-branch positives with features:", len(P))
# negatives: regenerate chunk 1, sample 6000 rows, drop the vote ops
subprocess.run(["python3","h733_gen.py","0x733001","200000","neg_inputs.txt"])
allops = set()
for k in votes: allops.add((k[0], k[1]))
neg_pairs = []
for l in open("neg_inputs.txt"):
    se, sig = l.split()
    if (se, sig) not in allops: neg_pairs.append((se, sig))
    if len(neg_pairs) >= 6000: break
N = []
for insn, flag in (("cos","--fcos-standalone"),("sin","--fsin-standalone")):
    for d in dump_rows(neg_pairs[:3000] if insn=="cos" else neg_pairs[3000:],
                       flag):
        f = feats(d)
        if f: N.append(f)
print("default-branch clean rows:", len(N))
import statistics
for key in ("disc_frac","fracL","fracR"):
    pv = [f[key] for f in P]; nv = [f[key] for f in N]
    print("%-10s pos mean %.4f sd %.4f | clean mean %.4f sd %.4f"
          % (key, statistics.mean(pv), statistics.pstdev(pv),
             statistics.mean(nv), statistics.pstdev(nv)))
for key in ("dl","low3","active","lsig_low","rsig_low"):
    pc = collections.Counter(f[key] for f in P)
    nc = collections.Counter(f[key] for f in N)
    tot_p = sum(pc.values()); tot_n = sum(nc.values())
    cells = []
    for v in sorted(set(pc) | set(nc)):
        cells.append("%s:%.2f/%.2f" % (v, pc.get(v,0)/tot_p,
                                       nc.get(v,0)/tot_n))
    print("%-10s %s" % (key, "  ".join(cells)))
