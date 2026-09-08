#!/usr/bin/env python3
"""Recover and compare the public Pentium Pro sibling update surfaces.

H1460 recovered the old 0x612 update without assuming a processor base key.
This companion applies the same exact control-address and GF(2) method to the
public 0x611, 0x616, 0x617, and 0x619 updates.  Four patches admit complete
physical recovery.  The reducible 0x616 control polynomial instead exposes a
precise format/cipher boundary: its controls recover and integrity-check, but
no state at physical word 14 reaches either exact control-block pre-state.

Inputs remain local public files.  The program never loads an update or runs
an x87 instruction, and it does not apply an unvalidated logical permutation.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import struct
from collections import Counter, defaultdict
from pathlib import Path

import h1460_unknown_p6_padding_key as old


DWORD = re.compile(r"0x([0-9A-Fa-f]{8})")
EXPECTED_KEYS = {
    0x611: 0xF5349300,
    0x612: 0xD8000000,
    0x616: 0x55555555,
    0x617: 0x68000000,
    0x619: 0x0037417F,
}
EXPECTED_CONTINUOUS_IV_COUNTS = {
    0x611: 1,
    0x612: 4,
    0x617: 1,
    0x619: 2,
}
PUBLIC_SOURCES = {
    0x611: (
        "https://github.com/platomav/CPUMicrocodes/blob/master/Intel/"
        "cpu00611_plat00_ver00000B27_1996-12-18_PRD_05793E46.bin"
    ),
    0x612: (
        "https://chromium.googlesource.com/chromiumos/third_party/coreboot/+/"
        "796af17f18554380a49d69d7768ac18ee039d711/src/cpu/intel/model_6xx/"
        "microcode-99-B_c6_612.h"
    ),
    0x616: (
        "https://chromium.googlesource.com/chromiumos/third_party/coreboot/+/"
        "796af17f18554380a49d69d7768ac18ee039d711/src/cpu/intel/model_6xx/"
        "microcode-51-B_c6_616.h"
    ),
    0x617: (
        "https://chromium.googlesource.com/chromiumos/third_party/coreboot/+/"
        "796af17f18554380a49d69d7768ac18ee039d711/src/cpu/intel/model_6xx/"
        "microcode-43-B_c6_617.h"
    ),
    0x619: (
        "https://chromium.googlesource.com/chromiumos/third_party/coreboot/+/"
        "796af17f18554380a49d69d7768ac18ee039d711/src/cpu/intel/model_6xx/"
        "microcode-153-d2_619.h"
    ),
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def words_digest(words: tuple[int, ...] | list[int]) -> str:
    return digest(struct.pack(f"<{len(words)}I", *words))


def load_public_patch(path: Path) -> tuple[bytes, tuple[int, ...]]:
    """Load either a packed 2 KiB update or a base64-encoded C header."""

    source = path.read_bytes()
    if len(source) == old.SEGMENT_SIZE:
        data = source
    else:
        try:
            header = base64.b64decode(source, validate=True).decode()
        except (ValueError, UnicodeDecodeError) as error:
            raise RuntimeError(f"unsupported public patch input {path}") from error
        words = tuple(int(item, 16) for item in DWORD.findall(header))
        if len(words) != 512:
            raise RuntimeError(
                f"expected 512 header dwords in {path}, found {len(words)}"
            )
        data = struct.pack("<512I", *words)

    if len(data) != old.SEGMENT_SIZE:
        raise RuntimeError(f"expected one 2048-byte update in {path}")
    words = struct.unpack("<512I", data)
    if words[0] != 1 or sum(words) & 0xFFFFFFFF:
        raise RuntimeError(f"invalid Intel update header/checksum in {path}")
    signature = words[3] & 0xFFFF
    if signature not in EXPECTED_KEYS:
        raise RuntimeError(f"unexpected processor signature 0x{signature:X}")
    return data, words


def source_record(path: Path, data: bytes, words: tuple[int, ...]) -> dict[str, object]:
    signature = words[3] & 0xFFFF
    return {
        "input_name": path.name,
        "packed_patch_sha256": digest(data),
        "public_source_url": PUBLIC_SOURCES[signature],
        "header": {
            "header_version": words[0],
            "revision": f"{words[1]:08X}",
            "date": f"{words[2]:08X}",
            "signature": f"{words[3]:08X}",
            "checksum": f"{words[4]:08X}",
            "platform_flags": f"{words[6]:08X}",
            "standard_checksum_ok": True,
        },
    }


def key_surface(words: tuple[int, ...], fprom: dict[int, int]) -> tuple[int, dict[str, object]]:
    rankings = old.rank_fprom_keys(words, fprom)
    winner = rankings[0]
    key = int(str(winner["key"]), 16)
    signature = words[3] & 0xFFFF
    if key != EXPECTED_KEYS[signature]:
        raise RuntimeError(
            f"unexpected key for 0x{signature:X}: 0x{key:08X}"
        )
    histogram = Counter(int(row["zero_mask_records"]) for row in rankings)
    return key, {
        "method": (
            "exact zero-mask address equation over every distinct public FPROM value"
        ),
        "winner": winner,
        "runner_up_score": int(rankings[1]["zero_mask_records"]),
        "score_histogram": {
            str(score): count for score, count in sorted(histogram.items())
        },
    }


def physical_groups(msram: tuple[int, ...]) -> list[dict[str, object]]:
    return [
        {
            "group": group,
            "candidate_patch_addresses": [
                f"{old.PATCH_ADDRESS_MIN + 4 * group + slot:04X}"
                for slot in range(3)
            ],
            "physical_dwords": [
                f"{word:08X}" for word in msram[group * 8 : group * 8 + 8]
            ],
        }
        for group in range(old.MSRAM_DWORDS // 8)
    ]


def decoded_controls(
    plaintext: tuple[int, ...], states: tuple[int, ...], fprom: dict[int, int]
) -> tuple[dict[str, object], ...]:
    controls = []
    for record in range(old.CONTROL_COUNT):
        relative = 4 * record
        address, mask, value, integrity = plaintext[relative : relative + 4]
        index = states[relative + 2] & 0xFF
        expected = fprom[index]
        controls.append(
            {
                "record": record,
                "address": f"{address:03X}",
                "mask": f"{mask:08X}",
                "value": f"{value:08X}",
                "integrity_index": f"{index:02X}",
                "integrity_got": f"{integrity:08X}",
                "integrity_expected": f"{expected:08X}",
                "integrity_ok": integrity == expected,
            }
        )
    return tuple(controls)


def decrypt_control_block(
    words: tuple[int, ...], key: int, state: int, fprom: dict[int, int]
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[dict[str, object], ...]]:
    last_ciphertext = words[old.CONTROL_START - 1]
    plaintext = []
    states = []
    for ciphertext in words[old.CONTROL_START : old.STREAM_STOP]:
        state = old.u32(old.block_function(state, key) ^ ciphertext)
        plaintext.append(old.u32(state ^ last_ciphertext))
        states.append(state)
        last_ciphertext = ciphertext
    result = (tuple(plaintext), tuple(states))
    return (*result, decoded_controls(*result, fprom))


def solved_anchor_spaces(
    words: tuple[int, ...], key: int, winner: dict[str, object]
) -> tuple[dict[str, object], ...]:
    ciphertext = words[old.STREAM_START : old.STREAM_STOP]
    rows = []
    for record, candidates in enumerate(winner["address_candidates"]):
        if not candidates:
            continue
        mask_word = old.CONTROL_START + 4 * record + 1
        try:
            particular, nullspace = old.affine_solution_space(
                ciphertext,
                key,
                mask_word - old.STREAM_START,
                words[mask_word - 1],
            )
        except RuntimeError:
            rows.append({"record": record, "status": "UNSAT"})
            continue
        rows.append(
            {
                "record": record,
                "status": "SAT",
                "particular": f"{particular:08X}",
                "nullspace_basis": [f"{item:08X}" for item in nullspace],
                "free_bits": len(nullspace),
            }
        )
    return tuple(rows)


def recover_continuous(
    words: tuple[int, ...], key: int, key_report: dict[str, object], fprom: dict[int, int]
) -> dict[str, object]:
    winner = key_report["winner"]
    spaces = solved_anchor_spaces(words, key, winner)
    sat_spaces = {
        (
            int(str(row["particular"]), 16),
            tuple(int(str(item), 16) for item in row["nullspace_basis"]),
        )
        for row in spaces
        if row["status"] == "SAT"
    }
    if len(sat_spaces) != 1 or any(row["status"] != "SAT" for row in spaces):
        raise RuntimeError("continuous patch anchors do not yield one affine IV class")
    particular, nullspace = next(iter(sat_spaces))
    candidates = old.enumerate_affine_space(particular, nullspace)
    decryptions = []
    for iv in candidates:
        plaintext, states = old.decrypt_stream(words, key, iv)
        controls = old.parse_controls(plaintext, states, fprom)
        index = states[old.MSRAM_UNKNOWN - old.STREAM_START] & 0xFF
        integrity = plaintext[old.MSRAM_INTEGRITY - old.STREAM_START]
        if integrity != fprom[index]:
            continue
        if not all(bool(control["integrity_ok"]) for control in controls):
            continue
        decryptions.append((iv, plaintext, states, controls))

    signature = words[3] & 0xFFFF
    if len(decryptions) != EXPECTED_CONTINUOUS_IV_COUNTS[signature]:
        raise RuntimeError(
            f"unexpected exact IV count for 0x{signature:X}: {len(decryptions)}"
        )
    reference = decryptions[0][1]
    varying_words = [
        index
        for index in range(len(reference))
        if len({item[1][index] for item in decryptions}) > 1
    ]
    controls = decryptions[0][3]
    if any(item[3] != controls for item in decryptions[1:]):
        raise RuntimeError("IV representatives disagree on decoded controls")
    msram = reference[: old.MSRAM_DWORDS]
    return {
        "status": "exact_continuous_physical_recovery",
        "anchor_spaces": list(spaces),
        "iv_equivalence_class": {
            "particular": f"{particular:08X}",
            "nullspace_basis": [f"{item:08X}" for item in nullspace],
            "validated_representatives": [
                f"{item[0]:08X}" for item in decryptions
            ],
            "representative_count": len(decryptions),
            "varying_stream_relative_words": varying_words,
            "varying_physical_words": [
                old.STREAM_START + index for index in varying_words
            ],
        },
        "decrypted_body": {
            "canonical_physical_words_14_through_227_sha256": words_digest(reference),
            "canonical_msram_words_14_through_165_sha256": words_digest(msram),
            "physical_groups": physical_groups(msram),
            "msram_integrity": {
                "index": f"{decryptions[0][2][old.MSRAM_UNKNOWN - old.STREAM_START] & 0xFF:02X}",
                "got": f"{reference[old.MSRAM_INTEGRITY - old.STREAM_START]:08X}",
                "expected": f"{fprom[decryptions[0][2][old.MSRAM_UNKNOWN - old.STREAM_START] & 0xFF]:08X}",
                "ok": True,
            },
            "controls": list(controls),
            "integrity_checks_passed": 16,
            "integrity_checks_total": 16,
        },
    }


def recover_616_controls(
    words: tuple[int, ...], key: int, key_report: dict[str, object], fprom: dict[int, int]
) -> dict[str, object]:
    winner = key_report["winner"]
    spaces = solved_anchor_spaces(words, key, winner)
    control_ciphertext = words[old.CONTROL_START : old.STREAM_STOP]
    record_zero_mask = 1
    particular, nullspace = old.affine_solution_space(
        control_ciphertext,
        key,
        record_zero_mask,
        words[old.CONTROL_START],
    )
    local_states = old.enumerate_affine_space(particular, nullspace)
    expected_address = int(str(winner["address_candidates"][0][0]), 16)
    validated = []
    for state in local_states:
        plaintext, states, controls = decrypt_control_block(words, key, state, fprom)
        if int(str(controls[0]["address"]), 16) != expected_address:
            continue
        if not all(bool(control["integrity_ok"]) for control in controls):
            continue
        validated.append((state, plaintext, states, controls))
    if len(validated) != 2:
        raise RuntimeError(f"expected two exact 0x616 control states, got {len(validated)}")
    controls = validated[0][3]
    if any(item[3] != controls for item in validated[1:]):
        raise RuntimeError("0x616 control-state representatives disagree")

    continuity = []
    msram_prefix = words[old.STREAM_START : old.CONTROL_START]
    for state, _, _, _ in validated:
        try:
            old.affine_solution_space(
                msram_prefix, key, len(msram_prefix) - 1, state
            )
        except RuntimeError:
            continuity.append(
                {
                    "control_pre_state": f"{state:08X}",
                    "physical_word_14_preimage": "UNSAT",
                }
            )
        else:
            raise RuntimeError("unexpected continuous 0x616 state preimage")

    return {
        "status": "exact_controls_only_continuous_msram_recovery_unsat",
        "full_stream_anchor_spaces": list(spaces),
        "control_block_state_equivalence_class": {
            "particular_before_address_constraint": f"{particular:08X}",
            "nullspace_before_address_constraint": [
                f"{item:08X}" for item in nullspace
            ],
            "architectural_first_address": f"{expected_address:03X}",
            "validated_pre_states": [f"{item[0]:08X}" for item in validated],
            "representative_count": len(validated),
        },
        "continuity_wall": continuity,
        "controls": list(controls),
        "control_integrity_checks_passed": 15,
        "control_integrity_checks_total": 15,
        "msram": {
            "status": "unrecovered",
            "reason": (
                "under the public 37-clock transform and exact control key, no "
                "state before physical word 14 reaches either validated state "
                "before physical word 168"
            ),
        },
    }


def control_triplets(report: dict[str, object]) -> tuple[tuple[str, str, str], ...]:
    body = report["recovery"]
    controls = (
        body["decrypted_body"]["controls"]
        if body["status"] == "exact_continuous_physical_recovery"
        else body["controls"]
    )
    return tuple(
        (str(row["address"]), str(row["mask"]), str(row["value"]))
        for row in controls
    )


def build_report(
    patch_paths: tuple[Path, ...], fprom_path: Path
) -> dict[str, object]:
    if len(patch_paths) != len(EXPECTED_KEYS):
        raise RuntimeError("provide exactly the five 0x611/612/616/617/619 updates")
    fprom = old.load_fprom(fprom_path)
    reports: dict[int, dict[str, object]] = {}
    for path in patch_paths:
        data, words = load_public_patch(path)
        signature = words[3] & 0xFFFF
        if signature in reports:
            raise RuntimeError(f"duplicate processor signature 0x{signature:X}")
        key, key_report = key_surface(words, fprom)
        recovery = (
            recover_616_controls(words, key, key_report, fprom)
            if signature == 0x616
            else recover_continuous(words, key, key_report, fprom)
        )
        reports[signature] = {
            **source_record(path, data, words),
            "control_key": f"{key:08X}",
            "key_recovery": key_report,
            "recovery": recovery,
        }
    if set(reports) != set(EXPECTED_KEYS):
        raise RuntimeError("the five required processor signatures were not supplied")

    p612 = reports[0x612]["recovery"]["decrypted_body"]
    p617 = reports[0x617]["recovery"]["decrypted_body"]
    m612 = tuple(
        int(word, 16)
        for group in p612["physical_groups"]
        for word in group["physical_dwords"]
    )
    m617 = tuple(
        int(word, 16)
        for group in p617["physical_groups"]
        for word in group["physical_dwords"]
    )
    differences = [index for index, pair in enumerate(zip(m612, m617)) if pair[0] != pair[1]]
    c612 = control_triplets(reports[0x612])
    c617 = control_triplets(reports[0x617])

    return {
        "query": "old_pentium_pro_sibling_patch_recovery",
        "status": "four_exact_physical_recoveries_one_exact_control_only_boundary",
        "method": {
            "cipher": "public 37-clock P6 LFSR block transform",
            "key": "exact local zero-mask architectural-control equations",
            "state": "exact GF(2) affine preimages",
            "validation": "encrypted FPROM integrity words",
        },
        "dependencies": {
            "fprom_name": fprom_path.name,
            "fprom_sha256": digest(fprom_path.read_bytes()),
            "h1460_source_sha256": digest(Path(old.__file__).read_bytes()),
        },
        "patches": {f"{signature:03X}": reports[signature] for signature in sorted(reports)},
        "sibling_comparison": {
            "c6_612_617_first_ten_control_triplets_identical": c612[:10] == c617[:10],
            "c6_612_617_last_five_control_triplets_identical": c612[10:] == c617[10:],
            "c6_612_617_msram_differences": len(differences),
            "c6_612_617_msram_equalities": old.MSRAM_DWORDS - len(differences),
            "c6_612_617_differing_physical_word_offsets": differences,
        },
        "interpretation_boundary": {
            "complete_physical_plaintext_signatures": ["611", "612", "617", "619"],
            "control_only_signature": "616",
            "logical_uops": (
                "not claimed: no validated Pentium Pro physical-to-logical permutation"
            ),
            "absolute_base_rom": "not recovered",
            "r59_selector": "none",
            "emulator_change": "none",
        },
        "execution": {
            "hardware": "none",
            "x87_instructions": "none",
            "capture_labels_opened": "none",
            "private_capture_ledger": "not accessed",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--patch", action="append", type=Path, required=True)
    parser.add_argument("--fprom-data", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = build_report(tuple(arguments.patch), arguments.fprom_data)
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
                "report_sha256": digest(text.encode()),
                "hardware": "none",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
