#!/usr/bin/env python3
"""Audit h206 arithmetic and h207 operation-path coverage.

The exact reference uses operands whose G/R/S positions are zero, so every
input bit has an ordinary numerical interpretation.  In that case the
physically complete borrow-sticky path must equal exact addition followed by
a sticky 67-bit carrier.  Separate topology census proves which FADD paths
the measured Tang reconstruction actually exercises.
"""

from __future__ import annotations

import random

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h200_p5_fadd_bitvector as h200
import h206_p5_fadd_complete as h206
import h207_tang_literal_fadd as h207


SEED = 0xF206
REFERENCE_CASES = 50_000


def reference_audit():
    rng = random.Random(SEED)
    counts = {}
    for index in range(REFERENCE_CASES):
        def operand():
            # Bits 2:0 are zero: no summarized sticky ambiguity enters the
            # exact numerical reference.
            return h200.Bus(
                rng.randrange(2),
                rng.randrange(-30, 31),
                ((1 << 63) | rng.getrandbits(63)) << 3,
            )

        left, right = operand(), operand()
        exact = h58.add_exact(left.value(), right.value())
        expected = (
            h200.normalized_bus(
                h110.quantize(exact, h110.Quant(67, "odd"))
            )
            if exact[1]
            else h200.Bus(0, 0, 0)
        )
        actual, trace = h206.fadd(
            left, right, "borrow-sticky", normalize=True
        )
        counts[trace.operation] = counts.get(trace.operation, 0) + 1
        if actual != expected:
            raise SystemExit(
                f"h210 reference mismatch at {index}: "
                f"{left=} {right=} {trace=} {actual=} {expected=}"
            )
    required = {"add", "far-sub", "near-sub"}
    if not required.issubset(counts):
        raise SystemExit(f"h210 missing reference paths: {counts}")
    return counts


def topology_census():
    points = h207.sample(h207.joint_partitions("sweep"))[0][1]
    products = h207.ProductRoute()
    result = {}
    for topology in h207.TOPOLOGIES:
        candidate = h207.Candidate(
            topology,
            "borrow-sticky",
            "retain",
            "retain",
            True,
            products,
        )
        counts = h207.trace_census(points, candidate)
        paths = collections_by_path(counts)
        if "add" not in paths or "far-sub" not in paths:
            raise SystemExit(
                f"h210 topology lacks exercised path: {topology} {paths}"
            )
        result[topology] = paths
    return result


def collections_by_path(counts):
    result = {}
    for path in {name for name, _ in counts}:
        differences = [
            difference
            for name, difference in counts
            if name == path
        ]
        result[path] = (
            sum(
                count
                for (name, _), count in counts.items()
                if name == path
            ),
            min(differences),
            max(differences),
        )
    return result


def main() -> None:
    print(f"h210 exact reference PASS {reference_audit()}")
    for topology, paths in topology_census().items():
        print(f"  {topology:16s} {paths}")


if __name__ == "__main__":
    main()
