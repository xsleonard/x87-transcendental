#!/usr/bin/env python3
"""Test compact algebraic PPro bit permutations against the H1561 NOP crib.

H1561 excludes the simple later-P6 dword-isomorphism family if the repeated
0x619 tail is the canonical logical NOP triplet.  This audit tests two broader
closed-form representations without learning an arbitrary bit table:

* every invertible affine permutation of the 216 connected-bit stream; and
* cyclic compaction into the published later-P6 lower-72 physical-bit order.

Both are crossed with natural/reversed dword traversal and four conventional
within-dword orientations, on the exact update and exact 0x619 CRBUS forms.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import h1493_ppro_serialization_isomorphisms as simple
import h1556_ppro_correct_layout_mapping_audit as corrected


EXPECTED_H1561_SHA256 = (
    "9a0fbf7fc0f60dda0a91d2f9df7a8384a31cb2c8106d7988dfa2938386f0fe8a"
)
EXPECTED_SOURCE_SHA256 = corrected.EXPECTED_SOURCE_SHA256
CONNECTED_BITS = 216
LANES = 3
LOGICAL_BITS = 72


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def coordinate_stream(
    masks: list[int], reverse_dwords: bool, transform
) -> list[tuple[int, int]]:
    dwords = list(range(7))
    if reverse_dwords:
        dwords.reverse()
    result = []
    for dword in dwords:
        for candidate_bit in range(32):
            source_bit = transform(candidate_bit)
            if (masks[dword] >> source_bit) & 1:
                result.append((dword, source_bit))
    if len(result) != CONNECTED_BITS or len(set(result)) != CONNECTED_BITS:
        raise RuntimeError("connected coordinate traversal is not a 216-bit bijection")
    return result


def one_positions(words: list[int], coordinates: list[tuple[int, int]]) -> set[int]:
    return {
        index
        for index, (dword, bit) in enumerate(coordinates)
        if (words[dword] >> bit) & 1
    }


def logical_nop_ones(word: int) -> set[tuple[int, int]]:
    return {
        (lane, bit)
        for lane in range(LANES)
        for bit in range(LOGICAL_BITS)
        if (word >> bit) & 1
    }


def search_representation(
    words: list[int], masks: list[int], nop_word: int
) -> dict[str, object]:
    nop_coordinates = logical_nop_ones(nop_word)
    lane_major_target = {
        lane * LOGICAL_BITS + bit for lane, bit in nop_coordinates
    }
    affine_units = [
        multiplier
        for multiplier in range(CONNECTED_BITS)
        if math.gcd(multiplier, CONNECTED_BITS) == 1
    ]
    affine_tested = 0
    affine_survivors = []
    compaction_tested = 0
    compaction_survivors = []

    for reverse_dwords in (False, True):
        for transform_name, transform in simple.TRANSFORMS.items():
            coordinates = coordinate_stream(masks, reverse_dwords, transform)
            observed_ones = one_positions(words, coordinates)

            for multiplier in affine_units:
                multiplied = {
                    (multiplier * index) % CONNECTED_BITS
                    for index in observed_ones
                }
                for offset in range(CONNECTED_BITS):
                    affine_tested += 1
                    if {
                        (index + offset) % CONNECTED_BITS
                        for index in multiplied
                    } == lane_major_target:
                        affine_survivors.append(
                            {
                                "reverse_dwords": reverse_dwords,
                                "within_dword_transform": transform_name,
                                "multiplier": multiplier,
                                "offset": offset,
                            }
                        )

            for reverse_core in (True, False):
                inverse = simple.inverse_core_mapping(reverse_core)
                target_order = [
                    logical
                    for logical, _physical in sorted(
                        inverse.items(), key=lambda item: item[1]
                    )
                ]
                target_positions = {
                    index
                    for index, logical in enumerate(target_order)
                    if logical in nop_coordinates
                }
                for offset in range(CONNECTED_BITS):
                    compaction_tested += 1
                    if {
                        (index + offset) % CONNECTED_BITS
                        for index in observed_ones
                    } == target_positions:
                        compaction_survivors.append(
                            {
                                "reverse_dwords": reverse_dwords,
                                "within_dword_transform": transform_name,
                                "logical_orientation": (
                                    "published_core"
                                    if reverse_core
                                    else "core_without_reversal"
                                ),
                                "offset": offset,
                            }
                        )

    expected_affine = (
        2 * len(simple.TRANSFORMS) * len(affine_units) * CONNECTED_BITS
    )
    expected_compaction = (
        2 * len(simple.TRANSFORMS) * 2 * CONNECTED_BITS
    )
    if affine_tested != expected_affine or compaction_tested != expected_compaction:
        raise RuntimeError("algebraic permutation enumeration was incomplete")
    return {
        "affine_connected_stream": {
            "candidate_count": affine_tested,
            "unit_multiplier_count": len(affine_units),
            "survivor_count": len(affine_survivors),
            "survivor_examples": affine_survivors[:20],
        },
        "published_p6_core_compaction": {
            "candidate_count": compaction_tested,
            "survivor_count": len(compaction_survivors),
            "survivor_examples": compaction_survivors[:20],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--h1561", required=True, type=Path)
    parser.add_argument("--msrom2scramble-source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")
    if digest(arguments.h1561) != EXPECTED_H1561_SHA256:
        raise RuntimeError("unexpected H1561 report hash")
    if digest(arguments.msrom2scramble_source) != EXPECTED_SOURCE_SHA256:
        raise RuntimeError("unexpected public msrom2scramble.c hash")

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
            int(word, 16)
            for word in report1561["repeated_tail"]["patch_words"]
        ],
        "source_exact_619_crbus_representation": [
            int(word, 16)
            for word in report1561["repeated_tail"]["crbus_words"]
        ],
    }
    nop_word = int(report1561["method"]["logical_nop_word"], 16)
    searches = {
        name: search_representation(words[name], masks[name], nop_word)
        for name in words
    }
    total_tested = sum(
        family["candidate_count"]
        for representation in searches.values()
        for family in representation.values()
    )
    total_survivors = sum(
        family["survivor_count"]
        for representation in searches.values()
        for family in representation.values()
    )

    result = {
        "status": "nop_crib_rejects_compact_algebraic_permutations",
        "question": (
            "Does the H1561 PPro NOP-tail crib admit an invertible affine "
            "216-bit stream permutation or an order-preserving compaction of "
            "the published later-P6 core wiring?"
        ),
        "dependencies": {
            "h1561": {"path": str(arguments.h1561), "sha256": digest(arguments.h1561)},
            "utools_msrom2scramble_c": {
                "url": corrected.SOURCE_URL,
                "sha256": digest(arguments.msrom2scramble_source),
            },
        },
        "method": {
            "connected_bits": CONNECTED_BITS,
            "source_traversals": (
                "forward/reversed dword order crossed with identity, reverse32, "
                "byteswap32, and reverse-each-byte bit order"
            ),
            "affine_law": "logical_index = a * source_index + b (mod 216), gcd(a,216)=1",
            "compaction_law": (
                "source stream assigned in order to the 216 lower-72 logical "
                "coordinates sorted by the published later-P6 physical wiring, "
                "with every cyclic offset and both core orientations"
            ),
            "crib_scope": report1561["method"]["crib_scope"],
            "hardware_executed": False,
            "x87_executed": False,
            "microcode_loaded": False,
            "private_ledger_accessed": False,
        },
        "searches": searches,
        "summary": {
            "total_candidates": total_tested,
            "total_survivors": total_survivors,
        },
        "conclusion": {
            "compact_algebraic_mapper_found": total_survivors != 0,
            "families_excluded_if_crib_is_correct": total_survivors == 0,
            "arbitrary_or_rail_specific_permutations_not_excluded": True,
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
