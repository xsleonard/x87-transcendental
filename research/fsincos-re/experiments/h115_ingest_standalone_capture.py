#!/usr/bin/env python3
"""Verify and summarize a standalone FSIN/FCOS capture-kit result."""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import tarfile
from collections.abc import Callable


ROOT = pathlib.Path(__file__).resolve().parents[1]
PII_FSIN = (
    ROOT / "capture-kit-captures" / "pentiumII" / "dense_fsin.txt"
)
EXPECTED_DENSE_LINES = 240000
EXPECTED_SWEEP_LINES = 50038
EXPECTED_TINY_LINES = 360
EXPECTED_OPTIONAL_STATUS_LINES = {
    "constraint_fsin_reduced_coefficient": 512,
    "constraint_fsin_table_terminal": 80,
}
EXPECTED_TIMING_LINES = {
    "poly": 2000,
    "table": 3584,
}


def directory_reader(root: pathlib.Path) -> Callable[[str], bytes]:
    candidates = (root / "standalone-out", root)
    base = next(
        (candidate for candidate in candidates if candidate.is_dir()),
        None,
    )
    if base is None:
        raise SystemExit("standalone-out directory not found")

    def read(name: str) -> bytes:
        path = base / name
        if not path.exists():
            raise SystemExit(f"missing capture member: {name}")
        return path.read_bytes()

    return read


def archive_reader(path: pathlib.Path) -> Callable[[str], bytes]:
    archive = tarfile.open(path, "r:*")
    members = {
        member.name.removeprefix("./"): member
        for member in archive.getmembers()
        if member.isfile()
    }

    def read(name: str) -> bytes:
        suffix = f"standalone-out/{name}"
        matches = [
            member
            for member_name, member in members.items()
            if member_name == suffix or member_name.endswith("/" + suffix)
        ]
        if len(matches) != 1:
            raise SystemExit(
                f"expected one archive member ending in {suffix}, "
                f"found {len(matches)}"
            )
        stream = archive.extractfile(matches[0])
        if stream is None:
            raise SystemExit(f"cannot read archive member: {name}")
        return stream.read()

    return read


def parse_status_line(line: str) -> tuple[tuple[int, int], int]:
    fields = line.split()
    if (
        len(fields) == 3
        and fields[0] == "C2"
        and fields[1] == "SW"
    ):
        return (-1, 0), int(fields[2], 16)
    if (
        len(fields) != 5
        or fields[0] != "OK"
        or fields[3] != "SW"
    ):
        raise ValueError(line)
    return (
        (int(fields[1], 16), int(fields[2], 16)),
        int(fields[4], 16),
    )


def parse_pair_status_line(
    line: str,
) -> tuple[tuple[tuple[int, int], tuple[int, int]], int]:
    fields = line.split()
    if (
        len(fields) == 3
        and fields[0] == "C2"
        and fields[1] == "SW"
    ):
        return ((-1, 0), (-1, 0)), int(fields[2], 16)
    if (
        len(fields) != 7
        or fields[0] != "OK"
        or fields[5] != "SW"
    ):
        raise ValueError(line)
    return (
        (
            (int(fields[1], 16), int(fields[2], 16)),
            (int(fields[3], 16), int(fields[4], 16)),
        ),
        int(fields[6], 16),
    )


