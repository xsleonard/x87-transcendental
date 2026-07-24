#!/usr/bin/env python3
"""Generate finite-normal separators for FPTAN and F2XM1 sibling capture.

The exact grid covers every k/128 point in [-1, 1] and neighboring x87
representable values.  A deterministic significand sweep adds non-grid
controls across the same exponent range.  Generation is hardware-blind.
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "capture-kit" / "inputs" / "sibling_fptan_f2xm1_h245.txt"
DEFAULT_METADATA = DEFAULT_OUTPUT.with_suffix(".meta.txt")


def encode_grid(numerator: int) -> tuple[int, int]:
    if numerator == 0:
        return 0, 0
    sign = int(numerator < 0)
    magnitude = abs(numerator)
    top = magnitude.bit_length() - 1
    exponent = top - 7
    significand = magnitude << (63 - top)
    return (sign << 15) | (exponent + 16383), significand


def operands() -> list[tuple[int, int]]:
    values: set[tuple[int, int]] = set()
    for numerator in range(-128, 129):
        se, significand = encode_grid(numerator)
        if not significand:
            values.add((0x0000, 0))
            values.add((0x8000, 0))
            continue
        for delta in (-8, -4, -2, -1, 0, 1, 2, 4, 8):
            candidate = significand + delta
            if 1 << 63 <= candidate < 1 << 64:
                values.add((se, candidate))

    state = 0xD1B54A32D192ED03
    for exponent in range(-32, 1):
        for _ in range(64):
            state = (
                state * 0x5851F42D4C957F2D + 0x14057B7EF767814F
            ) & ((1 << 64) - 1)
            significand = (1 << 63) | (state >> 1)
            for sign in (0, 1):
                values.add(
                    ((sign << 15) | (exponent + 16383), significand)
                )

    return sorted(values)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--metadata", type=pathlib.Path, default=DEFAULT_METADATA)
    args = parser.parse_args()
    rows = operands()
    text = "".join(f"{se:04x} {sig:016x}\n" for se, sig in rows)
    digest = hashlib.sha256(text.encode()).hexdigest()
    args.output.write_text(text)
    args.metadata.write_text(
        "h245 hardware-blind FPTAN/F2XM1 sibling inputs\n"
        f"rows: {len(rows)}\n"
        f"sha256: {digest}\n"
        "grid: every k/128 in [-1,1], significand deltas "
        "{-8,-4,-2,-1,0,1,2,4,8}\n"
        "controls: 64 deterministic significands per exponent -32..0, "
        "both signs\n"
    )
    print(f"wrote {len(rows)} rows to {args.output}")
    print(f"sha256 {digest}")


if __name__ == "__main__":
    main()
