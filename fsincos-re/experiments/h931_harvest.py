#!/usr/bin/env python3
# h931 step 2: frame harvest for the retest dataset.  For every
# distinct operand in h931_labels.tsv, stream a dump run of the
# current model and keep: ALL carry operands + AGREE operands whose
# terminal sum is in the adder window [0xF8, 0x106].  Per-operand
# label = C if ANY mode was C (the mode-consistency lesson).
# Output h931_frames.tsv: label, seed, insn, op, scalars, wv hexes,
# d60, grl (:= right sig low-7, the h928 proxy).
import subprocess, re, sys
from collections import defaultdict

MODEL = "./model_r92"
ops = {}                       # (insn, op) -> [label, seed]
for ln in open("h931_labels.tsv"):
    t = ln.rstrip("\n").split("\t")
    seed, insn, mode, op, cls = int(t[0]), t[1], t[2], t[3], t[8]
    k = (insn, op)
    if k not in ops:
        ops[k] = ["AGREE", seed]
    if cls == "C":
        ops[k][0] = "C"
    ops[k][1] = min(ops[k][1], seed)
print("distinct (insn,op):", len(ops), " C:",
      sum(1 for v in ops.values() if v[0] == "C"), file=sys.stderr)

WVRE = re.compile(r"(mul|lf|rf|f4|left|right)=(\d+):(-?\d+):([0-9a-f]{32})")
out = open("h931_frames.tsv", "w")
out.write("lab\tseed\tinsn\tse\tsig\tactive\tpayload\tlow3\tdist\trsh\t"
          "ud\tu5d\trud\tmule2\tmulsig\tlfe2\tlfsig\trfe2\trfsig\t"
          "f4e2\tf4sig\tlefte2\tleftsig\tleftsign\trighte2\trightsig\t"
          "rightsign\td60\tgrl\n")
kept = keptC = 0
for insn in ("cos", "sin"):
    batch = [(k[1], v) for k, v in ops.items() if k[0] == insn]
    fl = "--fsin-standalone" if insn == "sin" else "--fcos-standalone"
    CH = 200000
    for ci in range(0, len(batch), CH):
        chunk = batch[ci:ci + CH]
        p = subprocess.Popen([MODEL, "--batch", fl, "--dump-internals"],
                             stdin=subprocess.PIPE,
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.PIPE, text=True, bufsize=1)
        import threading
        def feed():
            for op, _ in chunk:
                p.stdin.write(op + "\n")
            p.stdin.close()
        threading.Thread(target=feed, daemon=True).start()
        idx = -1
        cur = {}
        def flush():
            global kept, keptC
            if idx < 0 or "d60" not in cur or "low3" not in cur:
                return
            op, (lab, seed) = chunk[idx]
            d60 = int(cur["d60"], 16)
            low3 = int(cur["low3"])
            summ = ((d60 >> 52) & 0xFF) + low3
            if lab != "C" and not (0xF8 <= summ <= 0x106):
                return
            se, sig = op.split()
            grl = int(cur["right"][2], 16) & 0x7F
            out.write("\t".join(str(x) for x in (
                lab, seed, insn, se, sig, cur.get("active", "?"),
                cur.get("payload", "0"), low3, cur.get("dist", "?"),
                cur.get("rsh", "?"), cur.get("ud", "?"),
                cur.get("u5d", "?"), cur.get("rud", "?"),
                cur["mul"][1], cur["mul"][2], cur["lf"][1], cur["lf"][2],
                cur["rf"][1], cur["rf"][2], cur["f4"][1], cur["f4"][2],
                cur["left"][1], cur["left"][2], cur["left"][0],
                cur["right"][1], cur["right"][2], cur["right"][0],
                cur["d60"], grl)) + "\n")
            kept += 1
            keptC += (lab == "C")
        for ln in p.stderr:
            if ln.startswith("DI_IN"):
                flush()
                idx += 1
                cur = {}
            elif ln.startswith("DI_TC "):
                for m in re.finditer(r"(\w+)=(-?\d+)\b", ln):
                    cur.setdefault(m.group(1), m.group(2))
                for m in WVRE.finditer(ln):
                    cur[m.group(1)] = (m.group(2), m.group(3), m.group(4))
            elif ln.startswith("DI_ACC"):
                m = re.search(r"d60=([0-9a-f]{32})", ln)
                if m:
                    cur["d60"] = m.group(1)
        flush()
        p.wait()
        print("harvest %s %d/%d kept=%d C=%d"
              % (insn, min(ci + CH, len(batch)), len(batch), kept, keptC),
              file=sys.stderr)
out.close()
print("kept rows:", kept, " C:", keptC, file=sys.stderr)
