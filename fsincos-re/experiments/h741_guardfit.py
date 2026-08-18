#!/usr/bin/env python3
# h741: THE GUARD-COLUMN FIT.  Hypothesis: the chip's terminal
# subtract sees the right product rounded at column m = dl - g
# (g guard bits below the S grid): B' = round_m(B).  Predicted
# corr-lsb delta per row:
#   trunc: B' = B - (B mod 2^m); delta = +1 iff 0 < (B mod 2^dl) and
#          (B mod 2^dl) == (B mod 2^m)  [disc+lost mass wraps]
#   rn:    B' = nearest; round-up side gives delta = -1 iff
#          (S-B) mod 2^dl < (2^m - B mod 2^m) etc.
# Exact per-row evaluation: recompute corr' = chop67-grid of
# (S - B') directly and diff.  Score: every positive must match its
# hardware in ALL 3 modes under the predicted corr'; every clean row
# must remain output-identical in all 3 modes.
import subprocess, collections
from fractions import Fraction
import h715_forensics as F

def parse_wv(s):
    sg, e2, hx = s.split(":")
    return (int(sg), int(e2), int(hx, 16))

def dump_rows(pairs, flag):
    inp = "\n".join("%s %s" % p for p in pairs) + "\n"
    p = subprocess.run(["./model_h235","--batch",flag,"--dump-internals"],
                       input=inp, capture_output=True, text=True)
    out = []; d = None
    for L in p.stderr.splitlines():
        t = L.split()
        if not t: continue
        if t[0] == "DI_IN":
            if d is not None: out.append(d)
            d = {"IN": (t[1], t[2])}
        elif d is not None and t[0].startswith("DI_"):
            dd = d.setdefault(t[0], {})
            for kv in t[1:]:
                k, v = kv.split("=", 1)
                dd[k] = v
    if d is not None: out.append(d)
    return out

def model3(se, sig, flag):
    out = []
    for mode in ("rn","rd","ru"):
        args = ["./model_h235","--batch",flag]
        if mode != "rn": args.append("--rc="+mode)
        r = subprocess.run(args, input="%s %s\n" % (se, sig),
                           capture_output=True, text=True)
        t = r.stdout.split()
        out.append(t[1:3] if t[0]=="OK" else ["C2"])
    return out

def prep(d, insn, mm):
    tc = d.get("DI_TC"); corr = d.get("DI_CORR", {})
    poly = d.get("DI_POLY", {})
    if not tc or corr.get("via") != "default": return None
    left = parse_wv(tc["left"]); right = parse_wv(tc["right"])
    dl = left[1] - right[1]
    if dl <= 0 or dl > 40: return None
    se, sig = d["IN"]
    flag = "--fcos-standalone" if insn=="cos" else "--fsin-standalone"
    mo3 = model3(se, sig, flag)
    cw = parse_wv(corr["out"])
    v_pre = 1 + F.wv_val(cw)
    neg = None
    for cand in (0,1):
        vs = -v_pre if cand else v_pre
        if F.round80(vs, "rn").split() == mo3[0]:
            neg = cand; break
    if neg is None: return None
    hw3 = []
    for mi, mode in enumerate(("rn","rd","ru")):
        if mm and mode in mm:
            hw3.append(mm[mode][0].split("/"))
        else:
            hw3.append(mo3[mi])
    S = left[2] << dl
    B = right[2]
    CL = Fraction(2)**cw[1]
    return dict(S=S, B=B, dl=dl, v_pre=v_pre, neg=neg,
                hw3=hw3, mo3=mo3, CL=CL, is_pos=mm is not None,
                se=se, sig=sig, insn=insn)

votes = collections.defaultdict(dict)
for l in open("h733_votes.txt"):
    t = l.split()
    votes[(t[3], t[4], t[1])][t[2]] = (t[5].split("=")[1], t[6].split("=")[1])
R = []
for insn in ("cos","sin"):
    flag = "--fcos-standalone" if insn=="cos" else "--fsin-standalone"
    pairs = [(k[0],k[1]) for k in votes if k[2]==insn]
    for d, pr in zip(dump_rows(pairs, flag), pairs):
        r = prep(d, insn, votes[(pr[0],pr[1],insn)])
        if r: R.append(r)
npos = len(R)
# clean rows (chunk-2 seed, distinct from h738's chunk-1 negatives)
subprocess.run(["python3","h733_gen.py","0x733002","120000","neg2.txt"])
allops = set((k[0],k[1]) for k in votes)
cl_pairs = []
for l in open("neg2.txt"):
    a, b = l.split()
    if (a,b) not in allops: cl_pairs.append((a,b))
    if len(cl_pairs) >= 4000: break
for insn, flag in (("cos","--fcos-standalone"),("sin","--fsin-standalone")):
    sel = cl_pairs[:2000] if insn=="cos" else cl_pairs[2000:]
    for d, pr in zip(dump_rows(sel, flag), sel):
        r = prep(d, insn, None)
        if r: R.append(r)
print("positives:", npos, " clean:", len(R)-npos)

def predict(r, g, mode):
    m = r["dl"] - g
    if m <= 0:
        Bp = r["B"]
    else:
        low = r["B"] & ((1 << m) - 1)
        Bp = r["B"] - low
        if mode == "rn" and low >= (1 << (m-1)):
            Bp += (1 << m)
    corr_old = (r["S"] - r["B"]) >> r["dl"]
    corr_new = (r["S"] - Bp) >> r["dl"]
    return corr_new - corr_old      # in corr-lsb units

best = []
for g in range(3, 13):
    for mode in ("trunc","rn"):
        okp = 0; badc = 0
        for r in R:
            dlt = predict(r, g, mode)
            v = r["v_pre"] + dlt * r["CL"]
            vs = -v if r["neg"] else v
            out3 = [F.round80(vs, md).split() for md in ("rn","rd","ru")]
            if r["is_pos"]:
                if all(out3[i] == r["hw3"][i] for i in range(3)): okp += 1
            else:
                if any(out3[i] != r["mo3"][i] for i in range(3)): badc += 1
        best.append((okp, badc, g, mode))
        print("g=%-3d %-6s : positives fixed %d/%d, clean broken %d"
              % (g, mode, okp, npos, badc))
best.sort(key=lambda x: (-x[0], x[1]))
print("BEST:", best[0])
