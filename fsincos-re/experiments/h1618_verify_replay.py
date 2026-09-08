#!/usr/bin/env python3
"""Verify an H1618 software replay, disclosing Mach-O metadata variation.

All observation streams and report fields must agree exactly. An executable
may differ only inside LC_UUID and the LC_CODE_SIGNATURE blob: executable
code, constants, remaining headers and all other bytes must stay identical.
Original files are never rewritten or normalized in place.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def macho_metadata_ranges(data: bytes) -> list[tuple[int, int]]:
    assert struct.unpack_from("<I", data)[0] == 0xFEEDFACF
    commands, commands_size = struct.unpack_from("<II", data, 16)
    cursor, ranges = 32, []
    for _ in range(commands):
        command, size = struct.unpack_from("<II", data, cursor)
        assert size >= 8 and cursor + size <= 32 + commands_size
        if command == 0x1B:  # LC_UUID: only the 16 UUID bytes.
            assert size == 24
            ranges.append((cursor + 8, cursor + 24))
        elif command == 0x1D:  # LC_CODE_SIGNATURE: only the pointed-to blob.
            assert size == 16
            offset, length = struct.unpack_from("<II", data, cursor + 8)
            assert 32 + commands_size <= offset <= offset + length <= len(data)
            ranges.append((offset, offset + length))
        cursor += size
    assert cursor == 32 + commands_size and len(ranges) == 2
    return sorted(ranges)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("replay", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    assert not args.output.exists()
    first = json.loads((args.original / "report.json").read_text())
    second = json.loads((args.replay / "report.json").read_text())
    assert {p.name for p in args.original.iterdir()} == {p.name for p in args.replay.iterdir()}
    equal_artifacts = []
    for name, expected in first["sha256"]["artifacts"].items():
        assert digest(args.original / name) == digest(args.replay / name) == expected
        assert second["sha256"]["artifacts"][name] == expected
        equal_artifacts.append(name)
    assert digest(args.original / "compiler.txt") == digest(args.replay / "compiler.txt") == first["sha256"]["compiler"]
    variants = {}
    for name in first["builds"]:
        left_path, right_path = args.original / name, args.replay / name
        left_hash, right_hash = digest(left_path), digest(right_path)
        assert left_hash == first["builds"][name]["binary_sha256"]
        assert right_hash == second["builds"][name]["binary_sha256"]
        if left_hash == right_hash:
            continue
        left, right = left_path.read_bytes(), right_path.read_bytes()
        assert len(left) == len(right)
        ranges = macho_metadata_ranges(left)
        assert ranges == macho_metadata_ranges(right)
        differences = [i for i, (a, b) in enumerate(zip(left, right)) if a != b]
        assert differences and all(any(start <= i < end for start, end in ranges) for i in differences)
        variants[name] = {"original_sha256": left_hash, "replay_sha256": right_hash,
                          "differing_bytes": len(differences), "allowed_metadata_ranges": ranges,
                          "all_other_bytes_identical": True}
        second["builds"][name]["binary_sha256"] = left_hash
    assert first == second, "a non-binary-hash report field changed"
    result = {"experiment": "h1618_verify_replay", "status": "PASS",
              "identical_observation_trace_artifacts": len(equal_artifacts),
              "all_results_and_non_binary_hash_report_fields_identical": True,
              "metadata_only_executable_variants": variants,
              "claim_boundary": "Compiler UUID/signature variation is disclosed, not silently removed from preserved reports. No hardware was executed.",
              "sha256": {"script": digest(Path(__file__)),
                         "original_report": digest(args.original / "report.json"),
                         "replay_report": digest(args.replay / "report.json")}}
    with args.output.open("x") as target:
        json.dump(result, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
