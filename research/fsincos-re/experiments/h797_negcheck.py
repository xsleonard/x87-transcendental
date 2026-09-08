#!/usr/bin/env python3
# h797: neg flags + sf8 for the 11 randv1/rv2 act0 default mo+1 rows.
import subprocess, pickle
def parse_wv(s):
    sg,e2,hx = s.split(":")
    return (int(sg), int(e2), int(hx,16))
CACHE = pickle.load(open("h787_state.pkl","rb"))
def tcstate(se, sig, insn):
    k = (se,sig,insn)
    if k in CACHE and CACHE[k] is not None: return CACHE[k]
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
                out = dict(sh=sh, disc=disc, run=rl, act=int(tc.get("active","0")),
                    low3=int(tc.get("low3","0")), pay=payload, neg=int(fin.get("neg","0")))
    CACHE[k] = out
    return out
rows = []
for L in open("h785.log"):
    if "via=default act=0" in L and "mo+1" in L:
        t = L.split()
        rows.append((t[0], t[1], t[2]))
for se, sg, insn in rows:
    st = tcstate(se, sg, insn)
    if st is None:
        print(se, sg, insn, "NO-STATE"); continue
    sf = (1<<st["sh"]) - st["disc"]
    sf8 = 256 - (st["disc"] >> (st["sh"]-8)) if st["sh"] >= 8 else 256 - (st["disc"] << (8-st["sh"]))
    print("%s %s %s  neg=%d run=%d low3=%d sh=%d sf=%d sf8=%d %s" % (
        se, sg, insn, st["neg"], st["run"], st["low3"], st["sh"], sf, sf8,
        "CARRY" if st["neg"]==1 else "BORROW"))
pickle.dump(CACHE, open("h787_state.pkl","wb"))
