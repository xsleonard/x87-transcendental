def norm(l):
    t = l.split()
    return ("C2",) if t[0]=="C2" else tuple(t[1:3])
inp = open("ck14_inputs.txt").read().splitlines()
base = set(); new = set()
basem = {}; newm = {}
for insn in ("cos","sin"):
    for mode in ("rn","rd","ru"):
        hw = open("ck14hw_%s_%s.txt"%(insn,mode)).read().splitlines()
        b  = open("ck14b_%s_%s.txt"%(insn,mode)).read().splitlines()
        g  = open("ck14g_%s_%s.txt"%(insn,mode)).read().splitlines()
        assert len(hw)==len(b)==len(g)==len(inp)
        for i,(a,x,y) in enumerate(zip(hw,b,g)):
            na = norm(a)
            if norm(x)!=na:
                base.add((insn,mode,i)); basem[(insn,mode,i)] = (inp[i], "/".join(na), "/".join(norm(x)))
            if norm(y)!=na:
                new.add((insn,mode,i)); newm[(insn,mode,i)] = (inp[i], "/".join(na), "/".join(norm(y)))
print("BLIND ck14: R71-baseline misses %d   R72 misses %d   FIXED %d   BROKEN %d" % (
    len(base), len(new), len(base-new), len(new-base)))
f = open("ck14_fixed.txt","w")
for k in sorted(base-new):
    v = basem[k]
    f.write("%s %s %s  %s hw=%s r71=%s\n" % (k[0],k[1],k[2],v[0],v[1],v[2]))
f.close()
f = open("ck14_broken.txt","w")
for k in sorted(new-base):
    v = newm[k]
    f.write("%s %s %s  %s hw=%s r72=%s\n" % (k[0],k[1],k[2],v[0],v[1],v[2]))
f.close()
