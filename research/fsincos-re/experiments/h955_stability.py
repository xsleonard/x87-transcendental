#!/usr/bin/env python3
# h955: IS THE GATE LABEL A FUNCTION OF THE OPERAND?  Every
# operand-derived coordinate is exhausted (h949/h953/h954) and
# matched-coordinate collisions persist (h486 signature, 5th
# instance).  Prior question never tested: label stability across
# capture context.  Re-capture every mixed-tuple op 3x — original
# order / reversed / shuffled with 10k random padding ops
# interleaved — recompute the op-level hw label per round, compare
# across rounds and vs the banked h948 label.
import pickle, random, subprocess, sys
from collections import Counter, defaultdict

CAP = "/root/x87_capture_x86_64"
table = pickle.load(open("h949_features.pkl", "rb"))

def tup(r):
    d = r["tc_dist"]
    ls, le2, lsig = r["tc_left"]; rs, re2, rsig = r["tc_right"]
    mask = (1 << d) - 1
    rlow = rsig & mask
    grl = (rlow if rlow else (1 << d)) if ls != rs else ((1 << d) - rlow)
    g = 64 if grl > 64 else int(grl)
    return ((d, r["tc_mul"][1]), g, r["tc_payload"])

bytup = defaultdict(list)
for r in table: bytup[tup(r)].append(r)
targets = []
for k, v in bytup.items():
    if len(set(r["hwlab"] for r in v)) > 1: targets.extend(v)
print("mixed-tuple target ops:", len(targets), file=sys.stderr)
random.seed(955)
if len(targets) > 5000: targets = random.sample(targets, 5000)

MODES = ["rn", "rd", "ru", "rz"]
def run_model(model, insn, mode, ops):
    fl = "--fsin-standalone" if insn == "sin" else "--fcos-standalone"
    args = [model, "--batch", fl]
    if mode != "rn": args.insert(2, "--rc=" + mode)
    p = subprocess.run(args, input="\n".join(ops) + "\n",
                       capture_output=True, text=True)
    o = [tuple(l.split()[1:3]) for l in p.stdout.splitlines()]
    assert len(o) == len(ops)
    return o

def capture(insn, mode, ops):
    p = subprocess.run([CAP, mode, insn], input="\n".join(ops) + "\n",
                       capture_output=True, text=True)
    o = [tuple(l.split()[:3]) for l in p.stdout.splitlines()]
    assert len(o) == len(ops), (insn, mode, len(o), len(ops))
    return o

byinsn = defaultdict(list)
for r in targets: byinsn[r["insn"]].append(r["op"])

# F/D reference per (insn, mode, op)
FD = {}
for insn, ops in byinsn.items():
    for mode in MODES:
        F = run_model("./model_h946_pg0", insn, mode, ops)
        D = run_model("./model_h946_r92payoff", insn, mode, ops)
        for op, f_, d_ in zip(ops, F, D): FD[(insn, mode, op)] = (f_, d_)
print("F/D references done", file=sys.stderr)

def label_round(order_fn, padding):
    """capture all targets, return (insn,op) -> set of leg labels"""
    got = defaultdict(set)
    for insn, ops in byinsn.items():
        seq = order_fn(list(ops))
        if padding:
            pad = ["%04x %016x" % (random.randint(0x3fbe, 0x403d)
                                   | (random.getrandbits(1) << 15),
                                   random.getrandbits(64) | (1 << 63))
                   for _ in range(10000)]
            seq2 = []
            pi = 0
            for i, o in enumerate(seq):
                seq2.append(o)
                for _ in range(2):
                    if pi < len(pad): seq2.append(pad[pi]); pi += 1
            seq = seq2
        for mode in MODES:
            hw = capture(insn, mode, seq)
            for op, h in zip(seq, hw):
                k = (insn, mode, op)
                if k not in FD: continue
                if h[0] != "OK": got[(insn, op)].add("ERR"); continue
                f_, d_ = FD[k]
                hv = (h[1].lower(), h[2].lower())
                fv = tuple(x.lower() for x in f_)
                dv = tuple(x.lower() for x in d_)
                if fv == dv: continue
                got[(insn, op)].add("FIRE" if hv == fv else
                                    ("DECL" if hv == dv else "OTHER"))
    return got

rounds = {}
rounds["A_orig"] = label_round(lambda x: x, False)
print("round A done", file=sys.stderr)
rounds["B_rev"] = label_round(lambda x: x[::-1], False)
print("round B done", file=sys.stderr)
rounds["C_shuf"] = label_round(lambda x: random.sample(x, len(x)), True)
print("round C done", file=sys.stderr)

banked = {(r["insn"], r["op"]): r["hwlab"] for r in targets}
stat = Counter()
flips = []
for k, lab0 in banked.items():
    labs = {}
    okall = True
    for rn, got in rounds.items():
        s = got.get(k, set())
        if len(s) != 1: okall = False; labs[rn] = "/".join(sorted(s)) or "none"
        else: labs[rn] = next(iter(s))
    vals = set(labs.values()) | {lab0}
    if len(vals) == 1: stat["stable-all"] += 1
    else:
        stat["UNSTABLE"] += 1
        flips.append((k, lab0, labs))
print("targets:", len(banked))
for k2, v in stat.items(): print(k2, v)
print("--- first 30 unstable ---")
for k, lab0, labs in flips[:30]:
    print(k[0], k[1], "banked=" + lab0, labs)
pickle.dump((rounds, banked), open("h955_rounds.pkl", "wb"), protocol=4)
