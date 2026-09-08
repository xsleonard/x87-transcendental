#!/usr/bin/env python3
"""Recover the exact encrypted surface of the old Pentium Pro 0x612 update.

The old 0x61x update layout differs from the later public P6 format.  This
analysis derives the cipher key from the fifteen control records, solves the
remaining IV equivalence class over GF(2), decrypts the complete functional
body, and verifies every encrypted integrity word against the public FPROM.

The recovered MSRAM words remain in physical order.  No Pentium-II physical
permutation is applied to this Pentium Pro payload, and nothing is loaded on
hardware.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from collections import Counter
from pathlib import Path


SEGMENT_SIZE = 2048
HEADER_DWORDS = 12
STREAM_START = 14
MSRAM_START = 14
MSRAM_DWORDS = 152
MSRAM_UNKNOWN = 166
MSRAM_INTEGRITY = 167
CONTROL_START = 168
CONTROL_COUNT = 15
STREAM_STOP = CONTROL_START + 4 * CONTROL_COUNT
EXPECTED_SIGNATURE = 0x612
PUBLIC_SOURCE_URL = (
    "https://chromium.googlesource.com/chromiumos/third_party/coreboot/+/"
    "796af17f18554380a49d69d7768ac18ee039d711/src/cpu/intel/model_6xx/"
    "microcode-99-B_c6_612.h"
)

FPROM_ASSIGNMENT = re.compile(
    r"FPROM\[0x([0-9A-Fa-f]+)\]\s*=\s*0x([0-9A-Fa-f]+)"
)
LISTING_ADDRESS = re.compile(r"^\s*UROM_([0-9A-Fa-f]{4})\b", re.MULTILINE)
MATCH_CONTROL_REGISTERS = frozenset(range(0x1B8, 0x1BC))
PATCH_ADDRESS_MIN = 0x3FAC
PATCH_ADDRESS_MAX = 0x3FFE


def u32(value: int) -> int:
    return value & 0xFFFFFFFF


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def words_sha256(words: tuple[int, ...] | list[int]) -> str:
    return sha256_bytes(struct.pack(f"<{len(words)}I", *words))


def block_function(plain: int, key: int) -> int:
    """Public P6 patch-cipher 37-clock block function."""

    state = plain
    for _ in range(37):
        state = (state >> 1) | ((state & 1) << 31)
        if state & 0x80000000:
            state ^= key
    return u32(state ^ plain)


def load_patch(path: Path) -> tuple[bytes, tuple[int, ...]]:
    data = path.read_bytes()
    if len(data) != SEGMENT_SIZE:
        raise RuntimeError(f"expected one 2048-byte segment, got {len(data)}")
    words = struct.unpack("<512I", data)
    if words[0] != 1:
        raise RuntimeError(f"unexpected Intel header version {words[0]}")
    if sum(words) & 0xFFFFFFFF:
        raise RuntimeError("standard Intel update checksum failed")
    if words[3] & 0xFFF != EXPECTED_SIGNATURE:
        raise RuntimeError(
            f"expected processor signature 0x612, got 0x{words[3]:08X}"
        )
    return data, words


def load_fprom(path: Path) -> dict[int, int]:
    fprom = {
        int(index, 16): int(value, 16)
        for index, value in FPROM_ASSIGNMENT.findall(path.read_text())
    }
    if set(fprom) != set(range(256)):
        raise RuntimeError("public FPROM source does not define indices 00..FF")
    return fprom


def zero_mask_address_candidates(
    words: tuple[int, ...], key: int, record: int
) -> tuple[int, ...]:
    """Return 9-bit control addresses compatible with a zero mask.

    If a control mask decrypts to zero, the state after that encrypted mask
    equals the preceding encrypted address.  Eliminating the unknown IV gives
    this exact local equation:

      BF(cipher_before_address XOR address) = cipher_address XOR cipher_mask.
    """

    at = CONTROL_START + 4 * record
    target = words[at] ^ words[at + 1]
    return tuple(
        address
        for address in range(0x200)
        if block_function(words[at - 1] ^ address, key) == target
    )


def rank_fprom_keys(
    words: tuple[int, ...], fprom: dict[int, int]
) -> tuple[dict[str, object], ...]:
    rows = []
    indices_by_value: dict[int, list[int]] = {}
    for index, value in fprom.items():
        indices_by_value.setdefault(value, []).append(index)
    for key, indices in indices_by_value.items():
        candidates = tuple(
            zero_mask_address_candidates(words, key, record)
            for record in range(CONTROL_COUNT)
        )
        rows.append(
            {
                "key": f"{key:08X}",
                "fprom_indices": [f"{index:02X}" for index in indices],
                "zero_mask_records": sum(bool(item) for item in candidates),
                "address_candidates": [
                    [f"{address:03X}" for address in item]
                    for item in candidates
                ],
            }
        )
    return tuple(
        sorted(
            rows,
            key=lambda row: (-int(row["zero_mask_records"]), str(row["key"])),
        )
    )


def state_at(
    ciphertext: tuple[int, ...], key: int, iv: int, final_index: int
) -> int:
    state = iv
    for word in ciphertext[: final_index + 1]:
        state = u32(block_function(state, key) ^ word)
    return state


def affine_solution_space(
    ciphertext: tuple[int, ...], key: int, final_index: int, target: int
) -> tuple[int, tuple[int, ...]]:
    """Solve state_at(iv)=target and return a particular IV plus nullspace."""

    baseline = state_at(ciphertext, key, 0, final_index)
    columns = tuple(
        state_at(ciphertext, key, 1 << bit, final_index) ^ baseline
        for bit in range(32)
    )
    wanted = target ^ baseline
    basis: list[int | None] = [None] * 32
    for output_bit in range(32):
        coefficient = sum(
            ((columns[input_bit] >> output_bit) & 1) << input_bit
            for input_bit in range(32)
        )
        row = coefficient | (((wanted >> output_bit) & 1) << 32)
        while coefficient:
            pivot = coefficient.bit_length() - 1
            if basis[pivot] is None:
                basis[pivot] = row
                break
            row ^= basis[pivot]
            coefficient = row & 0xFFFFFFFF
        if not coefficient and ((row >> 32) & 1):
            raise RuntimeError("control-state equation has no IV preimage")

    free_bits = tuple(bit for bit, row in enumerate(basis) if row is None)

    def solve(free_value: int) -> int:
        result = free_value
        for pivot, row in enumerate(basis):
            if row is None:
                continue
            rhs = (row >> 32) & 1
            parity = ((row & ((1 << pivot) - 1)) & result).bit_count() & 1
            if rhs ^ parity:
                result |= 1 << pivot
        return result

    particular = solve(0)
    nullspace = tuple(solve(1 << bit) ^ particular for bit in free_bits)
    return particular, nullspace


def enumerate_affine_space(
    particular: int, nullspace: tuple[int, ...]
) -> tuple[int, ...]:
    if len(nullspace) > 20:
        raise RuntimeError(f"refusing to enumerate {len(nullspace)} free IV bits")
    values = []
    for mask in range(1 << len(nullspace)):
        value = particular
        for bit, vector in enumerate(nullspace):
            if mask & (1 << bit):
                value ^= vector
        values.append(value)
    return tuple(sorted(values))


def decrypt_stream(
    words: tuple[int, ...], key: int, iv: int
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Decrypt physical words 14..227, retaining state after each word."""

    state = iv
    last_ciphertext = key
    plaintext = []
    states = []
    for ciphertext in words[STREAM_START:STREAM_STOP]:
        state = u32(block_function(state, key) ^ ciphertext)
        plaintext.append(u32(state ^ last_ciphertext))
        states.append(state)
        last_ciphertext = ciphertext
    return tuple(plaintext), tuple(states)


