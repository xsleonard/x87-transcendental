#!/usr/bin/env python3
# h799: family census of ck14's R71-baseline misses (miner density).
import subprocess, collections, pickle, os
def norm(l):
    t = l.split()
    return ("C2",) if t[0]=="C2" else tuple(t[1:3])
inp = open("ck14_inputs.txt").read().splitlines()
miss = {}
for insn in ("cos","sin"):
    for mode in ("rn","rd","ru"):
        args = ["./model_h780","--batch"]
        if mode=="rd": args.append("--rc=rd")
        if mode=="ru": args.append("--rc=ru")
        args.append("--fcos-standalone" if insn=="cos" else "--fsin-standalone")
        mo = subprocess.run(args, stdin=open("ck14_inputs.txt"), capture_output=True, text=True).stdout.splitlines()
        hw = open("ck14hw_%s_%s.txt"%(insn,mode)).read().splitlines()
        assert len(hw)==len(mo)==len(inp)
        for i,(a,b) in enumerate(zip(hw,mo)):
            na, nb = norm(a), norm(b)
            if na != nb:
                se, sg = inp[i].split()
                d = "C2" if ("C2",) in (na,nb) else ("up" if int(na[1],16)>int(nb[1],16) else "dn")
                miss.setdefault((se,sg,insn), []).append((mode,d))
print("ck14 R71-baseline misses: %d lines, %d distinct ops" % (sum(len(v) for v in miss.values()), len(miss)))
def classify(se, sig, insn):
    flag = "--fcos-standalone" if insn=="cos" else "--fsin-standalone"
    p = subprocess.run(["./model_h235","--batch",flag,"--dump-internals"],
                       input="%s %s\n"%(se,sig), capture_output=True, text=True)
    i1 = via = act = neg = None
    for L in p.stderr.splitlines():
        if L.startswith("DI_RED"):
            f = dict(x.split("=",1) for x in L.split()[1:] if "=" in x); i1 = f.get("i1")
        if L.startswith("DI_CORR"):
            f = dict(x.split("=",1) for x in L.split()[1:] if "=" in x); via = f.get("via")
        if L.startswith("DI_TC "):
            f = dict(x.split("=",1) for x in L.split()[1:] if "=" in x); act = f.get("active")
        if L.startswith("DI_FIN"):
            f = dict(x.split("=",1) for x in L.split()[1:] if "=" in x); neg = f.get("neg")
    return i1, via, act, neg
fam = collections.Counter()
for (se,sg,insn), lst in sorted(miss.items()):
    i1, via, act, neg = classify(se,sg,insn)
    dirs = set(d for _,d in lst)
    if i1=="0":
        f = "sine-branch " + ("+1(chip-above)" if dirs=={"up"} else "model-over" if dirs=={"dn"} else str(dirs))
    elif via=="default":
        mech = "carry" if (("up" in dirs) == (neg=="0")) else "borrow"
        f = "default act%s %s(neg=%s)" % (act, mech, neg)
    else:
        f = "via=%s act=%s dirs=%s" % (via, act, dirs)
    fam[f] += 1
for k,v in fam.most_common():
    print("  %-40s : %d" % (k,v))
