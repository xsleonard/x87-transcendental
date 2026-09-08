#!/usr/bin/env python3
"""h484: exact predicate synthesis (CEGIS-style) over the causal set.

Data: all 1,310 labeled constructed tie outcomes.  Quantities per row
(exact, width-normalized): windows of t4 (fourth power tail), rdisc
(right product discard), P = t4*rf windows, ldisc (inert control),
rf/rs/ls low bits, plus cell scalars.

Template families enumerated exhaustively:
  T1  u >= v + c                 (u, v windowed quantities, c in -2..2)
  T2  u + v >= 2^w + c           (aligned sums vs window boundary)
  T3  u top bit set / u == all-ones
Stages: global exact fit; per-cell exact fit (params may vary by
cell).  Any survivor must be validated on a FRESH constructed and
captured batch before belief.  Run from /tmp/stageA.
"""
import json
from collections import defaultdict
from multiprocessing import Pool

from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)

MODES = ("rn", "rd", "ru")
E2M = -66
JS = (2, 3, 4, 6, 8, 10, 12)


def sig(line):
    t = line.split()
    return f"{int(t[2],16):016x}" if t[0] == "OK" else "BAD"


def load_labels():
    rows = {}
    d479 = json.load(open("h479_locked.json"))
    order = []
    for p in d479["pairs"]:
        order += [p["g0"], p["g1"]]
    order += d479["controls"]
    st = {m: open(f"h479_cos_{m}_status.txt").read().splitlines()
          for m in MODES}
    for i, e in enumerate(order):
        hw = [sig(st[m][i]) for m in MODES]
        rows[e["m"]] = 1 if hw == e["fired"] else \
            (0 if hw == e["clean"] else 2)
    for line in open("h480_outcomes.tsv").read().splitlines()[1:]:
        f = line.split("\t")
        rows[f[0]] = {"CLEAN": 0, "FIRE": 1}.get(f[6], 2)
    d482 = json.load(open("h482_locked.json"))
    st = {m: open(f"cos_{m}_status.txt").read().splitlines()
          for m in MODES}
    for i, e in enumerate(d482["inputs"]):
        hw = [sig(st[m][i]) for m in MODES]
        rows[e["m"]] = 1 if hw == e["fired"] else \
            (0 if hw == e["clean"] else 2)
    return rows


def quantities(mhex):
    m = int(mhex, 16)
    mag = (0, E2M, m)
    square = mul_round(mag, mag, 67, "chop")
    fourth = mul_round(square, square, 67, "chop")
    negative = build_chain(fourth, C6_5, C6_3, C6_1, 67, 64, "rn",
                           False, False, False)
    positive = build_chain(fourth, C6_6, C6_4, C6_2, 67, 64, "rn",
                           False, False, False)
    left = mul_round(square, negative, 67, "chop")
    right = mul_round(fourth, positive, 67, "chop")
    f4_full = square[2] * square[2]
    s4 = f4_full.bit_length() - 67
    t4 = f4_full & ((1 << s4) - 1)
    rprod = fourth[2] * positive[2]
    sR = rprod.bit_length() - 67
    rdisc = rprod & ((1 << sR) - 1)
    lprod = square[2] * negative[2]
    sL = lprod.bit_length() - 67
    ldisc = lprod & ((1 << sL) - 1)
    low3 = square[2] & 7
    dist = abs(left[1] - right[1])
    payload = low3 + 8 - dist
    scale = min(left[1], right[1])
    if payload and left[1] - 8 < scale:
        scale = left[1] - 8
    M = (left[2] << (left[1] - scale)) \
        + (payload << (left[1] - 8 - scale)) \
        - (right[2] << (right[1] - scale))
    k = M.bit_length() - 67
    P = t4 * positive[2]
    q = {}
    for j in JS:
        q[f"T{j}"] = t4 >> (s4 - j) if s4 >= j else t4 << (j - s4)
        q[f"D{j}"] = rdisc >> (sR - j)
        q[f"P{j}"] = P >> (s4 + 64 - j)
        q[f"L{j}"] = ldisc >> (sL - j)
    for j in (2, 4, 6, 8):
        q[f"Flo{j}"] = positive[2] & ((1 << j) - 1)
        q[f"RSlo{j}"] = right[2] & ((1 << j) - 1)
        q[f"LSlo{j}"] = left[2] & ((1 << j) - 1)
    cell = (dist, low3, k, rdisc >> (sR - 1))
    return cell, payload, q


