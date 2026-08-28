#!/usr/bin/env python3
# h938 step: dump terminal frames for an arbitrary input list via the
# current model's --dump-internals (mode-independent internals).
# Usage: h938_frames.py <model> <insn cos|sin> <inputs.txt> <out.tsv>
# Output columns mirror h931_frames.tsv where relevant, plus idx.
import subprocess, re, sys, threading

model, insn, inp_path, out_path = sys.argv[1:5]
inputs = [ln.strip() for ln in open(inp_path) if ln.strip()]
fl = "--fsin-standalone" if insn == "sin" else "--fcos-standalone"
WVRE = re.compile(r"(mul|lf|rf|f4|left|right)=(\d+):(-?\d+):([0-9a-f]{32})")
out = open(out_path, "w")
out.write("idx\tinsn\tse\tsig\tactive\tpayload\tlow3\t"
          "lefte2\tleftsig\trighte2\trightsig\td60\n")
kept = 0
CH = 200000
for ci in range(0, len(inputs), CH):
    chunk = inputs[ci:ci + CH]
    p = subprocess.Popen([model, "--batch", fl, "--dump-internals"],
                         stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                         stderr=subprocess.PIPE, text=True, bufsize=1)
    def feed():
        for op in chunk:
            p.stdin.write(op + "\n")
        p.stdin.close()
    threading.Thread(target=feed, daemon=True).start()
    idx = -1
    cur = {}
    def flush():
        global kept
        if idx < 0:
            return
        op = chunk[idx]
        se, sig = op.split()
        if "left" not in cur or "right" not in cur:
            out.write("%d\t%s\t%s\t%s\tNOFRAME\t0\t0\t0\t0\t0\t0\t0\n"
                      % (ci + idx, insn, se, sig))
            return
        out.write("\t".join(str(x) for x in (
            ci + idx, insn, se, sig, cur.get("active", "?"),
            cur.get("payload", "0"), cur.get("low3", "?"),
            cur["left"][1], cur["left"][2],
            cur["right"][1], cur["right"][2],
            cur.get("d60", "-"))) + "\n")
        kept += 1
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
    print("frames %s %d/%d kept=%d" % (insn, min(ci + CH, len(inputs)),
                                       len(inputs), kept), file=sys.stderr)
out.close()
print("kept:", kept, "/", len(inputs), file=sys.stderr)
