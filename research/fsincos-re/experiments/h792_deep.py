#!/usr/bin/env python3
# h792: FULL DI_TC state for the 19 ck14 rows; within-cell contrasts.
import subprocess, collections
def parse_wv(s):
    sg,e2,hx = s.split(":")
    return (int(sg), int(e2), int(hx,16))
def full(se, sig, insn):
    flag = "--fcos-standalone" if insn=="cos" else "--fsin-standalone"
    p = subprocess.run(["./model_h235","--batch",flag,"--dump-internals"],
                       input="%s %s\n"%(se,sig), capture_output=True, text=True)
    tc = fin = None
    for L in p.stderr.splitlines():
        if L.startswith("DI_TC "): tc = dict(x.split("=",1) for x in L.split()[1:] if "=" in x)
        if L.startswith("DI_FIN"): fin = dict(x.split("=",1) for x in L.split()[1:] if "=" in x)
    return tc, fin
rows = []
for fn, tag in (("ck14_broken.txt","BRK"),("ck14_fixed.txt","FIX")):
    for L in open(fn):
        t = L.split()
        rows.append((tag, t[0], t[1], t[3], t[4]))
print("tag insn md   se  low3 run  dist rsh ud u5d rud  L.e2 Rlow12 Llow12 disc_below_run")
for tag, insn, mode, se, sg in rows:
    tc, fin = full(se, sg, insn)
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
    below = disc & ((1<<(sh-rl-1))-1) if sh-rl-1 > 0 else 0
    belw = sh-rl-1
    print("%s %s %-2s %s  %s   %-2d   %s  %s  %s  %-2s  %s  %-3d  %03x  %03x  %s (w%d)" % (
        tag, insn, mode, se, tc.get("low3"), rl, tc.get("dist"), tc.get("rsh"),
        tc.get("ud"), tc.get("u5d"), tc.get("rud"), left[1],
        right[2]&0xfff, left[2]&0xfff, bin(below)[2:].zfill(max(belw,1)), belw))
