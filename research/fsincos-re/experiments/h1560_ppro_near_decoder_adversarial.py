#!/usr/bin/env python3
"""Stress H1557 after removing the repeated CPUID-0x619 terminal wall.

H1557's 52/63 recognized-opcode headline includes 15 identical groups, or 45
identical decoded uops.  This audit separates that wall, reranks the six unique
0x619 groups, and then tests whether H1557's exact configuration remains a
non-random multimetric outlier over the nonrepeated 0x611/0x612/0x619 union.
The public CRBUS transform is source-exact only for 0x619; its use on 0x611 and
0x612 remains an explicitly marked transfer hypothesis.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from collections import Counter
from pathlib import Path

import numpy as np

import h1490_ppro_core_permutation_transfer as later
import h1493_ppro_serialization_isomorphisms as simple
import h1556_ppro_correct_layout_mapping_audit as corrected
import h1557_ppro_near_decoder as near


EXPECTED_H1555_SHA256 = (
    "cfa72d316ffb6efd58770b820d79b9568fc459d26691f09d6f9842da952d6280"
)
EXPECTED_H1557_SHA256 = (
    "5c1242f83e98f841d7544bf1a76bd31ceb7c91efbfba535ff6b4bf24b7b23f8a"
)
SIGNATURES = ("611", "612", "619")
METRICS = ("recognized_opcodes", "flow_zero", "u1_zero", "u2_zero")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def score(rows: np.ndarray, configuration: dict[str, object]) -> dict[str, int]:
    decoded = near.decode_rows(rows, configuration)
    return {
        "recognized_opcodes": sum(bool(item["recognized"]) for item in decoded),
        "flow_zero": sum(int(item["flow"]) == 0 for item in decoded),
        "u1_zero": sum(int(item["unknown1"]) == 0 for item in decoded),
        "u2_zero": sum(int(item["unknown2"]) == 0 for item in decoded),
    }


def pad(rows7: np.ndarray) -> np.ndarray:
    return np.column_stack((rows7, np.zeros(rows7.shape[0], dtype=np.uint32)))


def pareto_replay(
    rows8: np.ndarray, target: dict[str, int]
) -> dict[str, object]:
    datasets = np.expand_dims(rows8, 0)
    recognized = np.asarray(
        [later.recognized_opcode(opcode) is not None for opcode in range(4096)],
        dtype=np.uint8,
    )
    target_vector = np.asarray([target[name] for name in METRICS])
    candidate_count = 0
    meeting = 0
    strict_dominators = 0
    equal_vectors = 0
    examples = []
    maxima = {name: 0 for name in METRICS}

    for reverse_core in (True, False):
        inverse = simple.inverse_core_mapping(reverse_core)
        for transform_name, transform in simple.TRANSFORMS.items():
            contributions = simple.contributions(datasets, inverse, transform)
            for permutation in itertools.permutations(range(8)):
                candidate_count += 1
                arrays, _ = simple.counts(
                    simple.selected_fields(contributions, permutation), recognized
                )
                values = np.asarray([int(arrays[name][0]) for name in METRICS])
                for index, name in enumerate(METRICS):
                    maxima[name] = max(maxima[name], int(values[index]))
                if np.all(values >= target_vector):
                    meeting += 1
                    strict = bool(np.any(values > target_vector))
                    strict_dominators += int(strict)
                    equal_vectors += int(not strict)
                    if len(examples) < 20:
                        examples.append(
                            {
                                "metrics": {
                                    name: int(values[index])
                                    for index, name in enumerate(METRICS)
                                },
                                "configuration": simple.configuration(
                                    reverse_core, transform_name, permutation
                                ),
                            }
                        )

    expected = 2 * len(simple.TRANSFORMS) * 40320
    if candidate_count != expected:
        raise RuntimeError("candidate replay was incomplete")
    return {
        "candidate_count": candidate_count,
        "target_metrics": target,
        "per_metric_maxima": maxima,
        "componentwise_meeting_or_exceeding_target": meeting,
        "strict_dominators": strict_dominators,
        "equal_metric_vectors": equal_vectors,
        "examples": examples,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--h1555", required=True, type=Path)
    parser.add_argument("--h1557", required=True, type=Path)
    parser.add_argument("--msrom2scramble-source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")
    if digest(arguments.h1555) != EXPECTED_H1555_SHA256:
        raise RuntimeError("unexpected H1555 report hash")
    if digest(arguments.h1557) != EXPECTED_H1557_SHA256:
        raise RuntimeError("unexpected H1557 report hash")
    if digest(arguments.msrom2scramble_source) != corrected.EXPECTED_SOURCE_SHA256:
        raise RuntimeError("unexpected public converter source hash")

    report1555 = json.loads(arguments.h1555.read_text())
    report1557 = json.loads(arguments.h1557.read_text())
    configuration = report1557["canonical_best"]["configuration"]
    source = arguments.msrom2scramble_source.read_text()
    mapping = corrected.recover_public_mapping(
        corrected.parse_c_array(source, "dw_masks_619", 8),
        corrected.parse_c_array(source, "dw_to_crbusrom_619", 32),
    )
    connected = corrected.connected_masks(set(mapping.keys()), 7)

    partitions: dict[str, dict[str, object]] = {}
    nonrepeated_parts = []
    for signature in SIGNATURES:
        patch = corrected.load_patch_rows(report1555, (signature,))
        rows7 = np.asarray(
            [
                corrected.transform_words([int(word) for word in row], mapping, True)
                for row in patch
            ],
            dtype=np.uint32,
        )
        frequencies = Counter(tuple(int(word) for word in row) for row in rows7)
        nonrepeated_mask = np.asarray(
            [frequencies[tuple(int(word) for word in row)] == 1 for row in rows7]
        )
        nonrepeated = rows7[nonrepeated_mask]
        repeated = rows7[~nonrepeated_mask]
        nonrepeated_parts.append(nonrepeated)
        partitions[signature] = {
            "mapping_scope": (
                "source-exact CPUID-0x619 CRBUS transform"
                if signature == "619"
                else "CPUID-0x619 CRBUS transform transferred as hypothesis"
            ),
            "groups_total": len(rows7),
            "groups_nonrepeated": len(nonrepeated),
            "groups_repeated": len(repeated),
            "row_multiplicities_descending": sorted(
                frequencies.values(), reverse=True
            ),
            "canonical_all": score(pad(rows7), configuration),
            "canonical_nonrepeated": score(pad(nonrepeated), configuration),
            "canonical_repeated": score(pad(repeated), configuration),
        }

    rows619 = corrected.load_patch_rows(report1555, ("619",))
    rom619 = np.asarray(
        [
            corrected.transform_words([int(word) for word in row], mapping, True)
            for row in rows619
        ],
        dtype=np.uint32,
    )
    frequencies619 = Counter(tuple(int(word) for word in row) for row in rom619)
    active619 = rom619[
        np.asarray(
            [frequencies619[tuple(int(word) for word in row)] == 1 for row in rom619]
        )
    ]
    rank619 = near.rank_candidates(pad(active619))

    union7 = np.concatenate(nonrepeated_parts)
    union8 = pad(union7)
    canonical_union = score(union8, configuration)
    pareto = pareto_replay(union8, canonical_union)
    controls = corrected.simple_family_search(
        "nonrepeated_611_612_619_union", union7, connected
    )

    result = {
        "status": "tail_inflates_headline_but_does_not_explain_near_decoder",
        "question": (
            "Does H1557 survive removal of the 15-identical-group 0x619 tail, "
            "or was its unique result merely a repeated-wall fit?"
        ),
        "dependencies": {
            "h1555": {"path": str(arguments.h1555), "sha256": digest(arguments.h1555)},
            "h1557": {"path": str(arguments.h1557), "sha256": digest(arguments.h1557)},
            "utools_msrom2scramble_c": {
                "url": corrected.SOURCE_URL,
                "sha256": digest(arguments.msrom2scramble_source),
            },
        },
        "method": {
            "configuration": configuration,
            "candidate_family_size": pareto["candidate_count"],
            "hardware_executed": False,
            "x87_executed": False,
            "microcode_loaded": False,
            "private_ledger_accessed": False,
            "non_619_mapping_is_hypothetical_transfer": True,
        },
        "per_patch_partitions": partitions,
        "isolated_619_nonrepeated_ranking": {
            "groups": len(active619),
            "uops": 3 * len(active619),
            "canonical_metrics": partitions["619"]["canonical_nonrepeated"],
            "best_key": rank619["best_key"],
            "candidate_count_at_best_key": rank619["candidate_count_at_best_key"],
            "best_examples": rank619["best_examples"],
            "canonical_is_best": any(
                example["configuration"] == configuration
                for example in rank619["best_examples"]
            ),
        },
        "nonrepeated_union": {
            "groups": len(union7),
            "uops": 3 * len(union7),
            "canonical_metrics": canonical_union,
            "pareto_replay": pareto,
            "random_control_and_maximum_audit": controls,
        },
        "conclusion": {
            "h1557_headline_recognition_tail_dominated": True,
            "isolated_619_nonrepeated_canonical_wins_original_ranking": False,
            "same_configuration_unique_componentwise_on_nonrepeated_union": (
                pareto["componentwise_meeting_or_exceeding_target"] == 1
                and pareto["strict_dominators"] == 0
            ),
            "mapping_explained_only_by_repeated_tail": False,
            "authoritative_ppro_logical_decoder": False,
            "paired_logical_physical_fixture_still_required": True,
            "selector_found": False,
            "emulator_change": False,
            "frontier_closed": False,
        },
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
