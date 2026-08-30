#!/usr/bin/env python3
# h972: supplemental harvest for the offline exact-tail program.
# For every h968 census op, capture from model_r93_ref
# --dump-internals:
#   - the FULL right-side discarded field (rdisc, 32 hex — h970
#     banked only the high half),
#   - DI_CORR: the model's FINAL terminal value (via=default/r59/
#     plain, sign:e2:sig) — the post-carry ground truth that makes
#     carry replication unnecessary (epsilon = variant - DI_CORR).
import subprocess, sys
from collections import defaultdict

ops = []
for ln in open("h968_ops.tsv"):
    t = ln.rstrip("\n").split("\t")
    if t[0] == "insn":
        continue
    ops.append((t[0], t[1]))
byinsn = defaultdict(list)
for insn, op in ops:
    byinsn[insn].append(op)
print("ops:", len(ops), file=sys.stderr)

out = open("h972_corr.tsv", "w")
out.write("insn\top\trdisc\tvia\tcpay\tcsign\tce2\tcsig\n")
for insn, olist in sorted(byinsn.items()):
    fl = "--fsin-standalone" if insn == "sin" else "--fcos-standalone"
    p = subprocess.run(["./model_r93_ref", "--batch", fl,
                        "--dump-internals"],
                       input="\n".join(olist) + "\n",
                       capture_output=True, text=True)
    recs, cur = [], None
    for ln in p.stderr.splitlines():
        if ln.startswith("DI_IN"):
            if cur is not None:
                recs.append(cur)
            cur = {}
            continue
        if cur is None:
            continue
        if ln.startswith("DI_TC ") and "rdisc" not in cur:
            cur["rdisc"] = ln.split("rdisc=")[1][:32]
        elif ln.startswith("DI_CORR") and "via" not in cur:
            body = ln.split("DI_CORR ")[1]
            toks = body.split()
            via = toks[0].split("=", 1)[1]
            cpay = "-"
            for tk in toks[1:]:
                if tk.startswith("payload="):
                    cpay = tk.split("=", 1)[1]
            o = ln.split("out=")[1].split(":")
            cur["via"] = via
            cur["cpay"] = cpay
            cur["cs"] = o[0]
            cur["ce2"] = o[1]
            cur["csig"] = o[2][:32]
    if cur is not None:
        recs.append(cur)
    assert len(recs) == len(olist), (insn, len(recs), len(olist))
    for op, r in zip(olist, recs):
        out.write("\t".join((insn, op, r.get("rdisc", "-"),
                             r.get("via", "-"), r.get("cpay", "-"),
                             r.get("cs", "-"), r.get("ce2", "-"),
                             r.get("csig", "-"))) + "\n")
    print("done", insn, file=sys.stderr)
out.close()
from collections import Counter
c = Counter()
for ln in open("h972_corr.tsv"):
    t = ln.split("\t")
    if t[0] != "insn":
        c[t[3]] += 1
print("via counts:", dict(c))
