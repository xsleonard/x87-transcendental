#!/usr/bin/env python3
"""Classify exact three-input NPN coverage after h1535--h1538.

This is a coverage audit, not a feature search.  It enumerates all 256
three-input truth tables, quotients them by input permutation, input
complementation, and output complementation, and identifies which canonical
classes are covered by the complete circuit-class exclusions already run.
The current named-history universe is rebuilt only to verify that constant
zero/one literals exist, allowing h1535's XOR3 census to include XOR2.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path

import h1535_complete_three_wire_xor as h1535


EXISTING_ARTIFACTS = (
    "tmp/ledger33/current/h1535_complete_three_wire_xor.json",
    "tmp/ledger33/current/h1536_complete_three_wire_majority.json",
    "tmp/ledger33/current/h1537_complete_three_wire_mux.json",
    "tmp/ledger33/current/h1538_complete_three_input_unate.json",
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def truth_bit(function: int, assignment: int) -> int:
    return (function >> assignment) & 1


def transform(
        function: int, permutation: tuple[int, int, int],
        input_complements: int, output_complement: int,
) -> int:
    result = 0
    for output_assignment in range(8):
        output_bits = [
            (output_assignment >> index) & 1 for index in range(3)
        ]
        input_bits = [0, 0, 0]
        for output_index in range(3):
            input_bits[permutation[output_index]] = (
                output_bits[output_index]
                ^ ((input_complements >> output_index) & 1)
            )
        input_assignment = (
            input_bits[0] | (input_bits[1] << 1) | (input_bits[2] << 2)
        )
        result |= (
            truth_bit(function, input_assignment) ^ output_complement
        ) << output_assignment
    return result


def orbit(function: int) -> set[int]:
    return {
        transform(function, permutation, complements, output_complement)
        for permutation in itertools.permutations(range(3))
        for complements in range(8)
        for output_complement in range(2)
    }


def canonical(function: int) -> int:
    return min(orbit(function))


def function_table(operation) -> int:
    result = 0
    for assignment in range(8):
        a = assignment & 1
        b = (assignment >> 1) & 1
        c = (assignment >> 2) & 1
        result |= (int(bool(operation(a, b, c))) & 1) << assignment
    return result


def is_unate(function: int) -> bool:
    for decreasing_mask in range(8):
        valid = True
        for variable in range(3):
            for assignment in range(8):
                if assignment & (1 << variable):
                    continue
                low = truth_bit(function, assignment)
                high = truth_bit(function, assignment | (1 << variable))
                decreasing = (decreasing_mask >> variable) & 1
                if ((not decreasing and low > high)
                        or (decreasing and low < high)):
                    valid = False
                    break
            if not valid:
                break
        if valid:
            return True
    return False


def anf(function: int) -> str:
    coefficients = [truth_bit(function, assignment) for assignment in range(8)]
    for variable in range(3):
        for mask in range(8):
            if mask & (1 << variable):
                coefficients[mask] ^= coefficients[mask ^ (1 << variable)]
    names = ("1", "a", "b", "ab", "c", "ac", "bc", "abc")
    terms = [name for name, value in zip(names, coefficients) if value]
    return " XOR ".join(terms) if terms else "0"


def class_partition() -> dict[int, set[int]]:
    classes: dict[int, set[int]] = {}
    for function in range(256):
        classes.setdefault(canonical(function), set()).add(function)
    if len(classes) != 14:
        raise RuntimeError(f"expected 14 NPN classes, got {len(classes)}")
    if sum(map(len, classes.values())) != 256:
        raise RuntimeError("NPN partition lost truth tables")
    if set().union(*classes.values()) != set(range(256)):
        raise RuntimeError("NPN partition is not exhaustive")
    return classes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("positive_allmode", type=Path)
    parser.add_argument("control_allmode", type=Path)
    parser.add_argument("project_root", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit("refusing to overwrite " + str(args.report))

    classes = class_partition()
    templates = {
        "xor2": function_table(lambda a, b, c: b ^ c),
        "parity3": function_table(lambda a, b, c: a ^ b ^ c),
        "mux": function_table(lambda a, b, c: c if a else b),
        "gated_xor": function_table(lambda a, b, c: a & (b ^ c)),
        "exactly_one": function_table(lambda a, b, c: a + b + c == 1),
        "all_equal": function_table(lambda a, b, c: a == b == c),
        "xor_or": function_table(lambda a, b, c: a ^ (b | c)),
        "xor_or_mux": function_table(
            lambda a, b, c: (b | c) if a else (b ^ c)
        ),
    }
    template_classes = {
        name: canonical(function) for name, function in templates.items()
    }
    expected_template_classes = {
        "xor2": 0x3c,
        "parity3": 0x69,
        "mux": 0x1b,
        "gated_xor": 0x06,
        "exactly_one": 0x16,
        "all_equal": 0x18,
        "xor_or": 0x1e,
        "xor_or_mux": 0x19,
    }
    if template_classes != expected_template_classes:
        raise RuntimeError("template NPN classification changed")

    (source_rows, patterns, _, _, _, named_feature_count, constrained_rows,
     h1401_feature_count, h1401_pattern_count) = h1535.build_wall(
         args.features, args.positive_allmode, args.control_allmode, args.jobs)
    all_mask = (1 << constrained_rows) - 1
    constant_zero_present = 0 in patterns
    constant_one_present = all_mask in patterns
    if not constant_zero_present or not constant_one_present:
        raise RuntimeError("expanded literal universe lacks constants")

    unate_classes = {
        representative for representative, members in classes.items()
        if any(is_unate(function) for function in members)
    }
    expected_unate = {0x00, 0x01, 0x03, 0x07, 0x0f, 0x17}
    if unate_classes != expected_unate:
        raise RuntimeError("unexpected three-input unate NPN classes")
    covered_sources = {
        0x00: "constant targets excluded; H1538 repeated-input basis",
        0x01: "H1538 repeated-input basis",
        0x03: "H1538 repeated-input basis",
        0x07: "H1538 AND3/OR3/AO21/OA21",
        0x0f: "H1538 repeated-input basis",
        0x17: "H1536 majority plus H1538 dual unate basis",
        0x1b: "H1537 mux",
        0x3c: "H1535 XOR3 with verified constant-zero literal",
        0x69: "H1535 parity",
    }
    covered_classes = set(covered_sources)
    remaining_templates = {
        0x06: "gated_xor: a AND (b XOR c)",
        0x16: "exactly_one: popcount(a,b,c) == 1",
        0x18: "all_equal: a == b == c (opposite-minterm pair)",
        0x19: "xor_or_mux: a ? (b OR c) : (b XOR c)",
        0x1e: "xor_or: a XOR (b OR c)",
    }
    remaining_classes = set(classes) - covered_classes
    if remaining_classes != set(remaining_templates):
        raise RuntimeError("three-input coverage gap classification changed")

    class_rows = []
    for representative, members in sorted(classes.items()):
        class_rows.append({
            "representative_hex": f"{representative:02x}",
            "orbit_size": len(members),
            "representative_ones": representative.bit_count(),
            "representative_anf": anf(representative),
            "contains_unate_function": representative in unate_classes,
            "status": "covered" if representative in covered_classes
                      else "remaining",
            "source_or_template": (
                covered_sources.get(representative)
                or remaining_templates[representative]
            ),
        })

    artifact_hashes = {
        relative: digest(args.project_root / relative)
        for relative in EXISTING_ARTIFACTS
    }
    report = {
        "schema": "fsincos-h1539-three-input-npn-coverage-v1",
        "code": {"script_sha256": digest(Path(__file__))},
        "inputs": {
            "features_sha256": digest(args.features),
            "positive_allmode_sha256": digest(args.positive_allmode),
            "control_allmode_sha256": digest(args.control_allmode),
            "existing_artifact_sha256": artifact_hashes,
        },
        "wall": {
            "source_rows": len(source_rows),
            "constrained_rows": constrained_rows,
            "named_features": named_feature_count,
            "literal_patterns": len(patterns),
            "constant_zero_present": constant_zero_present,
            "constant_one_present": constant_one_present,
            "h1401_named_features": h1401_feature_count,
            "h1401_literal_patterns": h1401_pattern_count,
        },
        "classification": {
            "truth_tables": 256,
            "npn_classes": len(classes),
            "covered_classes": len(covered_classes),
            "covered_truth_tables": sum(
                len(classes[representative])
                for representative in covered_classes
            ),
            "remaining_classes": len(remaining_classes),
            "remaining_truth_tables": sum(
                len(classes[representative])
                for representative in remaining_classes
            ),
            "classes": class_rows,
        },
        "conclusion": (
            "h1535-h1538_cover_9_of_14_npn_classes_136_of_256_truth_tables;"
            "five_binate_classes_remain_unsearched"
        ),
        "hardware_policy": "no_x87_execution",
        "promotion": "none_coverage_audit_only",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        "wrote", args.report,
        "classes", len(classes),
        "covered", len(covered_classes),
        "remaining", len(remaining_classes),
        "truth_tables", report["classification"]["covered_truth_tables"],
        "+", report["classification"]["remaining_truth_tables"],
        flush=True,
    )


if __name__ == "__main__":
    main()
