#!/usr/bin/env python3
# h739: the compensation-bias hypothesis on the default stratum.
# chip corr = chop67(S - B + K) for a small constant K (units of
# 2^right.e2).  Per positive: does some K produce EXACTLY the
# needed +-1 corr-lsb flip; per clean row: which K would flip its
# OUTPUT (the wall — a flip is fatal only if it changes the rounded
# output in some mode).  Also splits all stats by needed direction.
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

votes = collections.defaultdict(dict)
for l in open("h733_votes.txt"):
    t = l.split()
    votes[(t[3], t[4], t[1])][t[2]] = (t[5].split("=")[1], t[6].split("=")[1])

def analyze(d, insn, modes_hw):
    tc = d.get("DI_TC"); corr = d.get("DI_CORR", {})
    poly = d.get("DI_POLY", {})
    if not tc or corr.get("via") != "default": return None
    left = parse_wv(tc["left"]); right = parse_wv(tc["right"])
    dl = left[1] - right[1]
    if dl <= 0 or dl > 30: return None
    cw = parse_wv(corr["out"])
    v_pre = 1 + F.wv_val(cw)
    i0 = int(poly.get("i0", "0"))
    se, sig = d["IN"]
    flag = "--fcos-standalone" if insn == "cos" else "--fsin-standalone"
    # model outputs all modes + sign calibration
    mo3 = []
    for mode in ("rn","rd","ru"):
        args = ["./model_h235","--batch",flag]
        if mode != "rn": args.append("--rc="+mode)
        r = subprocess.run(args, input="%s %s\n" % (se, sig),
                           capture_output=True, text=True)
        t = r.stdout.split()
        mo3.append(t[1:3] if t[0]=="OK" else ["C2"])
    neg = None
    for cand in (0,1):
        vs = -v_pre if cand else v_pre
        if F.round80(vs, "rn").split() == mo3[0]:
            neg = cand; break
    if neg is None: return None
    # hw3: vote modes override
    hw3 = []
    for mi, mode in enumerate(("rn","rd","ru")):
        if modes_hw and mode in modes_hw:
            hw3.append(modes_hw[mode][0].split("/"))
        else:
            hw3.append(mo3[mi])
    B_low = right[2] & ((1 << dl) - 1)
    # needed direction from bracket
    iv = None
    for mi, mode in enumerate(("rn","rd","ru")):
        pi = F.preimage(hw3[mi][0], hw3[mi][1], mode)
        iv = pi if iv is None else F.intersect(iv, pi)
    vs0 = -v_pre if neg else v_pre
    lo, hi, lc, hc = iv
    d_lo = lo - vs0; d_hi = hi - vs0
    if neg: d_lo, d_hi = -d_hi, -d_lo
    CL = Fraction(2)**cw[1]
    ql, qh = d_lo/CL, d_hi/CL
    # which K in 1..16 UL reproduces hw in all modes (chip corr =
    # chop(S-B+K) i.e. corr magnitude -floor((B_low - K)...):
    # S-B is NEGATIVE of corr? corr = chop67(S-B) with S-B<0:
    # adding +K UL to (S-B) makes it LESS negative => corr magnitude
    # SMALLER when crossing... careful: v_pre = 1 + corr(neg).
    # chip corr larger in magnitude = v_pre smaller.  (S-B+K) less
    # negative => |corr| smaller => v_pre LARGER.  The dominant class
    # needs |corr| LARGER => K NEGATIVE (a deficit, not excess) —
    # test K in -16..16.
    fits = []
    for K in range(-16, 17):
        if K == 0: continue
        # new corr value: magnitude = |chop67(S-B) + adjustment|:
        # crossing happens iff (B_low - K) mod 2^dl crosses 0:
        # delta_corr_lsb = floor((B_low) / 2^dl) - floor((B_low - K)/2^dl)
        dlt = (0 - ((B_low - K) >> dl)) if K > 0 else (0 - -(((K - B_low) + (1<<dl) - 1) >> dl) if False else 0 - ((B_low - K) >> dl))
        # simpler: python floor division handles negatives:
        dlt = 0 - ((B_low - K) >> dl) if False else (0 - ((B_low - K) // (1 << dl)))
        # dlt = +1 means |corr| smaller by 1 lsb (v_pre +CL)
        v_new = v_pre + dlt * CL
        vsn = -v_new if neg else v_new
        ok = all(F.round80(vsn, m).split() == hw3[mi]
                 for mi, m in enumerate(("rn","rd","ru")))
        if ok: fits.append(K)
    return dict(dl=dl, B_low=B_low, ql=float(ql), qh=float(qh),
                fits=fits, is_pos=modes_hw is not None)

P = []
for insn in ("cos","sin"):
    flag = "--fcos-standalone" if insn=="cos" else "--fsin-standalone"
    pairs = [(k[0],k[1]) for k in votes if k[2]==insn]
    ds = dump_rows(pairs, flag)
    for d, pr in zip(ds, pairs):
        r = analyze(d, insn, votes[(pr[0],pr[1],insn)])
        if r: P.append(r)
print("positives analyzed:", len(P))
dirneg = [r for r in P if r["qh"] < 0.5]   # need corr LARGER (v down)
dirpos = [r for r in P if r["ql"] > -0.5]
print("need |corr|+1 (v down):", len(dirneg), " need |corr|-1:", len(dirpos))
inter = None
for r in dirneg:
    s = set(r["fits"])
    inter = s if inter is None else inter & s
print("K values fitting ALL |corr|+1 rows:", sorted(inter) if inter else None)
cnt = collections.Counter()
for r in dirneg:
    for K in r["fits"]: cnt[K] += 1
print("K histogram over |corr|+1 rows:", dict(sorted(cnt.items())))
print("B_low histogram |corr|+1:", collections.Counter(
    r["B_low"] if r["B_low"] < 8 else "8+" for r in dirneg))
print("B_low histogram |corr|-1:", collections.Counter(
    r["B_low"] if r["B_low"] < 8 else "8+" for r in dirpos))