def parse_timing_line(line: str, instruction: str) -> None:
    fields = line.split()
    expected = 9 if instruction == "sincos" else 7
    if (
        len(fields) != expected
        or fields[0] != "OK"
        or fields[-4] != "SW"
        or fields[-2] != "CYC"
    ):
        raise ValueError(line)
    int(fields[-3], 16)
    if int(fields[-1]) <= 0:
        raise ValueError(line)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=pathlib.Path)
    args = parser.parse_args()
    read = (
        directory_reader(args.capture)
        if args.capture.is_dir()
        else archive_reader(args.capture)
    )

    manifest = {}
    for line in read("SHA256SUMS").decode().splitlines():
        digest, name = line.split(None, 1)
        manifest[name.strip().lstrip("*")] = digest
    for name, digest in manifest.items():
        actual = hashlib.sha256(read(name)).hexdigest()
        if actual != digest:
            raise SystemExit(f"checksum mismatch: {name}")
    print(f"manifest: {len(manifest)} payloads verified")

    captures: dict[
        tuple[str, str], list[tuple[tuple[int, int], int]]
    ] = {}
    paired: dict[
        str,
        list[tuple[tuple[tuple[int, int], tuple[int, int]], int]],
    ] = {}
    sweep_single: dict[
        tuple[str, str], list[tuple[tuple[int, int], int]]
    ] = {}
    sweep_paired: dict[
        str,
        list[tuple[tuple[tuple[int, int], tuple[int, int]], int]],
    ] = {}
    for instruction in ("fsin", "fcos"):
        for rc in ("rn", "rd", "ru"):
            name = f"dense_{instruction}_{rc}_status.txt"
            lines = read(name).decode().splitlines()
            if len(lines) != EXPECTED_DENSE_LINES:
                raise SystemExit(
                    f"{name}: {len(lines)} lines, "
                    f"expected {EXPECTED_DENSE_LINES}"
                )
            captures[instruction, rc] = [
                parse_status_line(line) for line in lines
            ]
    for rc in ("rn", "rd", "ru"):
        name = f"dense_fsincos_{rc}_status.txt"
        lines = read(name).decode().splitlines()
        if len(lines) != EXPECTED_DENSE_LINES:
            raise SystemExit(
                f"{name}: {len(lines)} lines, "
                f"expected {EXPECTED_DENSE_LINES}"
            )
        paired[rc] = [parse_pair_status_line(line) for line in lines]

    for family, expected_lines, instructions in (
        ("sweep", EXPECTED_SWEEP_LINES, ("fsin", "fcos", "fsincos")),
        ("constraint_fsin_tiny", EXPECTED_TINY_LINES, ("fsin",)),
    ):
        for instruction in instructions:
            stem = (
                family
                if family == "constraint_fsin_tiny"
                else f"{family}_{instruction}"
            )
            for rc in ("rn", "rd", "ru"):
                name = f"{stem}_{rc}_status.txt"
                lines = read(name).decode().splitlines()
                if len(lines) != expected_lines:
                    raise SystemExit(
                        f"{name}: {len(lines)} lines, "
                        f"expected {expected_lines}"
                    )
                parser = (
                    parse_pair_status_line
                    if instruction == "fsincos"
                    else parse_status_line
                )
                parsed = [parser(line) for line in lines]
                if family == "sweep":
                    if instruction == "fsincos":
                        sweep_paired[rc] = parsed
                    else:
                        sweep_single[instruction, rc] = parsed

    for family, expected_lines in EXPECTED_TIMING_LINES.items():
        for instruction in ("sin", "cos", "sincos"):
            name = f"{family}_{instruction}_timing.txt"
            lines = read(name).decode().splitlines()
            if len(lines) != expected_lines:
                raise SystemExit(
                    f"{name}: {len(lines)} lines, "
                    f"expected {expected_lines}"
                )
            for line in lines:
                parse_timing_line(line, instruction)
    optional_status = 0
    for stem, expected_lines in EXPECTED_OPTIONAL_STATUS_LINES.items():
        if f"{stem}_rn_status.txt" not in manifest:
            continue
        for rc in ("rn", "rd", "ru"):
            name = f"{stem}_{rc}_status.txt"
            lines = read(name).decode().splitlines()
            if len(lines) != expected_lines:
                raise SystemExit(
                    f"{name}: {len(lines)} lines, "
                    f"expected {expected_lines}"
                )
            for line in lines:
                parse_status_line(line)
            optional_status += 1
    print(
        "formats: dense, sweep, tiny-boundary status and timing files valid"
        + (
            f"; {optional_status} focused FSIN status files valid"
            if optional_status
            else ""
        )
    )

    for instruction in ("fsin", "fcos"):
        rd = captures[instruction, "rd"]
        ru = captures[instruction, "ru"]
        constrained = 0
        c1_bad = 0
        for (rd_value, rd_sw), (ru_value, ru_sw) in zip(rd, ru):
            if rd_value == ru_value:
                continue
            constrained += 2
            negative = bool(rd_value[0] >> 15)
            c1_bad += bool(rd_sw & 0x0200) != negative
            c1_bad += bool(ru_sw & 0x0200) == negative
        print(
            f"{instruction}: directed C1 "
            f"{constrained - c1_bad}/{constrained} consistent"
        )

    for dataset, singles, pairs in (
        ("dense", captures, paired),
        ("sweep", sweep_single, sweep_paired),
    ):
        for rc in ("rn", "rd", "ru"):
            sine_differences = 0
            cosine_differences = 0
            fcos_c1_differences = 0
            for fsin_row, fcos_row, pair_row in zip(
                singles["fsin", rc],
                singles["fcos", rc],
                pairs[rc],
            ):
                fsin_value, fsin_sw = fsin_row
                fcos_value, fcos_sw = fcos_row
                (pair_sine, pair_cosine), pair_sw = pair_row
                sine_differences += fsin_value != pair_sine
                cosine_differences += fcos_value != pair_cosine
                fcos_c1_differences += bool(fcos_sw & 0x0200) != bool(
                    pair_sw & 0x0200
                )
            print(
                f"{dataset} {rc}: standalone/FSINCOS value differences "
                f"sin={sine_differences}, cos={cosine_differences}; "
                f"FCOS/paired-C1 differences={fcos_c1_differences}"
            )

    if PII_FSIN.exists():
        pii = PII_FSIN.read_text().splitlines()
        current = captures["fsin", "rn"]
        differences = 0
        for old, (new, _) in zip(pii, current):
            fields = old.split()
            old_value = int(fields[1], 16), int(fields[2], 16)
            differences += old_value != new
        print(
            f"FSIN RN versus Pentium II: "
            f"{differences}/{EXPECTED_DENSE_LINES} differ"
        )


if __name__ == "__main__":
    main()
