#!/usr/bin/env python3
# h787: mechanism-correct labels (DI_FIN neg flag) + the (run x low3)
# joint frontier for the cos-default terminal, carry and borrow sides.
import subprocess, collections, math, pickle, os
def parse_wv(s):
    sg,e2,hx = s.split(":")
    return (int(sg), int(e2), int(hx,16))
CACHEF = "h787_state.pkl"
CACHE = pickle.load(open(CACHEF,"rb")) if os.path.exists(CACHEF) else {}
def tcstate(se, sig, insn):
    k = (se,sig,insn)
    if k in CACHE: return CACHE[k]
    flag = "--fcos-standalone" if insn=="cos" else "--fsin-standalone"
    p = subprocess.run(["./model_h235","--batch",flag,"--dump-internals"],
                       input="%s %s\n"%(se,sig), capture_output=True, text=True)
    tc = corr = fin = None
    for L in p.stderr.splitlines():
        if L.startswith("DI_TC "): tc = dict(x.split("=",1) for x in L.split()[1:] if "=" in x)
        if L.startswith("DI_CORR"): corr = dict(x.split("=",1) for x in L.split()[1:] if "=" in x)
        if L.startswith("DI_FIN"): fin = dict(x.split("=",1) for x in L.split()[1:] if "=" in x)
    out = None
    if tc and corr and corr.get("via")=="default" and fin is not None:
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
                    zrun = 0
                    for b in range(sh-1,-1,-1):
                        if not (disc>>b)&1: zrun += 1
                        else: break
                    out = dict(sh=sh, disc=disc, run=rl, zrun=zrun,
                        act=int(tc.get("active","0")), low3=int(tc.get("low3","0")),
                        pay=payload, neg=int(fin.get("neg","0")))
        except Exception:
            pass
    CACHE[k] = out
    return out
POS = {}
for fn in ("h753_allvotes.txt","h759_miner2_votes.txt"):
    for L in open(fn):
        t = L.split()
        if t[5].startswith("hw=C2") or t[6].startswith("mo=C2"): continue
        hv = int(t[5].split("/")[-1],16); mv = int(t[6].split("/")[-1],16)
        POS.setdefault((t[3],t[4],t[1]), set()).add("up" if hv>mv else "dn")
NEG = set()
for fn in ("h745_neg_r70.txt","h745_neg_r70b.txt"):
    for L in open(fn):
        t = L.split()
        NEG.add((t[3],t[4],t[1]))
NEG -= set(POS)
recs = []
for (se,sg,insn), ds in sorted(POS.items()):
    st = tcstate(se,sg,insn)
    if not st: continue
    if len(ds) > 1:
        mech = "MIXED"
    else:
        d = ds.pop()
        # output up + neg=0 => corr+1 (carry);  up + neg=1 => corr-1 (borrow)
        # output dn + neg=0 => corr-1 (borrow); dn + neg=1 => corr+1 (carry)
        mech = "CARRY" if ((d=="up") == (st["neg"]==0)) else "BORROW"
    recs.append((mech, st))
for (se,sg,insn) in sorted(NEG):
    st = tcstate(se,sg,insn)
    if st: recs.append(("NEG", st))
pickle.dump(CACHE, open(CACHEF,"wb"))
print("mech counts:", collections.Counter(m for m,_ in recs))
print()
print("=== CARRY side: (run x low3) joint, act=0   [POS | NEG] ===")
for actv in (0,1):
    print(" act=%d:" % actv)
    P = collections.Counter(); Nn = collections.Counter()
    for m, st in recs:
        if st["act"] != actv: continue
        if m=="CARRY": P[(min(st["run"],10), st["low3"])] += 1
        elif m=="NEG": Nn[(min(st["run"],10), st["low3"])] += 1
    for run in range(0,11):
        row = "  run%-2d " % run + " ".join("%2d/%-3d" % (P.get((run,l),0), Nn.get((run,l),0)) for l in range(8))
        if any(P.get((run,l),0)+Nn.get((run,l),0) for l in range(8)): print(row)
print()
print("=== BORROW side: (zrun x low3) joint  [POS | NEG] ===")
for actv in (0,1):
    print(" act=%d:" % actv)
    P = collections.Counter(); Nn = collections.Counter()
    for m, st in recs:
        if st["act"] != actv: continue
        if m=="BORROW": P[(min(st["zrun"],10), st["low3"])] += 1
        elif m=="NEG": Nn[(min(st["zrun"],10), st["low3"])] += 1
    for zr in range(0,11):
        row = "  zr%-2d " % zr + " ".join("%2d/%-3d" % (P.get((zr,l),0), Nn.get((zr,l),0)) for l in range(8))
        if any(P.get((zr,l),0)+Nn.get((zr,l),0) for l in range(8)): print(row)
print()
print("MIXED rows detail:")
for m, st in recs:
    if m=="MIXED": print("  ", st)
print("H787_DONE")
