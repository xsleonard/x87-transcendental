#!/usr/bin/env python3
"""Generate paired tomography from every remaining master table failure.

The Round-21 master residue contains 195 table-kernel inputs.  This generator
emits each original input for fresh RD/RU capture.  When its exact shared
residual ``a`` is representable by a direct x87 input, it also emits that same
``a`` through every valid table cell in the polynomial family.

Selection uses only the existing RN master result and current model.  No
h93 hardware output is consulted.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess

import h60_round16_parity as h60
import h78_paired_table_tomography as h78
import h80_round21_parity as h80


ROOT = pathlib.Path(__file__).resolve().parents[1]
MASTER_INPUTS = ROOT / "capture-kit" / "inputs" / "sweep_inputs.txt"
MASTER_CAPTURE = (
    ROOT / "capture-kit-captures" / "pentiumII" / "sweep_rn.txt"
)
MODEL = ROOT / "src" / "fsincos_skylake"
DEFAULT_OUTPUT = (
    ROOT / "capture-kit" / "inputs" / "constraint_table_residual_h93.txt"
)
DEFAULT_METADATA = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_table_residual_h93.meta.txt"
)


def run_candidate(
    binary: pathlib.Path,
    input_text: str,
) -> list[tuple[tuple[int, int], tuple[int, int]] | str]:
    completed = subprocess.run(
        [
            str(binary),
            "--batch",
            "--round18-poly",
            "--round21-table-bias",
        ],
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    )
    return [
        h60.parse_output(line)
        for line in completed.stdout.splitlines()
    ]


def signed_units(
    value: tuple[int, int, int],
    target_scale: int,
) -> int | None:
    sign, significand, scale = value
    shift = scale - target_scale
    if shift >= 0:
        units = significand << shift
    else:
        mask = (1 << -shift) - 1
        if significand & mask:
            return None
        units = significand >> -shift
    return -units if sign else units


def direct_for(
    family: str,
    cell: int,
    residual: int,
) -> tuple[int, int] | None:
    exponent = -2 if family == "narrow" else -1
    center_sig = cell << (59 if family == "narrow" else 58)
    sig = center_sig + residual
    if not (1 << 63 <= sig < 1 << 64):
        return None
    if (
        family == "wide"
        and sig >= h78.PI_BY_4_SIG
    ):
        return None
    if h78.h58.cell_for(sig, exponent) != cell:
        return None
    return exponent + 16383, sig


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=pathlib.Path, default=MODEL)
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--metadata", type=pathlib.Path, default=DEFAULT_METADATA
    )
    args = parser.parse_args()

    input_lines = MASTER_INPUTS.read_text().splitlines()
    inputs = [
        tuple(int(field, 16) for field in line.split())
        for line in input_lines
    ]
    hardware = [
        h60.parse_output(line)
        for line in MASTER_CAPTURE.read_text().splitlines()
    ]
    candidate = run_candidate(
        args.binary.resolve(),
        "\n".join(input_lines) + "\n",
    )
    failures = [
        index
        for index, (actual, expected) in enumerate(zip(candidate, hardware))
        if actual != expected
    ]
    if len(failures) != 195:
        raise SystemExit(
            f"expected 195 current failures, found {len(failures)}"
        )

    output_rows: list[str] = []
    metadata_rows: list[str] = []
    representable = 0
    paired = 0
    for group, index in enumerate(failures):
        se, sig = inputs[index]
        active = h80.active_table_input(se, sig)
        if active is None:
            raise AssertionError("remaining failure is not table-active")
        signed_n, point, reduced = active
        family = "wide" if point.wide else "narrow"
        target_scale = -64 if point.wide else -65
        residual = signed_units(point.a, target_scale)
        residual_text = "half" if residual is None else str(residual)
        output_rows.append(f"{se:04x} {sig:016x}")
        metadata_rows.append(
            f"{group} original {index + 1} {family} {point.cell} "
            f"{int(reduced)} {signed_n} {residual_text}"
        )
        if residual is None:
            continue
        representable += 1
        cells = h78.family_spec(family)[0]
        for cell in cells:
            direct = direct_for(family, cell, residual)
            if direct is None:
                continue
            direct_se, direct_sig = direct
            output_rows.append(
                f"{direct_se:04x} {direct_sig:016x}"
            )
            metadata_rows.append(
                f"{group} paired {index + 1} {family} {cell} "
                f"{int(reduced)} {signed_n} {residual}"
            )
            paired += 1

    args.output.write_text("\n".join(output_rows) + "\n")
    args.metadata.write_text("\n".join(metadata_rows) + "\n")
    print(
        f"h93: failures={len(failures)}; "
        f"representable states={representable}; "
        f"original inputs={len(failures)}; paired inputs={paired}; "
        f"total={len(output_rows)}"
    )


if __name__ == "__main__":
    main()
