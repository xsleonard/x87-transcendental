#!/usr/bin/env python3
# h721: joint clean+residual search for the terminal arithmetic form
#   U = S_pure + T(discL,gL) - B - T(discR,gR) + c
# scored as: floor(U/2^k) must equal the validated final retained
# (clean rows: model incl. fire; residual rows: chip = model+delta).
# Stage 1: 5k clean subsample + 28 residual; stage 2: verify top
# candidates on the full 132k sample.  Plus the twin diagnostic:
# distributions of the exact discard fractions, residual vs clean.
import sys
from fractions import Fraction

HEX128 = {"umag","S","B","Mreg","t4","sqlow","rd3","disc"}
def blocks(path):
    cur = None; d = None
    for line in open(path):
        t = line.split()
        if not t: continue
        if t[0] == "DI_IN":
            if cur is not None: yield cur, d
            cur = (t[1], t[2]); d = {}
        elif d is None: continue
        elif t[0] in ("DI_POLY","DI_TC","DI_R59","DI_CRIT","DI_BS","DI_BR","DI_CORR"):
            dd = d.setdefault(t[0], {})
            for kv in t[1:]:
                k, v = kv.split("=", 1)
                if t[0] == "DI_R59" and k in HEX128:
                    x = int(v, 16)
                    if x >= 1 << 127: x -= 1 << 128
                    dd[k] = x
                elif ":" in v and v.count(":") == 2: dd[k] = v
                elif "," in v: dd[k] = v
                elif v.lstrip("-").isdigit(): dd[k] = int(v)
                else: dd[k] = v
    if cur is not None: yield cur, d

def wv(s):
    sg, e2, hx = s.split(":")
    return (int(sg), int(e2), int(hx, 16))

CORR_P1 = {"44ca2bf","9242f0c","0749eaa","750943e","56e0a67",
           "54e2537","7503a2f","59862dd"}
MISS_SIGS = set(l.split()[1] for l in open("h714_ops.txt"))
def h715c_delta(sig):
    for s in CORR_P1:
        if sig.endswith(s): return +1
    if sig.endswith("30c1fc9"): return None
    return -1

def fire_adj(d):
    br = d.get("DI_BR", {})
    b = br.get("br", d.get("DI_CORR", {}).get("via"))
    th = d["DI_R59"]["theta"]
    if b == "tie":  return -1 if br.get("tfire") == 1 else 0
    if b == "band":
        return (-1 if th > 0 else +1) if br.get("fire") == 1 else 0
    if b == "corner":
        return (-1 if th >= 0 else +1) if br.get("fire") == 1 else 0
    return 0

FR = 12   # fractional bits
def prep(sig, d, is_miss):
    poly = d["DI_POLY"]; tc = d["DI_TC"]; r59 = d["DI_R59"]
    if "left" not in tc: return None
    sq = wv(poly["sq"]); odd = wv(poly["odd"])
    f4 = wv(poly["f4"]); ev = wv(poly["even"])
    left = wv(tc["left"]); right = wv(tc["right"])
    rscale = r59["rscale"]; k = r59["k"]
    S = r59["S"]; B = r59["B"]
    payload = r59["payload"]; dp = r59["dp"]
    S_pure = S - (payload << dp) if payload else S
    lf = sq[2] * odd[2]; shL = lf.bit_length() - 67
    if (lf >> shL) != left[2]: return None
    dLi = lf & ((1 << shL) - 1)
    eL = sq[1] + odd[1] - rscale + FR
    dL = (dLi << eL) if eL >= 0 else (dLi >> -eL)
    rf = f4[2] * ev[2]; shR = rf.bit_length() - 67
    if (rf >> shR) != right[2]: return None
    dRi = rf & ((1 << shR) - 1)
    eR = f4[1] + ev[1] - rscale + FR
    dR = (dRi << eR) if eR >= 0 else (dRi >> -eR)
    ret0 = r59["umag"] >> k
    fa = fire_adj(d)
    if is_miss:
        dlt = h715c_delta(sig)
        if dlt is None: return None
        tgt = ret0 + fa + dlt
    else:
        tgt = ret0 + fa
    W = (S_pure - B) << FR
    lo = (tgt << (k + FR)) - W
    hi = lo + (1 << (k + FR))
    return dict(sig=sig, th=r59["theta"], dL=dL, dR=dR, lo=lo, hi=hi,
                payload=payload, dp=dp, low3=r59["low3"],
                dist=r59["dist"], b1=r59["b1"], b2=r59["b2"],
                fa=fa, is_miss=is_miss)

res = []
for (se, sig), d in blocks("h714_dump.txt"):
    r = prep(sig, d, True)
    if r: res.append(r)
clean = []
for (se, sig), d in blocks("h720_sample.dump"):
    if sig in MISS_SIGS: continue
    r = prep(sig, d, False)
    if r: clean.append(r)
print("residual rows scored:", len(res), " clean rows:", len(clean))

def T(x, g):
    if g is None: return 0
    s = g + FR
    return (x >> s) << s if s >= 0 else x
GS = [None] + list(range(-8, 3))
CS = [Fraction(n, 4) for n in range(-16, 17)]
def score(rows, gL, gR, c12):
    ok = 0
    for r in rows:
        u = T(r["dL"], gL) - T(r["dR"], gR) + c12
        if r["lo"] <= u < r["hi"]: ok += 1
    return ok
sub = clean[:5000]
cands = []
for gL in GS:
    for gR in GS:
        for c in CS:
            c12 = int(c * (1 << FR))
            sr = score(res, gL, gR, c12)
            if sr < 20: continue
            sc = score(sub, gL, gR, c12)
            cands.append((sr + sc, sr, sc, gL, gR, c))
cands.sort(key=lambda x: -x[0])
print("stage1 top (res/28 + clean/5000):")
for tot, sr, sc, gL, gR, c in cands[:10]:
    print("  gL=%-4s gR=%-4s c=%-5s : res %d/28 clean %d/5000"
          % (gL, gR, c, sr, sc))
# model-as-candidate baseline: payload + fires == definitionally clean-perfect
print()
print("== twin diagnostic: exact discard content, residual vs clean ==")
def fr(x): return float(Fraction(x, 1 << FR))
import statistics
for grp, name in ((res, "MISS"),):
    for r in grp:
        exL = fr(r["dL"]) - r["payload"]
        print("  %s %-7s th=%+d fa=%+d pay=%d dL=%7.3f exL=%+7.3f dR=%7.3f lo=%7.3f hi=%7.3f"
              % (name, r["sig"][-7:], r["th"], r["fa"], r["payload"],
                 fr(r["dL"]), exL, fr(r["dR"]),
                 fr(r["lo"]), fr(r["hi"])))
cl_exL = [fr(r["dL"]) - r["payload"] for r in clean[:20000]]
cl_dR = [fr(r["dR"]) for r in clean[:20000]]
print("clean exL: mean %.3f sd %.3f min %.3f max %.3f"
      % (statistics.mean(cl_exL), statistics.pstdev(cl_exL),
         min(cl_exL), max(cl_exL)))
print("clean dR : mean %.3f sd %.3f min %.3f max %.3f"
      % (statistics.mean(cl_dR), statistics.pstdev(cl_dR),
         min(cl_dR), max(cl_dR)))