def build_row(item):
    mhex, o = item
    if o == 2:
        return None
    cell, payload, q = quantities(mhex)
    return (o, cell, payload, q)


def make_preds(QN):
    T_names = [n for n in QN if n[0] in ("T", "P")]
    D_names = [n for n in QN if n[0] == "D"]
    preds = []
    for u in QN:
        for v in QN:
            if u >= v:
                continue
            for c in (-2, -1, 0, 1, 2):
                preds.append(("T1", u, v, c))
    for u in T_names:
        for v in D_names:
            for w in JS:
                for c in (-1, 0, 1):
                    preds.append(("T2", u, v, (w, c)))
    for u in QN:
        for j in (2, 3, 4, 6, 8):
            preds.append(("T3top", u, j, None))
            preds.append(("T3ones", u, j, None))
    return preds


def eval_pred(p, q):
    kind, u, v, c = p
    if kind == "T1":
        return 1 if q[u] >= q[v] + c else 0
    if kind == "T2":
        w, cc = c
        return 1 if q[u] + q[v] >= (1 << w) + cc else 0
    if kind == "T3top":
        return 1 if q[u] >> (v - 1) else 0
    return 1 if q[u] == (1 << v) - 1 else 0


DATA = None
PREDS = None


def init_worker(data, preds):
    global DATA, PREDS
    DATA, PREDS = data, preds


def score_chunk(idxs):
    out = []
    for pi in idxs:
        p = PREDS[pi]
        exc = 0
        for o, cell, payload, q in DATA:
            if eval_pred(p, q) != o:
                exc += 1
                if exc > 150:
                    break
        out.append((exc, pi))
    return out


def main():
    rows = load_labels()
    with Pool(8) as pool:
        data = [r for r in pool.map(build_row, sorted(rows.items()),
                                    chunksize=50) if r]
    print(f"rows: {len(data)}, fires: {sum(d[0] for d in data)}")
    QN = sorted(data[0][3])
    preds = make_preds(QN)
    print(f"predicates: {len(preds)}")

    idx_chunks = [list(range(i, len(preds), 8)) for i in range(8)]
    with Pool(8, initializer=init_worker,
              initargs=(data, preds)) as pool:
        res = [x for ch in pool.map(score_chunk, idx_chunks)
               for x in ch]
    res.sort(key=lambda x: x[0])
    print("\n=== global best 12 ===")
    for exc, pi in res[:12]:
        print(f"  exceptions={exc:4d}  {preds[pi]}")

    cells = defaultdict(list)
    for o, cell, payload, q in data:
        cells[cell].append((o, q))
    print(f"\n=== per-cell exact solvability (n>=8, mixed) ===")
    solved = unsolved = 0
    for cell in sorted(cells):
        rs_ = cells[cell]
        if len(rs_) < 8:
            continue
        n1 = sum(o for o, _ in rs_)
        if n1 == 0 or n1 == len(rs_):
            continue
        found = None
        for p in preds:
            ok = True
            for o, q in rs_:
                if eval_pred(p, q) != o:
                    ok = False
                    break
            if ok:
                found = p
                break
        if found:
            solved += 1
            print(f"  {cell} n={len(rs_)} fires={n1}: EXACT {found}")
        else:
            unsolved += 1
            print(f"  {cell} n={len(rs_)} fires={n1}: no exact "
                  f"predicate")
    print(f"\nsolved cells: {solved}, unsolved: {unsolved}")


if __name__ == "__main__":
    main()
