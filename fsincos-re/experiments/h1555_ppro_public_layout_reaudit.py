#!/usr/bin/env python3
"""Reaudit recovered Pentium Pro updates against the public 7-dword layout.

The 2025 ruikruik/patchtools_pub Pentium Pro support publishes three facts
that were absent from the earlier Peter Bosch tree used by H1460/H1467:

* the Pentium Pro MSRAM payload has 148 dwords, arranged as 21 complete
  seven-dword physical groups plus one spare dword;
* its MSRAM integrity word is body-relative dword 150, followed by one
  skipped trap dword; and
* sixteen four-dword CRBUS records follow, rather than fifteen records after
  a 152-dword MSRAM payload.

This script independently replays that source-published layout and cipher on
the five exact public 0x61x files used by H1467.  It also invokes the compiled
public tool when requested and measures where the older H1467 interpretation
diverges.  It never loads an update or executes an x87 instruction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import subprocess
from itertools import combinations
from pathlib import Path


EXPECTED_INPUTS = {
    0x611: "3d963b50eef0867008a1c767c514214a21426922c0b02cad0f4848e81d7732df",
    0x612: "b411ab12fca67bef7103ea75c07adc8dbb53b4a966bb619ca32012b26eac7db1",
    0x616: "3b8ad8d55fc1f7fffb46efa77de1dbdc498d5f21d132bedbdeb285bfcb28faaf",
    0x617: "8fa7bcc2d450c2ac810648201a14ce6bcc0883840eb46975fa04ed1dfeabd678",
    0x619: "a513f9c3b37b98550323f7afb257cc08469b1597a0318bb65339b9fedca5921d",
}

EXPECTED_SOURCE_HASHES = {
    "README.md": "ef1c4f1decda00df0bf7577e8bb81eb75b3c30250981624fa9bcc93a52aa0e01",
    "cpukeys.c": "7e1bd2a0a9c2efbf092fbc5122de4bcb80866c90b8b21ad33c35142fda58f643",
    "crypto.c": "8fae236fda7dc147715cba248de0103967d2d195feb1d5151fbdb39063240123",
    "fprom_data.c": "758ce01ac9a4cbd37c3d847186f1f287a50d1818eb7b213221cc464a43681bb5",
    "patchfile.c": "55faefdff39c56896d83c3600da8247a3ef47bbc8603428fc566e216316d2605",
}

SOURCE_COMMIT = "4c05693873e93a662fb49e47d9c29c6947ef6151"
SOURCE_URL = f"https://github.com/ruikruik/patchtools_pub/tree/{SOURCE_COMMIT}"

# Values transcribed from cpukeys.c at SOURCE_COMMIT.  The source hashes above
# make this a pinned replay rather than a guessed key table.
PPRO_BASE_KEYS = {
    0x611: 0x28D4FC58,  # CPU_KEY_PPRO_B0
    0x612: 0x715F1F2F,  # CPU_KEY_PPRO_A0
    0x616: 0x715F1F2F,
    0x617: 0x715F1F2F,
    0x619: 0x61DAB85E,  # CPU_KEY_PPRO_B1
}

FPROM_ASSIGNMENT = re.compile(
    r"FPROM\[0x([0-9A-Fa-f]+)\]\s*=\s*0x([0-9A-Fa-f]+)"
)

HEADER_DWORDS = 12
BODY_START = HEADER_DWORDS
KEY_SEED_BODY_OFFSET = 0
MSRAM_BODY_OFFSET = 2
MSRAM_DWORDS = 0x4A * 2
MSRAM_GROUP_DWORDS = 7
MSRAM_GROUPS = 21
MSRAM_SPARE_DWORDS = 1
MSRAM_INTEGRITY_BODY_OFFSET = MSRAM_BODY_OFFSET + MSRAM_DWORDS
TRAP_BODY_OFFSET = MSRAM_INTEGRITY_BODY_OFFSET + 1
CONTROL_BODY_OFFSET = MSRAM_INTEGRITY_BODY_OFFSET + 2
CONTROL_COUNT = 16


def u32(value: int) -> int:
    return value & 0xFFFFFFFF


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def words_sha256(words: list[int] | tuple[int, ...]) -> str:
    return sha256_bytes(struct.pack(f"<{len(words)}I", *words))


def rotl32(value: int, count: int) -> int:
    count &= 31
    return u32((value << count) | (value >> ((32 - count) & 31)))


def block_function(plain: int, key: int) -> int:
    state = plain
    for _ in range(37):
        state = (state >> 1) | ((state & 1) << 31)
        if state & 0x80000000:
            state ^= key
    return u32(state ^ plain)


class Cipher:
    def __init__(self, key: int, iv: int) -> None:
        self.key = key
        self.last_ciphertext = key
        self.state = iv

    def decrypt(self, ciphertext: int) -> int:
        self.state = u32(block_function(self.state, self.key) ^ ciphertext)
        plaintext = u32(self.state ^ self.last_ciphertext)
        self.last_ciphertext = ciphertext
        return plaintext


def load_fprom(path: Path) -> dict[int, int]:
    table = {
        int(index, 16): int(value, 16)
        for index, value in FPROM_ASSIGNMENT.findall(path.read_text())
    }
    if set(table) != set(range(256)):
        raise RuntimeError("pinned public FPROM does not define indices 00..FF")
    return table


def load_patch(path: Path) -> tuple[bytes, tuple[int, ...]]:
    data = path.read_bytes()
    if len(data) != 2048:
        raise RuntimeError(f"{path}: expected 2048 bytes, got {len(data)}")
    words = struct.unpack("<512I", data)
    if words[0] != 1:
        raise RuntimeError(f"{path}: unexpected Intel header version {words[0]}")
    if sum(words) & 0xFFFFFFFF:
        raise RuntimeError(f"{path}: Intel checksum failed")
    return data, words


def replay_patch(
    path: Path, fprom: dict[int, int], h1467_patch: dict[str, object] | None
) -> dict[str, object]:
    data, words = load_patch(path)
    signature = words[3] & 0xFFF
    if signature not in EXPECTED_INPUTS:
        raise RuntimeError(f"{path}: unexpected signature 0x{signature:03X}")
    got_hash = sha256_bytes(data)
    if got_hash != EXPECTED_INPUTS[signature]:
        raise RuntimeError(f"{path}: unexpected SHA-256 {got_hash}")

    seed = words[BODY_START + KEY_SEED_BODY_OFFSET]
    iv = u32(rotl32(PPRO_BASE_KEYS[signature], signature & 0xF) + 6 + seed)
    key_mask = 0xFF if signature < 0x619 else 0x9C
    key_index = iv & key_mask
    key = fprom[key_index]
    cipher = Cipher(key, iv)

    msram_cipher = words[
        BODY_START + MSRAM_BODY_OFFSET :
        BODY_START + MSRAM_BODY_OFFSET + MSRAM_DWORDS
    ]
    msram = [cipher.decrypt(word) for word in msram_cipher]
    integrity_index = cipher.state & 0xFF
    msram_integrity = cipher.decrypt(
        words[BODY_START + MSRAM_INTEGRITY_BODY_OFFSET]
    )
    msram_integrity_expected = fprom[integrity_index]
    if msram_integrity != msram_integrity_expected:
        raise RuntimeError(
            f"0x{signature:03X}: MSRAM integrity mismatch "
            f"{msram_integrity:08X} != {msram_integrity_expected:08X}"
        )

    controls = []
    for record in range(CONTROL_COUNT):
        start = BODY_START + CONTROL_BODY_OFFSET + 4 * record
        address = cipher.decrypt(words[start])
        mask = cipher.decrypt(words[start + 1])
        value = cipher.decrypt(words[start + 2])
        check_index = cipher.state & 0xFF
        check = cipher.decrypt(words[start + 3])
        expected = fprom[check_index]
        if check != expected:
            raise RuntimeError(
                f"0x{signature:03X} control {record}: integrity mismatch "
                f"{check:08X} != {expected:08X}"
            )
        controls.append(
            {
                "record": record,
                "address": f"{address:03X}",
                "mask": f"{mask:08X}",
                "value": f"{value:08X}",
                "integrity_index": f"{check_index:02X}",
                "integrity": f"{check:08X}",
            }
        )

    groups = [
        {
            "group": group,
            "candidate_patch_addresses": [
                f"{0x3FAC + 4 * group + slot:04X}" for slot in range(3)
            ],
            "physical_dwords": [
                f"{word:08X}"
                for word in msram[
                    group * MSRAM_GROUP_DWORDS :
                    (group + 1) * MSRAM_GROUP_DWORDS
                ]
            ],
        }
        for group in range(MSRAM_GROUPS)
    ]
    spare = msram[MSRAM_GROUPS * MSRAM_GROUP_DWORDS :]
    if len(spare) != MSRAM_SPARE_DWORDS:
        raise AssertionError("incorrect Pentium Pro spare-dword partition")

    old_comparison: dict[str, object]
    if h1467_patch is None:
        old_comparison = {"available": False}
    else:
        old_body = h1467_patch.get("recovery", {}).get("decrypted_body")
        if not isinstance(old_body, dict):
            old_comparison = {
                "available": False,
                "old_status": h1467_patch.get("recovery", {}).get("status"),
            }
        else:
            old_words = [
                int(word, 16)
                for group in old_body["physical_groups"]
                for word in group["physical_dwords"]
            ]
            overlap = min(len(old_words), len(msram))
            differences = [
                index for index in range(overlap) if old_words[index] != msram[index]
            ]
            old_controls = old_body["controls"]
            old_control_triplets = [
                (item["address"], item["mask"], item["value"])
                for item in old_controls
            ]
            new_control_triplets = [
                (item["address"], item["mask"], item["value"])
                for item in controls
            ]
            old_comparison = {
                "available": True,
                "old_msram_dword_count": len(old_words),
                "new_msram_dword_count": len(msram),
                "overlap_dword_count": overlap,
                "equal_overlap_dwords": overlap - len(differences),
                "first_different_overlap_dword": differences[0] if differences else None,
                "old_control_count": len(old_controls),
                "new_control_count": len(controls),
                "old_controls_equal_new_suffix_from_record_1": (
                    old_control_triplets == new_control_triplets[1:]
                ),
                "new_leading_control": controls[0],
            }

    return {
        "signature": f"{signature:03X}",
        "input_name": path.name,
        "input_sha256": got_hash,
        "header": {
            "revision": f"{words[1]:08X}",
            "date": f"{words[2]:08X}",
            "signature": f"{words[3]:08X}",
            "checksum": f"{words[4]:08X}",
            "platform_flags": f"{words[6]:08X}",
            "standard_checksum_ok": True,
        },
        "key_derivation": {
            "base_key": f"{PPRO_BASE_KEYS[signature]:08X}",
            "seed": f"{seed:08X}",
            "iv": f"{iv:08X}",
            "key_index_mask": f"{key_mask:02X}",
            "key_index": f"{key_index:02X}",
            "fprom_key": f"{key:08X}",
        },
        "published_layout": {
            "msram_body_offset_dwords": MSRAM_BODY_OFFSET,
            "msram_dword_count": MSRAM_DWORDS,
            "complete_groups": MSRAM_GROUPS,
            "dwords_per_group": MSRAM_GROUP_DWORDS,
            "spare_dword_count": MSRAM_SPARE_DWORDS,
            "msram_integrity_body_offset_dwords": MSRAM_INTEGRITY_BODY_OFFSET,
            "skipped_trap_body_offset_dwords": TRAP_BODY_OFFSET,
            "control_body_offset_dwords": CONTROL_BODY_OFFSET,
            "control_count": CONTROL_COUNT,
        },
        "msram": {
            "dwords_sha256": words_sha256(msram),
            "complete_groups_sha256": words_sha256(
                msram[: MSRAM_GROUPS * MSRAM_GROUP_DWORDS]
            ),
            "groups": groups,
            "spare_dwords": [f"{word:08X}" for word in spare],
        },
        "msram_integrity": {
            "index": f"{integrity_index:02X}",
            "got": f"{msram_integrity:08X}",
            "expected": f"{msram_integrity_expected:08X}",
            "ok": True,
        },
        "controls": controls,
        "integrity_checks_passed": 1 + len(controls),
        "integrity_checks_total": 1 + len(controls),
        "h1467_layout_comparison": old_comparison,
    }


def invoke_public_tool(tool: Path, patches: list[Path]) -> dict[str, object]:
    results = {}
    for path in patches:
        completed = subprocess.run(
            [str(tool), "-d", "-p", str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
        signature = struct.unpack("<I", path.read_bytes()[12:16])[0] & 0xFFF
        if completed.returncode != 0:
            raise RuntimeError(
                f"public tool failed on 0x{signature:03X}: {completed.stderr}"
            )
        results[f"{signature:03X}"] = {
            "exit_code": completed.returncode,
            "stdout_sha256": sha256_bytes(completed.stdout.encode()),
            "stderr_sha256": sha256_bytes(completed.stderr.encode()),
            "stderr_empty": not completed.stderr,
            "reported_control_count": completed.stdout.count("\n\tAddr:"),
        }
    return results


def pairwise_summary(patches: list[dict[str, object]]) -> list[dict[str, object]]:
    rows = []
    for left, right in combinations(patches, 2):
        left_groups = left["msram"]["groups"]
        right_groups = right["msram"]["groups"]
        exact_groups = sum(
            a["physical_dwords"] == b["physical_dwords"]
            for a, b in zip(left_groups, right_groups, strict=True)
        )
        left_words = [word for group in left_groups for word in group["physical_dwords"]]
        right_words = [word for group in right_groups for word in group["physical_dwords"]]
        exact_dwords = sum(a == b for a, b in zip(left_words, right_words, strict=True))
        rows.append(
            {
                "left": left["signature"],
                "right": right["signature"],
                "exact_groups": exact_groups,
                "groups_total": MSRAM_GROUPS,
                "exact_dwords": exact_dwords,
                "dwords_total": MSRAM_GROUPS * MSRAM_GROUP_DWORDS,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--h1467-report", required=True, type=Path)
    parser.add_argument("--patchtools", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("patches", nargs=5, type=Path)
    arguments = parser.parse_args()

    source_hashes = {
        name: sha256_path(arguments.source_dir / name)
        for name in EXPECTED_SOURCE_HASHES
    }
    if source_hashes != EXPECTED_SOURCE_HASHES:
        raise RuntimeError(
            f"public source hash mismatch: {source_hashes} != {EXPECTED_SOURCE_HASHES}"
        )
    fprom = load_fprom(arguments.source_dir / "fprom_data.c")
    h1467 = json.loads(arguments.h1467_report.read_text())
    h1467_patches = h1467["patches"]

    ordered = sorted(
        arguments.patches,
        key=lambda path: struct.unpack("<I", path.read_bytes()[12:16])[0] & 0xFFF,
    )
    signatures = [
        struct.unpack("<I", path.read_bytes()[12:16])[0] & 0xFFF for path in ordered
    ]
    if signatures != sorted(EXPECTED_INPUTS):
        raise RuntimeError(
            f"expected signatures {sorted(EXPECTED_INPUTS)}, got {signatures}"
        )

    patch_reports = [
        replay_patch(path, fprom, h1467_patches.get(f"{signature:03X}"))
        for path, signature in zip(ordered, signatures, strict=True)
    ]
    public_tool = (
        invoke_public_tool(arguments.patchtools, ordered)
        if arguments.patchtools is not None
        else {"not_run": True}
    )

    report = {
        "status": "exact_public_layout_replay_pass_wrong_earlier_partition",
        "question": (
            "Does the newer public Pentium Pro patch layout reproduce the exact "
            "0x611/612/616/617/619 files, and what does it change relative to H1467?"
        ),
        "source": {
            "url": SOURCE_URL,
            "commit": SOURCE_COMMIT,
            "file_sha256": source_hashes,
        },
        "h1467_report": {
            "path": str(arguments.h1467_report),
            "sha256": sha256_path(arguments.h1467_report),
        },
        "method": {
            "independent_python_replay": True,
            "compiled_public_tool_invoked": arguments.patchtools is not None,
            "hardware_executed": False,
            "x87_executed": False,
            "private_ledger_accessed": False,
        },
        "public_tool_replay": public_tool,
        "patches": {row["signature"]: row for row in patch_reports},
        "pairwise_correct_grouping": pairwise_summary(patch_reports),
        "conclusion": {
            "all_five_standard_checksums_pass": True,
            "all_five_integrity_checks": "85/85",
            "correct_groups_per_patch": 21,
            "correct_dwords_per_group": 7,
            "correct_spare_dwords_per_patch": 1,
            "correct_controls_per_patch": 16,
            "h1467_grouping": "19 groups x 8 dwords plus 15 controls",
            "h1467_grouping_status": "falsified_by_exact_public_source_replay",
            "downstream_scope": (
                "H1490-H1554 old-mapper searches consumed the H1467 19x8 "
                "partition and therefore do not constrain the actual 21x7 "
                "Pentium Pro physical groups. Their internal SAT/UNSAT theorems "
                "remain valid only for that mispartitioned dataset."
            ),
            "selector_found": False,
            "emulator_change": False,
            "frontier_closed": False,
        },
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
