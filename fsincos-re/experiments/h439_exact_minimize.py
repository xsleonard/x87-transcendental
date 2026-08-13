#!/usr/bin/env python3
"""h439: espresso-style exact-ish minimization of the product gates.

Purpose: h438's fixed-size conjunction search could not tell us whether
the gates are truly complex or just mis-expressed.  This script answers
that with the classic espresso EXPAND + IRREDUNDANT procedure:

  1. every must-fire vector starts as a full conjunction of all its
     literals (a minterm, trivially clean of nofire vectors);
  2. EXPAND: literals are dropped one at a time, keeping the cube clean
     (covering zero nofire vectors), until no more can be dropped —
     yielding a prime clean cube per fire vector;
  3. IRREDUNDANT: greedy set-cover picks the fewest prime cubes that
     still cover every fire vector.

The size and count of the final cubes is the verdict: one or two short
cubes means we have the physical rule; many long cubes means the literal
basis is still not the one the hardware uses.
"""
from multiprocessing import Pool

from h437_gate_extraction import load_labeled_rows, label_one_row
from h438_bit_cover import bit_literals


def expand_to_prime_cube(fire_vector, nofire_vectors, n_literals):
    """Drop literals from the full minterm while staying clean."""
    active = set(range(n_literals))

    def cube_is_clean():
        for vec in nofire_vectors:
            if all(vec[i] == fire_vector[i] for i in active):
                return False
        return True

    # try dropping every literal, most-recently-kept last, until stable
    changed = True
    while changed:
        changed = False
        for literal in sorted(active):
            active.remove(literal)
            if cube_is_clean():
                changed = True          # stays dropped
            else:
                active.add(literal)     # needed, put it back
    return frozenset((i, fire_vector[i]) for i in active)


def minimize_gate(gate_name, fire, nofire, names):
    print(f"{gate_name}: fire-vecs={len(fire)} nofire-vecs={len(nofire)}")
    primes = set()
    for vec in fire:
        primes.add(expand_to_prime_cube(vec, nofire, len(names)))
    print(f"  prime clean cubes: {len(primes)} "
          f"(sizes {sorted({len(p) for p in primes})})")

    def covers(cube, vec):
        return all(vec[i] == want for i, want in cube)

    chosen, remaining = [], set(fire)
    while remaining:
        best = max(primes, key=lambda c: sum(1 for v in remaining if covers(c, v)))
        gained = {v for v in remaining if covers(best, v)}
        if not gained:
            break
        chosen.append(best)
        remaining -= gained
    print(f"  irredundant cover: {len(chosen)} cubes, "
          f"{len(remaining)} fire vectors uncovered")
    for cube in sorted(chosen, key=len)[:12]:
        text = " AND ".join(
            (names[i] if want else f"NOT {names[i]}")
            for i, want in sorted(cube))
        print(f"    ({len(cube)} literals) FIRE when: {text}")


def main():
    with Pool(8) as pool:
        labeled = pool.map(label_one_row, load_labeled_rows(), chunksize=2000)
    for gate_name, fi, li in (("G_R (right product)", 0, 1),
                              ("G_L (left product)", 2, 3)):
        fire, nofire, names = set(), set(), None
        for row in labeled:
            lits = bit_literals(row[fi])
            if names is None:
                names = list(lits)
            vec = tuple(lits[k] for k in names)
            if row[li] == 1:
                fire.add(vec)
            elif row[li] == 0:
                nofire.add(vec)
        minimize_gate(gate_name, sorted(fire), sorted(nofire), names)


if __name__ == "__main__":
    main()
