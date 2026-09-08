#!/usr/bin/env python3
"""Test the published later-P6 72-bit core wiring on recovered PPro patches.

H1467 recovers four Pentium Pro update bodies exactly in physical eight-dword
groups, but no validated physical-to-logical permutation.  The later public
P6 descrambler maps 231 physical bits to three 80-bit uops.  Seventy-one bits
per uop use its main left/right permutation, while logical bit 70 draws three
more physical positions; bits 72--79 are later-generation additions.  This
audit first validates a dependency-free 72-bit transcription against a paired
later-P6 physical/logical fixture, then applies only that mapping to the four
old bodies.

Recognition statistics are diagnostics, not a decoder oracle.  No update is
loaded and no x87 instruction or capture is executed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter
from pathlib import Path


ORD_LEFT = (
    58, 71, 69, 57, 56, 68, 55, 43, 42, 49, 48, 41, 40, 47, 46, 39,
    36, 45, 44, 35, 34, 38, 37, 33, 27, 20, 21, 26, 25, 19, 18, 24,
    23, 16, 2, 17,
)
ORD_RIGHT_A = (8, 6, 13)
ORD_RIGHT_B = (7, 11, 10, 14, 9, 4, 12, 15, 5, 1, 67, 65)
ORD_RIGHT_C = (
    59, 66, 54, 60, 61, 53, 52, 62, 64, 51,
    30, 63, 32, 29, 3, 31, 28, 0, 22, 50,
)

ARITHMETIC = {
    0x400, 0x401, 0x402, 0x403, 0x404, 0x405, 0x406, 0x407,
    0x408, 0x409, 0x40A, 0x40B, 0x40C, 0x40D, 0x40E, 0x40F,
    0x420, 0x421, 0x422, 0x423, 0x424, 0x425, 0x426, 0x427, 0x46F,
}
EXACT_UOPS = {
    0x021, 0x022, 0x024, 0x02A, 0x030, 0x031, 0x032, 0x033, 0x03A,
    0x090, 0x0E0, 0x160, 0x161, 0x1C0, 0x1C6, 0x210, 0x212, 0x214,
    0x225, 0x226, 0x22F, 0x250, 0x26B, 0x290, 0x291, 0x294, 0x2D0,
    0x414, 0x415, 0x461, 0x463, 0x464, 0x466, 0x611, 0x612, 0x613,
    0x630, 0x7EB,
}
CC_BASES = {0x180, 0x240, 0x310, 0x350, 0x390, 0x3D0}
MEMORY_BASES = {0x800, 0x804, 0x840, 0x844, 0xC00, 0xC03, 0xC05, 0xC40,
                0xC43, 0xC45}
DATA_SIZES = {0x000, 0x080, 0x100, 0x200, 0x300}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def bits(value: int) -> list[int]:
    return [(value >> index) & 1 for index in range(32)]


def decode_group(words: list[int], reverse_core: bool = True) -> list[int]:
    if len(words) != 8:
        raise ValueError("one physical group must contain eight dwords")
    raw = [bits(word) for word in words]
    left = (raw[0][10:31] + raw[1][0:31] + raw[2][0:31]
            + raw[3][0:25])
    left_extra = raw[3][25:31]
    right_extra = raw[4][7:19]
    right = (raw[4][19:31] + raw[5][0:31] + raw[6][0:31]
             + raw[7][0:31])
    if len(left) != 108 or len(right) != 105:
        raise AssertionError("physical core extraction length changed")
    uops = [[0] * 72 for _ in range(3)]
    for lane in range(3):
        for source, destination in zip(
                left[36 * lane:36 * (lane + 1)], ORD_LEFT):
            uops[lane][destination] = source
        for source, destination in zip(
                right[3 * lane:3 * (lane + 1)], ORD_RIGHT_A):
            uops[lane][destination] = source
        for source, destination in zip(
                right[9 + 12 * lane:9 + 12 * (lane + 1)], ORD_RIGHT_B):
            uops[lane][destination] = source
        for source, destination in zip(
                right[45 + 20 * lane:45 + 20 * (lane + 1)], ORD_RIGHT_C):
            uops[lane][destination] = source
    uops[0][70] = right_extra[6]
    uops[1][70] = right_extra[9]
    uops[2][70] = left_extra[2]
    if reverse_core:
        uops = [list(reversed(uop)) for uop in uops]
    return [sum(bit << index for index, bit in enumerate(uop)) for uop in uops]


def parse_physical(path: Path):
    result = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        address, payload = line.split(":", 1)
        words = [int(field, 16) for field in payload.split()]
        if len(words) != 8:
            raise RuntimeError(f"{path}: physical row does not have eight dwords")
        physical_address = int(address, 16)
        if physical_address & 7:
            raise RuntimeError(f"{path}: physical group address is not 8-byte aligned")
        result[physical_address // 2] = words
    return result


def parse_logical(path: Path):
    result = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        address, payload = line.split(":", 1)
        values = [int(field, 16) for field in payload.split()]
        if len(values) != 3:
            raise RuntimeError(f"{path}: logical row does not have three uops")
        result[int(address, 16)] = values
    return result


def field(value: int, start: int, width: int) -> int:
    return (value >> start) & ((1 << width) - 1)


def recognized_opcode(opcode: int) -> str | None:
    if (opcode & 0xC7F) in ARITHMETIC and (opcode & 0x380) in DATA_SIZES:
        return "arithmetic"
    if opcode in EXACT_UOPS:
        return "exact"
    if (opcode & 0xFF0) in CC_BASES:
        return "conditional"
    if (opcode & 0xC4F) in MEMORY_BASES and (opcode & 0x380) in DATA_SIZES:
        return "memory"
    return None


def decode_fields(value: int):
    opcode = field(value, 56, 12)
    return {
        "raw72": f"{value:018X}",
        "flow": field(value, 0, 4),
        "immediate": field(value, 4, 9),
        "alias": field(value, 13, 5),
        "segment": field(value, 18, 4),
        "unknown1": field(value, 22, 1),
        "destination": field(value, 23, 8),
        "source1": field(value, 31, 8),
        "source2": field(value, 39, 8),
        "unknown2": field(value, 47, 9),
        "opcode": f"{opcode:03X}",
        "opcode_class": recognized_opcode(opcode) or "unknown",
        "opcode_alias": field(value, 68, 4),
    }


def score(values: list[int]):
    decoded = [decode_fields(value) for value in values]
    classes = Counter(row["opcode_class"] for row in decoded)
    opcodes = Counter(row["opcode"] for row in decoded)
    return {
        "uops": len(values),
        "recognized_opcodes": len(values) - classes["unknown"],
        "recognized_fraction": (
            (len(values) - classes["unknown"]) / len(values) if values else 0),
        "opcode_classes": dict(sorted(classes.items())),
        "opcode_histogram": dict(sorted(opcodes.items())),
        "unknown1_zero": sum(row["unknown1"] == 0 for row in decoded),
        "unknown2_zero": sum(row["unknown2"] == 0 for row in decoded),
        "flow_histogram": dict(sorted(Counter(
            f"{row['flow']:X}" for row in decoded).items())),
    }


def hook_destinations(patch):
    hooks = []
    controls = patch["recovery"]["decrypted_body"]["controls"]
    for control in controls:
        if control["address"] not in ("1B8", "1B9", "1BA", "1BB"):
            continue
        value = int(control["value"], 16)
        hooks.append({
            "register": control["address"],
            "source": f"{value >> 16:04X}",
            "destination": f"{value & 0xffff:04X}",
        })
    return hooks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1467", type=Path)
    parser.add_argument("later_physical", type=Path)
    parser.add_argument("later_logical", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--random-uops", type=int, default=100_000)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    physical = parse_physical(args.later_physical)
    logical = parse_logical(args.later_logical)
    if set(physical) != set(logical):
        raise RuntimeError("later physical/logical calibration addresses differ")
    mismatches = []
    later_values = []
    for address in sorted(physical):
        decoded = decode_group(physical[address], reverse_core=True)
        expected = [value & ((1 << 72) - 1) for value in logical[address]]
        later_values.extend(expected)
        for lane, (actual, wanted) in enumerate(zip(decoded, expected)):
            if actual != wanted:
                mismatches.append({
                    "address": f"{address + lane:04X}",
                    "actual": f"{actual:018X}",
                    "expected": f"{wanted:018X}",
                })
    if mismatches:
        raise RuntimeError(f"core descrambler calibration failed: {mismatches[:3]}")

    report1467 = json.loads(args.h1467.read_text())
    patch_results = {}
    for signature, patch in sorted(report1467["patches"].items()):
        decrypted = patch["recovery"].get("decrypted_body")
        groups = decrypted.get("physical_groups") if decrypted else None
        if not groups:
            patch_results[signature] = {"status": "NO_RECOVERED_BODY"}
            continue
        physical_groups = [
            [int(word, 16) for word in group["physical_dwords"]]
            for group in groups
        ]
        orientations = {}
        reversed_by_group = []
        for reverse in (True, False):
            decoded_groups = [
                decode_group(words, reverse_core=reverse)
                for words in physical_groups
            ]
            values = [value for group in decoded_groups for value in group]
            orientations["published_core" if reverse else "core_without_reversal"] = score(values)
            if reverse:
                reversed_by_group = decoded_groups
        hooks = hook_destinations(patch)
        for hook in hooks:
            destination = int(hook["destination"], 16)
            delta = destination - 0x3FAC
            if delta < 0 or delta // 4 >= len(reversed_by_group) or delta % 4 >= 3:
                hook["decoded_destination"] = "OUTSIDE_THREE_UOP_PATCH_SLOTS"
                continue
            group = delta // 4
            lane = delta % 4
            hook["decoded_destination"] = decode_fields(reversed_by_group[group][lane])
        patch_results[signature] = {
            "status": "CORE_TRANSFER_DIAGNOSTIC_ONLY",
            "physical_groups": len(physical_groups),
            "candidate_uops": len(physical_groups) * 3,
            "orientations": orientations,
            "hooks": hooks,
        }

    generator = random.Random(0x243F6A8885A308D3)
    random_values = [generator.getrandbits(72) for _ in range(args.random_uops)]
    baseline = score(random_values)
    old_scores = [
        item["orientations"]["published_core"]["recognized_fraction"]
        for item in patch_results.values()
        if item["status"] == "CORE_TRANSFER_DIAGNOSTIC_ONLY"
    ]
    later_score = score(later_values)
    maximum_old = max(old_scores)
    credible = maximum_old >= 0.5 and maximum_old >= later_score["recognized_fraction"] / 2
    report = {
        "experiment": "h1490_ppro_core_permutation_transfer",
        "status": (
            "PUBLISHED_CORE_TRANSFER_REQUIRES_FURTHER_VALIDATION"
            if credible else "PUBLISHED_CORE_TRANSFER_NOT_CREDIBLE"
        ),
        "hardware_execution": "none",
        "updates_loaded": "none",
        "capture_labels_opened": "none",
        "mapping": {
            "scope": "published later-P6 physical permutation for logical bits 0..71 only",
            "excluded": "later-P6 logical bits 72..79 and all old-format shared/control inference",
            "published_core_bit_count": 216,
        },
        "later_p6_calibration": {
            "physical_groups": len(physical),
            "uops": len(later_values),
            "lower72_mismatches": len(mismatches),
            "score": later_score,
        },
        "random_72bit_baseline": {
            "seed": "0x243f6a8885a308d3",
            **baseline,
        },
        "pentium_pro_patches": patch_results,
        "interpretation": (
            "The dependency-free mapping exactly reproduces the paired later-P6 "
            "logical fixture, but old-format outputs have no credible opcode "
            "structure relative to that calibration. The 72-bit wiring therefore "
            "cannot be transferred to Pentium Pro from these data."
            if not credible else
            "At least one old-format body has substantial opcode structure under "
            "the later-P6 core mapping, but this statistical result does not "
            "validate an old-format physical permutation."
        ),
        "claim_boundary": (
            "Opcode recognition is a diagnostic bounded by the public map. A "
            "negative result rejects this exact transfer; it does not prove that "
            "the old 72-bit uops are unrecoverable under another permutation."
        ),
        "emulator_change": "none",
        "paper_change": "none",
        "sha256": {
            "h1467": digest(args.h1467),
            "later_physical": digest(args.later_physical),
            "later_logical": digest(args.later_logical),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps({
        "output": str(args.output),
        "status": report["status"],
        "later_recognized_fraction": later_score["recognized_fraction"],
        "random_recognized_fraction": baseline["recognized_fraction"],
        "old_published_core_fractions": old_scores,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
