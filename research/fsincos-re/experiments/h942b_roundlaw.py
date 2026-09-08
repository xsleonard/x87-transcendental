#!/usr/bin/env python3
# h942b: final-rounding tail-law test with REAL base bytes and a
# rule-quiet gate.  Laws are alternative pre-final-rounding tails:
#   L0 raw chop (V<<kk) — quiet legs: == base
#   L3 full exact tail (M)         L4 drop-R-tail (M+aR)
#   L6 sticky-only tail: V<<kk | (1 if f else 0)  (chip GRS sticky)
#   L7 drop-R sticky:   V<<kk | (1 if aX else 0)
import subprocess, sys
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
    bl = N.bit_length()
    g = bl - 64
    if g <= 0:
        return (shift + g, N << -g) if g < 0 else (shift, N)
    q, r = N >> g, N & ((1 << g) - 1)
    if mode == "rn":
        half = 1 << (g - 1)
        if r > half or (r == half and (q & 1)): q += 1
    elif mode == "ru" and r and not neg: q += 1
    elif mode == "rd" and r and neg: q += 1
    if q >> 64: q >>= 1; g += 1
    return (shift + g, q)

def outse(e2, neg):
    return (e2 + 63 + 16383) | (0x8000 if neg else 0)

legs = {}
f = open("h931_labels.tsv")
for ln in f:
    t = ln.rstrip("\n").split("\t")
    if len(t) != 9 or t[8] != "C": continue
    legs.setdefault((t[1], t[3]), {})[t[2]] = ("C", t[6], t[7])
nC = sum(len(v) for v in legs.values())
for ln in open("h940_species.tsv"):
    t = ln.rstrip("\n").split("\t")
    if len(t) != 9: continue
    hw = t[8].split()
    if hw[0] != "OK": continue
    legs.setdefault((t[2], t[5]), {}).setdefault(t[3], ("S", hw[1], hw[2]))
print("ops:", len(legs), "C legs:", nC, file=sys.stderr)

frames = {}
for path in ("h931_frames.tsv", "h941_cos_frames2.tsv", "h941_sin_frames2.tsv"):
    f = open(path)
    hdr = f.readline().rstrip("\n").split("\t")
    col = {c: i for i, c in enumerate(hdr)}
    for ln in f:
        t = ln.rstrip("\n").split("\t")
        if len(t) != len(hdr): continue
        if t[col["active"]] == "NOFRAME": continue
        key = (t[col["insn"]], t[col["se"]] + " " + t[col["sig"]])
        if key in frames: continue
        try:
            g = geo(int(t[col["lefte2"]]), int(t[col["righte2"]]),
                    int(t[col["leftsig"]], 16), int(t[col["rightsig"]], 16),
                    int(t[col["payload"]]))
        except ValueError: continue
        if g: frames[key] = g
print("frames:", len(frames), file=sys.stderr)

# real base bytes per op x 4 modes
ops_by_insn = {"cos": [], "sin": []}
for (insn, op) in legs:
    ops_by_insn[insn].append(op)
base = {}
for insn, ops in ops_by_insn.items():
    fl = "--fsin-standalone" if insn == "sin" else "--fcos-standalone"
    for mode in ("rn", "rd", "ru", "rz"):
        args = ["./model_r92", "--batch", fl]
        if mode != "rn": args.insert(2, "--rc=" + mode)
        p = subprocess.run(args, input="\n".join(ops) + "\n",
                           capture_output=True, text=True)
        outs = p.stdout.splitlines()
        assert len(outs) == len(ops)
        for op, o in zip(ops, outs):
            t = o.split()
            base[(insn, op, mode)] = (t[1], t[2]) if t[0] == "OK" else ("C2", "")
    print(insn, "base done", file=sys.stderr)

res = Counter()
for (insn, op), modes in legs.items():
    fr = frames.get((insn, op))
    if not fr:
        res[(insn, "noframe")] += len(modes); continue
    M, kk, aR, aX, scale = fr
    if scale >= 0:
        res[(insn, "posscale")] += len(modes); continue
    V = M >> kk
    f = M & ((1 << kk) - 1)
    laws = {"L0": V << kk, "L3": M, "L4": M + aR,
            "L6": (V << kk) | (1 if f else 0),
            "L7": (V << kk) | (1 if aX else 0)}
    for mode, (cls, hwse, hwsig) in modes.items():
        b = base.get((insn, op, mode))
        if not b or b[0] == "C2":
            res[(insn, cls, "nobase")] += 1; continue
        neg = bool(int(hwse, 16) & 0x8000)
        outs = {}
        for nm, T in laws.items():
            N = (1 << -scale) - T
            if N <= 0:
                outs[nm] = None; continue
            e2, sig = round64(N, scale, mode, neg)
            outs[nm] = ("%04x" % outse(e2, neg), "%016x" % sig)
        hwt = (hwse.lower(), hwsig.lower())
        bt = (b[0].lower(), b[1].lower())
        quiet = outs["L0"] == bt
        if not quiet:
            res[(insn, cls, mode, "NONQUIET")] += 1
            continue
        for nm in ("L3", "L4", "L6", "L7"):
            res[(insn, cls, mode, nm,
                 "HW" if outs[nm] == hwt else
                 ("=base" if outs[nm] == bt else "wrong"))] += 1
for k in sorted(res):
    print(k, res[k])
