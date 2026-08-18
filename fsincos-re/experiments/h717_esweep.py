#!/usr/bin/env python3
# h717: which umag offsets e (S-B low-unit deltas) reproduce the
# hardware in ALL THREE modes, per census row.  Unified hypothesis:
# chip umag = model umag + e (|e| small) at wrap-adjacent rows.
def norm(line):
    t = line.split()
    return "C2" if t[0] == "C2" else "%s/%s" % (t[1], t[2])
ops = []; hw3 = []
for line in open("h714_hw3.txt"):
    left, h3, m3 = line.strip().split(" | ")
    se, sig, corp, lineno = left.split()
    ops.append((se, sig, corp)); hw3.append(h3.split())
ES = [-4,-3,-2,-1,1,2,3,4]
MODES = ("rn","rd","ru")
pt = {}
for e in ES:
    for m in MODES:
        pt[(e,m)] = [norm(l) for l in open(f"pt_umag_{e}_{m}.txt")]
HEX128 = {"umag","S","B","Mreg","t4","sqlow","rd3","disc"}
di = {}; cur = None
for line in open("h714_dump.txt"):
    t = line.split()
    if not t: continue
    if t[0] == "DI_IN":
        cur = (t[1], t[2]); di[cur] = {}
    elif t[0] in ("DI_R59","DI_TC","DI_BR","DI_CORR") and cur:
        d = di[cur].setdefault(t[0], {})
        for kv in t[1:]:
            k, v = kv.split("=", 1)
            if t[0] == "DI_R59" and k in HEX128:
                d[k] = int(v, 16)
            elif v.lstrip("-").isdigit(): d[k] = int(v)
            else: d[k] = v
print("%-18s %-6s %3s %-7s | %-12s | %s" %
      ("sig","corp","th","gate","e-hits","payload dist low3 dl dr dp disc"))
for oi,(se,sig,corp) in enumerate(ops):
    hw = ["%s/%s" % (h[0], h[1]) for h in [x.split("/") for x in hw3[oi]]]
    hwj = hw3[oi]
    hits = [e for e in ES
            if all(pt[(e,m)][oi] == hwj[mi] for mi,m in enumerate(MODES))]
    d = di[(se,sig)]; r59 = d.get("DI_R59", {})
    br = d.get("DI_BR", {}); corr = d.get("DI_CORR", {})
    branch = br.get("br", corr.get("via","?"))
    disc = r59.get("disc")
    print("%-18s %-6s %3s %-7s | %-12s | p=%s d=%s l3=%s dl=%s dr=%s dp=%s disc=%s"
          % (sig, corp, r59.get("theta"), branch, hits,
             r59.get("payload"), r59.get("dist"), r59.get("low3"),
             r59.get("dl"), r59.get("dr"), r59.get("dp"), disc))
