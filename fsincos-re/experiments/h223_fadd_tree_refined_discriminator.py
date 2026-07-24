#!/usr/bin/env python3
"""Fresh separators for h222's h221-refined causal branches.

h222 adds one physical atom to the two h220 family-A predicates.  This pass
keeps the sole surviving normalized-final rule and five physically distinct
raw-final representatives, then reuses h221's mutation/pairwise generator on
new states.  No h221 result is used while scoring the fresh capture.
"""

from __future__ import annotations

import argparse
import itertools
import pathlib

import h171_fsin_table_correction_discriminator as h171
import h188_table_stage_local_pairs as h188
import h207_tang_literal_fadd as h207
import h213_fadd_causal_selector as h213
import h221_fadd_tree_discriminator as h221


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT / "capture-kit" / "inputs" / "constraint_table_fadd_tree_h223.txt"
)
DEFAULT_METADATA = DEFAULT_OUTPUT.with_suffix(".meta.txt")
CAPTURE_STEM = "constraint_table_fadd_tree_h223"
SEED = 0xF223C5
BASE_SEED_OPERANDS = h221.seed_operands


def extend(branch, atom):
    return h213.Rule(branch.candidate, (*branch.terms, atom))


RULES = {
    "norm_linear6z": extend(
        h221.RULES["a_norm_chop"], ("term.linear.bit6", 0)
    ),
    "raw_q7": extend(h221.RULES["a_raw_odd"], ("term.q.bit7", 1)),
    "raw_linear_guard": extend(
        h221.RULES["a_raw_odd"], ("term.linear.guard", 1)
    ),
    "raw_p_guard": extend(
        h221.RULES["a_raw_odd"], ("term.p.guard", 1)
    ),
    "raw_p3": extend(h221.RULES["a_raw_odd"], ("term.p.bit3", 1)),
    "raw_direct": extend(
        h221.RULES["a_raw_odd"], ("global.reduced", 0)
    ),
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
    for index, line in enumerate(h221.DEFAULT_OUTPUT.read_text().splitlines()):
        se, sig = (int(field, 16) for field in line.split())
        observed = h171.observed_from_input(index, se, sig)
        if observed is None:
            continue
        point = h207.Point(h188.prepare(h221.blank(observed)), True)
        if h221.any_branch_selected(point):
            result.add((se, sig))
    return tuple(sorted(result))


def score_capture(inputs, metadata_path, capture):
    points = h221.load_capture(inputs, capture)
    metadata = metadata_path.read_text().splitlines()
    print(f"loaded {len(points)} fresh h223 separators")
    print(f"  all baseline={h221.score(points, None)}")
    for name, branch in RULES.items():
        indices = h221.targeted(metadata, name, "rules")
        selected = [points[index] for index in indices]
        baseline = h221.score(selected, None)
        value = h221.score(selected, branch)
        status = "PASS" if h207.no_worse(value, baseline) else "FAIL"
        print(
            f"{status} {name:16s} n={len(indices):3d} "
            f"sine {baseline[0]}->{value[0]} "
            f"cosine {baseline[1]}->{value[1]}"
        )
    for left, right in PAIRS:
        name = f"{left}-{right}"
        indices = h221.targeted(metadata, name, "pairs")
        selected = [points[index] for index in indices]
        print(
            f"PAIR {name:35s} n={len(indices):3d} "
            f"{h221.score(selected, RULES[left])}"
            f"->{h221.score(selected, RULES[right])}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--score", type=pathlib.Path)
    parser.add_argument("--per-rule", type=int, default=16)
    parser.add_argument("--per-pair", type=int, default=12)
    parser.add_argument("--scan-limit", type=int, default=30_000_000)
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--metadata", type=pathlib.Path, default=DEFAULT_METADATA)
    args = parser.parse_args()
    configure()
    if args.generate:
        h221.generate(
            args.output,
            args.metadata,
            args.per_rule,
            args.per_pair,
            args.scan_limit,
        )
    if args.score is not None:
        score_capture(args.output, args.metadata, args.score)
    if not args.generate and args.score is None:
        parser.error("select --generate and/or --score CAPTURE_DIRECTORY")


if __name__ == "__main__":
    main()
