#!/usr/bin/env python3
# h723: cell-matched contrast.  For each band/tie/q67th2/corner miss,
# find clean rows in the SAME cell (branch, sgn_th, |th|, s4, side,
# low3, b1, b2, dist, rsh) and compare the un-modeled features:
# ud (top-3 left-discard bits), u5d, rud, disc, pm, deep block bits
# (umag at k+16, k+24), payload.  Report per-cell: miss value vs
# clean distribution.
import sys, collections
HEX128 = {"umag","S","B","Mreg","t4","sqlow","rd3","disc"}
def blocks(path):
    cur = None; d = None
    for line in open(path):
        t = line.split()
        if not t: continue
        if t[0] == "DI_IN":
            if cur is not None: yield cur, d
            cur = (t[1], t[2]); d = {}
        elif d is None: continue
        else:
            dd = d.setdefault(t[0], {})
            for kv in t[1:]:
                k, v = kv.split("=", 1)
                if t[0] == "DI_R59" and k in HEX128:
                    x = int(v, 16)
                    if x >= 1 << 127: x -= 1 << 128
                    dd[k] = x
                elif ":" in v and v.count(":") == 2: dd[k] = v
                elif "," in v: dd[k] = v
                elif v.lstrip("-").isdigit(): dd[k] = int(v)
                else: dd[k] = v
    if cur is not None: yield cur, d

def feats(d):
    r59 = d["DI_R59"]; tc = d.get("DI_TC", {}); br = d.get("DI_BR", {})
    th = r59["theta"]; k = r59["k"]
    umag = r59["umag"]; S = r59["S"]; B = r59["B"]
    pmask = ~(S ^ B) & ((1 << 128) - 1)
    pm = 0; j = k
    while pm < 32 and (pmask >> j) & 1:
        pm += 1; j += 1
    b = br.get("br", d.get("DI_CORR", {}).get("via"))
    cell = (b, 0 if th == 0 else (1 if th > 0 else -1), abs(th),
            r59["s4"], r59["side"], r59["low3"], r59["b1"], r59["b2"],
            r59["dist"], r59["rsh"])
    f = dict(ud=tc.get("ud"), u5d=tc.get("u5d"), rud=tc.get("rud"),
             disc=r59["disc"] if r59["disc"] < 8 else r59["disc"] - (1 << k),
             pm=pm, pay=r59["payload"],
             bs16=(umag >> (k + 16)) & 1, bs24=(umag >> (k + 24)) & 1,
             t4top=(r59["t4"] >> 60) & 0xf)
    return cell, f

MISS = set(l.split()[1] for l in open("h714_ops.txt"))
miss_rows = []
for (se, sig), d in blocks("h714_dump.txt"):
    if "DI_R59" not in d: continue
    cell, f = feats(d)
    miss_rows.append((sig, cell, f))
clean_by_cell = collections.defaultdict(list)
want = set(c for _, c, _ in miss_rows)
for (se, sig), d in blocks("h720_sample.dump"):
    if sig in MISS or "DI_R59" not in d: continue
    cell, f = feats(d)
    if cell in want:
        clean_by_cell[cell].append(f)
KEYS = ("ud","u5d","rud","disc","pm","pay","bs16","bs24","t4top")
for sig, cell, f in miss_rows:
    cl = clean_by_cell.get(cell, [])
    print("MISS %s cell=%s  clean_twins=%d" % (sig[-8:], cell, len(cl)))
    if not cl:
        continue
    for key in KEYS:
        mv = f[key]
        vals = [c[key] for c in cl if c[key] is not None]
        if not vals or mv is None: continue
        n_eq = sum(1 for v in vals if v == mv)
        frac = n_eq / len(vals)
        flag = "  <<<" if frac < 0.03 and len(vals) >= 30 else ""
        print("    %-5s miss=%-4s cleanP(=)=%.3f n=%d%s"
              % (key, mv, frac, len(vals), flag))
