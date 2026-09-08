#!/usr/bin/env python3
"""h438: express the product-increment gates as small boolean formulas.

The h437 pass proved both gates (G_R, G_L) are separable over
product-generation state but not by threshold trees.  This script
converts each product's state into individual named BIT literals — the
form every previously recovered x87 rounding rule has taken — and then
searches exhaustively for a small disjunction of conjunctions (up to
three literals each) that is true on every must-fire vector and false on
every must-not-fire vector.

Method: enumerate all conjunctions of 1..3 literals that cover at least
one fire vector while covering zero nofire vectors, then greedily cover
the fire set with as few conjunctions as possible.
"""
from collections import Counter
from itertools import combinations
from multiprocessing import Pool

# reuse the explicit loaders from h437 (same directory)
from h437_gate_extraction import (
    ROUNDING_MODES, load_labeled_rows, label_one_row)


def bit_literals(feats):
    """Product-generation state -> ordered dict of named binary literals."""
    lits = {}
    top16 = feats["disc_top16"]
    for b in range(16):
        # bit 15 is the guard (first discarded bit), 14 the next, ...
        lits[f"disc_bit{15 - b}"] = (top16 >> b) & 1
    kept = feats["kept_low8"]
    for b in range(8):
        lits[f"kept_bit{b}"] = (kept >> b) & 1
    for b in range(3):
        lits[f"multiplicand_bit{b}"] = (feats["multiplicand_low3"] >> b) & 1
        lits[f"multiplier_bit{b}"] = (feats["multiplier_low3"] >> b) & 1
    lits["above_half"] = feats["above_half"]
    lits["exactly_half"] = feats["exactly_half"]
    lits["sticky_below_guard"] = feats["sticky_below_guard"]
    lits["disc_nonzero"] = feats["disc_nonzero"]
    lits["disc_width_odd"] = feats["disc_width"] & 1
    top8 = top16 >> 8
    lits["disc_top8_eq_kept8"] = 1 if top8 == kept else 0
    lits["disc_top8_gt_kept8"] = 1 if top8 > kept else 0
    lits["disc_top8_all_ones"] = 1 if top8 == 0xFF else 0
    lits["disc_top8_zero"] = 1 if top8 == 0 else 0
    return lits


def find_cover(fire_vectors, nofire_vectors, names, max_size=3):
    """Greedy cover of fire_vectors by conjunctions clean on nofire."""
    n = len(names)
    literals = []          # (index, wanted_value)
    for i in range(n):
        literals.append((i, 1))
        literals.append((i, 0))

    def matches(vec, conj):
        return all(vec[i] == want for i, want in conj)

    clean = []
    for size in range(1, max_size + 1):
        for combo in combinations(literals, size):
            idxs = [i for i, _ in combo]
            if len(set(idxs)) != size:
                continue
            if any(matches(v, combo) for v in nofire_vectors):
                continue
            covered = [v for v in fire_vectors if matches(v, combo)]
            if covered:
                clean.append((len(covered), combo))
        if clean:
            break              # prefer the smallest conjunction size found
    rules = []
    remaining = set(fire_vectors)
    while remaining and clean:
        clean.sort(key=lambda c: -sum(1 for v in remaining if matches(v, c[1])))
        best_count, best = clean[0]
        newly = {v for v in remaining if matches(v, best)}
        if not newly:
            break
        rules.append(best)
        remaining -= newly
    return rules, remaining


def main():
    with Pool(8) as pool:
        labeled = pool.map(label_one_row, load_labeled_rows(), chunksize=2000)
    for gate_name, fi, li in (("G_R (right product)", 0, 1),
                              ("G_L (left product)", 2, 3)):
        fire, nofire = set(), set()
        names = None
        for row in labeled:
            lits = bit_literals(row[fi])
            if names is None:
                names = list(lits)
            vec = tuple(lits[k] for k in names)
            if row[li] == 1:
                fire.add(vec)
            elif row[li] == 0:
                nofire.add(vec)
        overlap = fire & nofire
        print(f"{gate_name}: fire-vecs={len(fire)} nofire-vecs={len(nofire)} "
              f"overlap={len(overlap)}")
        if overlap:
            continue
        rules, uncovered = find_cover(sorted(fire), sorted(nofire), names)
        print(f"  cover: {len(rules)} conjunction(s), "
              f"{len(uncovered)} fire vectors uncovered")
        for conj in rules:
            text = " AND ".join(
                (names[i] if want else f"NOT {names[i]}") for i, want in conj)
            print(f"    FIRE when: {text}")


if __name__ == "__main__":
    main()
