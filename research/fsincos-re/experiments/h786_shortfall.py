#!/usr/bin/env python3
# h786: THE UNIFIED DELTA FRAME for the cos-default terminal:
# carry fires when the S-B discard is NEAR-FULL (shortfall small),
# model-over (corr-minus-1) when NEAR-EMPTY (disc small).
# Quantify shortfall/disc distributions per class x act stratum;
# the run5-act0 twins get their own shortfall contrast.
import subprocess, collections, math
def parse_wv(s):
    sg,e2,hx = s.split(":")
    return (int(sg), int(e2), int(hx,16))
CACHE = {}
def tcstate(se, sig, insn):
    k = (se,sig,insn)
    if k in CACHE: return CACHE[k]
    flag = "--fcos-standalone" if insn=="cos" else "--fsin-standalone"
    p = subprocess.run(["./model_h235","--batch",flag,"--dump-internals"],
                       input="%s %s\n"%(se,sig), capture_output=True, text=True)
    tc = corr = None
    for L in p.stderr.splitlines():
        if L.startswith("DI_TC "): tc = dict(x.split("=",1) for x in L.split()[1:] if "=" in x)
        if L.startswith("DI_CORR"): corr = dict(x.split("=",1) for x in L.split()[1:] if "=" in x)
    out = None
    if tc and corr and corr.get("via")=="default":
        try:
            left = parse_wv(tc["left"]); right = parse_wv(tc["right"])
            dl = left[1]-right[1]
            payload = int(tc.get("payload","0"))
            if 0 < dl <= 40:
                S = (left[2]<<dl) + ((payload<<(dl-8)) if payload and dl>=8 else 0)
                D = S - right[2]
                sh = D.bit_length()-67
                if sh > 0:
                    disc = D & ((1<<sh)-1)
                    rl = 0
                    for b in range(sh-1,-1,-1):
                        if (disc>>b)&1: rl += 1
                        else: break
                    out = dict(sh=sh, disc=disc, run=rl,
                        act=int(tc.get("active","0")), low3=int(tc.get("low3","0")),
                        pay=payload)
        except Exception:
            pass
    CACHE[k] = out
    return out
def relscale(x, sh):
    # log2 of x relative to 2^(sh-8): 0 means x == 2^(sh-8)
    if x <= 0: return -99
    return math.log2(x) - (sh-8)
POS = {}
for fn in ("h753_allvotes.txt","h759_miner2_votes.txt"):
    for L in open(fn):
        t = L.split()
        hv = int(t[5].split("/")[-1],16); mv = int(t[6].split("/")[-1],16)
        d = "carry" if hv>mv else "over"
        POS.setdefault((t[3],t[4],t[1]), set()).add(d)
NEG = set()
for fn in ("h745_neg_r70.txt","h745_neg_r70b.txt"):
    for L in open(fn):
        t = L.split()
        NEG.add((t[3],t[4],t[1]))
NEG -= set(POS)
print("distinct POS ops %d  NEG ops %d" % (len(POS), len(NEG)))
recs = []
for (se,sg,insn), ds in sorted(POS.items()):
    st = tcstate(se,sg,insn)
    if st: recs.append((("POS-"+"/".join(sorted(ds))), st))
for (se,sg,insn) in sorted(NEG):
    st = tcstate(se,sg,insn)
    if st: recs.append(("NEG", st))
print("default-path rows: %s" % collections.Counter(c for c,_ in recs))
print()
print("=== SHORTFALL (2^sh - disc) rel 2^(sh-8): class x act ===")
H = collections.defaultdict(list)
for c, st in recs:
    sf = (1<<st["sh"]) - st["disc"]
    H[(c, st["act"]>0)].append(relscale(sf, st["sh"]))
for k in sorted(H):
    v = sorted(H[k])
    b = collections.Counter(int(math.floor(x)) for x in v)
    print("  %-14s act=%d n=%-4d : %s" % (k[0], k[1], len(v),
        " ".join("%d:%d"%(kk,b[kk]) for kk in sorted(b))))
print()
print("=== DISC rel 2^(sh-8) (mirror side): class x act ===")
H2 = collections.defaultdict(list)
for c, st in recs:
    H2[(c, st["act"]>0)].append(relscale(st["disc"], st["sh"]))
for k in sorted(H2):
    v = sorted(H2[k])
    b = collections.Counter(int(math.floor(x)) for x in v)
    print("  %-14s act=%d n=%-4d : %s" % (k[0], k[1], len(v),
        " ".join("%d:%d"%(kk,b[kk]) for kk in sorted(b))))
print()
print("=== RUN5/ACT0 TWINS: shortfall detail ===")
for c, st in recs:
    if st["run"]==5 and st["act"]==0:
        sf = (1<<st["sh"]) - st["disc"]
        print("  %-14s sh=%-2d run=%d low3=%d pay=%d sf_rel=%.3f disc_low8=%02x" % (
            c, st["sh"], st["run"], st["low3"], st["pay"], relscale(sf,st["sh"]),
            st["disc"] & 0xff))
print("H786_DONE")
