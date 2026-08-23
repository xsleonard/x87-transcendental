import sys
banked_f, inputs_f, insn, mode = sys.argv[1:5]
def norm(t): return ("C2",) if t[0] == "C2" else tuple(t[1:3])
n = 0
with open(banked_f) as bk, open(inputs_f) as ins:
    for today, banked, op in zip(sys.stdin, bk, ins):
        if norm(today.split()) != norm(banked.split()):
            se, mant = op.split()
            print(f"{insn}\t{mode}\t{n}\t{se}\t{mant}\tbanked:{banked.strip()}\ttoday:{today.strip()}")
        n += 1
print(f"# {insn} {mode} compared {n}", file=sys.stderr)
