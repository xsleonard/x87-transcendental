#!/usr/bin/env python3
# h912 four-hypothesis classifier: for every labeled operand, run
# A (chop+pay+gates), B (chop, no pay, gates off), AF (full tails +
# pay, gates off), BF (full tails, no pay, gates off) in all four
# modes plus fresh hw; report which hypotheses match hw everywhere.
import subprocess, collections
ops = collections.defaultdict(set)   # insn -> {(se,sig)}
srcof = {}
for fn in ("act_pool_hits.tsv", "act_census.tsv", "act_fresh.tsv"):
    for l in open(fn):
        t = l.rstrip("\n").split("\t")
        if len(t) < 9 or t[0] == "WEIRD":
            continue
        se, sig = t[5].split()
        ops[t[2]].add((se, sig))
        srcof.setdefault((t[2], se, sig), t[1])
MODELS = (("A", "./model_payA"), ("B", "./model_payB"),
          ("AF", "./model_payAF"), ("BF", "./model_payBF"),
          ("LF", "./model_payLF"), ("ALF", "./model_payALF"))
def n3(line):
    f = line.split()
    return " ".join(f[:3]) if f and f[0] == "OK" else (f[0] if f else "")
out = open("act_classify.tsv", "w")
out.write("insn\tse\tsig\tsrc\tsurvivors\tperm\n")
cnt = collections.Counter()
for insn, s in ops.items():
    g = sorted(s)
    inp = "".join(a + " " + b + "\n" for a, b in g)
    FL = ["--fsin-standalone"] if insn == "sin" else ["--fcos-standalone"]
    res = {}   # (name,mode) -> [out per row]
    for mode in ("rn", "rd", "ru", "rz"):
        RC = {"rn": [], "rd": ["--rc=rd"], "ru": ["--rc=ru"], "rz": ["--rc=rz"]}[mode]
        for name, path in MODELS:
            p = subprocess.run([path, "--batch"] + RC + FL, input=inp,
                               capture_output=True, text=True)
            res[(name, mode)] = [n3(x) for x in p.stdout.splitlines()]
        p = subprocess.run(["/root/x87_capture_x86_64", mode, insn], input=inp,
                           capture_output=True, text=True)
        res[("HW", mode)] = [n3(x) for x in p.stdout.splitlines()]
    for i, (se, sig) in enumerate(g):
        ok = {name: True for name, _ in MODELS}
        perm = []
        for mode in ("rn", "rd", "ru", "rz"):
            hw = res[("HW", mode)][i]
            tags = "".join(name for name, _ in MODELS
                           if res[(name, mode)][i] == hw)
            perm.append(f"{mode}:{tags if tags else 'X'}")
            for name, _ in MODELS:
                if res[(name, mode)][i] != hw:
                    ok[name] = False
        surv = ",".join(n for n in ok if ok[n]) or "NONE"
        cnt[surv] += 1
        out.write("\t".join((insn, se, sig, srcof.get((insn, se, sig), ""),
                             surv, ";".join(perm))) + "\n")
out.close()
for k, v in sorted(cnt.items(), key=lambda kv: -kv[1]):
    print(f"{v:5d}  {k}")
