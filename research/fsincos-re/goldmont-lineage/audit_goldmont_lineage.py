#!/usr/bin/env python3
"""Reproduce the static Goldmont/P5 constant and control-flow audit.

The public repositories are inputs, not vendored dependencies.  Pin them to
the revisions recorded in README.md before running this program.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


EXPECTED_506C9_HASHES = {
    "ms_array0.txt": "a5b6ca20c8466504d525bc78505ed47b57843f94e72969d13535b8b8386118b0",
    "ms_array1.txt": "24e43b97f042f78848042ed1436710367481aba43313d603a0db2145bf6d7b95",
    "ms_array2.txt": "f3cf26e4662907393d8798b2bbedc07f2a86a83e3e7c24b9e4618382e61ca315",
    "ms_array3.txt": "9ea94cec57af01a16fcac9a3d98bbd6ee22424e10f33de48cf95ac79a38705ec",
    "ms_array4.txt": "c79fd231bdd7052f0ea26138cc9a2d1224575043beaecba4f82b53dc8aacdfae",
    "ucode_glm.txt": "46fb61bfaf174765c117de65b036b73ae4433b9c2b9871d5289fd02d4867067e",
    "rom.txt": "87b9ee93e0c7a1f988906d8fd79d886590aa41a7368d06ef1954be8d5aca14db",
    "imms.txt": "6b25df6b7ad557ea7587b7a4302d9ae15c1b7db67ba6e509fb519aef6f5aa07e",
}

EXPECTED_506CA_HASHES = {
    "ms_array0.txt": "b9f93d01c81983758f97be8071b450029928627b9c9dec81b4926bc6d4214798",
    "ms_array1.txt": "b747966ed8b0126a571707352c181cc0883021f4f72732ff8f8657a8205c8403",
    "ms_array2.txt": "b8728f19170e76e6d0fa4c5bb1a53fe68ca3ccb40fbff9eb8c95f16a0cf5a996",
    "ms_array3.txt": "ebf31d06fc120852d7b9e8dbd228450324cbb0fffa812e17a330444742be3c48",
    "ms_array4.txt": "1b34aeb115b830f2c2bbc9212bf52329fe0346339f6b58e2b70bd3a2f40aef94",
}

EXPECTED_P6_MODEL_HASH = (
    "a844951c2c5193142e5520d709c3dc6b2f8d947c1cd266a7288c3ec3614058d2"
)

GLM_NAMES = {
    "ms_array0.txt": "ms_rom.txt",
    "ms_array1.txt": "ms_irom.txt",
    "ms_array2.txt": "ms_patch_imm.txt",
    "ms_array3.txt": "ms_match_patch.txt",
    "ms_array4.txt": "ms_patch_ram.txt",
}

COEFFICIENT_BLOCKS_506C9 = {
    "paired six-term U3e6d..U3e99": (
        0x3E6D,
        0x3E99,
        [0x21, 0x27, 0x20, 0x26, 0x1F, 0x25,
         0x1E, 0x24, 0x1D, 0x23, 0x1C, 0x22],
    ),
    "scalar six-term sine half U6cf8..U6d0c": (
        0x6CF8,
        0x6D0C,
        [0x20, 0x21, 0x1E, 0x1F, 0x1C, 0x1D],
    ),
    "scalar six-term cosine half U679a..U67a9": (
        0x679A,
        0x67A9,
        [0x26, 0x27, 0x24, 0x25, 0x22, 0x23],
    ),
    "shared four-term pair U6d84..U6da0": (
        0x6D84,
        0x6DA0,
        [0x2B, 0x2F, 0x2A, 0x2E, 0x29, 0x2D, 0x28, 0x2C],
    ),
}

COEFFICIENT_BLOCKS_506CA = {
    "paired six-term U3f31..U3f59": (
        0x3F31,
        0x3F59,
        [0x21, 0x27, 0x20, 0x26, 0x1F, 0x25,
         0x1E, 0x24, 0x1D, 0x23, 0x1C, 0x22],
    ),
    "scalar six-term sine half U6e06..U6e15": (
        0x6E06,
        0x6E15,
        [0x20, 0x21, 0x1E, 0x1F, 0x1C, 0x1D],
    ),
    "scalar six-term cosine half U68a2..U68b1": (
        0x68A2,
        0x68B1,
        [0x26, 0x27, 0x24, 0x25, 0x22, 0x23],
    ),
    "shared four-term pair U6ec6..U6ede": (
        0x6EC6,
        0x6EDE,
        [0x2B, 0x2F, 0x2A, 0x2E, 0x29, 0x2D, 0x28, 0x2C],
    ),
}

CONTROL_MARKERS = {
    "candidate paired entry": ("U0a58:", "SEQW GOTO U3e41"),
    "paired call to shared reducer": ("U3e60:", "SEQW GOTO U3cbc"),
    "paired table-path transfer": ("U3e6c:", "SEQW GOTO U643d"),
    "call to shared four-term/table kernel": ("U6441:", "SEQW GOTO U6d84"),
    "paired architectural results, primary route": ("U64b1:", "U64b6:"),
    "paired architectural results, alternate route": ("U4ad1:", "U4ad6:"),
    "candidate scalar entry": ("U0a60:", "SEQW GOTO U3c99"),
    "scalar reducer continuation": ("U3cba:", "SAVEUIP(0x00, U6ce4)"),
    "scalar architectural result branches": ("U6d12:", "U67b6:"),
    "scalar table-result branches": ("U5a21:", "U5a2d:", "U5844:"),
    "explicit sine table read": ("U6da2:", "FPREADROM_DTYPENOP"),
    "explicit cosine table read": ("U6da6:", "FPREADROM_DTYPENOP"),
}

PROTECTED_506C9_RANGES = {
    "paired/scalar xlat stubs": (0x0A58, 0x0A66),
    "paired phase/lane route": (0x2B09, 0x2B10),
    "scalar front end and shared reducer": (0x3C99, 0x3CC6),
    "paired front end and six-term kernel": (0x3E41, 0x3EA8),
    "alternate paired terminal": (0x4ACD, 0x4AD6),
    "paired table route and terminal": (0x643D, 0x64B6),
    "scalar cosine kernel and terminal": (0x679A, 0x67B6),
    "scalar continuation and table kernel": (0x6CE4, 0x6DA8),
}

EXPECTED_506C9_UPDATE_REVISIONS = (0x2E, 0x32, 0x36, 0x38, 0x3C, 0x40, 0x44, 0x46)

EXPECTED_506C9_UPDATE_HASHES = {
    0x2E: "d795b56cf044fbb48eab661b2c2b936a89577a9791986eb751ec61ea8fa9c2ca",
    0x32: "7198b4d188172c40adef65ee8b362ac0fed47d4fa56cc96ca3f7f4ad5e87b7be",
    0x36: "e5c7a41ecdcd964faef2adb74445b596ab49bb7127a011e03226418c768efaf4",
    0x38: "ecf1a3209e1b7a7f3d761b787c0390148511a52ab1a165b3bffa6b249fdf2f95",
    0x3C: "05a118f668f9628fefc54a688bbe81fec6a5af1de24cd5bf05b87149da65a85b",
    0x40: "7bc0556588293045a4d92ced9541afeaf0390b850d5f81410f9eabc932c9b9ea",
    0x44: "092fe430bb1727d91fe22dd81aa47d6874b52b9f3e78e4f2991e9b379231d833",
    0x46: "f7c56d0c4eee4682c7faee9c2b77b14003ddd46cafad3ef848da5f0d4d4fcd4a",
}

EXPECTED_COEFFICIENT_ROWS = {
    **{f"P5S6_{number}": 0x1B + number for number in range(1, 7)},
    **{f"P5C6_{number}": 0x21 + number for number in range(1, 7)},
    **{f"P5S4_{number}": 0x27 + number for number in range(1, 5)},
    **{f"P5C4_{number}": 0x2B + number for number in range(1, 5)},
}

EXPECTED_TABLE_ROWS = {
    "sin(18/64)": 0x69,
    "cos(18/64)": 0x71,
    "sin(22/64)": 0x6A,
    "cos(22/64)": 0x72,
    "sin(26/64)": 0x6B,
    "cos(26/64)": 0x73,
    "sin(30/64)": 0x6C,
    "cos(30/64)": 0x74,
    "sin(36/64)": 0x65,
    "cos(36/64)": 0x6D,
    "sin(44/64)": 0x66,
    "cos(44/64)": 0x6E,
    "sin(52/64)": 0x67,
    "cos(52/64)": 0x6F,
    "sin(60/64)": 0x68,
    "cos(60/64)": 0x70,
}

PI_OVER_2_HIGH64 = 0xC90FDAA22168C234
EXPECTED_PI_OVER_2_ROWS = (0x3F, 0x41, 0x42, 0x56, 0x115)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def die(message: str) -> None:
    raise ValueError(message)


def parse_rom(path: Path) -> List[int]:
    values = []
    for lineno, line in enumerate(path.read_text().splitlines(), 1):
        match = re.fullmatch(r"0x([0-9A-Fa-f]+)", line.strip())
        if not match:
            die(f"{path}:{lineno}: malformed FP-ROM row")
        values.append(int(match.group(1), 16))
    if len(values) != 512:
        die(f"{path}: expected 512 FP-ROM rows, found {len(values)}")
    return values


def parse_ms_array(path: Path) -> List[int]:
    values: List[int] = []
    for lineno, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        if re.fullmatch(r"\s*array\s+[0-9A-Fa-f]+:\s*", line):
            continue
        match = re.fullmatch(
            r"\s*([0-9A-Fa-f]+):\s+"
            r"([0-9A-Fa-f]+)\s+([0-9A-Fa-f]+)\s+"
            r"([0-9A-Fa-f]+)\s+([0-9A-Fa-f]+)\s*",
            line,
        )
        if not match:
            die(f"{path}:{lineno}: malformed four-word array row")
        address = int(match.group(1), 16)
        if address != len(values):
            die(
                f"{path}:{lineno}: row address 0x{address:x}, "
                f"expected 0x{len(values):x}"
            )
        values.extend(int(word, 16) for word in match.groups()[1:])
    if len(values) < 0x7C00:
        die(f"{path}: expected at least 0x7c00 words, found 0x{len(values):x}")
    return values


def parse_p5_coefficients(path: Path) -> List[Tuple[str, int]]:
    text = path.read_text()
    pattern = re.compile(
        r"static const p5c_t (P5[SC][64]_\d) = \{.*?"
        r"0x([0-9a-f]+)ull<<64\)\|0x([0-9a-f]+)ull",
        re.IGNORECASE,
    )
    values = [
        (name, (int(high, 16) << 64) | int(low, 16))
        for name, high, low in pattern.findall(text)
    ]
    if len(values) != 20:
        die(f"{path}: expected 20 named P5 coefficients, found {len(values)}")
    return values


def parse_p5_table(path: Path) -> List[Tuple[str, int]]:
    text = path.read_text()
    pattern = re.compile(
        r"\{ (\d+), \{.*?0x([0-9a-f]+)ull<<64\)\|"
        r"0x([0-9a-f]+)ull \}, \{.*?0x([0-9a-f]+)ull<<64\)\|"
        r"0x([0-9a-f]+)ull \} \}",
        re.IGNORECASE,
    )
    values: List[Tuple[str, int]] = []
    for breakpoint, sin_high, sin_low, cos_high, cos_low in pattern.findall(text):
        values.append(
            (f"sin({breakpoint}/64)",
             (int(sin_high, 16) << 64) | int(sin_low, 16))
        )
        values.append(
            (f"cos({breakpoint}/64)",
             (int(cos_high, 16) << 64) | int(cos_low, 16))
        )
    if len(values) != 16:
        die(f"{path}: expected 16 P5 table payloads, found {len(values)}")
    return values


def verify_p6_adjustment(path: Path) -> None:
    verify_hash(path, "P6 model", EXPECTED_P6_MODEL_HASH)
    text = path.read_text()
    initialization = "p5c_t p6s4_4 = P5S4_4;"
    adjustment = "p6s4_4.sig -= (u128)1 << 60;"
    if text.count(initialization) < 1 or text.count(adjustment) < 1:
        die(f"{path}: missing reconstructed P6 P5S4_4 bit-60 adjustment")
    print("P6 ADJUSTMENT OK P5S4_4.sig -= 1<<60")


def constant_reads(listing: str, start: int, end: int) -> List[int]:
    reads = []
    pattern = re.compile(
        r"^U([0-9a-f]{4}):\s+([0-9a-f]{12}).*\bunk_6a0\b",
        re.IGNORECASE,
    )
    for line in listing.splitlines():
        match = pattern.search(line)
        if not match:
            continue
        address = int(match.group(1), 16)
        if start <= address <= end:
            word = match.group(2)
            reads.append(int(word[4:6], 16))
    return reads


def raw_constant_reads(uops: Sequence[int], start: int, end: int) -> List[int]:
    reads = []
    for word in uops[start:end + 1]:
        if (word >> 32) & 0xFFF == 0x6A0:
            reads.append((word >> 24) & 0xFF)
    return reads


def sequence_target(sequence_words: Sequence[int], address: int) -> int:
    word = sequence_words[address & ~3]
    return (word & 0x7FFF00) >> 8


def indexes_of(rom: Sequence[int], value: int) -> List[int]:
    return [index for index, observed in enumerate(rom) if observed == value]


def format_indexes(indexes: Iterable[int]) -> str:
    return ",".join(f"0x{index:x}" for index in indexes) or "-"


def verify_hash(path: Path, key: str, expected: str) -> None:
    actual = sha256(path)
    if actual != expected:
        die(f"{path}: SHA-256 {actual}, expected {expected}")
    print(f"HASH OK  {key:16} {actual}")


def verify_artifacts(glm: Path, disasm: Path, cpu: Path) -> None:
    print("[artifact identity]")
    for array_name, glm_name in GLM_NAMES.items():
        glm_path = glm / glm_name
        disasm_path = disasm / "ucode" / array_name
        cpu_path = cpu / "uasm-lib" / "0x000506C9" / array_name
        verify_hash(disasm_path, array_name, EXPECTED_506C9_HASHES[array_name])
        if glm_path.read_bytes() != disasm_path.read_bytes():
            die(f"{glm_path} differs from {disasm_path}")
        if cpu_path.read_bytes() != disasm_path.read_bytes():
            die(f"{cpu_path} differs from {disasm_path}")
        print(f"IDENTICAL glm/{glm_name} == disasm/{array_name} == cpu/506C9/{array_name}")
    verify_hash(
        disasm / "ucode" / "ucode_glm.txt",
        "ucode_glm.txt",
        EXPECTED_506C9_HASHES["ucode_glm.txt"],
    )
    verify_hash(
        cpu / "bios" / "dumps" / "rom.txt",
        "rom.txt",
        EXPECTED_506C9_HASHES["rom.txt"],
    )
    verify_hash(
        cpu / "bios" / "dumps" / "imms.txt",
        "imms.txt",
        EXPECTED_506C9_HASHES["imms.txt"],
    )

    print("\n[506CA base arrays]")
    for array_name, expected in EXPECTED_506CA_HASHES.items():
        verify_hash(
            cpu / "uasm-lib" / "0x000506CA" / array_name,
            f"506CA/{array_name}",
            expected,
        )


def verify_constants(
    rom: Sequence[int], p5_header: Path, p6_model: Path
) -> None:
    print("\n[P5/P6 payload projection in Goldmont FP ROM]")
    verify_p6_adjustment(p6_model)
    exact_coefficients = 0
    near_coefficients = 0
    p6_exact_coefficients = 0
    for name, p5_value in parse_p5_coefficients(p5_header):
        projected = p5_value >> 3
        expected_index = EXPECTED_COEFFICIENT_ROWS[name]
        observed = rom[expected_index]
        indexes = indexes_of(rom, projected)
        if observed == projected:
            exact_coefficients += 1
            print(
                f"EXACT {name:7} p5={p5_value:017X} >>3={projected:016X} "
                f"gold=0x{expected_index:x} aliases={format_indexes(indexes)}"
            )
            continue
        distance = bin(projected ^ observed).count("1")
        if name != "P5S4_4" or projected ^ observed != 0x0200000000000000:
            die(
                f"{name} at FP-ROM row 0x{expected_index:x}: got "
                f"{observed:016X}, expected {projected:016X}"
            )
        near_coefficients += 1
        print(
            f"NEAR  {name:7} p5={p5_value:017X} >>3={projected:016X} "
            f"gold=0x{expected_index:x}:{observed:016X} "
            f"distance={distance}bit xor={projected ^ observed:016X}"
        )
        p6_value = p5_value - ((1 << 60) if name == "P5S4_4" else 0)
        if observed != p6_value >> 3:
            die(
                f"{name} at FP-ROM row 0x{expected_index:x}: got "
                f"{observed:016X}, expected effective P6 {(p6_value >> 3):016X}"
            )
        p6_exact_coefficients += 1
        print(
            f"P6EX  {name:7} p6={p6_value:017X} >>3={p6_value >> 3:016X} "
            f"gold=0x{expected_index:x}:{observed:016X}"
        )
        continue
    p6_exact_coefficients += exact_coefficients
    if (exact_coefficients, near_coefficients) != (19, 1):
        die(
            "coefficient comparison changed: expected 19 exact and one "
            "one-bit-near projection"
        )
    if p6_exact_coefficients != 20:
        die(
            "effective P6 coefficient comparison changed: expected 20 exact, "
            f"found {p6_exact_coefficients}"
        )

    exact_table = 0
    for name, p5_value in parse_p5_table(p5_header):
        projected = p5_value >> 3
        expected_index = EXPECTED_TABLE_ROWS[name]
        observed = rom[expected_index]
        if observed == projected:
            exact_table += 1
        print(
            f"{'EXACT' if observed == projected else 'MISS '} {name:10} "
            f"p5={p5_value:017X} >>3={projected:016X} "
            f"gold=0x{expected_index:x}:{observed:016X}"
        )
    if exact_table != 16:
        die(f"table comparison changed: expected 16 exact, found {exact_table}")
    print(
        "SUMMARY P5 35/36 trig payloads project exactly; "
        "effective P6 model set 36/36"
    )

    for index in EXPECTED_PI_OVER_2_ROWS:
        if rom[index] != PI_OVER_2_HIGH64:
            die(
                f"FP-ROM row 0x{index:x}: got {rom[index]:016X}, "
                f"expected pi/2 high payload {PI_OVER_2_HIGH64:016X}"
            )
    print(
        "PI/2 HIGH64 OK rows "
        + ",".join(f"0x{index:x}" for index in EXPECTED_PI_OVER_2_ROWS)
    )


def verify_506c9_xlat_shape(listing: str) -> None:
    print("\n[506C9 xlat-entry structural criteria]")
    for address in (0x0A58, 0x0A60):
        marker = f"U{address:04x}"
        if not 0 <= address < 0x1000 or address % 8:
            die(f"{marker}: violates published xlat address criteria")
        occurrences = len(re.findall(rf"\b{marker}\b", listing))
        if occurrences != 1:
            die(
                f"{marker}: expected definition-only occurrence, "
                f"found {occurrences} textual occurrences"
            )
        print(f"XLAT SHAPE OK {marker}: aligned, below U1000, definition only")


def verify_506ca_control(cpu: Path) -> None:
    c9_root = cpu / "uasm-lib" / "0x000506C9"
    ca_root = cpu / "uasm-lib" / "0x000506CA"
    c9_uops = parse_ms_array(c9_root / "ms_array0.txt")
    ca_uops = parse_ms_array(ca_root / "ms_array0.txt")
    ca_sequence = parse_ms_array(ca_root / "ms_array1.txt")

    print("\n[506CA fresh static control audit]")
    if c9_uops[0x0A58:0x0A67] != ca_uops[0x0A58:0x0A67]:
        die("506C9 and 506CA U0a58..U0a66 xlat-stub uops differ")
    print("XLAT UOPS OK 506C9 == 506CA at U0a58..U0a66")

    transfers = {
        "paired xlat relocation": (0x0A5C, 0x3F05),
        "scalar xlat relocation": (0x0A64, 0x3D91),
        "paired call to shared reducer": (0x3F24, 0x3DB4),
        "paired table-path transfer": (0x3F30, 0x657D),
        "paired call to four-term/table helper": (0x6580, 0x6EC5),
        "paired return to two-result finalizer": (0x6594, 0x3F65),
        "scalar table-path transfer": (0x6DFC, 0x6EB6),
    }
    for description, (address, expected) in transfers.items():
        observed = sequence_target(ca_sequence, address)
        if observed != expected:
            die(
                f"506CA {description} at U{address:04x}: "
                f"target U{observed:04x}, expected U{expected:04x}"
            )
        print(f"TRANSFER OK {description}: U{address:04x} -> U{observed:04x}")

    for description, (start, end, expected) in COEFFICIENT_BLOCKS_506CA.items():
        observed = raw_constant_reads(ca_uops, start, end)
        if observed != expected:
            die(
                f"506CA {description}: got {[hex(v) for v in observed]}, "
                f"expected {[hex(v) for v in expected]}"
            )
        print(f"ORDER OK {description}: {' '.join(f'{value:02x}' for value in observed)}")

    expected_words = {
        "shared reducer row 0x56": (0x3DB4, 0x06A056039000),
        "sine table base 0x65": (0x6EE2, 0x000065031CC8),
        "sine table read": (0x6EE4, 0x07160003B031),
        "cosine table base 0x6d": (0x6EE6, 0x00006D031CC8),
        "cosine table read": (0x6EE8, 0x07160003C031),
        "paired result mm7": (0x3F66, 0x04B441809E40),
        "paired result mm0": (0x3F6C, 0x26A631808F7E),
        "paired alternate result mm0": (0x05A6, 0x26A631808FBD),
        "scalar sine result mm0": (0x6E21, 0x268900008F78),
        "scalar cosine result mm0": (0x68BE, 0x268900008F7C),
        "scalar table result mm0": (0x5B01, 0x268900008E7B),
    }
    for description, (address, expected) in expected_words.items():
        observed = ca_uops[address]
        if observed != expected:
            die(
                f"506CA {description} at U{address:04x}: "
                f"word {observed:012x}, expected {expected:012x}"
            )
        print(f"UOP OK {description}: U{address:04x} {observed:012x}")


def verify_update_patch_exclusion(cpu: Path) -> None:
    collection = cpu / "ucode_collection"
    paths = sorted(collection.glob("*506C9*.bin.txt"))
    revisions = []
    hook_count = 0
    conflicts = []
    for path in paths:
        revision_match = re.search(r"_ver([0-9A-Fa-f]+)_", path.name)
        if not revision_match:
            die(f"{path}: cannot parse update revision")
        revision = int(revision_match.group(1), 16)
        revisions.append(revision)
        expected_hash = EXPECTED_506C9_UPDATE_HASHES.get(revision)
        if expected_hash is None:
            die(f"{path}: unexpected 506C9 update revision 0x{revision:x}")
        actual_hash = sha256(path)
        if actual_hash != expected_hash:
            die(f"{path}: SHA-256 {actual_hash}, expected {expected_hash}")
        hooks = [
            int(match, 16)
            for match in re.findall(
                r"<match & patch:\s*0x([0-9A-Fa-f]+)\s*->",
                path.read_text(),
            )
        ]
        hook_count += len(hooks)
        for hook in hooks:
            for description, (start, end) in PROTECTED_506C9_RANGES.items():
                if start <= hook <= end:
                    conflicts.append((revision, hook, description))

    if tuple(revisions) != EXPECTED_506C9_UPDATE_REVISIONS:
        die(
            "506C9 update set changed: got "
            f"{[hex(revision) for revision in revisions]}"
        )
    if hook_count != 447:
        die(f"506C9 update hook count changed: expected 447, found {hook_count}")
    if conflicts:
        details = ", ".join(
            f"rev 0x{revision:x} U{hook:04x} ({description})"
            for revision, hook, description in conflicts
        )
        die(f"published 506C9 update hooks overlap candidate paths: {details}")
    print("\n[published 506C9 update patch exclusion]")
    print(
        "PATCH EXCLUSION OK revisions 2e,32,36,38,3c,40,44,46; "
        "447 hook records; no candidate-path overlap"
    )


def verify_control(listing_path: Path, cpu: Path) -> None:
    listing = listing_path.read_text()
    verify_506c9_xlat_shape(listing)
    print("\n[static control markers]")
    for description, markers in CONTROL_MARKERS.items():
        missing = [marker for marker in markers if marker not in listing]
        if missing:
            die(f"{description}: missing marker(s): {missing}")
        print(f"MARKER OK {description}")

    print("\n[immediate-indexed opcode 0x6a0 reads]")
    for description, (start, end, expected) in COEFFICIENT_BLOCKS_506C9.items():
        observed = constant_reads(listing, start, end)
        if observed != expected:
            die(
                f"{description}: got {[hex(v) for v in observed]}, "
                f"expected {[hex(v) for v in expected]}"
            )
        print(f"ORDER OK {description}: {' '.join(f'{value:02x}' for value in observed)}")
    verify_506ca_control(cpu)
    verify_update_patch_exclusion(cpu)


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--glm-ucode", type=Path, required=True)
    parser.add_argument("--ucode-disasm", type=Path, required=True)
    parser.add_argument("--custom-processing-unit", type=Path, required=True)
    parser.add_argument(
        "--p5-header",
        type=Path,
        default=script_dir.parent / "src" / "p5_rom_constants.h",
    )
    parser.add_argument(
        "--p6-model",
        type=Path,
        default=script_dir.parent / "src" / "fsincos_skylake.c",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        verify_artifacts(
            args.glm_ucode, args.ucode_disasm, args.custom_processing_unit
        )
        rom_path = args.custom_processing_unit / "bios" / "dumps" / "rom.txt"
        rom = parse_rom(rom_path)
        verify_constants(rom, args.p5_header, args.p6_model)
        verify_control(
            args.ucode_disasm / "ucode" / "ucode_glm.txt",
            args.custom_processing_unit,
        )
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("\nAUDIT PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
