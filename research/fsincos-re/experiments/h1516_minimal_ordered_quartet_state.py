#!/usr/bin/env python3
"""Derive a word-minimal ordered-quartet state for the H1498 defect.

H1515 proves that arithmetic quartet sums, even together with each complete
unordered propagate word, do not determine pair-A/pair-B disagreement on the
normalized Booth domain.  This experiment starts after the first compressor
level and quantifies over arbitrary redundant pairs.  It retains each
quartet's arithmetic residue T=S+C and asks which groups require the ordered
first word U=S rather than the unordered propagate word P=S XOR C.  Two-copy
UNSAT proves a quotient; SAT rejects it.  It then tests each retained word for
necessity and proves a canonical decoder.

No x87 instruction or hardware capture is executed.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path

try:
    import z3
except ImportError as error:
    raise SystemExit("z3-solver 4.15.3.0 is required") from error

from h1400_p5_representation_audit import tree_variants


WIDTH = 9
GROUPS = 6
ORDER_CANDIDATES = tuple(range(GROUPS))
EXPECTED_A = "pair_02_14_35_hold2"
EXPECTED_B = "pair_03_14_25_hold2"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def csa3(a, b, c):
    return a ^ b ^ c, ((a & b) | (a & c) | (b & c)) << 1


def csa42(values, d_slot: int):
    ordered = list(values)
    distinguished = ordered.pop(d_slot)
    first_sum, first_carry = csa3(*ordered)
    return csa3(distinguished, first_sum, first_carry)


def reduce_from_level1(level1, config):
    if config.input_order != "natural" or config.d_slots != (0, 0, 0, 0):
        raise RuntimeError("surviving layout stopped using canonical lanes")
    level2 = [
        csa42(level1[left] + level1[right], config.d_slots[1])
        for left, right in config.pairing
    ]
    remaining = [index for index in range(3) if index != config.hold]
    level3 = csa42(
        level2[remaining[0]] + level2[remaining[1]], config.d_slots[2]
    )
    return csa42(level3 + level2[config.hold], config.d_slots[3])


def defect(level1, pair_a, pair_b):
    final_a = reduce_from_level1(level1, pair_a)
    final_b = reduce_from_level1(level1, pair_b)
    return z3.Extract(WIDTH - 1, WIDTH - 1,
                      final_a[0] ^ final_a[1] ^ final_b[0] ^ final_b[1])


def symbolic_pairs(prefix: str):
    return [
        (
            z3.BitVec(f"{prefix}_g{group}_s", WIDTH),
            z3.BitVec(f"{prefix}_g{group}_c", WIDTH),
        )
        for group in range(GROUPS)
    ]


def state_constraints(left, right, sums, ordered, propagated):
    constraints = [
        left[group][0] + left[group][1]
        == right[group][0] + right[group][1]
        for group in sums
    ]
    constraints.extend(
        left[group][0] == right[group][0] for group in ordered
    )
    constraints.extend(
        (left[group][0] ^ left[group][1])
        == (right[group][0] ^ right[group][1])
        for group in propagated
    )
    return constraints


def render_pairs(model, pairs):
    return [
        {
            "group": group,
            "sum_word": f"{model.eval(pair[0], model_completion=True).as_long():03x}",
            "carry_word": f"{model.eval(pair[1], model_completion=True).as_long():03x}",
            "arithmetic_residue": f"{model.eval(pair[0] + pair[1], model_completion=True).as_long():03x}",
        }
        for group, pair in enumerate(pairs)
    ]


def two_copy_query(
    name: str,
    left,
    right,
    defect_left,
    defect_right,
    sums,
    ordered,
    propagated,
    timeout_ms: int,
):
    solver = z3.SolverFor("QF_BV")
    solver.set(timeout=timeout_ms)
    solver.add(
        *state_constraints(left, right, sums, ordered, propagated),
        defect_left != defect_right,
    )
    status = solver.check()
    result = {
        "query": name,
        "status": str(status),
        "retained_arithmetic_groups": list(sums),
        "retained_ordered_groups": list(ordered),
        "retained_propagate_groups": list(propagated),
    }
    if status == z3.unknown:
        result["reason_unknown"] = solver.reason_unknown()
    elif status == z3.sat:
        model = solver.model()
        result["witness"] = {
            "left_defect": model.eval(defect_left, model_completion=True).as_long(),
            "right_defect": model.eval(defect_right, model_completion=True).as_long(),
            "left": render_pairs(model, left),
            "right": render_pairs(model, right),
        }
    return result


def canonical_pairs(level1, retained_ordered):
    result = []
    retained = set(retained_ordered)
    for group, (sum_word, carry_word) in enumerate(level1):
        total = sum_word + carry_word
        if group in retained:
            result.append((sum_word, total - sum_word))
        else:
            propagate_word = sum_word ^ carry_word
            generate_word = z3.LShR(total - propagate_word, 1)
            result.append((propagate_word | generate_word, generate_word))
    return result


def canonical_query(level1, pair_a, pair_b, ordered, timeout_ms: int):
    original = defect(level1, pair_a, pair_b)
    canonical = defect(
        canonical_pairs(level1, ordered), pair_a, pair_b
    )
    solver = z3.SolverFor("QF_BV")
    solver.set(timeout=timeout_ms)
    solver.add(original != canonical)
    status = solver.check()
    result = {
        "status": str(status),
        "retained_arithmetic_groups": list(range(GROUPS)),
        "retained_ordered_groups": list(ordered),
        "retained_propagate_groups": [
            group for group in range(GROUPS) if group not in set(ordered)
        ],
    }
    if status == z3.unknown:
        result["reason_unknown"] = solver.reason_unknown()
    elif status == z3.sat:
        model = solver.model()
        result["witness"] = {
            "original_defect": model.eval(original, model_completion=True).as_long(),
            "canonical_defect": model.eval(canonical, model_completion=True).as_long(),
            "level1": render_pairs(model, level1),
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1498", type=Path)
    parser.add_argument("h1515", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout-ms", type=int, default=10_000)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")
    if z3.get_version_string() != "4.15.3":
        raise RuntimeError(f"unexpected Z3 version {z3.get_version_string()}")

    h1498 = json.loads(arguments.h1498.read_text())
    h1515 = json.loads(arguments.h1515.read_text())
    if h1498["status"] != "EXACT_LOCAL_SWAP_ISOMORPHISM":
        raise RuntimeError("H1498 theorem changed")
    if h1515["status"] not in (
        "SOME_QUARTET_STATE_QUOTIENTS_REJECTED",
        "QUARTET_STATE_QUOTIENT_AUDIT_PARTLY_UNKNOWN",
    ):
        raise RuntimeError("H1515 quotient boundary changed")

    layouts = {name: config for name, _, config in tree_variants()}
    pair_a = layouts[EXPECTED_A]
    pair_b = layouts[EXPECTED_B]
    left = symbolic_pairs("left")
    right = symbolic_pairs("right")
    defect_left = defect(left, pair_a, pair_b)
    defect_right = defect(right, pair_a, pair_b)

    subset_queries = []
    for size in range(len(ORDER_CANDIDATES) + 1):
        for ordered in itertools.combinations(ORDER_CANDIDATES, size):
            propagated = tuple(
                group for group in range(GROUPS) if group not in ordered
            )
            subset_queries.append(two_copy_query(
                "ordered_subset_" + ("none" if not ordered else "_".join(map(str, ordered))),
                left,
                right,
                defect_left,
                defect_right,
                tuple(range(GROUPS)),
                ordered,
                propagated,
                arguments.timeout_ms,
            ))
    if any(query["status"] == "unknown" for query in subset_queries):
        raise RuntimeError("ordered-subset quotient query is UNKNOWN")
    exact_subsets = [
        tuple(query["retained_ordered_groups"])
        for query in subset_queries if query["status"] == "unsat"
    ]
    minimum_ordered_count = min(map(len, exact_subsets)) if exact_subsets else None
    minimal_exact = [
        subset for subset in exact_subsets
        if len(subset) == minimum_ordered_count
    ]
    if not minimal_exact:
        raise RuntimeError("no ordered-state quotient survived")

    arithmetic_necessity = []
    for ordered in minimal_exact:
        for omitted in range(GROUPS):
            retained_sums = tuple(
                group for group in range(GROUPS) if group != omitted
            )
            arithmetic_necessity.append(two_copy_query(
                f"omit_arithmetic_group_{omitted}_ordered_"
                + "_".join(map(str, ordered)),
                left,
                right,
                defect_left,
                defect_right,
                retained_sums,
                ordered,
                tuple(group for group in range(GROUPS) if group not in ordered),
                arguments.timeout_ms,
            ))
    if any(query["status"] == "unknown" for query in arithmetic_necessity):
        raise RuntimeError("arithmetic-necessity query is UNKNOWN")

    companion_necessity = []
    for ordered in minimal_exact:
        propagated = tuple(
            group for group in range(GROUPS) if group not in ordered
        )
        for omitted in range(GROUPS):
            companion_necessity.append(two_copy_query(
                f"omit_companion_group_{omitted}_ordered_"
                + "_".join(map(str, ordered)),
                left,
                right,
                defect_left,
                defect_right,
                tuple(range(GROUPS)),
                tuple(group for group in ordered if group != omitted),
                tuple(group for group in propagated if group != omitted),
                arguments.timeout_ms,
            ))
    if any(query["status"] == "unknown" for query in companion_necessity):
        raise RuntimeError("companion-necessity query is UNKNOWN")

    canonical_proofs = [
        {
            "ordered_groups": list(ordered),
            **canonical_query(
                symbolic_pairs("canonical_" + "_".join(map(str, ordered))),
                pair_a,
                pair_b,
                ordered,
                arguments.timeout_ms,
            ),
        }
        for ordered in minimal_exact
    ]
    if any(proof["status"] != "unsat" for proof in canonical_proofs):
        raise RuntimeError("canonical decoder proof failed")

    all_arithmetic_essential = all(
        query["status"] == "sat" for query in arithmetic_necessity
    )
    all_companions_essential = all(
        query["status"] == "sat" for query in companion_necessity
    )
    status = (
        "EXACT_WORD_MINIMAL_ORDERED_QUARTET_STATE"
        if all_arithmetic_essential and all_companions_essential else
        "EXACT_ORDERED_QUARTET_STATE_WITH_REDUNDANT_WORD"
    )
    report = {
        "experiment": "h1516_minimal_ordered_quartet_state",
        "status": status,
        "z3_version": z3.get_version_string(),
        "domain": {
            "description": "arbitrary first-level redundant quartet pairs",
            "groups": GROUPS,
            "word_width": WIDTH,
            "target_bit": WIDTH - 1,
        },
        "layouts": {"pair_a": EXPECTED_A, "pair_b": EXPECTED_B},
        "ordered_subset_queries": subset_queries,
        "minimal_exact_ordered_subsets": [list(value) for value in minimal_exact],
        "arithmetic_word_necessity": arithmetic_necessity,
        "companion_word_necessity": companion_necessity,
        "canonical_decoder_proofs": canonical_proofs,
        "representation": (
            "Retain T_g=(S_g+C_g) mod 2^9 for each named arithmetic group "
            "and one companion word per group: U_g=S_g for the minimal "
            "ordered groups, P_g=S_g XOR C_g for the others. Reconstruct "
            "C_g=T_g-U_g for ordered groups; for unordered groups derive "
            "G_g=(T_g-P_g)>>1 and use canonical (P_g OR G_g,G_g) before "
            "applying the common downstream template."
        ),
        "claim_boundary": (
            "This is a universal exact representation of the abstract "
            "pair-A/pair-B defect at one nine-column cone. It does not choose "
            "the physical Skylake orientation or validate a silicon selector."
        ),
        "hardware_execution": "none",
        "hardware_labels_opened": "none",
        "capture_manifest": "none",
        "emulator_change": "none",
        "paper_change": "none",
        "sha256": {
            "h1498": digest(arguments.h1498),
            "h1515": digest(arguments.h1515),
        },
    }
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(text)
    print(json.dumps({
        "output": str(arguments.output),
        "report_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "status": status,
        "minimal_exact_ordered_subsets": report[
            "minimal_exact_ordered_subsets"
        ],
        "all_arithmetic_words_essential": all_arithmetic_essential,
        "all_companion_words_essential": all_companions_essential,
        "ordered_subset_status_counts": {
            state: sum(query["status"] == state for query in subset_queries)
            for state in ("sat", "unsat")
        },
    }, sort_keys=True))


if __name__ == "__main__":
    main()
