#!/usr/bin/env python3
"""Test whether the 0x612/0x617 C6 bodies differ only by bit relabeling.

Both updates have revision C6, identical first-ten architectural controls,
identical MSRAM address ranges, and exact H1467 physical plaintext.  If their
address-aligned payloads were the same bit matrix under one fixed physical
channel permutation, the multiset of 19-bit column signatures would be
identical.  Canonicalizing each signature with its complement additionally
allows an independent fixed XOR polarity on every physical channel.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


SIGNATURE_A = "612"
SIGNATURE_B = "617"
GROUPS = 19
DWORDS = 8


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def body(report: dict[str, object], signature: str) -> list[list[int]]:
    groups = report["patches"][signature]["recovery"]["decrypted_body"][
        "physical_groups"
    ]
    if len(groups) != GROUPS:
        raise RuntimeError(f"0x{signature} has {len(groups)} rather than 19 groups")
    expected_addresses = None
    result = []
    for index, group in enumerate(groups):
        if int(group["group"]) != index:
            raise RuntimeError(f"0x{signature} group order is not canonical")
        addresses = tuple(group["candidate_patch_addresses"])
        if expected_addresses is None:
            expected_addresses = []
        expected_addresses.append(addresses)
        words = [int(word, 16) for word in group["physical_dwords"]]
        if len(words) != DWORDS:
            raise RuntimeError(f"0x{signature} group {index} is not eight dwords")
        result.append(words)
    return result


def address_rows(report: dict[str, object], signature: str) -> list[tuple[str, ...]]:
    groups = report["patches"][signature]["recovery"]["decrypted_body"][
        "physical_groups"
    ]
    return [tuple(group["candidate_patch_addresses"]) for group in groups]


def control_surface(
    report: dict[str, object], signature: str
) -> list[tuple[str, str, str]]:
    controls = report["patches"][signature]["recovery"]["decrypted_body"][
        "controls"
    ]
    return [
        (control["address"], control["mask"], control["value"])
        for control in controls[:10]
    ]


def columns(words: list[list[int]], included_bits: tuple[int, ...]) -> list[dict[str, object]]:
    rows = []
    for dword in range(DWORDS):
        for bit in included_bits:
            signature = 0
            for group in range(GROUPS):
                signature |= ((words[group][dword] >> bit) & 1) << group
            rows.append(
                {
                    "dword": dword,
                    "bit": bit,
                    "signature": signature,
                    "hex": f"{signature:05X}",
                    "weight": signature.bit_count(),
                }
            )
    return rows


def multiset_overlap(
    left: list[dict[str, object]],
    right: list[dict[str, object]],
    allow_complement: bool,
) -> dict[str, object]:
    mask = (1 << GROUPS) - 1

    def key(row: dict[str, object]) -> int:
        value = int(row["signature"])
        if allow_complement:
            value = min(value, mask ^ value)
        return value

    left_counter = Counter(key(row) for row in left)
    right_counter = Counter(key(row) for row in right)
    overlap = left_counter & right_counter
    example_pairs = []
    for signature in sorted(overlap):
        left_rows = [row for row in left if key(row) == signature]
        right_rows = [row for row in right if key(row) == signature]
        for left_row, right_row in zip(left_rows, right_rows):
            right_raw = int(right_row["signature"])
            left_raw = int(left_row["signature"])
            example_pairs.append(
                {
                    "left": {k: left_row[k] for k in ("dword", "bit", "hex")},
                    "right": {k: right_row[k] for k in ("dword", "bit", "hex")},
                    "right_complemented": left_raw != right_raw,
                }
            )
            if len(example_pairs) == 8:
                break
        if len(example_pairs) == 8:
            break
    matched = sum(overlap.values())
    return {
        "allow_independent_channel_complement": allow_complement,
        "left_channels": len(left),
        "right_channels": len(right),
        "left_distinct_signatures": len(left_counter),
        "right_distinct_signatures": len(right_counter),
        "maximum_exactly_matchable_channels": matched,
        "perfect_bijection_exists": matched == len(left) == len(right),
        "example_pairs": example_pairs,
    }


def nearest_distances(
    left: list[dict[str, object]], right: list[dict[str, object]]
) -> dict[str, int]:
    histogram: Counter[int] = Counter()
    right_values = [int(row["signature"]) for row in right]
    for row in left:
        value = int(row["signature"])
        histogram[min((value ^ candidate).bit_count() for candidate in right_values)] += 1
    return {str(distance): histogram[distance] for distance in sorted(histogram)}


def analyze_view(
    left_words: list[list[int]],
    right_words: list[list[int]],
    included_bits: tuple[int, ...],
) -> dict[str, object]:
    left = columns(left_words, included_bits)
    right = columns(right_words, included_bits)
    return {
        "physical_bits_per_dword": list(included_bits),
        "exact_permutation": multiset_overlap(left, right, False),
        "permutation_plus_independent_fixed_xor": multiset_overlap(left, right, True),
        "nearest_raw_hamming_distance_by_left_channel": nearest_distances(left, right),
    }


def build_report(path: Path) -> dict[str, object]:
    h1467 = json.loads(path.read_text())
    left_header = h1467["patches"][SIGNATURE_A]["header"]
    right_header = h1467["patches"][SIGNATURE_B]["header"]
    if left_header["revision"] != "000000C6" or right_header["revision"] != "000000C6":
        raise RuntimeError("expected both compared patches to have revision C6")
    left_addresses = address_rows(h1467, SIGNATURE_A)
    right_addresses = address_rows(h1467, SIGNATURE_B)
    if left_addresses != right_addresses:
        raise RuntimeError("the two recovered bodies are not address-aligned")
    left_controls = control_surface(h1467, SIGNATURE_A)
    right_controls = control_surface(h1467, SIGNATURE_B)
    if left_controls != right_controls:
        raise RuntimeError("the first ten architectural controls differ")

    left_words = body(h1467, SIGNATURE_A)
    right_words = body(h1467, SIGNATURE_B)
    views = {
        "all_256_physical_channels": analyze_view(
            left_words, right_words, tuple(range(32))
        ),
        "low_31_bits_of_each_dword": analyze_view(
            left_words, right_words, tuple(range(31))
        ),
    }
    return {
        "query": "pentium_pro_c6_address_aligned_body_bit_isomorphism",
        "status": "no_fixed_channel_permutation_isomorphism",
        "fixed_facts": {
            "signatures": [SIGNATURE_A, SIGNATURE_B],
            "revision": "000000C6",
            "identical_first_ten_control_address_mask_value_triplets": True,
            "identical_group_address_rows": True,
            "group_count": GROUPS,
            "candidate_uop_addresses": [list(row) for row in left_addresses],
            "both_bodies_h1467_integrity_checks": "16/16",
        },
        "views": views,
        "proof": (
            "A fixed channel permutation preserves the multiset of address-column "
            "signatures. Independent fixed per-channel XOR additionally preserves "
            "their complement-canonical multiset. The reported multiset intersections "
            "are the exact maximum number of channels that can be paired under each "
            "relation."
        ),
        "interpretation": {
            "confirmed": [
                (
                    "the address-aligned 0x612 and 0x617 C6 physical bodies cannot "
                    "represent one identical bit matrix under any fixed physical "
                    "channel permutation"
                ),
                (
                    "allowing one independent fixed XOR polarity per physical "
                    "channel does not repair that isomorphism"
                ),
            ],
            "not_claimed": [
                "the two stepping-specific updates have identical logical programs",
                "all stepping-specific physical encodings are excluded",
                "the H1467 physical plaintext is a logical Pentium Pro decode",
                "an R59 selector or absolute base-ROM state",
            ],
            "consequence": (
                "shared revision and control hooks cannot serve as an identical-body "
                "crib for recovering the old physical-to-logical permutation"
            ),
        },
        "dependencies": {"h1467_report_sha256": digest(path)},
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
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")
    report = build_report(arguments.h1467)
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
