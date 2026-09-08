#!/usr/bin/env python3
"""Test rail-specific affine PPro mappings against the H1561 NOP crib.

H1562 excludes one global affine permutation of the 216 connected bits, but
does not exclude a mapper built from three independently wired 72-bit uop
rails.  This audit factorizes that larger exact family.  It tests both natural
ways of splitting each conventional connected-bit traversal into three rails:

* round-robin rails selected by stream index modulo three; and
* three contiguous 72-bit rails.

Each source rail may be assigned to any logical lane and receives its own
invertible affine permutation ``logical_bit = a * source_bit + b (mod 72)``.
Because the crib is three copies of the same NOP word, the six lane assignments
are symmetric but remain included in the represented model count.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path

import h1493_ppro_serialization_isomorphisms as simple
import h1556_ppro_correct_layout_mapping_audit as corrected
import h1562_ppro_nop_algebraic_permutations as global_affine


EXPECTED_H1561_SHA256 = (
    "9a0fbf7fc0f60dda0a91d2f9df7a8384a31cb2c8106d7988dfa2938386f0fe8a"
)
EXPECTED_H1562_SHA256 = (
    "457ae8c3c2cddbbd4c53a9a6e009ebfef22f8ba8c81da14c4b2d2fa7dfa4b6c0"
)
EXPECTED_SOURCE_SHA256 = corrected.EXPECTED_SOURCE_SHA256
CONNECTED_BITS = 216
RAILS = 3
RAIL_BITS = 72
LANE_ASSIGNMENTS = math.factorial(RAILS)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rail_positions(
    one_positions: set[int], partition: str
) -> tuple[set[int], set[int], set[int]]:
    if partition == "round_robin_mod3":
        return tuple(
            {index // RAILS for index in one_positions if index % RAILS == rail}
            for rail in range(RAILS)
        )
    if partition == "contiguous_72":
        return tuple(
            {
                index - rail * RAIL_BITS
                for index in one_positions
                if rail * RAIL_BITS <= index < (rail + 1) * RAIL_BITS
            }
            for rail in range(RAILS)
        )
    raise ValueError(f"unknown rail partition {partition}")


def affine_solutions(
    source_ones: set[int], target_ones: set[int]
) -> list[dict[str, int]]:
    solutions = []
    for multiplier in range(RAIL_BITS):
        if math.gcd(multiplier, RAIL_BITS) != 1:
            continue
        multiplied = {
            (multiplier * source) % RAIL_BITS for source in source_ones
        }
        for offset in range(RAIL_BITS):
            if {
                (value + offset) % RAIL_BITS for value in multiplied
            } == target_ones:
                solutions.append(
                    {"multiplier": multiplier, "offset": offset}
                )
    return solutions


def search_representation(
    words: list[int], masks: list[int], target_ones: set[int]
) -> dict[str, object]:
    unit_count = sum(
        math.gcd(multiplier, RAIL_BITS) == 1
        for multiplier in range(RAIL_BITS)
    )
    maps_per_rail = unit_count * RAIL_BITS
    primitive_tests = 0
    represented_models = 0
    survivor_count = 0
    cases = []

    for partition in ("round_robin_mod3", "contiguous_72"):
        for reverse_dwords in (False, True):
            for transform_name, transform in simple.TRANSFORMS.items():
                coordinates = global_affine.coordinate_stream(
                    masks, reverse_dwords, transform
                )
                observed_ones = global_affine.one_positions(words, coordinates)
                rails = rail_positions(observed_ones, partition)
                solutions = []
                for rail in rails:
                    primitive_tests += maps_per_rail
                    solutions.append(affine_solutions(rail, target_ones))

                case_models = LANE_ASSIGNMENTS * maps_per_rail**RAILS
                case_survivors = LANE_ASSIGNMENTS * math.prod(
                    len(rail_solutions) for rail_solutions in solutions
                )
                represented_models += case_models
                survivor_count += case_survivors
                cases.append(
                    {
                        "partition": partition,
                        "reverse_dwords": reverse_dwords,
                        "within_dword_transform": transform_name,
                        "source_one_counts_by_rail": [len(rail) for rail in rails],
                        "affine_solution_counts_by_rail": [
                            len(rail_solutions) for rail_solutions in solutions
                        ],
                        "affine_solution_examples_by_rail": [
                            rail_solutions[:8] for rail_solutions in solutions
                        ],
                        "represented_models": case_models,
                        "survivor_count": case_survivors,
                    }
                )

    expected_cases = 2 * 2 * len(simple.TRANSFORMS)
    expected_primitives = expected_cases * RAILS * maps_per_rail
    expected_models = (
        expected_cases * LANE_ASSIGNMENTS * maps_per_rail**RAILS
    )
    if len(cases) != expected_cases:
        raise RuntimeError("rail-specific case enumeration was incomplete")
    if primitive_tests != expected_primitives:
        raise RuntimeError("rail-specific primitive enumeration was incomplete")
    if represented_models != expected_models:
        raise RuntimeError("rail-specific model count was inconsistent")
    return {
        "case_count": len(cases),
        "unit_multiplier_count": unit_count,
        "affine_maps_per_rail": maps_per_rail,
        "primitive_affine_tests": primitive_tests,
        "represented_model_count": represented_models,
        "survivor_count": survivor_count,
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--h1561", required=True, type=Path)
    parser.add_argument("--h1562", required=True, type=Path)
    parser.add_argument("--msrom2scramble-source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")
    expected = {
        arguments.h1561: EXPECTED_H1561_SHA256,
        arguments.h1562: EXPECTED_H1562_SHA256,
        arguments.msrom2scramble_source: EXPECTED_SOURCE_SHA256,
    }
    for path, expected_sha256 in expected.items():
        actual = digest(path)
        if actual != expected_sha256:
            raise RuntimeError(f"unexpected dependency hash for {path}: {actual}")

    report1561 = json.loads(arguments.h1561.read_text())
    source = arguments.msrom2scramble_source.read_text()
    mapping = corrected.recover_public_mapping(
        corrected.parse_c_array(source, "dw_masks_619", 8),
        corrected.parse_c_array(source, "dw_to_crbusrom_619", 32),
    )
    masks = {
        "correct_patch_representation": corrected.connected_masks(
            set(mapping.values()), 7
        ),
        "source_exact_619_crbus_representation": corrected.connected_masks(
            set(mapping.keys()), 7
        ),
    }
    words = {
        "correct_patch_representation": [
            int(word, 16) for word in report1561["repeated_tail"]["patch_words"]
        ],
        "source_exact_619_crbus_representation": [
            int(word, 16) for word in report1561["repeated_tail"]["crbus_words"]
        ],
    }
    nop_word = int(report1561["method"]["logical_nop_word"], 16)
    target_ones = {
        bit for bit in range(RAIL_BITS) if (nop_word >> bit) & 1
    }
    if target_ones != {23, 65, 66}:
        raise RuntimeError(f"unexpected Pentium Pro NOP one bits {target_ones}")

    searches = {
        name: search_representation(words[name], masks[name], target_ones)
        for name in words
    }
    total_primitives = sum(
        int(search["primitive_affine_tests"]) for search in searches.values()
    )
    total_models = sum(
        int(search["represented_model_count"]) for search in searches.values()
    )
    total_survivors = sum(
        int(search["survivor_count"]) for search in searches.values()
    )

    result = {
        "status": "nop_crib_rejects_rail_specific_affine_mappings",
        "question": (
            "Does the H1561 Pentium Pro NOP-tail crib admit three independently "
            "affine 72-bit rail mappings under either natural stream partition?"
        ),
        "dependencies": {
            "h1561": {"path": str(arguments.h1561), "sha256": digest(arguments.h1561)},
            "h1562": {"path": str(arguments.h1562), "sha256": digest(arguments.h1562)},
            "utools_msrom2scramble_c": {
                "url": corrected.SOURCE_URL,
                "sha256": digest(arguments.msrom2scramble_source),
            },
        },
        "method": {
            "connected_bits": CONNECTED_BITS,
            "rails": RAILS,
            "bits_per_rail": RAIL_BITS,
            "target_one_bits_per_lane": sorted(target_ones),
            "source_traversals": (
                "forward/reversed dword order crossed with identity, reverse32, "
                "byteswap32, and reverse-each-byte bit order"
            ),
            "rail_partitions": ["round_robin_mod3", "contiguous_72"],
            "per_rail_law": (
                "logical_bit = a * source_bit + b (mod 72), gcd(a,72)=1"
            ),
            "lane_assignments": LANE_ASSIGNMENTS,
            "factorization": (
                "Each rail is necessary and independent for this identical-word "
                "crib, so exhaustive per-rail solution counts exactly determine "
                "the Cartesian-product survivor count without materializing it."
            ),
            "crib_scope": report1561["method"]["crib_scope"],
            "hardware_executed": False,
            "x87_executed": False,
            "microcode_loaded": False,
            "private_ledger_accessed": False,
        },
        "searches": searches,
        "summary": {
            "primitive_affine_tests": total_primitives,
            "represented_model_count": total_models,
            "total_survivors": total_survivors,
        },
        "conclusion": {
            "rail_specific_affine_mapper_found": total_survivors != 0,
            "family_excluded_if_crib_is_correct": total_survivors == 0,
            "arbitrary_rail_or_cross_rail_permutations_not_excluded": True,
            "authoritative_ppro_logical_decoder": False,
            "selector_found": False,
            "emulator_change": False,
            "frontier_closed": False,
        },
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
