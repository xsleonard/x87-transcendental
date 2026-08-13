#!/usr/bin/env python3
"""h499: fine-comb transition profiles.  With 128 comb segments at
2^54 spacing: per (dist, low3, rud) stratum, fire rate per segment —
the true rate-vs-m shape at 32x the old resolution.  Then, per
segment with mixed rate: the (T4, D4) staircase position — testing
whether theta(m) moves smoothly (drift) or in steps (quantized), and
fitting theta(m) explicitly."""
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h497_transition import build

SEG0 = 12105675798371893248
STEP = 18014398509481984

def load_comb():
    rows = []
    seen = set()
    for line in open("ties_comb.txt"):
        f = line.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        rows.append(f)
    inputs = sorted(f[0] for f in rows)
    order = {m: i for i, m in enumerate(inputs)}
    st = {md: open(f"comb_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    out = []
    for f in rows:
        R = int(f[7], 16)
        ce = int(f[8])
        i = order[f[0]]
        hw = []
        bad = False
        for md in ROUNDING_MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[2], 16))
        if bad:
            continue
        clean = [final_cosine_result(-R, ce, md)
                 for md in ROUNDING_MODES]
        fired = [final_cosine_result(-(R-1), ce, md)
                 for md in ROUNDING_MODES]
        if hw == clean:
            out.append((f[0], False))
        elif hw == fired:
            out.append((f[0], True))
    return out

def main():
    rows = load_comb()
    print(f"comb labeled rows: {len(rows)}")
    with Pool(8) as pool:
        data = pool.map(build, rows, chunksize=500)
    prof = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for (s, m, fr, iv, fire), (mhex, _f) in zip(data, rows):
        seg = (m - SEG0) // STEP
        c = prof[s][seg]
        c[0] += 1
        c[1] += fire
    for s in sorted(prof):
        segs = prof[s]
        usable = {g: v for g, v in segs.items() if v[0] >= 60}
        if len(usable) < 20:
            continue
        line = []
        for g in range(128):
            if g in usable:
                n, f = usable[g]
                r = f / n
                line.append("#" if r > 0.9 else
                            "+" if r > 0.6 else
                            "o" if r > 0.4 else
                            "-" if r > 0.1 else "0")
            else:
                line.append(".")
        print(f"{str(s):12s} [{''.join(line)}]")
    # numeric profile for the widest stratum
    best = max(prof, key=lambda s: len(prof[s]))
    print(f"\nnumeric profile {best}:")
    for g in sorted(prof[best]):
        n, f = prof[best][g]
        if n >= 60:
            m_mid = (SEG0 + g * STEP) / 2**64
            print(f"  seg {g:3d} m~{m_mid:.5f} n={n:5d} "
                  f"rate={f/n:.3f}")

if __name__ == "__main__":
    main()
