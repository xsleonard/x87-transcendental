#!/usr/bin/env python3
# h790: the sine-branch MODEL-OVER family (14 randv1/rv2 ops) vs the
# sq&7 frontier — mirror test.  d_mirror = (r - 1/2) in even-lsbs
# (model rounded up; chip stayed down => chip mass DEFICIT delta > d).
import subprocess, collections
from fractions import Fraction
exec(open("h774_bitscan.py").read().split("vrec = pickle.load")[0])
HALF = Fraction(1,2)
OPS = [
 ("4007","fcc604a63feaa792","sin"), ("400b","f7ff321dac409000","sin"),
 ("400c","96b81d1e7cda0ace","cos"), ("4010","db968af9ec506a2c","cos"),
 ("4018","8f0efa1d0817ffda","cos"), ("402c","94d94a7d028857c2","sin"),
 ("4039","f93a965b8e95df8a","sin"), ("bffc","b57c805f76864db7","sin"),
 ("bffc","dbbc049866e45800","sin"), ("bfff","e037754b2d04015a","cos"),
 ("c00d","dbd08dc1357cf85a","sin"), ("c017","8e83533ce892f449","cos"),
 ("c033","f615104067c40949","cos"), ("c03c","efed38eda9675800","cos"),
]
def chain_s(m):
    def trunc(v,b):
        a = abs(v); g = TWO**(texp(a)-b+1)
        f = (a/g).__floor__()*g
        return f if v>0 else -f
    def rnb(v,b):
        a = abs(v); g = TWO**(texp(a)-b+1)
        q = a/g; fl = q.__floor__(); r = q-fl
        if r>HALF or (r==HALF and fl%2==1): fl += 1
        return fl*g if v>0 else -fl*g
    sq = trunc(m*m,67); f4 = trunc(sq*sq,67)
    o = trunc(f4*CV[5],67); o = rnb(CV[3]+o,64)
    o = trunc(f4*o,67); o = rnb(CV[1]+o,64); o = trunc(sq*o,67)
    e = trunc(f4*CV[6],67); e = rnb(CV[4]+e,64)
    e = trunc(f4*e,67); e = rnb(CV[2]+e,64); e = trunc(f4*e,67)
    return o, e
print("op                     insn  mag_src   sq&7 sq&63 d_signed(even-lsb)  de2")
for se, sg, insn in OPS:
    flag = "--fcos-standalone" if insn=="cos" else "--fsin-standalone"
    p = subprocess.run(["./model_h235","--batch",flag,"--dump-internals"],
                       input="%s %s\n"%(se,sg), capture_output=True, text=True)
    magw = None
    for L in p.stderr.splitlines():
        if L.startswith("DI_SPOLY"):
            f = dict(x.split("=",1) for x in L.split()[1:] if "=" in x)
            magw = f["mag"]
    if magw is None:
        print(se, sg, insn, "NO DI_SPOLY"); continue
    sgn, e2, hx = magw.split(":")
    mag = Fraction(int(hx,16)) * TWO**int(e2)
    s = sigs(mag)
    o, e = chain_s(mag)
    ssum = o + e
    es = texp(abs(ssum)); ee = texp(abs(e))
    g = TWO**(es-63)
    r = abs(ssum)/g - (abs(ssum)/g).__floor__()
    d = float((r - HALF) * TWO**(es-63-ee+66))   # positive = model rounded UP (r>1/2)
    print("%s %s %s   %s  %d  %2d   %+9.4f   %d" % (se, sg, insn, hx[-4:], s["sq"]&7, s["sq"]&63, d, texp(abs(o))-ee))
