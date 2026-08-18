#!/usr/bin/env python3
# h742: guard-column fit, corrected grid + expanded family.
#   grid: sh = width(S-B) - 67  (the real chop column); corr lsb =
#         2^(right.e2+sh) == dumped corr.e2 (asserted).
#   families: round the RIGHT PRODUCT (B) or the SUBTRACT RESULT
#   (S-B) at column m, m = dl - g (guard bits below S's lsb) or
#   m = sh - g (guard bits below the retained field);
#   modes trunc / rn / away.
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
        hw3.append(mm[mode][0].split("/") if mm and mode in mm else mo3[mi])
    S = left[2] << dl
    payload = int(tc.get("payload", "0"))
    if payload:
        dp = dl - 8
        if dp < 0: return None
        S += payload << dp
    B = right[2]
    D = S - B
    sh = D.bit_length() - 67
    if sh < 0: return None
    if right[1] + sh != cw[1]: return None     # grid sanity
    if (D >> sh) != cw[2]: return None          # corr sanity
    return dict(S=S, B=B, D=D, dl=dl, sh=sh, v_pre=v_pre, neg=neg,
                hw3=hw3, mo3=mo3, CL=Fraction(2)**cw[1],
                is_pos=mm is not None)

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
subprocess.run(["python3","h733_gen.py","0x733002","120000","neg2.txt"])
allops = set((k[0],k[1]) for k in votes)
cl = []
for l in open("neg2.txt"):
    a,b = l.split()
    if (a,b) not in allops: cl.append((a,b))
    if len(cl) >= 24000: break
for insn, flag in (("cos","--fcos-standalone"),("sin","--fsin-standalone")):
    sel = cl[:12000] if insn=="cos" else cl[12000:]
    for d, pr in zip(dump_rows(sel, flag), sel):
        r = prep(d, insn, None)
        if r: R.append(r)
print("positives:", npos, " clean:", len(R)-npos)

def rnd(x, m, mode):
    if m <= 0: return x
    low = x & ((1 << m) - 1)
    y = x - low
    if mode == "rn" and low >= (1 << (m-1)): y += 1 << m
    if mode == "away" and low: y += 1 << m
    return y

def predict(r, tgt, ref, g, mode):
    m = (r["dl"] - g) if ref == "dl" else (r["sh"] - g)
    if m <= 0: return 0
    if tgt == "B":
        Dp = r["S"] - rnd(r["B"], m, mode)
    else:
        Dp = rnd(r["D"], m, mode)
    return (Dp >> r["sh"]) - (r["D"] >> r["sh"])

results = []
for tgt in ("SB",):
    for ref in ("sh",):
        for mode in ("rn","away"):
            for g in (3, 4, 5):
                okp = 0; badc = 0
                for r in R:
                    dlt = predict(r, tgt, ref, g, mode)
                    v = r["v_pre"] - dlt * r["CL"]
                    vs = -v if r["neg"] else v
                    o3 = [F.round80(vs, md).split() for md in ("rn","rd","ru")]
                    if r["is_pos"]:
                        if all(o3[i] == r["hw3"][i] for i in range(3)): okp += 1
                    else:
                        if any(o3[i] != r["mo3"][i] for i in range(3)): badc += 1
                results.append((okp, badc, tgt, ref, mode, g))
results.sort(key=lambda x: (-x[0], x[1]))
for okp, badc, tgt, ref, mode, g in results[:14]:
    print("tgt=%-2s ref=%-2s %-5s g=%-3d : pos %d/%d clean-broken %d"
          % (tgt, ref, mode, g, okp, npos, badc))
