#!/usr/bin/env python3
"""h458: direction-1 exact synthesis over raw aligned operand bits,
with held-out validation.

Every previous basis search scored covers on the full corpus, so
memorization was only detectable by cover growth.  This pass makes the
verdict crisp: split the constrained zone rows into train/test halves
by a deterministic input hash, synthesize on train only, score on test.
A physical basis transfers; memorization collapses.

Two searches over the fire bit (303 fires / 2,447 zone rows):
  A. Espresso-style prime-cube cover over ~37 raw literals: ls low
     byte, rs low 16 bits, payload nibble, theta, dist, low3, b_model.
     (Raw aligned bits of the terminal subtract operands — the exact
     vectors a physical carry structure sees.)
  B. Parametric wide-compare predicates
         fire <=> [((rs >> u) mod 2^k) >= ((ls >> v) mod 2^k) + c]
     optionally conditioned on theta sign, swept over k/u/v/c — the
     comparison family bit-threshold trees cannot express compactly.

Run from /tmp/stageA.
"""
from collections import defaultdict
from multiprocessing import Pool

from h437_gate_extraction import (
    ROUNDING_MODES, load_labeled_rows, chop_to_67_bits, final_cosine_result)

PROBE = list(range(-8, 9))


def analyze_row(row):
    fields, hw_results = row
    payload = int(fields["payload"])
    left_e2, right_e2 = int(fields["le2"]), int(fields["re2"])
    left_sig, right_sig = int(fields["ls"], 16), int(fields["rs"], 16)
    left_sign, right_sign = int(fields["lsign"]), int(fields["rsign"])
    dist = int(fields["dist"])
    low3 = int(fields["low3"])
    if left_sign != 1 or right_sign != 0 or not payload:
        return None
    prepay = low3 + 8 - dist
    scale = min(left_e2, right_e2, left_e2 - 8)
    A = left_sig << (left_e2 - scale)
    B = right_sig << (right_e2 - scale)
    unit = left_e2 - 8 - scale

    def matches(payload_value):
        corr, corr_e = chop_to_67_bits(-(A - B + (payload_value << unit)),
                                       scale)
        return all(final_cosine_result(corr, corr_e, m) == hw_results[m]
                   for m in ROUNDING_MODES)

    allowed = [off for off in PROBE if matches(prepay + off)]
    if not allowed or len(allowed) == len(PROBE):
        return None
    lo_run = allowed[0] == PROBE[0]
    hi_run = allowed[-1] == PROBE[-1]
    if lo_run and not hi_run:
        b_hw, theta = 0, allowed[-1] + 1
    elif hi_run and not lo_run:
        b_hw, theta = 1, allowed[0]
    else:
        return None
    if not -3 <= theta <= 3:
        return None
    fire = 1 if (1 if 0 >= theta else 0) != b_hw else 0
    return (fire, theta, dist, low3, payload, left_sig, right_sig)


def literals(theta, dist, low3, payload, ls, rs):
    bits = []
    for b in range(8):
        bits.append((ls >> b) & 1)
    for b in range(16):
        bits.append((rs >> b) & 1)
    for b in range(4):
        bits.append((payload >> b) & 1)
    enc = theta + 3
    for b in range(3):
        bits.append((enc >> b) & 1)
    for b in range(2):
        bits.append(((dist - 7) >> b) & 1)
    for b in range(3):
        bits.append((low3 >> b) & 1)
    bits.append(1 if theta <= 0 else 0)      # b_model
    return tuple(bits)


def expand_cube(vec, nofire_vecs, n):
    active = set(range(n))
    for lit in sorted(active, key=lambda i: (i * 7919) % n):
        active.discard(lit)
        clean = True
        for nv in nofire_vecs:
            if all(nv[i] == vec[i] for i in active):
                clean = False
                break
        if not clean:
            active.add(lit)
    return frozenset((i, vec[i]) for i in active)


def cube_matches(cube, vec):
    return all(vec[i] == want for i, want in cube)


def search_espresso(train, test):
    n = len(train[0][1])
    fire_train = sorted({v for f, v in train if f})
    nofire_train = sorted({v for f, v in train if not f})
    overlap = set(fire_train) & set(nofire_train)
    print(f"  train: fire-vecs={len(fire_train)} "
          f"nofire-vecs={len(nofire_train)} conflicts={len(overlap)}")
    fire_train = [v for v in fire_train if v not in overlap]
    primes = {expand_cube(v, nofire_train, n) for v in fire_train}
    chosen, remaining = [], set(fire_train)
    while remaining:
        best = max(primes,
                   key=lambda c: sum(1 for v in remaining
                                     if cube_matches(c, v)))
        got = {v for v in remaining if cube_matches(best, v)}
        if not got:
            break
        chosen.append(best)
        remaining -= got
    sizes = sorted(len(c) for c in chosen)
    print(f"  cover: {len(chosen)} cubes, literal sizes {sizes[:8]}..."
          f"{sizes[-3:]}")
    # test-set transfer
    tp = fp = fn = tn = 0
    for f, v in test:
        pred = 1 if any(cube_matches(c, v) for c in chosen) else 0
        if pred and f:
            tp += 1
        elif pred:
            fp += 1
        elif f:
            fn += 1
        else:
            tn += 1
    print(f"  TEST transfer: caught {tp}/{tp + fn} fires, "
          f"false-fires {fp}/{fp + tn} nofires")


def search_compare(rows):
    best = []
    fires_total = sum(r[0] for r in rows)
    for k in (4, 8, 12, 16):
        mask = (1 << k) - 1
        for u in range(0, 9):
            for v in range(0, 9):
                for c in range(-2, 3):
                    for cond in ("all", "pos", "neg"):
                        err = 0
                        for fire, theta, dist, low3, pay, ls, rs in rows:
                            if cond == "pos" and theta <= 0:
                                pred = 0
                            elif cond == "neg" and theta > 0:
                                pred = 0
                            else:
                                pred = 1 if ((rs >> u) & mask) >= \
                                    (((ls >> v) & mask) + c) else 0
                            if pred != fire:
                                err += 1
                                if err > fires_total:
                                    break
                        best.append((err, k, u, v, c, cond))
    best.sort()
    print(f"  baseline (predict never-fire): {fires_total} errors")
    for err, k, u, v, c, cond in best[:6]:
        print(f"  err={err}: [(rs>>{u}) mod 2^{k}] >= "
              f"[(ls>>{v}) mod 2^{k}] + {c}  cond={cond}")


def main():
    rows = load_labeled_rows()
    with Pool(8) as pool:
        zone = [r for r in pool.map(analyze_row, rows, chunksize=2000)
                if r is not None]
    fires = sum(r[0] for r in zone)
    print(f"zone rows: {len(zone)}, fires: {fires}")

    data = [(r[0], literals(*r[1:])) for r in zone]
    train = [d for d, r in zip(data, zone) if (r[5] * 2654435761) % 2 == 0]
    test = [d for d, r in zip(data, zone) if (r[5] * 2654435761) % 2 == 1]
    print(f"split: train={len(train)} ({sum(f for f, _ in train)} fires), "
          f"test={len(test)} ({sum(f for f, _ in test)} fires)")

    print("\n=== A: espresso cover with held-out transfer ===")
    search_espresso(train, test)

    print("\n=== B: parametric wide-compare sweep (full set) ===")
    search_compare(zone)


if __name__ == "__main__":
    main()
