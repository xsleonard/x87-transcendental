#!/usr/bin/env python3
# h944: WHEN does the final rounding see the tail?  Confusion matrix
# of tail-law variants over C legs + ALL labels-AGREE legs (base==hw)
# where the law would move the output.  Variants:
#   full tail f;  guard-g: only top g bits of the below-window field
#   (f >> (kk-g));  drop-R tail aX (payload+left bits only), guard-g.
import sys
from collections import Counter

def geo(le2, re2, L, R, pay):
    scale = min(le2, re2)
    if pay and le2 - 8 < scale: scale = le2 - 8
    X = L << (le2 - scale)
    X += pay << max(0, le2 - 8 - scale) if pay >= 0 else -((-pay) << max(0, le2 - 8 - scale))
    AR = R << (re2 - scale)
    M = X - AR
    if M <= 0: return None
    kk = M.bit_length() - 67
    if kk < 1: return None
    return M, kk, AR & ((1 << kk) - 1), X & ((1 << kk) - 1), scale

def round64(N, shift, mode, neg):
    bl = N.bit_length(); g = bl - 64
    if g <= 0: return (shift + g, N << -g) if g < 0 else (shift, N)
    q, r = N >> g, N & ((1 << g) - 1)
    if mode == "rn":
        half = 1 << (g - 1)
        if r > half or (r == half and (q & 1)): q += 1
    elif mode == "ru" and r and not neg: q += 1
    elif mode == "rd" and r and neg: q += 1
    if q >> 64: q >>= 1; g += 1
    return (shift + g, q)

frames = {}
for path in ("h931_frames.tsv", "h941_cos_frames2.tsv", "h941_sin_frames2.tsv"):
    f = open(path)
    hdr = f.readline().rstrip("\n").split("\t")
    col = {c: i for i, c in enumerate(hdr)}
    for ln in f:
        t = ln.rstrip("\n").split("\t")
        if len(t) != len(hdr) or t[col["active"]] == "NOFRAME": continue
        key = (t[col["insn"]], t[col["se"]] + " " + t[col["sig"]])
        if key in frames: continue
        try:
            g = geo(int(t[col["lefte2"]]), int(t[col["righte2"]]),
                    int(t[col["leftsig"]], 16), int(t[col["rightsig"]], 16),
                    int(t[col["payload"]]))
        except ValueError: continue
        if g: frames[key] = g
print("frames:", len(frames), file=sys.stderr)

res = Counter()
fdep = {"C": Counter(), "A": Counter()}
nolegs = Counter()
for ln in open("h931_labels.tsv"):
    t = ln.rstrip("\n").split("\t")
    if len(t) != 9: continue
    insn, mode, op, cls = t[1], t[2], t[3], t[8]
    fr = frames.get((insn, op))
    if not fr:
        nolegs[cls] += 1; continue
    M, kk, aR, aX, scale = fr
    if scale >= 0: continue
    V = M >> kk
    f = M & ((1 << kk) - 1)
    if not f: continue
    neg = bool(int(t[6], 16) & 0x8000)
    hwt = (t[6].lower().lstrip("0"), t[7].lower())
    base_e2, base_sig = round64((1 << -scale) - (V << kk), scale, mode, neg)
    base_t = ("%04x" % ((base_e2 + 63 + 16383) | (0x8000 if neg else 0)), "%016x" % base_sig)
    base_t = (base_t[0].lstrip("0"), base_t[1])
    stick_e2, stick_sig = round64((1 << -scale) - ((V << kk) | 1), scale, mode, neg)
    stick_t = ("%04x" % ((stick_e2 + 63 + 16383) | (0x8000 if neg else 0)), "%016x" % stick_sig)
    stick_t = (stick_t[0].lstrip("0"), stick_t[1])
    if stick_t == base_t: continue          # sticky irrelevant at this leg
    # this leg is EDGE: sticky flips the output.  hw tells if seen.
    seen = hwt == stick_t
    unseen = hwt == base_t
    lab = "C" if cls == "C" else "A"
    ftop = kk - f.bit_length() + 1          # depth of tail top bit
    # which source: does the R tail reach above the X tail?
    rtop = kk - aR.bit_length() + 1 if aR else 99
    xtop = kk - aX.bit_length() + 1 if aX else 99
    res[(lab, mode, "SEEN" if seen else ("UNSEEN" if unseen else "OTHER"))] += 1
    fdep[lab][("ftop", min(ftop, 12))] += 1
    if seen:
        fdep[lab][("seen_ftop", min(ftop, 12))] += 1
for k in sorted(res): print(k, res[k])
print("--- tail-top depth (all edge legs vs seen) ---")
for lab in ("C", "A"):
    print(lab, dict(sorted(fdep[lab].items())))
print("noframe:", dict(nolegs))
