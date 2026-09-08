#!/usr/bin/env python3
# h923: the R91 wall census.  Input: h922_diff.txt.gz (rows where the
# r59-ON and r59-OFF builds disagree — ON is hw-exact off-ledger by
# suite-zero, so every non-ledger diff row is a scope constraint).
# For each distinct diff operand: extract the ON-side r59 frame
# (branch, theta, ce, cell, fire) and the OFF-side terminal frame
# (act, top8, low3, sum) via two dump runs, then census the
# coordinate tuples: POS = the 8 h921-fixed keys; every tuple's NEG
# count is the wall test.  Scope arms probed explicitly:
#   ARM A: ce=-74 (the three randv1 keys, all OFF-sum 0x102)
#   ARM B: fire=1 override (the five comb keys; be60 = known breaker)
import subprocess, re, sys, gzip, collections

ON = "./model_h917_noled"
OFF = "./model_h921_nor59"

# the 8 h921-fixed keys (se, sig) and be60 (the non-fixed fire=1 tie)
FIXED = {
    ("3ffc", "ba100000056e0a67"), ("3ffc", "cca0000009242f0c"),
    ("3ffc", "fa50000007503a2f"), ("3ffc", "f310000007fc5117"),
    ("3ffc", "fffc00000bd0e8f0"), ("c019", "92599b98fa10f92b"),
    ("402b", "a023d0b24157b0d6"), ("4016", "b1dbc588a7057f83"),
}
ledger_ops = set()
for l in open("probe_keys.tsv"):
    f = l.split()
    if len(f) == 6:
        ledger_ops.add((f[2], f[3]))

# 1. distinct diff operands per corpus
by_corpus = collections.defaultdict(set)
modes_of = collections.defaultdict(set)
for ln in gzip.open("h922_diff.txt.gz", "rt"):
    t = ln.split()
    if len(t) < 3:
        continue
    by_corpus[t[0]].add(int(t[2]))
    modes_of[(t[0], int(t[2]))].add(t[1])

def ops_of(corpus, nrs):
    out = []
    want = sorted(nrs)
    i = 0
    with open("/root/h491/%s_inputs.txt" % corpus) as fh:
        for n, ln in enumerate(fh, 1):
            if i < len(want) and n == want[i]:
                out.append(ln.split())
                i += 1
    return out

def parse_kv(line):
    d = {}
    for m in re.finditer(r"(\w+)=([0-9a-fA-F-]+)", line):
        d[m.group(1)] = m.group(2)
    return d

def frames2(model, ops):
    inp = "".join("%s %s\n" % (se, sig) for se, sig in ops)
    p = subprocess.run([model, "--batch", "--fcos-standalone",
                        "--dump-internals"],
                       input=inp, capture_output=True, text=True)
    rows = []
    cur = {}
    for ln in p.stderr.splitlines():
        if ln.startswith("DI_IN"):
            if cur:
                rows.append(cur)
            m = re.match(r"DI_IN ([0-9a-f]{4}) ([0-9a-f]{16})", ln)
            cur = {"se": m.group(1), "sig": m.group(2)}
        elif ln.startswith("DI_R59"):
            d = parse_kv(ln)
            cur["theta"] = int(d["theta"]); cur["ce"] = int(d["ce"])
            cur["s4"] = int(d["s4"]); cur["side"] = int(d["side"])
            cur["dist"] = int(d["dist"]); cur["rsh"] = int(d["rsh"])
            cur["low3"] = int(d["low3"])
            cur["b1"] = int(d["b1"]); cur["b2"] = int(d["b2"])
        elif ln.startswith("DI_BR"):
            cur["br"] = re.search(r"br=(\w+)", ln).group(1)
            m = re.search(r"t?fire=(\d)", ln)
            cur["fire"] = int(m.group(1)) if m else -1
        elif ln.startswith("DI_TC "):
            d = parse_kv(ln)
            cur["act"] = int(d.get("active", "-1"))
            cur["tlow3"] = int(d.get("low3", "-1"))
        elif ln.startswith("DI_ACC"):
            m = re.search(r"d60=([0-9a-f]{32})", ln)
            if m:
                cur["top8"] = (int(m.group(1), 16) >> 52) & 0xFF
        elif ln.startswith("DI_B81"):
            d = parse_kv(ln)
            cur["b81act"] = int(d["act"]); cur["b81pay"] = int(d["pay"])
    if cur:
        rows.append(cur)
    return rows

census = collections.Counter()
pos_seen = []
armA_neg = collections.Counter()
armB_neg = collections.Counter()
nneg = 0
def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def absorb(corpus, onf, off):
    global nneg
    for o, f in zip(onf, off):
        key = (o.get("se"), o.get("sig"))
        assert key == (f.get("se"), f.get("sig"))
        sums = f.get("top8", -1)
        if sums >= 0:
            sums = sums + f.get("tlow3", 0)
        tup = (o.get("br", "?"), o.get("theta", 99), o.get("ce", 0),
               o.get("fire", -1), sums >= 0 and 0xFD <= sums <= 0x106)
        ispos = key in FIXED
        isled = key in ledger_ops
        if ispos:
            pos_seen.append((corpus, key[1][:8], tup, hex(sums)
                             if sums >= 0 else "-"))
            continue
        if isled:
            continue
        nneg += 1
        census[tup] += 1
        if o.get("ce", 0) == -74:
            armA_neg[(o.get("br"), o.get("theta"), o.get("fire"),
                      hex(sums) if sums >= 0 else "-")] += 1
        if o.get("fire", -1) == 1:
            armB_neg[(o.get("br"), o.get("theta"),
                      sums >= 0 and 0xFD <= sums <= 0x106)] += 1

for corpus in sorted(by_corpus):
    allops = ops_of(corpus, by_corpus[corpus])
    done = 0
    for ops in chunks(allops, 100000):
        onf = frames2(ON, ops)
        off = frames2(OFF, ops)
        absorb(corpus, onf, off)
        done += len(ops)
        print("  ...%s %d/%d" % (corpus, done, len(allops)),
              file=sys.stderr)

print("diff operands: NEG=%d  POS seen=%d" % (nneg, len(pos_seen)))
print("\n== POS tuples (br, theta, ce, fire, sum-in-band) ==")
for p in pos_seen:
    print("  %s %s %s sum=%s" % p)
print("\n== ARM A: ce=-74 NEG diff rows (br, theta, fire, sum) ==")
tot = 0
for kk in sorted(armA_neg, key=lambda x: -armA_neg[x])[:20]:
    print("  %-40s %d" % (str(kk), armA_neg[kk])); tot += armA_neg[kk]
print("  ARM A NEG total: %d" % sum(armA_neg.values()))
print("\n== ARM B: fire=1 NEG diff rows (br, theta, in-band) ==")
for kk in sorted(armB_neg, key=lambda x: -armB_neg[x])[:20]:
    print("  %-40s %d" % (str(kk), armB_neg[kk]))
print("  ARM B NEG total: %d" % sum(armB_neg.values()))
print("\n== full census top tuples ==")
for kk in sorted(census, key=lambda x: -census[x])[:25]:
    print("  %-45s %d" % (str(kk), census[kk]))
