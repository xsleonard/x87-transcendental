import collections
ops = [tuple(l.split()) for l in open("ledger_ops.txt")]
keys = {}
for line in open("probe_keys.tsv"):
    insn, mode, se, mant, hse, hsig = line.split()
    keys[(insn, mode, se, mant)] = (hse, hsig)
def norm(t): return ("C2",) if t[0] == "C2" else tuple(t[1:3])
agree_i7 = agree_model = neither = 0
offkey_dev = 0
for insn in ("cos","sin"):
    for mode in ("rn","rd","ru","rz"):
        cap = open(f"vmcap_{insn}_{mode}.txt").read().splitlines()
        mo  = open(f"vmmo_{insn}_{mode}.txt").read().splitlines()
        for (se, mant), c, m in zip(ops, cap, mo):
            k = (insn, mode, se, mant)
            nc, nm = norm(c.split()), norm(m.split())
            if k in keys:
                hw = keys[k]
                tag = "VM==i7hw" if nc == hw else ("VM==model" if nc == nm else "NEITHER")
                if nc == hw: agree_i7 += 1
                elif nc == nm: agree_model += 1
                else: neither += 1; 
                print(f"KEY {insn}/{mode} {se}:{mant} i7hw={hw[1]} model={nm[1] if nm[0]!='C2' else 'C2'} vm={nc[1] if nc[0]!='C2' else 'C2'} -> {tag}")
            else:
                if nc != nm:
                    offkey_dev += 1
                    print(f"OFFKEY-DEV {insn}/{mode} {se}:{mant} model={nm} vm={nc}")
print(f"SUMMARY ledger-keys: VM==i7hw {agree_i7}, VM==model {agree_model}, neither {neither}; off-key deviations {offkey_dev}")
