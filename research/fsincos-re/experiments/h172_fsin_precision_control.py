#!/usr/bin/env python3
"""Verify whether x87 precision control reaches standalone FSIN.

The updated compiler-free capture binary runs the structured sweep and
h171's table separators under RN with PC24, PC53, and PC64.  A byte-for-byte
match includes the 80-bit result and instruction-local status word, so it
rules out both visible rounding and C1/PE changes.
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_CAPTURE = (
    ROOT / "capture-kit-captures" / "skylake-fsin-h172"
)
LEGACY = {
    "sweep": (
        ROOT
        / "capture-kit-captures"
        / "skylake-fsin-h110"
        / "sweep_fsin_rn_status.txt"
    ),
    "h171": (
        ROOT
        / "capture-kit-captures"
        / "skylake-fsin-h171"
        / "constraint_fsin_table_correction_h171_rn_status.txt"
    ),
}


def payload(
    capture: pathlib.Path, family: str, pc: str
) -> bytes:
    stem = (
        "sweep_fsin_rn"
        if family == "sweep"
        else "constraint_fsin_table_correction_h171_rn"
    )
    return (capture / f"{stem}_{pc}_status.txt").read_bytes()


def validate_lines(data: bytes) -> int:
    lines = data.splitlines()
    for line in lines:
        fields = line.split()
        valid_ok = (
            len(fields) == 5
            and fields[0] == b"OK"
            and fields[3] == b"SW"
        )
        valid_c2 = (
            len(fields) == 3
            and fields[0] == b"C2"
            and fields[1] == b"SW"
        )
        if not (valid_ok or valid_c2):
            raise ValueError(line)
    return len(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--capture", type=pathlib.Path, default=DEFAULT_CAPTURE
    )
    args = parser.parse_args()
    total = 0
    for family in ("sweep", "h171"):
        values = {
            pc: payload(args.capture, family, pc)
            for pc in ("pc24", "pc53", "pc64")
        }
        line_count = validate_lines(values["pc64"])
        total += line_count * len(values)
        if not all(
            value == values["pc64"] for value in values.values()
        ):
            for pc, value in values.items():
                differing = sum(
                    left != right
                    for left, right in zip(
                        value.splitlines(),
                        values["pc64"].splitlines(),
                    )
                )
                print(
                    f"h172 {family} {pc}: "
                    f"{differing}/{line_count} lines differ"
                )
            raise SystemExit("precision control changes FSIN")
        legacy = LEGACY[family].read_bytes()
        if legacy != values["pc64"]:
            raise SystemExit(
                f"{family} PC64 does not reproduce prior capture"
            )
        digest = hashlib.sha256(values["pc64"]).hexdigest()
        print(
            f"h172 {family}: {line_count} lines, "
            f"PC24=PC53=PC64=legacy, sha256={digest}"
        )
    print(
        f"h172: {total} result/status lines prove standalone "
        "FSIN ignores x87 precision control"
    )


if __name__ == "__main__":
    main()
