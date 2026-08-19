#!/usr/bin/env python3
# h785: family census of ALL current randv1 + rv2 residual rows.
import subprocess, collections
def norm(l):
    t = l.split()
    return ("C2",) if t[0]=="C2" else tuple(t[1:3])
inp = open("/root/h491/randv1_inputs.txt").read().splitlines()
rows = []   # (src, insn, mode, se, sig, hw, mo)
for insn in ("cos","sin"):
    for mode in ("rn","rd","ru"):
        hw = open("/root/h491/randv1_%s_%s_hw_status.txt"%(insn,mode)).read().splitlines()
        mo = open("h785mo_%s_%s.txt"%(insn,mode)).read().splitlines()
        assert len(hw)==len(mo)==len(inp)
        for i,(a,b) in enumerate(zip(hw,mo)):
            na, nb = norm(a), norm(b)
            if na != nb:
                se, sg = inp[i].split()
                rows.append(("randv1", insn, mode, se, sg, na, nb))
for L in open("h780_votes.txt"):
    t = L.split()
    hwp = t[5].split("=")[1].split("/"); mop = t[6].split("=")[1].split("/")
    rows.append(("rv2", t[1], t[2], t[3], t[4], tuple(hwp), tuple(mop)))
print("total miss lines: randv1 %d rv2 %d" % (
    sum(1 for r in rows if r[0]=="randv1"), sum(1 for r in rows if r[0]=="rv2")))
def parse_wv(s):
    sg,e2,hx = s.split(":")
    return (int(sg), int(e2), int(hx,16))
def classify(se, sig, insn):
    flag = "--fcos-standalone" if insn=="cos" else "--fsin-standalone"
    p = subprocess.run(["./model_h235","--batch",flag,"--dump-internals"],
                       input="%s %s\n"%(se,sig), capture_output=True, text=True)
    tc = corr = spoly = red = None
    for L in p.stderr.splitlines():
        if L.startswith("DI_TC "): tc = dict(x.split("=",1) for x in L.split()[1:] if "=" in x)
        if L.startswith("DI_CORR"): corr = dict(x.split("=",1) for x in L.split()[1:] if "=" in x)
        if L.startswith("DI_SPOLY"): spoly = L
        if L.startswith("DI_RED"): red = dict(x.split("=",1) for x in L.split()[1:] if "=" in x)
    out = dict(via=corr.get("via") if corr else None,
               i1=red.get("i1") if red else None)
    if tc:
        out["act"] = tc.get("active"); out["low3"] = tc.get("low3"); out["pay"] = tc.get("payload")
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
                    out["run"] = rl
        except Exception as ex:
            out["run"] = "?"
    return out
ops = {}
for (src, insn, mode, se, sg, hw, mo) in rows:
    ops.setdefault((se,sg,insn), []).append((src,mode,hw,mo))
print("distinct (op,insn):", len(ops))
fam = collections.Counter()
for (se,sg,insn), lst in sorted(ops.items()):
    c = classify(se,sg,insn)
    dirs = []
    for src,mode,hw,mo in lst:
        if hw==("C2",) or mo==("C2",): d="C2"
        else:
            hv = int(hw[1],16); mv = int(mo[1],16)
            d = "chip+1" if hv>mv else ("mo+1" if mv>hv else "?")
        dirs.append("%s:%s:%s"%(src,mode,d))
    key = (c.get("i1"), c.get("via"), c.get("act"), "run%s"%c.get("run"), "|".join(sorted(set(x.split(":")[2] for x in dirs))))
    fam[key] += 1
    print("%s %s %s  i1=%s via=%s act=%s low3=%s pay=%s run=%s  %s" % (
        se, sg, insn, c.get("i1"), c.get("via"), c.get("act"), c.get("low3"),
        c.get("pay"), c.get("run"), " ".join(dirs)))
print()
print("FAMILY SUMMARY (i1, via, act, run, dirset):")
for k,v in fam.most_common():
    print("  %s : %d" % (k, v))
print("H785_CENSUS_DONE")
