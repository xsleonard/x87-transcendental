#!/usr/bin/env python3
"""h660: theta ladder — cross-schedule differencing of the 3/4 pair-bit.

The comb7 input list was captured under BOTH schedules (cos =
comb7_*_status, sincos cos-lane = comb7_sc_*_status).  h488 showed the
tie-gate outcome flips ~independently across schedules at theta=0.
Question here: does the theta-ladder pair-bit do the same?

  - If fire_cos vs fire_sc agree ~at chance (given 3/4 rates) inside
    the fireable band -> the pair-bit is schedule-arranged state
    (h488 class): black-box value modeling cannot reach it, the
    instrument must be schedule-side.
  - If they agree ~always -> the bit is input-determined BEFORE the
    schedule: it IS a computable function of m, and the search
    continues (frame hunting justified).

Rows where the paired producer polynomially differs from standalone
(the lead-3 window) label as OTHER under the standalone R frame and
are excluded (counted).
"""
import pickle, sys
from collections import defaultdict

sys.path.insert(0, "/Users/steve/llm/x87-transcendental/fsincos-re/experiments")
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result

UNIT = 2**66

QUAD = {
    (66, 1): (2, 2, 1,  0, 4, 1, 0, lambda d: -5 * (d - 7)),
    (66, 0): (4, 1, 0,  0, 2, 1, 0, lambda d: -9 - 5 * (d - 9)),
    (67, 0): (4, 2, 1, -2, 4, 2, 1, lambda d: -5 * (d - 7)),
    (67, 1): (2, 2, 3, -3, 8, 2, 1, lambda d: -4 - 2 * (d - 7)),
}
TAPS = {
    ("dn", 1, (66, 1)): (8, 1, -1, 1, -3),
    ("dn", 1, (67, 0)): (8, 1, -1, 1, -3),
    ("dn", 1, (67, 1)): (2, 1, 0, 0, 4),
    ("dn", 2, (66, 1)): (18, 0, 0, 0, -6),
    ("dn", 2, (67, 0)): (18, 0, 0, 0, -6),
    ("up", 1, (66, 1)): (6, -1, 0, 1, -1),
    ("up", 1, (67, 0)): (6, -1, 0, 1, -1),
    ("up", 1, (67, 1)): (6, 1, 0, -2, 0),
    ("up", 2, (66, 1)): (6, 0, 0, 1, 0),
    ("up", 2, (67, 0)): (6, 0, 0, 1, 0),
    ("up", 2, (67, 1)): (12, 0, 0, 0, 0),
}


def in_region(sign, th, quad, dist, L, b1, b2, M):
    tap = TAPS.get((sign, th, quad))
    if tap is None:
        return False
    a, G1, G2, p, Q, K, par, W = QUAD[quad]
    lp = L % 2
    base = a * L + G1 * b1 + G2 * b2 + p * lp + W(dist)
    c0, cb1, cb2, clp, cd = tap
    T = c0 + cb1 * b1 + cb2 * b2 + clp * lp + cd * (dist - 7)
    if sign == "dn":
        u = K * ((base - T) // Q) + par * lp
        return M < u * UNIT
    u = K * ((base + T) // Q) + par * lp
    return M >= u * UNIT


def load_sc_labels():
    """label each comb7 input under the sincos schedule, standalone-R
    frame: 0 clean, 1 dn, 2 up, -1 OTHER/bad."""
    rows, seen = [], set()
    for lineS in open("ties_comb7.txt"):
        f = lineS.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        rows.append(f)
    inputs = sorted(f[0] for f in rows)
    order = {mm: i for i, mm in enumerate(inputs)}
    st = {md: open(f"comb7_sc_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    lab = {}
    for f in rows:
        R, ce, i = int(f[7], 16), int(f[8]), order[f[0]]
        hw, bad = [], False
        for md in ROUNDING_MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            # sincos line: OK sin_se sin_m cos_se cos_m SW sw
            hw.append(int(t[4], 16))
        if bad:
            lab[f[0]] = -1
            continue
        clean = [final_cosine_result(-R, ce, md) for md in ROUNDING_MODES]
        dn = [final_cosine_result(-(R - 1), ce, md) for md in ROUNDING_MODES]
        up = [final_cosine_result(-(R + 1), ce, md) for md in ROUNDING_MODES]
        lab[f[0]] = (0 if hw == clean else 1 if hw == dn
                     else 2 if hw == up else -1)
    return lab


def main():
    sc = load_sc_labels()
    print(f"sincos labels: {len(sc)}", flush=True)
    rows = pickle.load(open("h657m_comb7.pkl", "rb"))
    agree = defaultdict(lambda: [0, 0, 0, 0])  # key -> [nn, nf, fn, ff]
    other = tot = 0
    for mhex, theta, dist, s4, side, L, rdisc, sR, label, M, sqlow in rows:
        b1 = 1 if 3 * rdisc >= (1 << sR) else 0
        b2 = 1 if 3 * rdisc >= (1 << (sR + 1)) else 0
        sign = "dn" if theta > 0 else "up"
        if not in_region(sign, abs(theta), (s4, side), dist, L, b1, b2, M):
            continue
        tot += 1
        sl = sc.get(mhex, -1)
        if sl < 0:
            other += 1
            continue
        fire_cos = int(label == (1 if sign == "dn" else 2))
        fire_sc = int(sl == (1 if sign == "dn" else 2))
        key = (sign, abs(theta), (s4, side))
        agree[key][2 * fire_cos + fire_sc] += 1
    print(f"fireable-band comb7 rows: {tot}, OTHER/bad under sc: {other}\n")
    print(f"{'group':>22} {'n':>7} {'p_cos':>6} {'p_sc':>6} "
          f"{'agree':>6} {'exp_iid':>7} {'both':>6} {'cos>sc':>7} {'sc>cos':>7}")
    G = [0, 0, 0, 0]
    for key in sorted(agree, key=str):
        nn, nf, fn, ff = agree[key]
        n = nn + nf + fn + ff
        if n < 100:
            continue
        for i in range(4):
            G[i] += agree[key][i]
        pc = (fn + ff) / n
        ps = (nf + ff) / n
        ag = (nn + ff) / n
        exp = pc * ps + (1 - pc) * (1 - ps)
        print(f"{str(key):>22} {n:>7} {pc:>6.3f} {ps:>6.3f} "
              f"{ag:>6.3f} {exp:>7.3f} {ff:>6} {fn:>7} {nf:>7}", flush=True)
    nn, nf, fn, ff = G
    n = sum(G)
    pc = (fn + ff) / n
    ps = (nf + ff) / n
    ag = (nn + ff) / n
    exp = pc * ps + (1 - pc) * (1 - ps)
    print(f"\nPOOLED: n={n} p_cos={pc:.4f} p_sc={ps:.4f} "
          f"agree={ag:.4f} iid-expectation={exp:.4f}")
    print("agree >> exp -> input-determined (computable; keep hunting)")
    print("agree ~= exp -> schedule-arranged (h488 class; value-frame dead)")


if __name__ == "__main__":
    main()
