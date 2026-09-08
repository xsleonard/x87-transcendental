#!/usr/bin/env python3
"""Audit historical official Intel P6 patches for a 0x612 control-state lead.

The current public patch corpus was audited by h1457.  This companion checks
the complete filename and blob history of the official Intel repository, then
tests the historical Klamath key guesses against the original 0x632 update.
It is a static file-format audit: it never loads an update or executes x87.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path


SEGMENT_SIZE = 2048
EXACT_LINEAGE = re.compile(r"^intel-ucode/06-(?:01|02)-")
P6_FILE = re.compile(r"^intel-ucode/06-[0-9a-f]{2}-[0-9a-f]{2}$")
FPROM_ASSIGNMENT = re.compile(
    r"FPROM\[0x([0-9A-Fa-f]+)\]\s*=\s*0x([0-9A-Fa-f]+)"
)
SUPPORTED_CALIBRATION = "intel-ucode/06-05-00"
UNSUPPORTED_FILES = (
    "intel-ucode/06-03-02",
    "intel-ucode/06-08-03",
    "intel-ucode/06-0d-06",
)


@dataclass(frozen=True)
class Header:
    revision: int
    date: int
    signature: int
    platform_flags: int


@dataclass(frozen=True)
class IntegrityResult:
    base: int
    seed: int
    iv: int
    key_index: int
    key: int
    integrity_index: int
    got: int
    expected: int

    @property
    def matches(self) -> bool:
        return self.got == self.expected


def checked(command: list[str], cwd: Path) -> bytes:
    result = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command)}\n"
            f"stdout:\n{result.stdout.decode(errors='replace')}\n"
            f"stderr:\n{result.stderr.decode(errors='replace')}"
        )
    return result.stdout


def git(repo: Path, *arguments: str) -> bytes:
    return checked(["git", *arguments], repo)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def split_segments(data: bytes) -> tuple[bytes, ...]:
    if not data or len(data) % SEGMENT_SIZE:
        raise RuntimeError(f"unexpected Intel update file size: {len(data)}")
    return tuple(
        data[offset : offset + SEGMENT_SIZE]
        for offset in range(0, len(data), SEGMENT_SIZE)
    )


def parse_header(segment: bytes) -> Header:
    words = struct.unpack_from("<512I", segment)
    if words[0] != 1:
        raise RuntimeError(f"unexpected header version: {words[0]}")
    if sum(words) & 0xFFFFFFFF:
        raise RuntimeError(f"standard Intel checksum failure: {sha256(segment)}")
    return Header(words[1], words[2], words[3], words[6])


def u32(value: int) -> int:
    return value & 0xFFFFFFFF


def rotate_left(value: int, count: int) -> int:
    if not count:
        return value
    return u32((value << count) | (value >> (32 - count)))


def block_function(plain: int, key: int) -> int:
    state = plain
    for _ in range(37):
        state = (state >> 1) | ((state & 1) << 31)
        if state & 0x80000000:
            state ^= key
    return u32(state ^ plain)


def check_msram_integrity(
    segment: bytes, base: int, fprom: dict[int, int]
) -> IntegrityResult:
    words = struct.unpack_from("<512I", segment)
    signature = words[3]
    seed = words[12]
    iv = u32(rotate_left(base, signature & 0xF) + 6 + seed)
    key_index = iv & 0x9C
    key = fprom[key_index]
    state = iv
    last_ciphertext = key

    def decrypt(ciphertext: int) -> int:
        nonlocal state, last_ciphertext
        state = u32(block_function(state, key) ^ ciphertext)
        plaintext = u32(state ^ last_ciphertext)
        last_ciphertext = ciphertext
        return plaintext

    for ciphertext in words[14 : 14 + 168]:
        decrypt(ciphertext)
    integrity_index = state & 0xFF
    got = decrypt(words[14 + 168])
    expected = fprom[integrity_index]
    return IntegrityResult(
        base,
        seed,
        iv,
        key_index,
        key,
        integrity_index,
        got,
        expected,
    )


def load_fprom(path: Path) -> dict[int, int]:
    fprom = {
        int(index, 16): int(value, 16)
        for index, value in FPROM_ASSIGNMENT.findall(path.read_text())
    }
    if set(fprom) != set(range(256)):
        raise RuntimeError(f"expected public FPROM indices 0x00..0xFF in {path}")
    return fprom


def commits_for_path(repo: Path, path: str) -> tuple[str, ...]:
    return tuple(
        line
        for line in git(repo, "log", "--all", "--format=%H", "--", path)
        .decode()
        .splitlines()
        if line
    )


def historical_blobs(repo: Path, path: str) -> tuple[tuple[str, bytes], ...]:
    unique: dict[str, tuple[str, bytes]] = {}
    for commit in commits_for_path(repo, path):
        data = git(repo, "show", f"{commit}:{path}")
        unique.setdefault(sha256(data), (commit, data))
    return tuple(unique[key] for key in sorted(unique))


def format_integrity(result: IntegrityResult) -> str:
    return (
        f"base={result.base:08X} seed={result.seed:08X} iv={result.iv:08X} "
        f"key_index={result.key_index:02X} key={result.key:08X} "
        f"integrity_index={result.integrity_index:02X} got={result.got:08X} "
        f"expected={result.expected:08X} match={int(result.matches)}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--intel-repo", type=Path, required=True)
    parser.add_argument("--patchtools-dir", type=Path, required=True)
    arguments = parser.parse_args()
    repo = arguments.intel_repo.resolve()
    patchtools = arguments.patchtools_dir.resolve()
    head = git(repo, "rev-parse", "HEAD").decode().strip()
    family6_names = sorted(
        {
            line
            for line in git(
                repo, "log", "--all", "--name-only", "--format=", "--", "intel-ucode"
            )
            .decode()
            .splitlines()
            if P6_FILE.fullmatch(line)
        }
    )
    legacy_p6_names = tuple(
        name
        for name in family6_names
        if int(Path(name).name.split("-")[1], 16) <= 0x0D
    )
    exact_lineage = tuple(
        name for name in family6_names if EXACT_LINEAGE.fullmatch(name)
    )
    fprom_path = patchtools / "fprom_data.c"
    fprom = load_fprom(fprom_path)

    print("h1458 historical P6 patch surface")
    print(f"intel_head={head}")
    print(f"intel_historical_family6_files={len(family6_names)}")
    print(f"intel_historical_legacy_p6_files={len(legacy_p6_names)}")
    print(
        "intel_historical_legacy_p6_names="
        + ",".join(Path(name).name for name in legacy_p6_names)
    )
    print(f"exact_06_01_or_06_02_files={len(exact_lineage)}")
    print(f"patchtools_fprom_sha256={sha256(fprom_path.read_bytes())}")

    calibration = git(repo, "show", f"HEAD:{SUPPORTED_CALIBRATION}")
    calibration_results = tuple(
        check_msram_integrity(segment, 0x3B021CE0, fprom)
        for segment in split_segments(calibration)
    )
    print(f"calibration_file={Path(SUPPORTED_CALIBRATION).name}")
    print(f"calibration_sha256={sha256(calibration)}")
    print(f"calibration_segments={len(calibration_results)}")
    for index, result in enumerate(calibration_results):
        print(f"calibration[{index}] {format_integrity(result)}")
    if not all(result.matches for result in calibration_results):
        raise RuntimeError("public cipher replica failed supported 0x650 calibration")

    for path in UNSUPPORTED_FILES:
        blobs = historical_blobs(repo, path)
        print(f"file={Path(path).name} unique_historical_blobs={len(blobs)}")
        for blob_index, (commit, data) in enumerate(blobs):
            segments = split_segments(data)
            print(
                f"blob[{blob_index}] commit={commit} sha256={sha256(data)} "
                f"bytes={len(data)} segments={len(segments)}"
            )
            for segment_index, segment in enumerate(segments):
                header = parse_header(segment)
                print(
                    f"  segment[{segment_index}] sha256={sha256(segment)} "
                    f"revision={header.revision:08X} date={header.date:08X} "
                    f"signature={header.signature:08X} "
                    f"platform={header.platform_flags:08X} checksum=ok"
                )
                if (header.signature & 0xFFF) == 0x632:
                    for base in (0x30000000, 0x3A000000):
                        print("    klamath_guess " + format_integrity(
                            check_msram_integrity(segment, base, fprom)
                        ))


if __name__ == "__main__":
    main()
