#!/usr/bin/env python3
# h939: classify fire rows (base-vs-v2 diffs) by B_e; append candidates.
import sys
fr, idxf, outf = sys.argv[1:4]
f = open(fr); hdr = f.readline().rstrip("\n").split("\t")
col = {c: i for i, c in enumerate(hdr)}
idxs = [int(x) for x in open(idxf)]
out = open(outf, "a")
nbe0 = nbe1 = nskip = 0
for ln in f:
    t = ln.rstrip("\n").split("\t")
    if len(t) != len(hdr) or t[col["active"]] == "NOFRAME":
        nskip += 1; continue
    le2 = int(t[col["lefte2"]]); re2 = int(t[col["righte2"]])
    L = int(t[col["leftsig"]], 16); R = int(t[col["rightsig"]], 16)
    pay = int(t[col["payload"]])
    scale = min(le2, re2)
    if pay and le2 - 8 < scale: scale = le2 - 8
    X = L << (le2 - scale)
    X += pay << max(0, le2 - 8 - scale) if pay >= 0 else -((-pay) << max(0, le2 - 8 - scale))
    AR = R << (re2 - scale)
    M = X - AR
    if M <= 0:
        nskip += 1; continue
    kk = M.bit_length() - 67
    if kk < 1:
        nskip += 1; continue
    mask = (1 << kk) - 1
    aR = AR & mask; aX = X & mask
    if not aR:
        nskip += 1; continue
    if aX < aR:
        nbe1 += 1
        continue
    nbe0 += 1
    k = int(t[col["idx"]])
    out.write("%s\t%s\t%s\t%d\t%#x\t%#x\n"
              % (t[col["se"]], t[col["sig"]], t[col["insn"]], kk, aR, aX))
out.close()
print("BE0 %d BE1 %d SKIP %d" % (nbe0, nbe1, nskip))
