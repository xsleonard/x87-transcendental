#!/usr/bin/env python3
# h930: THE BORROW-DOMAIN LENS AT THE TERMINAL WINDOW.  The r59
# lattice's pmask ~(S^B) is the borrow-propagate structure of the
# S-B subtraction at the umag window — closed-form-derived physics
# (h662k block-start, R59-R65).  The terminal accumulator computes
# the SAME KIND of subtraction, M = (L' + P') - R', chopped at 67
# bits — but the borrow-domain features at ITS window have never
# been computed for the act band.  A window-limited borrow
# predictor there would produce exactly the parked deterministic
# +-1s, and can distinguish value-identical twins (encodings
# differ where sums agree).
# Data: band_raw_frames.tsv (mined pool, 132 C / 948 N) as train;
# band5_raw_frames.tsv (the h905 fresh atlas) as holdout;
# twin_groups.json as the acid test.
import sys, json, math
from collections import defaultdict

def load(fn):
    rows = []
    with open(fn) as f:
        hdr = f.readline().rstrip("\n").split("\t")
        for ln in f:
            t = ln.rstrip("\n").split("\t")
            if len(t) != len(hdr):
                continue
            rows.append(dict(zip(hdr, t)))
    return rows

def feats(r):
    lab = r["lab"]
    le2 = int(r["lefte2"]); re2 = int(r["righte2"])
    L = int(r["leftsig"], 16); R = int(r["rightsig"], 16)
    pay = int(r["payload"])
    low3 = int(r["low3"]); dist = int(r["dist"])
    act = r.get("active", "?")
    scale = min(le2, re2)
    if pay and le2 - 8 < scale:
        scale = le2 - 8
    AL = L << (le2 - scale)
    AR = R << (re2 - scale)
    AP = abs(pay) << max(0, le2 - 8 - scale)
    X = AL + (AP if pay >= 0 else -AP)
    if pay < 0 and X < 0:
        return None
    M = X - AR
    if M <= 0:
        return None
    kk = M.bit_length() - 67
    if kk < 0:
        return None
    # d60 cross-check: the top 60 bits of the below-window discard
    W0 = M & ((1 << kk) - 1) if kk > 0 else 0
    d60c = (W0 >> (kk - 60)) if kk >= 60 else (W0 << (60 - kk))
    okd = None
    if "d60" in r and r["d60"]:
        okd = (d60c == (int(r["d60"], 16) & ((1 << 60) - 1)))
    # borrow-domain propagate mask of X - AR
    pmask = ~(X ^ AR)
    pm = 0; j = kk
    while pm < 32 and ((pmask >> j) & 1):
        pm += 1; j += 1
    # phase of the window LSB's absolute exponent
    phw = ((scale + kk) % 8 + 8) % 8
    crit = ((pm + phw) % 8 == 7) and pm in (7, 8)
    crit9 = ((pm + phw) % 8 == 7) and pm == 9
    bsrel = 8 + ((8 - phw) % 8)
    bit8 = (M >> (kk + 8)) & 1 if kk + 8 < M.bit_length() else 0
    bitbs = (M >> (kk + bsrel)) & 1 if kk + bsrel < M.bit_length() else 0
    # below-window structure
    W = M & ((1 << kk) - 1) if kk > 0 else 0
    wfrac = W / (1 << kk) if kk > 0 else 0.0
    # first generate (borrow-generate: X_i=0 & AR_i=1) below window
    gmask = (~X) & AR
    fg = -1
    for b in range(kk - 1, max(-1, kk - 33), -1):
        if (gmask >> b) & 1:
            fg = kk - b  # depth below window
            break
    # 3:2 compressor S/C (X = AL + APsigned as one op; second ~AR)
    S3 = X ^ (~AR)
    C3 = (X & (~AR)) << 1
    s3b = (S3 >> max(0, kk - 8)) & 0xFF
    c3b = (C3 >> max(0, kk - 8)) & 0xFF
    # known frame
    d60v = int(r["d60"], 16) if r.get("d60") else d60c
    top8 = (d60v >> 52) & 0xFF
    summ = top8 + low3
    return dict(lab=1 if lab.startswith("C") else 0, act=act,
                sum=summ, low3=low3, dist=dist, pm=pm, phw=phw,
                crit=int(crit), crit9=int(crit9), bit8=int(bit8),
                bitbs=int(bitbs), wfrac=wfrac, fg=fg, s3b=s3b,
                c3b=c3b, okd=okd, kk=kk,
                key=(r.get("se", ""), r.get("sig", "")))

