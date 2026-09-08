#!/usr/bin/env python3
"""Transfer H1557's unique 0x619 near-decoder across all recovered PPro bodies.

The public CRBUS/update permutation is named for CPUID 0x619, so applying it
to 0x611/0x612/0x616/0x617 is explicitly a transfer test rather than a source-
proven decode.  Repeated tails and cross-stepping agreement are reported as
structure, not promoted to an authoritative logical map.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np

import h1556_ppro_correct_layout_mapping_audit as corrected
import h1557_ppro_near_decoder as near


EXPECTED_H1557_SHA256 = (
    "5c1242f83e98f841d7544bf1a76bd31ceb7c91efbfba535ff6b4bf24b7b23f8a"
)
SIGNATURES = ("611", "612", "616", "617", "619")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows_digest(rows: list[dict[str, object]]) -> str:
    payload = "\n".join(str(row["raw72"]) for row in rows).encode()
    return hashlib.sha256(payload).hexdigest()


def repeated_tail(triads: list[tuple[str, str, str]]) -> dict[str, object]:
    terminal = triads[-1]
    start = len(triads) - 1
    while start > 0 and triads[start - 1] == terminal:
        start -= 1
    return {
        "start_group": start,
        "groups": len(triads) - start,
        "raw72_triad": list(terminal),
    }


def summarize(rows: list[dict[str, object]]) -> dict[str, object]:
    triads = [
        tuple(str(rows[3 * group + lane]["raw72"]) for lane in range(3))
        for group in range(len(rows) // 3)
    ]
    return {
        "uops": len(rows),
        "recognized": sum(bool(row["recognized"]) for row in rows),
        "flow_zero": sum(int(row["flow"]) == 0 for row in rows),
        "unknown1_zero": sum(int(row["unknown1"]) == 0 for row in rows),
        "unknown2_zero": sum(int(row["unknown2"]) == 0 for row in rows),
        "opcode_histogram": dict(
            sorted(Counter(str(row["opcode"]) for row in rows).items())
        ),
        "unknown_opcode_histogram": dict(
            sorted(
                Counter(
                    str(row["opcode"]) for row in rows if not bool(row["recognized"])
                ).items()
            )
        ),
        "distinct_triads": len(set(triads)),
        "repeated_terminal_triad": repeated_tail(triads),
        "logical_rows_sha256": rows_digest(rows),
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
    if digest(arguments.h1557) != EXPECTED_H1557_SHA256:
        raise RuntimeError("unexpected H1557 report hash")
    if digest(arguments.msrom2scramble_source) != corrected.EXPECTED_SOURCE_SHA256:
        raise RuntimeError("unexpected public converter source hash")

    report1555 = json.loads(arguments.h1555.read_text())
    report1557 = json.loads(arguments.h1557.read_text())
    configuration = report1557["canonical_best"]["configuration"]
    source = arguments.msrom2scramble_source.read_text()
    masks = corrected.parse_c_array(source, "dw_masks_619", 8)
    routes = corrected.parse_c_array(source, "dw_to_crbusrom_619", 32)
    mapping = corrected.recover_public_mapping(masks, routes)

    results: dict[str, dict[str, object]] = {}
    listings: dict[str, list[dict[str, object]]] = {}
    for signature in SIGNATURES:
        patch = corrected.load_patch_rows(report1555, (signature,))
        rom7 = np.asarray(
            [
                corrected.transform_words([int(word) for word in row], mapping, True)
                for row in patch
            ],
            dtype=np.uint32,
        )
        rom8 = np.column_stack((rom7, np.zeros(rom7.shape[0], dtype=np.uint32)))
        listing = near.decode_rows(rom8, configuration)
        listings[signature] = listing
        results[signature] = {
            "physical_scope": (
                "source-proven 0x619 mapping"
                if signature == "619"
                else "0x619 mapping transferred as hypothesis"
            ),
            "summary": summarize(listing),
            "listing": listing,
        }

    equality = []
    for left_index, left in enumerate(SIGNATURES):
        for right in SIGNATURES[left_index + 1 :]:
            same = results[left]["summary"]["logical_rows_sha256"] == results[right]["summary"]["logical_rows_sha256"]
            equality.append({"left": left, "right": right, "identical": same})

    triad_owners: dict[tuple[str, str, str], set[str]] = {}
    triad_counts: Counter[tuple[str, str, str]] = Counter()
    for signature, listing in listings.items():
        for group in range(len(listing) // 3):
            triad = tuple(
                str(listing[3 * group + lane]["raw72"]) for lane in range(3)
            )
            triad_counts[triad] += 1
            triad_owners.setdefault(triad, set()).add(signature)
    common_triads = [
        {
            "raw72_triad": list(triad),
            "occurrences": count,
            "signatures": sorted(triad_owners[triad]),
        }
        for triad, count in triad_counts.most_common()
        if len(triad_owners[triad]) >= 2
    ]

    result = {
        "status": "near_decoder_transfers_structurally_not_authoritatively",
        "question": (
            "Does the unique H1557 0x619 near-decoder preserve recognizable "
            "structure when transferred unchanged to the other corrected PPro bodies?"
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
            "hardware_executed": False,
            "x87_executed": False,
            "microcode_loaded": False,
            "private_ledger_accessed": False,
            "non_619_mapping_is_hypothetical_transfer": True,
        },
        "patches": results,
        "pairwise_logical_equality": equality,
        "cross_patch_repeated_triads": common_triads,
        "conclusion": {
            "source_exact_for_619": True,
            "transfer_structure_present": True,
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
