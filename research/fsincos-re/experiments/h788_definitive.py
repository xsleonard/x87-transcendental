#!/usr/bin/env python3
# h788: DEFINITIVE cos-default pool — cache rebuilt (retry Nones),
# every h745 row ground-truthed vs the SHIPPED model (model_h780),
# corrected (run x low3) joint + form test.
import subprocess, collections, pickle, os
def parse_wv(s):
    sg,e2,hx = s.split(":")
    return (int(sg), int(e2), int(hx,16))
CACHEF = "h787_state.pkl"
CACHE = pickle.load(open(CACHEF,"rb")) if os.path.exists(CACHEF) else {}
def tcstate(se, sig, insn, retry=True):
    k = (se,sig,insn)
    if k in CACHE and (CACHE[k] is not None or not retry): return CACHE[k]
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
                    out = dict(sh=sh, disc=disc, run=rl,
                        act=int(tc.get("active","0")), low3=int(tc.get("low3","0")),
                        pay=payload, neg=int(fin.get("neg","0")))
        except Exception:
            pass
    CACHE[k] = out
    return out
def shipped(se, sig, insn, mode):
    flag = "--fcos-standalone" if insn=="cos" else "--fsin-standalone"
    args = ["./model_h780","--batch"]
    if mode=="rd": args.append("--rc=rd")
    if mode=="ru": args.append("--rc=ru")
    args.append(flag)
    p = subprocess.run(args, input="%s %s\n"%(se,sig), capture_output=True, text=True)
    t = p.stdout.split()
    return (t[1], t[2]) if len(t)>=3 else None
POS = {}
for fn in ("h753_allvotes.txt","h759_miner2_votes.txt"):
    for L in open(fn):
        t = L.split()
        if t[5].startswith("hw=C2") or t[6].startswith("mo=C2"): continue
        hv = int(t[5].split("/")[-1],16); mv = int(t[6].split("/")[-1],16)
        POS.setdefault((t[3],t[4],t[1]), set()).add("up" if hv>mv else "dn")
# ground-truth h745 rows: chip (hw field) vs SHIPPED model output
NEGV = {}
promoted = 0
for fn in ("h745_neg_r70.txt","h745_neg_r70b.txt"):
    for L in open(fn):
        t = L.split()
        k = (t[3],t[4],t[1])
        if k in POS or k in NEGV: continue
        hwp = t[5].split("=")[1].split("/")
        sh_ = shipped(t[3],t[4],t[1],t[2])
        if sh_ is None: continue
        if tuple(hwp) == sh_:
            NEGV[k] = "NEG"
        else:
            hv = int(hwp[1],16); mv = int(sh_[1],16)
            POS.setdefault(k, set()).add("up" if hv>mv else "dn")
            promoted += 1
print("h745 ground-truth: %d rows promoted to POS (chip != shipped); NEG kept %d" % (promoted, len(NEGV)))
recs = []
for (se,sg,insn), ds in sorted(POS.items()):
    st = tcstate(se,sg,insn)
    if not st: continue
    if len(ds) > 1: mech = "MIXED"
    else:
        d = ds.copy().pop()
        mech = "CARRY" if ((d=="up") == (st["neg"]==0)) else "BORROW"
    recs.append((mech, st, (se,sg,insn)))
nnone = 0
for (se,sg,insn) in sorted(NEGV):
    st = tcstate(se,sg,insn)
    if st: recs.append(("NEG", st, (se,sg,insn)))
    else: nnone += 1
pickle.dump(CACHE, open(CACHEF,"wb"))
print("recs:", collections.Counter(m for m,_,_ in recs), "unparsed-neg:", nnone)
print()
print("=== CORRECTED act0 CARRY (run x low3)  [POS | NEG] ===")
P = collections.Counter(); Nn = collections.Counter()
for m, st, _ in recs:
    if st["act"] != 0: continue
    if m=="CARRY": P[(min(st["run"],10), st["low3"])] += 1
    elif m=="NEG": Nn[(min(st["run"],10), st["low3"])] += 1
for run in range(0,11):
    if any(P.get((run,l),0)+Nn.get((run,l),0) for l in range(8)):
        print("  run%-2d " % run + " ".join("%2d/%-3d" % (P.get((run,l),0), Nn.get((run,l),0)) for l in range(8)))
# form test on the corrected pool
tp=fn_=fp=tn=0
viol = []
for m, st, k in recs:
    if st["act"] != 0: continue
    fire = (st["low3"] << st["run"]) > 128
    if m=="CARRY":
        if fire: tp+=1
        else: fn_+=1; viol.append(("POSMISS",k,st))
    elif m=="NEG":
        if fire: fp+=1; viol.append(("NEGFIRE",k,st))
        else: tn+=1
print("form test act0: CARRY %d/%d, NEG %d/%d" % (tp, tp+fn_, tn, tn+fp))
for v in viol[:12]: print("  ", v)
print("H788_DONE")
