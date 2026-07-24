#!/usr/bin/env python3
"""Verify and summarize the FPTAN/F2XM1 sibling capture."""

from __future__ import annotations

import argparse
import hashlib
import pathlib


EXPECTED = {"dense": 240000, "sweep": 50038, "target": 6466}
ONE = (0x3FFF, 0x8000000000000000)


def parse_single(line: str) -> tuple[tuple[int, int] | None, int]:
    fields = line.split()
    if len(fields) == 3 and fields[:2] == ["C2", "SW"]:
        return None, int(fields[2], 16)
    if len(fields) != 5 or fields[0] != "OK" or fields[3] != "SW":
        raise ValueError(line)
    return (int(fields[1], 16), int(fields[2], 16)), int(fields[4], 16)


def parse_pair(
    line: str,
) -> tuple[tuple[tuple[int, int], tuple[int, int]] | None, int]:
    fields = line.split()
    if len(fields) == 3 and fields[:2] == ["C2", "SW"]:
        return None, int(fields[2], 16)
    if len(fields) != 7 or fields[0] != "OK" or fields[5] != "SW":
        raise ValueError(line)
    return (
        (int(fields[1], 16), int(fields[2], 16)),
        (int(fields[3], 16), int(fields[4], 16)),
    ), int(fields[6], 16)


def read_lines(root: pathlib.Path, name: str, expected: int) -> list[str]:
    lines = (root / name).read_text().splitlines()
    if len(lines) != expected:
        raise SystemExit(f"{name}: {len(lines)} lines, expected {expected}")
    return lines


def directed_c1(rows_rd, rows_ru, pair: bool) -> tuple[int, int]:
    constrained = 0
    bad = 0
    for rd_row, ru_row in zip(rows_rd, rows_ru):
        rd_value, rd_sw = rd_row
        ru_value, ru_sw = ru_row
        if rd_value is None or ru_value is None:
            continue
        if pair:
            rd_value = rd_value[0]
            ru_value = ru_value[0]
        if rd_value == ru_value:
            continue
        constrained += 2
        negative = bool(rd_value[0] >> 15)
        bad += bool(rd_sw & 0x0200) != negative
        bad += bool(ru_sw & 0x0200) == negative
    return constrained - bad, constrained


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=pathlib.Path)
    args = parser.parse_args()
    root = args.capture.resolve()

    manifest = {}
    for line in (root / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split(None, 1)
        manifest[name.strip().lstrip("*")] = digest
    for name, digest in manifest.items():
        actual = hashlib.sha256((root / name).read_bytes()).hexdigest()
        if actual != digest:
            raise SystemExit(f"checksum mismatch: {name}")
    print(f"manifest: {len(manifest)} payloads verified")

    captures = {}
    for dataset, count in EXPECTED.items():
        for instruction, parser_fn in (("fptan", parse_pair), ("f2xm1", parse_single)):
            for rc in ("rn", "rd", "ru"):
                name = f"{dataset}_{instruction}_{rc}_status.txt"
                captures[dataset, instruction, rc] = [
                    parser_fn(line) for line in read_lines(root, name, count)
                ]

    for dataset, count in EXPECTED.items():
        successful = 0
        c2 = 0
        one_bad = 0
        for value, _ in captures[dataset, "fptan", "rn"]:
            if value is None:
                c2 += 1
            else:
                successful += 1
                one_bad += value[1] != ONE
        if one_bad:
            raise SystemExit(f"{dataset}: {one_bad} FPTAN pushed-one mismatches")
        print(
            f"{dataset}: FPTAN success={successful}/{count}, C2={c2}, "
            "pushed-one exact"
        )
        for instruction, pair in (("fptan", True), ("f2xm1", False)):
            good, total = directed_c1(
                captures[dataset, instruction, "rd"],
                captures[dataset, instruction, "ru"],
                pair,
            )
            print(f"  {instruction} directed C1 {good}/{total} consistent")

    for instruction in ("fptan", "f2xm1"):
        variants = [
            read_lines(
                root,
                f"target_{instruction}_rn_{pc}_status.txt",
                EXPECTED["target"],
            )
            for pc in ("pc24", "pc53", "pc64")
        ]
        differences = sum(
            not (pc24 == pc53 == pc64)
            for pc24, pc53, pc64 in zip(*variants)
        )
        print(f"target {instruction}: PC24/PC53/PC64 differences={differences}")

        timing = read_lines(
            root,
            f"target_{instruction}_timing.txt",
            EXPECTED["target"],
        )
        expected_fields = 9 if instruction == "fptan" else 7
        for line in timing:
            fields = line.split()
            if (
                fields[0] == "OK"
                and (
                    len(fields) != expected_fields
                    or fields[-4] != "SW"
                    or fields[-2] != "CYC"
                    or int(fields[-1]) <= 0
                )
            ):
                raise ValueError(line)
        print(f"target {instruction}: {len(timing)} timing rows valid")


if __name__ == "__main__":
    main()