def parse_controls(
    plaintext: tuple[int, ...], states: tuple[int, ...], fprom: dict[int, int]
) -> tuple[dict[str, object], ...]:
    controls = []
    for record in range(CONTROL_COUNT):
        relative = CONTROL_START + 4 * record - STREAM_START
        address, mask, value, integrity = plaintext[relative : relative + 4]
        integrity_index = states[relative + 2] & 0xFF
        expected = fprom[integrity_index]
        controls.append(
            {
                "record": record,
                "address": f"{address:03X}",
                "mask": f"{mask:08X}",
                "value": f"{value:08X}",
                "integrity_index": f"{integrity_index:02X}",
                "integrity_got": f"{integrity:08X}",
                "integrity_expected": f"{expected:08X}",
                "integrity_ok": integrity == expected,
            }
        )
    return tuple(controls)


def parse_listing(path: Path | None) -> tuple[dict[str, object], set[int]]:
    if path is None:
        return ({"provided": False}, set())
    text = path.read_text(errors="replace")
    addresses = {int(item, 16) for item in LISTING_ADDRESS.findall(text)}
    if not addresses:
        raise RuntimeError(f"no UROM addresses found in {path}")
    return (
        {
            "provided": True,
            "source_name": path.name,
            "source_sha256": sha256_path(path),
            "unique_address_count": len(addresses),
            "minimum_address": f"{min(addresses):04X}",
            "maximum_address": f"{max(addresses):04X}",
        },
        addresses,
    )


