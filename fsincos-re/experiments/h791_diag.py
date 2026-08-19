#!/usr/bin/env python3
# h791: DI-classify the ck14 blind fixed/broken rows into staircase cells.
import subprocess
def parse_wv(s):
    sg,e2,hx = s.split(":")
    return (int(sg), int(e2), int(hx,16))
def tcstate(se, sig, insn):
    flag = "--fcos-standalone" if insn=="cos" else "--fsin-standalone"
    p = subprocess.run(["./model_h235","--batch",flag,"--dump-internals"],
                       input="%s %s\n"%(se,sig), capture_output=True, text=True)
    tc = corr = fin = None
    for L in p.stderr.splitlines():
        if L.startswith("DI_TC "): tc = dict(x.split("=",1) for x in L.split()[1:] if "=" in x)
        if L.startswith("DI_CORR"): corr = dict(x.split("=",1) for x in L.split()[1:] if "=" in x)
        if L.startswith("DI_FIN"): fin = dict(x.split("=",1) for x in L.split()[1:] if "=" in x)
    if not (tc and corr and fin): return None
    left = parse_wv(tc["left"]); right = parse_wv(tc["right"])
    dl = left[1]-right[1]
    payload = int(tc.get("payload","0"))
    S = (left[2]<<dl) + ((payload<<(dl-8)) if payload and dl>=8 else 0)
    D = S - right[2]
    sh = D.bit_length()-67
    disc = D & ((1<<sh)-1)
    rl = 0
    for b in range(sh-1,-1,-1):
        if (disc>>b)&1: rl += 1
        else: break
    return dict(via=corr.get("via"), sh=sh, disc=disc, run=rl,
        act=tc.get("active"), low3=tc.get("low3"), pay=payload,
        neg=fin.get("neg"), dl=dl)
import sys
for fn, tag in (("ck14_broken.txt","BRK"),("ck14_fixed.txt","FIX")):
    for L in open(fn):
        t = L.split()
        insn, mode, se, sg = t[0], t[1], t[3], t[4]
        st = tcstate(se, sg, insn)
        if st is None:
            print("%s %s %s %s %s -> NO-STATE" % (tag, insn, mode, se, sg)); continue
        print("%s %s %-2s %s %s  via=%s act=%s run=%-2d low3=%s sh=%-2d pay=%d neg=%s dl=%d disc=%x" % (
            tag, insn, mode, se, sg, st["via"], st["act"], st["run"], st["low3"],
            st["sh"], st["pay"], st["neg"], st["dl"], st["disc"]))
