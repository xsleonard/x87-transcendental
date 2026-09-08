#!/usr/bin/env python3
"""Exhaust simple serialization isomorphisms for recovered PPro bodies.

H1490 rejects the published later-P6 physical-to-logical mapping when applied
literally to four H1467 Pentium Pro bodies.  This audit tests whether the old
format differs only by a global eight-dword order and a common conventional
within-dword endian transform.  It exhausts all 8! dword permutations, four
bit/byte orientations, and both logical core orientations.

Opcode recognition is a diagnostic supplied by the public P6 ISA map, not a
decoder oracle.  Deterministic random controls preserve the observed dword
bit-31 surface and undergo the identical multiple-hypothesis search.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import random
from collections import Counter
from pathlib import Path

import numpy as np

import h1490_ppro_core_permutation_transfer as later


SIGNATURES = ("611", "612", "617", "619")
GROUPS_PER_PATCH = 19
UOPS_PER_GROUP = 3
RANDOM_SEEDS = (
    0x243F6A8885A308D3,
    0x13198A2E03707344,
    0x9E3779B97F4A7C15,
    0xD1B54A32D192ED03,
)
TRANSFORMS = {
    "identity": lambda bit: bit,
    "reverse32": lambda bit: 31 - bit,
    "byteswap32": lambda bit: (3 - bit // 8) * 8 + bit % 8,
    "reverse_each_byte": lambda bit: (bit // 8) * 8 + 7 - bit % 8,
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def configuration(
    reverse_core: bool, transform: str, permutation: tuple[int, ...]
) -> dict[str, object]:
    return {
        "logical_orientation": (
            "published_core" if reverse_core else "core_without_reversal"
        ),
        "within_dword_transform": transform,
        "candidate_position_to_original_dword": list(permutation),
    }


def update_maximum(
    tracker: dict[str, object],
    value: int,
    config: dict[str, object],
    complete_metrics: dict[str, int],
) -> None:
    maximum = int(tracker["maximum"])
    if value > maximum:
        tracker["maximum"] = value
        tracker["candidate_count_at_maximum"] = 1
        tracker["examples"] = [{"configuration": config, **complete_metrics}]
    elif value == maximum:
        tracker["candidate_count_at_maximum"] = (
            int(tracker["candidate_count_at_maximum"]) + 1
        )
        examples = tracker["examples"]
        if len(examples) < 5:
            examples.append({"configuration": config, **complete_metrics})


def empty_maximum() -> dict[str, object]:
    return {"maximum": -1, "candidate_count_at_maximum": 0, "examples": []}


def inverse_core_mapping(reverse_core: bool) -> dict[tuple[int, int], tuple[int, int]]:
    """Recover the exact physical coordinate of each lower-72 logical bit."""

    inverse: dict[tuple[int, int], tuple[int, int]] = {}
    for dword in range(8):
        for bit in range(32):
            physical = [0] * 8
            physical[dword] = 1 << bit
            for lane, value in enumerate(
                later.decode_group(physical, reverse_core=reverse_core)
            ):
                for logical_bit in range(72):
                    if not ((value >> logical_bit) & 1):
                        continue
                    key = (lane, logical_bit)
                    if key in inverse:
                        raise RuntimeError(f"duplicate physical source for {key}")
                    inverse[key] = (dword, bit)
    if len(inverse) != 3 * 72:
        raise RuntimeError(
            f"published lower-72 mapping has {len(inverse)} rather than 216 bits"
        )
    return inverse


def load_recovered(h1467: dict[str, object]) -> np.ndarray:
    rows = []
    for signature in SIGNATURES:
        groups = h1467["patches"][signature]["recovery"]["decrypted_body"]
        groups = groups["physical_groups"]
        if len(groups) != GROUPS_PER_PATCH:
            raise RuntimeError(f"unexpected group count for 0x{signature}")
        rows.extend(
            [int(word, 16) for word in group["physical_dwords"]]
            for group in groups
        )
    result = np.array(rows, dtype=np.uint32)
    expected_shape = (len(SIGNATURES) * GROUPS_PER_PATCH, 8)
    if result.shape != expected_shape:
        raise RuntimeError(f"unexpected recovered body shape {result.shape}")
    return result


def random_controls(recovered: np.ndarray) -> tuple[np.ndarray, ...]:
    high_bits = recovered & np.uint32(0x80000000)
    controls = []
    for seed in RANDOM_SEEDS:
        generator = random.Random(seed)
        values = np.array(
            [generator.getrandbits(31) for _ in range(recovered.size)],
            dtype=np.uint32,
        ).reshape(recovered.shape)
        controls.append(values | high_bits)
    return tuple(controls)


def contributions(
    datasets: np.ndarray,
    inverse: dict[tuple[int, int], tuple[int, int]],
    transform,
) -> dict[str, np.ndarray]:
    """Build compact field contributions by candidate and original dword."""

    dataset_count, group_count, _ = datasets.shape
    shapes = (8, 8, dataset_count, group_count, 3)
    fields = {
        "opcode": np.zeros(shapes, dtype=np.uint16),
        "flow": np.zeros(shapes, dtype=np.uint8),
        "u1": np.zeros(shapes, dtype=np.uint8),
        "u2": np.zeros(shapes, dtype=np.uint16),
    }
    specifications = {
        "opcode": range(56, 68),
        "flow": range(0, 4),
        "u1": range(22, 23),
        "u2": range(47, 56),
    }
    starts = {"opcode": 56, "flow": 0, "u1": 22, "u2": 47}
    for name, logical_bits in specifications.items():
        destination = fields[name]
        for lane in range(3):
            for logical_bit in logical_bits:
                candidate_dword, candidate_bit = inverse[(lane, logical_bit)]
                original_bit = transform(candidate_bit)
                shift = logical_bit - starts[name]
                for original_dword in range(8):
                    selected = (
                        (datasets[:, :, original_dword] >> original_bit) & 1
                    ).astype(destination.dtype)
                    destination[candidate_dword, original_dword, :, :, lane] |= (
                        selected << shift
                    )
    return fields


def selected_fields(
    fields: dict[str, np.ndarray], permutation: tuple[int, ...]
) -> dict[str, np.ndarray]:
    indices = np.arange(8)
    return {
        name: np.bitwise_or.reduce(values[indices, permutation], axis=0)
        for name, values in fields.items()
    }


def counts(
    selected: dict[str, np.ndarray], recognized: np.ndarray
) -> tuple[dict[str, np.ndarray], np.ndarray]:
    opcode = selected["opcode"]
    recognized_rows = recognized[opcode]
    result = {
        "recognized_opcodes": recognized_rows.sum(axis=(1, 2)),
        "flow_zero": (selected["flow"] == 0).sum(axis=(1, 2)),
        "u1_zero": (selected["u1"] == 0).sum(axis=(1, 2)),
        "u2_zero": (selected["u2"] == 0).sum(axis=(1, 2)),
    }
    return result, recognized_rows


def summarize_candidate(
    config: dict[str, object], metrics: dict[str, int]
) -> dict[str, object]:
    return {"configuration": config, **metrics}


def build_report(h1467_path: Path, h1490_path: Path) -> dict[str, object]:
    h1467 = json.loads(h1467_path.read_text())
    h1490 = json.loads(h1490_path.read_text())
    recovered = load_recovered(h1467)
    controls = random_controls(recovered)
    datasets = np.stack((recovered, *controls))
    dataset_names = ("recovered",) + tuple(
        f"random_bit31_matched_{seed:016X}" for seed in RANDOM_SEEDS
    )
    uops = recovered.shape[0] * UOPS_PER_GROUP
    recognized = np.array(
        [later.recognized_opcode(opcode) is not None for opcode in range(4096)],
        dtype=np.uint8,
    )

    maxima = {
        name: {
            metric: empty_maximum()
            for metric in ("recognized_opcodes", "flow_zero", "u1_zero", "u2_zero")
        }
        for name in dataset_names
    }
    early_transfer = {
        "training_maximum": -1,
        "candidate_count_at_training_maximum": 0,
        "held_out_minimum_among_maximizers": uops + 1,
        "held_out_maximum_among_maximizers": -1,
        "best_held_out_examples": [],
    }
    late_transfer = json.loads(json.dumps(early_transfer))
    identity_metrics = None
    threshold_hits = Counter()
    calibration = h1490["later_p6_calibration"]["score"]
    thresholds = {
        metric: math.ceil(
            int(calibration[source]) * uops / int(calibration["uops"])
        )
        for metric, source in (
            ("recognized_opcodes", "recognized_opcodes"),
            ("flow_zero", "flow_histogram"),
            ("u1_zero", "unknown1_zero"),
            ("u2_zero", "unknown2_zero"),
        )
        if metric != "flow_zero"
    }
    thresholds["flow_zero"] = math.ceil(
        int(calibration["flow_histogram"]["0"]) * uops
        / int(calibration["uops"])
    )

    candidate_count = 0
    for reverse_core in (True, False):
        inverse = inverse_core_mapping(reverse_core)
        for transform_name, transform in TRANSFORMS.items():
            fields = contributions(datasets, inverse, transform)
            for permutation in itertools.permutations(range(8)):
                candidate_count += 1
                config = configuration(reverse_core, transform_name, permutation)
                selected = selected_fields(fields, permutation)
                metric_arrays, recognized_rows = counts(selected, recognized)
                complete_by_dataset = []
                for dataset_index, dataset_name in enumerate(dataset_names):
                    complete = {
                        metric: int(values[dataset_index])
                        for metric, values in metric_arrays.items()
                    }
                    complete_by_dataset.append(complete)
                    for metric, value in complete.items():
                        update_maximum(
                            maxima[dataset_name][metric], value, config, complete
                        )

                recovered_metrics = complete_by_dataset[0]
                for metric, threshold in thresholds.items():
                    if recovered_metrics[metric] >= threshold:
                        threshold_hits[metric] += 1
                if all(
                    recovered_metrics[metric] >= threshold
                    for metric, threshold in thresholds.items()
                ):
                    threshold_hits["all"] += 1

                per_patch = recognized_rows[0].reshape(
                    len(SIGNATURES), GROUPS_PER_PATCH, UOPS_PER_GROUP
                ).sum(axis=(1, 2))
                early = int(per_patch[:2].sum())
                late_count = int(per_patch[2:].sum())
                for tracker, training, held_out in (
                    (early_transfer, early, late_count),
                    (late_transfer, late_count, early),
                ):
                    if training > int(tracker["training_maximum"]):
                        tracker["training_maximum"] = training
                        tracker["candidate_count_at_training_maximum"] = 1
                        tracker["held_out_minimum_among_maximizers"] = held_out
                        tracker["held_out_maximum_among_maximizers"] = held_out
                        tracker["best_held_out_examples"] = [
                            summarize_candidate(config, recovered_metrics)
                        ]
                    elif training == int(tracker["training_maximum"]):
                        tracker["candidate_count_at_training_maximum"] = (
                            int(tracker["candidate_count_at_training_maximum"]) + 1
                        )
                        tracker["held_out_minimum_among_maximizers"] = min(
                            int(tracker["held_out_minimum_among_maximizers"]),
                            held_out,
                        )
                        prior_max = int(tracker["held_out_maximum_among_maximizers"])
                        if held_out > prior_max:
                            tracker["held_out_maximum_among_maximizers"] = held_out
                            tracker["best_held_out_examples"] = [
                                summarize_candidate(config, recovered_metrics)
                            ]
                        elif held_out == prior_max and len(
                            tracker["best_held_out_examples"]
                        ) < 5:
                            tracker["best_held_out_examples"].append(
                                summarize_candidate(config, recovered_metrics)
                            )

                if (
                    reverse_core
                    and transform_name == "identity"
                    and permutation == tuple(range(8))
                ):
                    identity_metrics = {
                        "aggregate": recovered_metrics,
                        "recognized_by_patch": {
                            signature: int(per_patch[index])
                            for index, signature in enumerate(SIGNATURES)
                        },
                    }

    expected_count = 2 * len(TRANSFORMS) * math.factorial(8)
    if candidate_count != expected_count:
        raise RuntimeError(f"candidate count {candidate_count} != {expected_count}")
    if identity_metrics is None:
        raise RuntimeError("literal H1490 candidate was not visited")
    for signature, actual in identity_metrics["recognized_by_patch"].items():
        expected = int(
            h1490["pentium_pro_patches"][signature]["orientations"]
            ["published_core"]["recognized_opcodes"]
        )
        if actual != expected:
            raise RuntimeError(
                f"literal H1490 replay differs for 0x{signature}: {actual} != {expected}"
            )

    recovered_max = maxima["recovered"]
    random_maxima = {
        name: {
            metric: int(row["maximum"])
            for metric, row in maxima[name].items()
        }
        for name in dataset_names[1:]
    }
    return {
        "query": "pentium_pro_simple_serialization_isomorphisms",
        "status": "no_credible_old_format_mapping_in_exhausted_simple_family",
        "search": {
            "candidate_count": candidate_count,
            "dword_permutations": math.factorial(8),
            "within_dword_transforms": list(TRANSFORMS),
            "logical_core_orientations": 2,
            "lane_permutations": (
                "not enumerated because every reported aggregate field metric is lane invariant"
            ),
            "patches": list(SIGNATURES),
            "groups": recovered.shape[0],
            "uops": uops,
        },
        "literal_h1490_replay": identity_metrics,
        "later_p6_calibration": calibration,
        "scaled_calibration_rate_thresholds": thresholds,
        "candidates_reaching_each_scaled_threshold": {
            **{metric: threshold_hits[metric] for metric in thresholds},
            "all": threshold_hits["all"],
        },
        "recovered_body_maxima": recovered_max,
        "early_to_late_recognition_transfer": {
            "training_patches": ["611", "612"],
            "held_out_patches": ["617", "619"],
            **early_transfer,
        },
        "late_to_early_recognition_transfer": {
            "training_patches": ["617", "619"],
            "held_out_patches": ["611", "612"],
            **late_transfer,
        },
        "random_controls": {
            "construction": (
                "independent deterministic random low 31 bits with every recovered "
                "dword bit 31 preserved in place"
            ),
            "seeds": [f"{seed:016X}" for seed in RANDOM_SEEDS],
            "maxima_after_identical_candidate_search": random_maxima,
        },
        "interpretation": {
            "confirmed": [
                (
                    "the exact later-P6 core wiring cannot be repaired on the four "
                    "recovered old bodies by any global dword permutation, tested "
                    "conventional within-dword endian transform, or core reversal"
                ),
                (
                    "the best opcode-recognition maximum is in the range reached by "
                    "bit31-matched random controls after the same multiple search"
                ),
            ],
            "not_claimed": [
                "all Pentium Pro physical-to-logical mappings are impossible",
                "the old mapping is a member of the bounded serialization family",
                "opcode recognition alone proves a decoder",
                "an R59 selector or absolute base-ROM state",
            ],
            "remaining_mapping_space": (
                "a genuinely different cross-dword bit permutation, shared triplet "
                "fields, stepping-specific format, or unreleased old-format tool"
            ),
        },
        "dependencies": {
            "h1467_report_sha256": digest(h1467_path),
            "h1490_report_sha256": digest(h1490_path),
            "h1490_source_sha256": digest(Path(later.__file__)),
            "numpy_version": np.__version__,
        },
        "execution": {
            "hardware": "none",
            "x87_instructions": "none",
            "capture_labels_opened": "none",
            "private_capture_ledger": "not accessed",
            "emulator_change": "none",
            "paper_change": "none",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1467", type=Path)
    parser.add_argument("h1490", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")
    report = build_report(arguments.h1467, arguments.h1490)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(text)
    print(
        json.dumps(
            {
                "output": str(arguments.output),
                "report_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "hardware": "none",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
