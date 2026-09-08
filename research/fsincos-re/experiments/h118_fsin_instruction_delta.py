#!/usr/bin/env python3
"""Classify the full-sweep RN differences between FSIN and FSINCOS.

The standalone FSIN capture is Skylake.  The FSINCOS capture is Pentium II,
whose full RN sweep was already proved byte-identical to Skylake.  This pass
maps each instruction-level difference back through the recovered M66 range
reduction so that the residual kernel family and quadrant are explicit.
"""

from __future__ import annotations

import collections
import pathlib

import h60_round16_parity as h60


ROOT = pathlib.Path(__file__).resolve().parents[1]
INPUTS = ROOT / "capture-kit" / "inputs" / "sweep_inputs.txt"
FSIN = (
    ROOT
    / "capture-kit-captures"
    / "skylake-fsin-h110"
    / "sweep_fsin_rn_status.txt"
)
FSINCOS = (
    ROOT / "capture-kit-captures" / "pentiumII" / "sweep_rn.txt"
)


def sine_value(line: str) -> tuple[int, int] | str:
    fields = line.split()
    if fields[0] == "C2":
        return "C2"
    return int(fields[1], 16), int(fields[2], 16)


def magnitude_rank(value: tuple[int, int]) -> int:
    se, sig = value
    return ((se & 0x7FFF) << 63) + sig


def classify(se: int, sig: int) -> tuple[str, int, int, bool]:
    reduced = h60.reduced_kernel_input(se, sig)
    if reduced is None:
        signed_n, r_se, r_sig, c_nonzero = 0, se, sig, False
        source = "direct"
    else:
        signed_n, r_se, r_sig, c_nonzero = reduced
        source = "reduced"
    exponent = (r_se & 0x7FFF) - 16383
    if r_sig == 0:
        family = "zero"
    elif exponent < -2:
        family = "polynomial"
    elif exponent == -2:
        family = "narrow-table"
    else:
        family = "wide-table"
    quadrant = signed_n & 3
    return f"{source}/{family}", quadrant, exponent, c_nonzero


def main() -> None:
    inputs = [
        tuple(int(field, 16) for field in line.split())
        for line in INPUTS.read_text().splitlines()
    ]
    fsin = FSIN.read_text().splitlines()
    fsincos = FSINCOS.read_text().splitlines()
    counts: collections.Counter[tuple[str, int, bool, int]] = (
        collections.Counter()
    )
    directions: collections.Counter[str] = collections.Counter()
    rows = []
    for index, ((se, sig), fsin_line, fsincos_line) in enumerate(
        zip(inputs, fsin, fsincos)
    ):
        left = sine_value(fsin_line)
        right = sine_value(fsincos_line)
        if left == right:
            continue
        if left == "C2" or right == "C2":
            raise SystemExit(f"C2 disagreement at input {index}")
        family, quadrant, exponent, c_nonzero = classify(se, sig)
        fsin_rank = magnitude_rank(left)
        fsincos_rank = magnitude_rank(right)
        delta = fsin_rank - fsincos_rank
        if abs(delta) != 1:
            raise SystemExit(
                f"non-ulp instruction difference at input {index}: "
                f"{left} != {right}"
            )
        direction = "FSIN magnitude +1" if delta > 0 else "FSIN magnitude -1"
        directions[direction] += 1
        counts[(family, quadrant, c_nonzero, exponent)] += 1
        rows.append(
            (
                index,
                f"{se:04x}",
                f"{sig:016x}",
                family,
                quadrant,
                exponent,
                int(c_nonzero),
                direction.rsplit(" ", 1)[-1],
            )
        )

    print(f"instruction differences: {len(rows)}/{len(inputs)}")
    for direction, count in sorted(directions.items()):
        print(f"  {direction}: {count}")
    print("classification (source/family, quadrant, c, r exponent):")
    for key, count in sorted(counts.items()):
        print(f"  {key}: {count}")
    print("index input_se input_sig source/family quadrant r_exp c delta")
    for row in rows:
        print(" ".join(str(field) for field in row))


if __name__ == "__main__":
    main()
