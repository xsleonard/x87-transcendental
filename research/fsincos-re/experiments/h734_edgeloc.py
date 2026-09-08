#!/usr/bin/env python3
# h734: per-edge localization for the sin-side B10 rows.  For each
# sin miss operand x each h235 edge x delta, does the perturbed
# model reproduce hardware FSIN in ALL THREE modes?  (FSIN and FCOS
# are separate executions — single-instruction consistency is the
# correct bar.)  Also dumps DI_H235 presence to confirm path.
import subprocess, re
def norm(l):
    t = l.split()
    return "C2" if t[0] == "C2" else "%s/%s" % (t[1], t[2])
miss = {}
for l in open("h728.log"):
    m = re.match(r"MISMATCH (\w+) (\w+) line (\d+)", l)
    if m: miss.setdefault(int(m.group(3)), set()).add(m.group(1))
inp = open("/root/h491/randv1_inputs.txt").read().splitlines()
sin_lns = [ln for ln in sorted(miss) if "sin" in miss[ln]]
cos_lns = [ln for ln in sorted(miss) if "cos" in miss[ln]]
for name, lns, insn, flag in (("SIN", sin_lns, "sin", "--fsin-standalone"),
                              ("COS", cos_lns, "cos", "--fcos-standalone")):
    ops = [inp[ln] for ln in lns]
    hw = {}
    for mode in ("rn","rd","ru"):
        vals = {}
        for i, l in enumerate(open(f"/root/h491/randv1_{insn}_{mode}_hw_status.txt")):
            if i in miss: vals[i] = norm(l)
        hw[mode] = vals
    # path check: which rows hit the h235 graph
    p = subprocess.run(["./model_h235","--batch",flag,"--dump-internals"],
                       input="\n".join(ops)+"\n", capture_output=True, text=True)
    h235rows = set()
    cur = -1
    for l in p.stderr.splitlines():
        if l.startswith("DI_IN"): cur += 1
        elif l.startswith("DI_H235"): h235rows.add(cur)
    TGTS = ("h235sq","h235f4","h235neg","h235pos","h235tail")
    out = {}
    for t in TGTS:
        for d in (-2,-1,1,2):
            for mode in ("rn","rd","ru"):
                args = ["./model_h235","--batch",flag,f"--perturb={t}:{d}"]
                if mode != "rn": args.append(f"--rc={mode}")
                r = subprocess.run(args, input="\n".join(ops)+"\n",
                                   capture_output=True, text=True)
                out[(t,d,mode)] = [norm(x) for x in r.stdout.splitlines()]
    print(f"== {name} rows ==")
    print("%-8s %-22s h235 | %s" % ("line","operand",
          " ".join("%-9s" % t[4:] for t in TGTS)))
    for oi, ln in enumerate(lns):
        cells = []
        for t in TGTS:
            fits = [d for d in (-2,-1,1,2)
                    if all(out[(t,d,m)][oi] == hw[m][ln]
                           for m in ("rn","rd","ru"))]
            cells.append("%-9s" % (",".join("%+d"%d for d in fits) if fits else "-"))
        print("%-8d %-22s %-4s | %s" % (ln, inp[ln],
              "Y" if oi in h235rows else "n", " ".join(cells)))
