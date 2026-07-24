#!/usr/bin/env python3
"""Large head-to-head separator for h223's two surviving carrier signals.

The refined raw-final schedule passes h223 under either ``q.bit7=1`` or
``p.guard=1``.  Their aggregate h223 scores tie while individual predictions
differ.  This pass retains only those two rules and requests 64 fresh
baseline and pairwise separators from mutations around all prior states.
"""

from __future__ import annotations

import argparse
import itertools
import pathlib

import h171_fsin_table_correction_discriminator as h171
import h188_table_stage_local_pairs as h188
import h207_tang_literal_fadd as h207
import h221_fadd_tree_discriminator as h221
import h223_fadd_tree_refined_discriminator as h223


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT / "capture-kit" / "inputs" / "constraint_table_fadd_tree_h224.txt"
)
DEFAULT_METADATA = DEFAULT_OUTPUT.with_suffix(".meta.txt")
CAPTURE_STEM = "constraint_table_fadd_tree_h224"
SEED = 0xF224C5
BASE_SEED_OPERANDS = h223.seed_operands
RULES = {
    name: h223.RULES[name] for name in ("raw_q7", "raw_p_guard")
}
PAIRS = tuple(itertools.combinations(RULES, 2))


def configure() -> None:
    h221.RULES = RULES
    h221.PAIRS = PAIRS
    h221.SEED = SEED
    h221.CAPTURE_STEM = CAPTURE_STEM
    h221.seed_operands = seed_operands


def seed_operands():
    result = set(BASE_SEED_OPERANDS())
    for path in (h221.DEFAULT_OUTPUT, h223.DEFAULT_OUTPUT):
        for index, line in enumerate(path.read_text().splitlines()):
            se, sig = (int(field, 16) for field in line.split())
            observed = h171.observed_from_input(index, se, sig)
            if observed is None:
                continue
            point = h207.Point(h188.prepare(h221.blank(observed)), True)
            if h221.any_branch_selected(point):
                result.add((se, sig))
    return tuple(sorted(result))


def score_capture(capture):
    points = h221.load_capture(DEFAULT_OUTPUT, capture)
    metadata = DEFAULT_METADATA.read_text().splitlines()
    print(f"loaded {len(points)} fresh h224 separators")
    print(f"  all baseline={h221.score(points, None)}")
    for name, branch in RULES.items():
        indices = h221.targeted(metadata, name, "rules")
        selected = [points[index] for index in indices]
        baseline = h221.score(selected, None)
        value = h221.score(selected, branch)
        status = "PASS" if h207.no_worse(value, baseline) else "FAIL"
        print(f"{status} {name:11s} n={len(indices):3d} {baseline}->{value}")
    left, right = PAIRS[0]
    name = f"{left}-{right}"
    indices = h221.targeted(metadata, name, "pairs")
    selected = [points[index] for index in indices]
    print(f"PAIR {name} n={len(indices)} baseline={h221.score(selected, None)}")
    print(f"  {left}={h221.score(selected, RULES[left])}")
    print(f"  {right}={h221.score(selected, RULES[right])}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--score", type=pathlib.Path)
    parser.add_argument("--per-rule", type=int, default=64)
    parser.add_argument("--per-pair", type=int, default=64)
    parser.add_argument("--scan-limit", type=int, default=30_000_000)
    args = parser.parse_args()
    configure()
    if args.generate:
        h221.generate(
            DEFAULT_OUTPUT,
            DEFAULT_METADATA,
            args.per_rule,
            args.per_pair,
            args.scan_limit,
        )
    if args.score is not None:
        score_capture(args.score)
    if not args.generate and args.score is None:
        parser.error("select --generate and/or --score CAPTURE_DIRECTORY")


if __name__ == "__main__":
    main()