def table(rows, name):
    fs = [f for f in (feats(r) for r in rows) if f]
    nC = sum(f["lab"] for f in fs)
    okd = [f["okd"] for f in fs if f["okd"] is not None]
    print("%s: %d usable, C=%d, d60-crosscheck %d/%d ok"
          % (name, len(fs), nC, sum(okd), len(okd)))
    return fs

tr = table(load("band_raw_frames.tsv"), "train(pool)")
ho = table(load("band5_raw_frames.tsv"), "holdout(h905)")

def contrast(fs, feat, name, cond=lambda f: 0):
    cells = defaultdict(lambda: [[], []])
    for f in fs:
        cells[cond(f)][f["lab"]].append(feat(f))
    num = den = 0.0
    for c, (nn, cc) in cells.items():
        if not nn or not cc:
            continue
        d = sum(cc) / len(cc) - sum(nn) / len(nn)
        allv = nn + cc
        m = sum(allv) / len(allv)
        v = (sum((x - m) ** 2 for x in allv) / max(1, len(allv) - 1)
             ) * (1 / len(cc) + 1 / len(nn))
        if v <= 0:
            continue
        w = 1 / v
        num += w * d; den += w
    z = num / math.sqrt(den) if den > 0 else 0.0
    return z

COND = lambda f: (f["act"], f["sum"], f["low3"])
FEATS = [("pm", lambda f: f["pm"]), ("crit", lambda f: f["crit"]),
         ("crit|9", lambda f: f["crit"] or f["crit9"]),
         ("bit8", lambda f: f["bit8"]), ("bitbs", lambda f: f["bitbs"]),
         ("b8&bbs", lambda f: f["bit8"] & f["bitbs"]),
         ("wfrac", lambda f: f["wfrac"]), ("fg", lambda f: f["fg"]),
         ("fg<=8", lambda f: 0 <= f["fg"] <= 8),
         ("s3b", lambda f: f["s3b"]), ("c3b", lambda f: f["c3b"]),
         ("phw", lambda f: f["phw"]),
         ("pm+phw%8==7", lambda f: (f["pm"] + f["phw"]) % 8 == 7)]
print("\nfeature            train-z   holdout-z   (conditioned on act,sum,low3)")
for nm, fe in FEATS:
    zt = contrast(tr, fe, nm, COND)
    zh = contrast(ho, fe, nm, COND)
    flag = " <== " if abs(zt) > 3 and abs(zh) > 2.5 and zt * zh > 0 else ""
    print("  %-16s %+7.2f   %+7.2f%s" % (nm, zt, zh, flag))

# the twins
try:
    tg = json.load(open("twin_groups.json"))
    fmap = {f["key"]: f for f in tr + ho if f["key"][0]}
    print("\ntwin groups: %d" % len(tg))
    shown = 0
    for grp in tg:
        ks = []
        def walk(x):
            if isinstance(x, list):
                if len(x) >= 2 and all(isinstance(e, str) for e in x[:2]):
                    ks.append((x[0], x[1]))
                else:
                    for e in x:
                        walk(e)
        walk(grp)
        hit = [fmap.get(k) for k in ks if k in fmap]
        if len(hit) >= 2 and len(set(h["lab"] for h in hit)) == 2 and shown < 6:
            shown += 1
            for h in hit:
                print("  twin %s lab=%d pm=%d phw=%d crit=%d b8=%d bbs=%d "
                      "fg=%d s3b=%02x c3b=%02x wfrac=%.3f"
                      % (h["key"][1][:10], h["lab"], h["pm"], h["phw"],
                         h["crit"], h["bit8"], h["bitbs"], h["fg"],
                         h["s3b"], h["c3b"], h["wfrac"]))
            print("  --")
except Exception as e:
    print("twin check skipped:", e)
