#!/usr/bin/env python3
"""Audit public PPro representations after correcting the patch layout.

H1555 proved that the Pentium Pro update body is 21 seven-dword groups plus
one spare dword, not the 19 eight-dword partition used by H1467--H1554.  A
newer public utools source also publishes the CPUID 0x619 permutation between
the seven-dword CRBUS MSROM readout and the seven-dword update representation.

This audit reconstructs that permutation independently, proves that it is a
bijection over exactly 216 bits, cross-checks it against the compiled public
converter, and reruns the bounded later-P6 simple-isomorphism search on the
correct groups.  It never loads a microcode update or executes x87 hardware.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import random
import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np

import h1490_ppro_core_permutation_transfer as later
import h1493_ppro_serialization_isomorphisms as simple


SOURCE_COMMIT = "ab6aa24ed91de1c048313c10cb7546ea3397b827"
SOURCE_URL = f"https://github.com/ruikruik/utools/tree/{SOURCE_COMMIT}"
EXPECTED_SOURCE_SHA256 = (
    "7c41477039cb2a183f32aeb0b0263560c52fdee8bbad965d69a7a786ea195d00"
)
EXPECTED_H1555_SHA256 = (
    "cfa72d316ffb6efd58770b820d79b9568fc459d26691f09d6f9842da952d6280"
)
UNIQUE_SIGNATURES = ("611", "612", "619")
ALL_SIGNATURES = ("611", "612", "616", "617", "619")
GROUPS_PER_PATCH = 21
RANDOM_SEEDS = simple.RANDOM_SEEDS


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def words_digest(rows: np.ndarray) -> str:
    return hashlib.sha256(rows.astype("<u4", copy=False).tobytes()).hexdigest()


def parse_c_array(source: str, name: str, expected_rows: int) -> list[list[int]]:
    match = re.search(
        rf"uint32_t\s+{re.escape(name)}\[\]\[8\]\s*=\s*\{{(.*?)\n\}};",
        source,
        re.DOTALL,
    )
    if not match:
        raise RuntimeError(f"could not locate {name}")
    body = re.sub(r"/\*.*?\*/", "", match.group(1), flags=re.DOTALL)
    rows = [
        [int(value, 16) for value in re.findall(r"0x[0-9A-Fa-f]+", row)]
        for row in re.findall(r"\{([^{}]+)\}", body)
    ]
    if len(rows) != expected_rows or any(len(row) != 8 for row in rows):
        raise RuntimeError(
            f"{name}: expected {expected_rows}x8 values, got "
            f"{len(rows)} rows with widths {[len(row) for row in rows]}"
        )
    return rows


def recover_public_mapping(
    masks: list[list[int]], routes: list[list[int]]
) -> dict[tuple[int, int], tuple[int, int]]:
    """Reproduce the inverse-map construction in public msrom2scramble.c."""

    rom_to_patch: dict[tuple[int, int], tuple[int, int]] = {}
    for rom_dword in range(8):
        for patch_bit in range(32):
            for patch_dword in range(8):
                intersection = routes[patch_bit][rom_dword] & masks[patch_dword][rom_dword]
                if not intersection:
                    continue
                if intersection & (intersection - 1):
                    raise RuntimeError("public route/mask intersection is not one bit")
                rom_bit = intersection.bit_length() - 1
                source = (rom_dword, rom_bit)
                destination = (patch_dword, patch_bit)
                if source in rom_to_patch:
                    raise RuntimeError(f"duplicate ROM source coordinate {source}")
                rom_to_patch[source] = destination

    destinations = list(rom_to_patch.values())
    if len(rom_to_patch) != 216 or len(set(destinations)) != 216:
        raise RuntimeError(
            "0x619 public mapping is not a 216-bit source/destination bijection"
        )
    if any(dword >= 7 for dword, _ in rom_to_patch):
        raise RuntimeError("0x619 mapping unexpectedly consumes ROM dword seven")
    if any(dword >= 7 for dword, _ in destinations):
        raise RuntimeError("0x619 mapping unexpectedly emits patch dword seven")
    return rom_to_patch


def connected_masks(
    coordinates: set[tuple[int, int]], width: int = 8
) -> np.ndarray:
    result = np.zeros(width, dtype=np.uint32)
    for dword, bit in coordinates:
        result[dword] |= np.uint32(1 << bit)
    return result


def transform_words(
    words: list[int], mapping: dict[tuple[int, int], tuple[int, int]], reverse: bool
) -> list[int]:
    """Apply ROM->patch when reverse is false, or patch->ROM when true."""

    result = [0] * 7
    for rom_coordinate, patch_coordinate in mapping.items():
        source, destination = (
            (patch_coordinate, rom_coordinate) if reverse else (rom_coordinate, patch_coordinate)
        )
        source_dword, source_bit = source
        destination_dword, destination_bit = destination
        if (words[source_dword] >> source_bit) & 1:
            result[destination_dword] |= 1 << destination_bit
    return result


def load_patch_rows(report: dict[str, object], signatures: tuple[str, ...]) -> np.ndarray:
    rows: list[list[int]] = []
    for signature in signatures:
        groups = report["patches"][signature]["msram"]["groups"]
        if len(groups) != GROUPS_PER_PATCH:
            raise RuntimeError(f"0x{signature}: expected 21 groups")
        rows.extend(
            [int(word, 16) for word in group["physical_dwords"]]
            for group in groups
        )
    result = np.asarray(rows, dtype=np.uint32)
    if result.shape != (len(signatures) * GROUPS_PER_PATCH, 7):
        raise RuntimeError(f"unexpected corrected patch shape {result.shape}")
    return result


def converter_crosscheck(
    converter: Path | None,
    patch_619: np.ndarray,
    rom_619: np.ndarray,
) -> dict[str, object]:
    if converter is None:
        return {"run": False}
    lines = []
    for index, row in enumerate(rom_619):
        lines.append(
            f"{index * 8:04X}: " + " ".join(f"{int(word):08X}" for word in row)
        )
    with tempfile.TemporaryDirectory(prefix="h1556-") as directory:
        input_path = Path(directory) / "rom619.txt"
        input_path.write_text("\n".join(lines) + "\n")
        completed = subprocess.run(
            [str(converter), str(input_path)],
            check=False,
            capture_output=True,
            text=True,
        )
    if completed.returncode != 0:
        raise RuntimeError(f"public converter failed: {completed.stderr}")
    expected = "\n".join(
        f"{index * 8:04X}: " + " ".join(f"{int(word):08X}" for word in row)
        for index, row in enumerate(patch_619)
    ) + "\n"
    if completed.stdout != expected:
        raise RuntimeError("compiled public converter disagrees with independent replay")
    return {
        "run": True,
        "exit_code": completed.returncode,
        "rows": len(patch_619),
        "stdout_sha256": hashlib.sha256(completed.stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(completed.stderr.encode()).hexdigest(),
        "stderr_empty": not completed.stderr,
        "exact_match": True,
    }


def random_controls(recovered: np.ndarray, used_mask: np.ndarray) -> tuple[np.ndarray, ...]:
    fixed = recovered & ~used_mask
    controls = []
    for seed in RANDOM_SEEDS:
        generator = random.Random(seed)
        random_words = np.asarray(
            [generator.getrandbits(32) for _ in range(recovered.size)],
            dtype=np.uint32,
        ).reshape(recovered.shape)
        controls.append((random_words & used_mask) | fixed)
    return tuple(controls)


def scaled_thresholds(uops: int) -> dict[str, int]:
    return {
        "recognized_opcodes": math.ceil(61 * uops / 63),
        "flow_zero": uops,
        "u1_zero": uops,
        "u2_zero": math.ceil(54 * uops / 63),
    }


def simple_family_search(
    name: str, recovered7: np.ndarray, used7: np.ndarray
) -> dict[str, object]:
    recovered = np.column_stack(
        (recovered7, np.zeros(recovered7.shape[0], dtype=np.uint32))
    )
    used = np.concatenate((used7, np.zeros(1, dtype=np.uint32)))
    controls = random_controls(recovered, used)
    datasets = np.stack((recovered, *controls))
    dataset_names = ("recovered",) + tuple(
        f"random_connected_surface_{seed:016X}" for seed in RANDOM_SEEDS
    )
    recognized = np.asarray(
        [later.recognized_opcode(opcode) is not None for opcode in range(4096)],
        dtype=np.uint8,
    )
    maxima = {
        dataset: {
            metric: simple.empty_maximum()
            for metric in ("recognized_opcodes", "flow_zero", "u1_zero", "u2_zero")
        }
        for dataset in dataset_names
    }
    thresholds = scaled_thresholds(recovered.shape[0] * 3)
    threshold_counts = {metric: 0 for metric in thresholds}
    threshold_counts["all"] = 0
    literal = None
    candidate_count = 0

    for reverse_core in (True, False):
        inverse = simple.inverse_core_mapping(reverse_core)
        for transform_name, transform in simple.TRANSFORMS.items():
            fields = simple.contributions(datasets, inverse, transform)
            for permutation in itertools.permutations(range(8)):
                candidate_count += 1
                configuration = simple.configuration(
                    reverse_core, transform_name, permutation
                )
                selected = simple.selected_fields(fields, permutation)
                metric_arrays, _ = simple.counts(selected, recognized)
                recovered_metrics = None
                for dataset_index, dataset_name in enumerate(dataset_names):
                    complete = {
                        metric: int(values[dataset_index])
                        for metric, values in metric_arrays.items()
                    }
                    if dataset_index == 0:
                        recovered_metrics = complete
                    for metric, value in complete.items():
                        simple.update_maximum(
                            maxima[dataset_name][metric], value, configuration, complete
                        )
                assert recovered_metrics is not None
                for metric, threshold in thresholds.items():
                    if recovered_metrics[metric] >= threshold:
                        threshold_counts[metric] += 1
                if all(
                    recovered_metrics[metric] >= threshold
                    for metric, threshold in thresholds.items()
                ):
                    threshold_counts["all"] += 1
                if (
                    reverse_core
                    and transform_name == "identity"
                    and permutation == tuple(range(8))
                ):
                    literal = recovered_metrics

    expected_candidates = 2 * len(simple.TRANSFORMS) * math.factorial(8)
    if candidate_count != expected_candidates or literal is None:
        raise RuntimeError("simple-family enumeration was incomplete")
    return {
        "representation": name,
        "groups": recovered.shape[0],
        "uops": recovered.shape[0] * 3,
        "candidate_count": candidate_count,
        "candidate_family": {
            "global_dword_permutations": math.factorial(8),
            "within_dword_transforms": list(simple.TRANSFORMS),
            "logical_core_orientations": 2,
            "zero_padding_dword": (
                "the eighth input dword is zero; all eight placements are included "
                "inside the global permutation"
            ),
        },
        "literal_zero_last": literal,
        "scaled_later_p6_thresholds": thresholds,
        "candidates_reaching_thresholds": threshold_counts,
        "recovered_maxima": maxima["recovered"],
        "random_control_maxima": {
            dataset: {
                metric: int(row["maximum"])
                for metric, row in maxima[dataset].items()
            }
            for dataset in dataset_names[1:]
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--h1555", required=True, type=Path)
    parser.add_argument("--msrom2scramble-source", required=True, type=Path)
    parser.add_argument("--converter", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")

    h1555_hash = digest(arguments.h1555)
    if h1555_hash != EXPECTED_H1555_SHA256:
        raise RuntimeError(f"unexpected H1555 report hash {h1555_hash}")
    source_hash = digest(arguments.msrom2scramble_source)
    if source_hash != EXPECTED_SOURCE_SHA256:
        raise RuntimeError(f"unexpected public source hash {source_hash}")

    source = arguments.msrom2scramble_source.read_text()
    masks = parse_c_array(source, "dw_masks_619", 8)
    routes = parse_c_array(source, "dw_to_crbusrom_619", 32)
    mapping = recover_public_mapping(masks, routes)
    patch_coordinates = set(mapping.values())
    rom_coordinates = set(mapping)
    patch_mask8 = connected_masks(patch_coordinates)
    rom_mask8 = connected_masks(rom_coordinates)
    patch_mask7 = patch_mask8[:7]
    rom_mask7 = rom_mask8[:7]

    report1555 = json.loads(arguments.h1555.read_text())
    patch_all = load_patch_rows(report1555, ALL_SIGNATURES)
    if np.any(patch_all & ~patch_mask7):
        raise RuntimeError("corrected PPro patch has nonzero disconnected bits")

    patch_unique = load_patch_rows(report1555, UNIQUE_SIGNATURES)
    rom_unique = np.asarray(
        [transform_words([int(word) for word in row], mapping, True) for row in patch_unique],
        dtype=np.uint32,
    )
    replay_unique = np.asarray(
        [transform_words([int(word) for word in row], mapping, False) for row in rom_unique],
        dtype=np.uint32,
    )
    if not np.array_equal(replay_unique, patch_unique):
        raise RuntimeError("public 0x619 permutation did not round-trip")
    if np.any(rom_unique & ~rom_mask7):
        raise RuntimeError("recovered CRBUS representation has nonzero disconnected bits")

    patch_619 = load_patch_rows(report1555, ("619",))
    rom_619 = np.asarray(
        [transform_words([int(word) for word in row], mapping, True) for row in patch_619],
        dtype=np.uint32,
    )
    converter_result = converter_crosscheck(arguments.converter, patch_619, rom_619)

    mapping_rows = [
        {
            "rom_dword": rom[0],
            "rom_bit": rom[1],
            "patch_dword": patch[0],
            "patch_bit": patch[1],
        }
        for rom, patch in sorted(mapping.items())
    ]
    unused_patch = sorted(
        set(itertools.product(range(7), range(32))) - patch_coordinates
    )
    unused_rom = sorted(set(itertools.product(range(7), range(32))) - rom_coordinates)

    searches = {
        "correct_patch_representation_unique_bodies": simple_family_search(
            "correct_patch_representation_unique_bodies", patch_unique, patch_mask7
        ),
        "public_619_crbus_representation": simple_family_search(
            "public_619_crbus_representation", rom_619, rom_mask7
        ),
    }
    threshold_survivors = {
        name: row["candidates_reaching_thresholds"]["all"]
        for name, row in searches.items()
    }
    result = {
        "status": "exact_619_representation_replay_no_threshold_exact_public_p6_decoder",
        "question": (
            "Does the newly public 0x619 CRBUS/update permutation repair the "
            "Pentium Pro physical representation, and does the corrected 21x7 "
            "partition admit the public later-P6 decoder under simple isomorphisms?"
        ),
        "dependencies": {
            "h1555": {"path": str(arguments.h1555), "sha256": h1555_hash},
            "utools": {
                "url": SOURCE_URL,
                "commit": SOURCE_COMMIT,
                "msrom2scramble_c_sha256": source_hash,
            },
        },
        "method": {
            "hardware_executed": False,
            "x87_executed": False,
            "microcode_loaded": False,
            "private_ledger_accessed": False,
            "compiled_public_converter_invoked": arguments.converter is not None,
        },
        "public_619_permutation": {
            "mapped_bits": len(mapping),
            "rom_connected_bits_by_dword": [int(value).bit_count() for value in rom_mask8],
            "patch_connected_bits_by_dword": [
                int(value).bit_count() for value in patch_mask8
            ],
            "unused_rom_coordinates": [list(item) for item in unused_rom],
            "unused_patch_coordinates": [list(item) for item in unused_patch],
            "all_observed_disconnected_patch_bits_zero": True,
            "round_trip_unique_bodies": True,
            "mapping": mapping_rows,
            "correct_patch_unique_bodies_sha256": words_digest(patch_unique),
            "derived_crbus_unique_bodies_sha256": words_digest(rom_unique),
            "derived_crbus_619_sha256": words_digest(rom_619),
            "compiled_converter_crosscheck_619": converter_result,
            "scope": (
                "The source names this table for CPUID 0x619. Its physical meaning "
                "is exact for 0x619; applying it to 0x611/0x612 is only a transfer "
                "hypothesis, although every application is algebraically reversible."
            ),
        },
        "corrected_simple_isomorphism_searches": searches,
        "conclusion": {
            "h1467_partition_repaired": True,
            "exact_619_crbus_to_patch_representation_recovered": True,
            "simple_public_p6_decoder_survivors": threshold_survivors,
            "logical_ppro_decoder_recovered": False,
            "selector_found": False,
            "emulator_change": False,
            "frontier_closed": False,
            "strong_nonrandom_near_decoder_observed": True,
            "interpretation": (
                "The public converter supplies the missing physical-to-physical "
                "0x619 representation map. A strong non-random simple alignment "
                "with the later-P6 decoder appears, but no candidate satisfies all "
                "later-P6 calibration thresholds and the still-unreleased Pentium "
                "Pro p6scrambler is required for an authoritative logical decode."
            ),
        },
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