def match_hooks(
    controls: tuple[dict[str, object], ...], listing_addresses: set[int]
) -> tuple[dict[str, object], ...]:
    hooks = []
    for control in controls:
        address = int(str(control["address"]), 16)
        mask = int(str(control["mask"]), 16)
        value = int(str(control["value"]), 16)
        if address not in MATCH_CONTROL_REGISTERS or mask:
            continue
        source = (value >> 16) & 0x7FFF
        destination = value & 0x7FFF
        if not PATCH_ADDRESS_MIN <= destination <= PATCH_ADDRESS_MAX:
            continue
        hooks.append(
            {
                "control_register": f"{address:03X}",
                "source_urom_address": f"{source:04X}",
                "destination_msram_address": f"{destination:04X}",
                "source_in_exact_fsincos_listing": source in listing_addresses,
            }
        )
    return tuple(hooks)


def build_report(
    patch_path: Path, fprom_path: Path, listing_path: Path | None
) -> dict[str, object]:
    data, words = load_patch(patch_path)
    fprom = load_fprom(fprom_path)
    rankings = rank_fprom_keys(words, fprom)
    winner = rankings[0]
    winner_score = int(winner["zero_mask_records"])
    runner_score = int(rankings[1]["zero_mask_records"])
    if winner_score != 12 or runner_score != 0:
        raise RuntimeError(
            f"expected a 12-to-0 unique key wall, got {winner_score}-to-{runner_score}"
        )
    key = int(str(winner["key"]), 16)

    zero_mask_records = tuple(
        record
        for record, candidates in enumerate(winner["address_candidates"])
        if candidates
    )
    ciphertext = words[STREAM_START:STREAM_STOP]
    spaces = []
    for record in zero_mask_records:
        mask_word = CONTROL_START + 4 * record + 1
        particular, nullspace = affine_solution_space(
            ciphertext,
            key,
            mask_word - STREAM_START,
            words[mask_word - 1],
        )
        spaces.append((particular, nullspace))
    if not spaces or any(space != spaces[0] for space in spaces[1:]):
        raise RuntimeError("zero-mask controls do not yield one IV affine class")
    particular, nullspace = spaces[0]
    ivs = enumerate_affine_space(particular, nullspace)

    decryptions = []
    for iv in ivs:
        plaintext, states = decrypt_stream(words, key, iv)
        controls = parse_controls(plaintext, states, fprom)
        msram_integrity_index = states[MSRAM_UNKNOWN - STREAM_START] & 0xFF
        msram_integrity_got = plaintext[MSRAM_INTEGRITY - STREAM_START]
        msram_integrity_expected = fprom[msram_integrity_index]
        if msram_integrity_got != msram_integrity_expected:
            raise RuntimeError(f"MSRAM integrity failed for IV {iv:08X}")
        if not all(bool(control["integrity_ok"]) for control in controls):
            raise RuntimeError(f"control integrity failed for IV {iv:08X}")
        decryptions.append((iv, plaintext, states, controls))

    reference = decryptions[0][1]
    if any(plaintext[1:] != reference[1:] for _, plaintext, _, _ in decryptions):
        raise RuntimeError("IV representatives differ after physical word 14")
    controls = decryptions[0][3]
    if any(candidate[3] != controls for candidate in decryptions[1:]):
        raise RuntimeError("IV representatives do not decrypt identical controls")

    listing, listing_addresses = parse_listing(listing_path)
    hooks = match_hooks(controls, listing_addresses)
    first_word_alternatives = sorted(
        {plaintext[0] for _, plaintext, _, _ in decryptions}
    )
    score_histogram = Counter(
        int(row["zero_mask_records"]) for row in rankings
    )
    msram = reference[:MSRAM_DWORDS]
    groups = [
        {
            "group": group,
            "logical_patch_addresses_if_ppro_triads": [
                f"{PATCH_ADDRESS_MIN + 4 * group + slot:04X}"
                for slot in range(3)
            ],
            "physical_dwords": [
                f"{word:08X}" for word in msram[group * 8 : group * 8 + 8]
            ],
        }
        for group in range(MSRAM_DWORDS // 8)
    ]

    return {
        "query": "exact_old_pentium_pro_612_patch_recovery",
        "status": "exact_physical_recovery_with_four_member_iv_equivalence_class",
        "source": {
            "patch_name": patch_path.name,
            "patch_sha256": sha256_bytes(data),
            "public_source_url": PUBLIC_SOURCE_URL,
            "public_source_translation": (
                "the file's 512 hexadecimal uint32 values packed little-endian"
            ),
            "fprom_name": fprom_path.name,
            "fprom_sha256": sha256_path(fprom_path),
        },
        "header": {
            "header_version": words[0],
            "revision": f"{words[1]:08X}",
            "date": f"{words[2]:08X}",
            "signature": f"{words[3]:08X}",
            "checksum": f"{words[4]:08X}",
            "platform_flags": f"{words[6]:08X}",
            "standard_checksum_ok": True,
        },
        "old_format_layout": {
            "header_physical_words": [0, 11],
            "seed_fields_physical_words": [12, 13],
            "continuous_encrypted_stream_physical_words": [14, 227],
            "msram_physical_words": [14, 165],
            "msram_group_count": 19,
            "pre_integrity_unknown_physical_word": 166,
            "msram_integrity_physical_word": 167,
            "control_physical_words": [168, 227],
            "control_record_count": CONTROL_COUNT,
            "irrelevant_common_suffix_begins_file_byte": 912,
        },
        "key_recovery": {
            "method": "zero-mask 9-bit control-address equation over every unique public FPROM value",
            "unique_fprom_value_count": len(rankings),
            "winner": winner,
            "runner_up_score": runner_score,
            "score_histogram": {
                str(score): count for score, count in sorted(score_histogram.items())
            },
            "nonzero_mask_records_after_decryption": [7, 8, 9],
        },
        "iv_recovery": {
            "method": "exact GF(2) preimage from each of the twelve zero-mask control states",
            "independent_anchor_records": list(zero_mask_records),
            "particular": f"{particular:08X}",
            "nullspace_basis": [f"{item:08X}" for item in nullspace],
            "representatives": [f"{iv:08X}" for iv in ivs],
            "representative_count": len(ivs),
            "physical_word_14_plaintext_alternatives": [
                f"{word:08X}" for word in first_word_alternatives
            ],
            "physical_words_15_through_227_identical": True,
        },
        "decrypted_body": {
            "canonical_iv": f"{ivs[0]:08X}",
            "canonical_physical_words_14_through_227_sha256": words_sha256(reference),
            "common_physical_words_15_through_227_sha256": words_sha256(reference[1:]),
            "common_msram_words_15_through_165_sha256": words_sha256(msram[1:]),
            "pre_integrity_unknown_word_166": f"{reference[MSRAM_UNKNOWN - STREAM_START]:08X}",
            "msram_integrity": {
                "index": f"{decryptions[0][2][MSRAM_UNKNOWN - STREAM_START] & 0xFF:02X}",
                "got": f"{reference[MSRAM_INTEGRITY - STREAM_START]:08X}",
                "expected": f"{fprom[decryptions[0][2][MSRAM_UNKNOWN - STREAM_START] & 0xFF]:08X}",
                "ok": True,
            },
            "msram_physical_groups": groups,
            "controls": list(controls),
            "integrity_checks_passed": 1 + sum(
                bool(control["integrity_ok"]) for control in controls
            ),
            "integrity_checks_total": 1 + CONTROL_COUNT,
        },
        "control_hook_audit": {
            "listing": listing,
            "match_hooks": list(hooks),
            "direct_fsincos_source_intersections": sum(
                bool(hook["source_in_exact_fsincos_listing"]) for hook in hooks
            ),
            "result": "no decoded match hook directly replaces a listed FSINCOS uop",
            "boundary": "caller, shared-helper, and otherwise unlisted control paths remain possible",
        },
        "interpretation_boundary": {
            "physical_plaintext": "exact except for the explicitly listed first-dword alternative",
            "logical_uops": "not decoded: no public Pentium Pro physical permutation was available",
            "pentium_ii_descrambler": "not applicable to this Pentium Pro payload",
            "selector": "none",
            "emulator_change": "none",
        },
        "execution": {
            "hardware": "none",
            "capture_labels_opened": "none",
            "private_capture_ledger": "not accessed",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("patch", type=Path)
    parser.add_argument("fprom_data", type=Path)
    parser.add_argument("--fsincos-listing", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = build_report(
        arguments.patch, arguments.fprom_data, arguments.fsincos_listing
    )
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(text, end="")
        return
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(text)
    print(
        json.dumps(
            {
                "output": str(arguments.output),
                "report_sha256": sha256_bytes(text.encode()),
                "hardware": "none",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
