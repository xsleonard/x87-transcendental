#!/usr/bin/env python3
"""Test the H1556/H1557 simple mapper family against a PPro NOP-tail crib.

The exact 0x619 body ends in fifteen copies of one nine-bit group.  A public
Pentium Pro assembly source in utools fills unused MSRAM with triplets of
``MOVE.DSZ32(CONST, CONST_0)``.  The documented 72-bit logical format assigns
exactly nine one-bits to three such SINK-destination uops.  This audit asks
whether any of the 322,560 simple later-P6 isomorphisms can map the observed
nine-bit repeated group to that exact logical triplet.

The identification of the historical Intel patch's repeated group as NOP
padding is a physically grounded crib, not a source-proven logical/physical
pair.  Therefore even a survivor would remain diagnostic; a failure excludes
only the bounded simple-isomorphism family under this explicit crib.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
from collections import Counter
from pathlib import Path

import numpy as np

import h1493_ppro_serialization_isomorphisms as simple
import h1556_ppro_correct_layout_mapping_audit as corrected
import h1557_ppro_near_decoder as near


EXPECTED_H1555_SHA256 = (
    "cfa72d316ffb6efd58770b820d79b9568fc459d26691f09d6f9842da952d6280"
)
EXPECTED_H1556_SHA256 = (
    "65fbbf326f7a11f4b748b97b05b137091ab64a12beb2fe5514b2cdb35d912cdc"
)
EXPECTED_H1557_SHA256 = (
    "5c1242f83e98f841d7544bf1a76bd31ceb7c91efbfba535ff6b4bf24b7b23f8a"
)
EXPECTED_UTOOLS_COMMIT = "ab6aa24ed91de1c048313c10cb7546ea3397b827"
EXPECTED_ASM_SHA256 = (
    "314563685370c287a5710405c40173e6a0fea9c84d1405116c1426ebc5df9823"
)
EXPECTED_MAKEFILE_SHA256 = (
    "03a3a460127bbf4cf3c46dc3e26918bad3df72a5d6f63dcca36c24772883dc28"
)
UOPS_PER_GROUP = 3


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def nop_word() -> int:
    # Public P6 logical format: opcode bits 56..67, destination bits 23..30.
    # MOVE is 0x400, DSZ32 contributes 0x200, and omitted destination is SINK=1.
    return (0x600 << 56) | (1 << 23)


def ones_by_word(words: list[int], transform) -> list[frozenset[int]]:
    result = []
    for word in words:
        result.append(
            frozenset(
                candidate_bit
                for candidate_bit in range(32)
                if (word >> transform(candidate_bit)) & 1
            )
        )
    return result


def exact_crib_survivors(
    words8: list[int],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    target = nop_word()
    target_one_coordinates = {
        (lane, bit)
        for lane in range(UOPS_PER_GROUP)
        for bit in range(72)
        if (target >> bit) & 1
    }
    survivors: list[dict[str, object]] = []
    tested = 0
    for reverse_core in (True, False):
        inverse = simple.inverse_core_mapping(reverse_core)
        required = [set() for _ in range(8)]
        for logical_coordinate in target_one_coordinates:
            dword, bit = inverse[logical_coordinate]
            required[dword].add(bit)
        required_frozen = [frozenset(bits) for bits in required]
        for transform_name, transform in simple.TRANSFORMS.items():
            observed = ones_by_word(words8, transform)
            for permutation in itertools.permutations(range(8)):
                tested += 1
                if all(
                    observed[permutation[candidate_dword]]
                    == required_frozen[candidate_dword]
                    for candidate_dword in range(8)
                ):
                    configuration = simple.configuration(
                        reverse_core, transform_name, permutation
                    )
                    decoded = near.decode_rows(
                        np.asarray([words8], dtype=np.uint32), configuration
                    )
                    raw = [row["raw72"] for row in decoded]
                    expected = f"{target:018X}"
                    if raw != [expected] * UOPS_PER_GROUP:
                        raise RuntimeError("set filter admitted a non-exact NOP triplet")
                    survivors.append(configuration)
    expected_tested = 2 * len(simple.TRANSFORMS) * 40320
    if tested != expected_tested:
        raise RuntimeError(f"tested {tested} candidates, expected {expected_tested}")
    return (
        {
            "candidate_count": tested,
            "survivor_count": len(survivors),
            "survivor_examples": survivors[:20],
        },
        survivors,
    )


def score_survivors(
    rows8: np.ndarray, configurations: list[dict[str, object]]
) -> dict[str, object]:
    best_key: tuple[int, int, int, int] | None = None
    best_count = 0
    examples = []
    for configuration in configurations:
        decoded = near.decode_rows(rows8, configuration)
        metrics = {
            "recognized_opcodes": sum(bool(row["recognized"]) for row in decoded),
            "flow_zero": sum(int(row["flow"]) == 0 for row in decoded),
            "u1_zero": sum(int(row["unknown1"]) == 0 for row in decoded),
            "u2_zero": sum(int(row["unknown2"]) == 0 for row in decoded),
        }
        key = tuple(metrics[name] for name in (
            "recognized_opcodes", "flow_zero", "u1_zero", "u2_zero"
        ))
        if best_key is None or key > best_key:
            best_key = key
            best_count = 1
            examples = [{"configuration": configuration, "metrics": metrics}]
        elif key == best_key:
            best_count += 1
            if len(examples) < 20:
                examples.append({"configuration": configuration, "metrics": metrics})
    return {
        "candidate_count": len(configurations),
        "best_key": list(best_key) if best_key is not None else None,
        "candidate_count_at_best_key": best_count,
        "best_examples": examples,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--h1555", required=True, type=Path)
    parser.add_argument("--h1556", required=True, type=Path)
    parser.add_argument("--h1557", required=True, type=Path)
    parser.add_argument("--utools-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")
    expected_reports = {
        arguments.h1555: EXPECTED_H1555_SHA256,
        arguments.h1556: EXPECTED_H1556_SHA256,
        arguments.h1557: EXPECTED_H1557_SHA256,
    }
    for path, expected in expected_reports.items():
        actual = digest(path)
        if actual != expected:
            raise RuntimeError(f"unexpected dependency hash for {path}: {actual}")
    asm_path = arguments.utools_dir / "patches/msromdumper.asm"
    makefile_path = arguments.utools_dir / "Makefile"
    if digest(asm_path) != EXPECTED_ASM_SHA256:
        raise RuntimeError("unexpected public msromdumper.asm hash")
    if digest(makefile_path) != EXPECTED_MAKEFILE_SHA256:
        raise RuntimeError("unexpected public utools Makefile hash")

    asm_text = asm_path.read_text()
    makefile_text = makefile_path.read_text()
    asm_lines = asm_text.splitlines()
    last_jump = max(
        index for index, line in enumerate(asm_lines) if "U_JMP.NT" in line
    )
    trailing_source = [
        line.strip()
        for line in asm_lines[last_jump + 1 :]
        if line.strip() and not line.lstrip().startswith(";")
    ]
    if not trailing_source or not all(
        re.match(r"^MOVE\.DSZ32\s*\(CONST\s*,\s*CONST_0", line)
        for line in trailing_source
    ):
        raise RuntimeError("public PPro source tail is not all MOVE.DSZ32 padding")
    if len(trailing_source) != 36:
        raise RuntimeError(
            f"expected 36 public source padding uops, got {len(trailing_source)}"
        )
    makefile_has_ppro_rule = all(
        needle in makefile_text
        for needle in (
            "PPRO_DCPUID = 612 619",
            "$(PPRO_DATS) : EXTRA_OPTS = -t pentiumpro",
            "patches/619/msromdumper-619.uhex: patches/msromdumper.asm",
        )
    )
    if not makefile_has_ppro_rule:
        raise RuntimeError("pinned Makefile lacks the expected Pentium Pro build rule")

    report1555 = json.loads(arguments.h1555.read_text())
    report1557 = json.loads(arguments.h1557.read_text())
    patch619 = corrected.load_patch_rows(report1555, ("619",))
    source = (arguments.utools_dir / "msrom2scramble.c").read_text()
    mapping = corrected.recover_public_mapping(
        corrected.parse_c_array(source, "dw_masks_619", 8),
        corrected.parse_c_array(source, "dw_to_crbusrom_619", 32),
    )
    rom619_7 = np.asarray(
        [
            corrected.transform_words([int(word) for word in row], mapping, True)
            for row in patch619
        ],
        dtype=np.uint32,
    )

    frequencies = Counter(tuple(int(word) for word in row) for row in patch619)
    repeated_tuple, multiplicity = frequencies.most_common(1)[0]
    if multiplicity != 15:
        raise RuntimeError(f"expected 15 repeated 0x619 groups, got {multiplicity}")
    repeated_patch = list(repeated_tuple) + [0]
    repeated_index = next(
        index
        for index, row in enumerate(patch619)
        if tuple(int(word) for word in row) == repeated_tuple
    )
    repeated_rom = [int(word) for word in rom619_7[repeated_index]] + [0]
    expected_nop = nop_word()
    expected_triplet_one_bits = UOPS_PER_GROUP * expected_nop.bit_count()
    observed_one_bits = sum(word.bit_count() for word in repeated_patch)
    if observed_one_bits != expected_triplet_one_bits:
        raise RuntimeError("repeated group and logical NOP triplet bit counts diverged")

    patch_search, _patch_survivors = exact_crib_survivors(repeated_patch)
    rom_search, rom_survivors = exact_crib_survivors(repeated_rom)
    searches = {
        "correct_patch_representation": patch_search,
        "source_exact_619_crbus_representation": rom_search,
    }

    # The H1557 canonical configuration is checked explicitly because its
    # aggregate metrics were the strongest previous statistical signal.
    canonical = report1557["canonical_best"]["configuration"]
    canonical_tail = near.decode_rows(
        np.asarray([repeated_rom], dtype=np.uint32), canonical
    )

    # If a bounded-family survivor exists, score it on the six nonrepeated
    # source-exact 0x619 groups.  This never promotes recognition to an oracle.
    rom_frequencies = Counter(tuple(int(word) for word in row) for row in rom619_7)
    active_rom = rom619_7[
        np.asarray(
            [
                rom_frequencies[tuple(int(word) for word in row)] == 1
                for row in rom619_7
            ]
        )
    ]
    active_rom8 = np.column_stack(
        (active_rom, np.zeros(active_rom.shape[0], dtype=np.uint32))
    )
    active_scores = score_survivors(active_rom8, rom_survivors)

    result = {
        "status": "nop_crib_rejects_simple_mapper_family",
        "question": (
            "Can any H1556/H1557 simple later-P6 isomorphism map the exact "
            "nine-bit repeated 0x619 tail group to the public PPro logical "
            "MOVE.DSZ32 padding triplet?"
        ),
        "dependencies": {
            "h1555": {"path": str(arguments.h1555), "sha256": digest(arguments.h1555)},
            "h1556": {"path": str(arguments.h1556), "sha256": digest(arguments.h1556)},
            "h1557": {"path": str(arguments.h1557), "sha256": digest(arguments.h1557)},
            "utools": {
                "url": f"https://github.com/ruikruik/utools/tree/{EXPECTED_UTOOLS_COMMIT}",
                "commit": EXPECTED_UTOOLS_COMMIT,
                "msromdumper_asm_sha256": digest(asm_path),
                "makefile_sha256": digest(makefile_path),
                "msrom2scramble_c_sha256": digest(arguments.utools_dir / "msrom2scramble.c"),
            },
        },
        "method": {
            "simple_family_per_representation": 322560,
            "representations": [
                "correct seven-dword update body",
                "source-exact CPUID-0x619 CRBUS body",
            ],
            "logical_nop_word": f"{expected_nop:018X}",
            "logical_nop_one_bits_per_uop": expected_nop.bit_count(),
            "crib_scope": (
                "The public source proves how a PPro assembler spells logical "
                "padding, but the historical Intel tail's NOP identity remains "
                "a structural inference because the generated custom .hex is absent."
            ),
            "hardware_executed": False,
            "x87_executed": False,
            "microcode_loaded": False,
            "private_ledger_accessed": False,
        },
        "public_source_crib": {
            "trailing_move_dsz32_padding_uops": len(trailing_source),
            "tail_is_only_move_dsz32_const_const0": True,
            "makefile_has_cpuid_619_pentiumpro_build_rule": makefile_has_ppro_rule,
            "generated_uhex_or_hex_available": False,
        },
        "repeated_tail": {
            "multiplicity": multiplicity,
            "groups_total": len(patch619),
            "first_group_index": repeated_index,
            "patch_words": [f"{word:08X}" for word in repeated_patch[:7]],
            "crbus_words": [f"{word:08X}" for word in repeated_rom[:7]],
            "observed_one_bits": observed_one_bits,
            "expected_three_nop_one_bits": expected_triplet_one_bits,
        },
        "canonical_h1557_tail": {
            "configuration": canonical,
            "raw72": [row["raw72"] for row in canonical_tail],
            "opcodes": [row["opcode"] for row in canonical_tail],
            "opcode_names": [row["opcode_name"] for row in canonical_tail],
            "equals_exact_nop_triplet": all(
                row["raw72"] == f"{expected_nop:018X}" for row in canonical_tail
            ),
        },
        "searches": searches,
        "active_619_survivor_scores": active_scores,
        "conclusion": {
            "bitcount_consistent_with_three_logical_nops": True,
            "h1557_canonical_satisfies_nop_crib": False,
            "simple_family_nop_crib_survivors": {
                name: int(search["survivor_count"])
                for name, search in searches.items()
            },
            "simple_family_excluded_if_crib_is_correct": all(
                int(search["survivor_count"]) == 0 for search in searches.values()
            ),
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
