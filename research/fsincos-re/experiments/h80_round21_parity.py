#!/usr/bin/env python3
"""Prove the C Round-21 table-state candidate matches its Python oracle.

The checker covers direct and M66-reduced table inputs under RN/RD/RU.  It
reconstructs the exact reduced magnitude, including the 65th residual bit,
applies the family-specific shared-S state correction, rotates through the
reduction quadrant, and verifies that inactive paths remain byte-identical
to the no-flag C model.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess

import h58_constraint_search as h58
import h60_round16_parity as h60
import h67_wide_producer_discriminator as h67
import h79_table_state_bias as h79


ROOT = pathlib.Path(__file__).resolve().parents[1]
PI_BY_4_SIG = 0xC90FDAA22168C234
DUMMY_HW = (((0, 0), (0, 0)),) * 3


def direct_table_input(
    se: int,
    sig: int,
) -> tuple[int, h58.PreparedPoint, bool] | None:
    exponent = (se & 0x7FFF) - 16383
    if exponent not in (-2, -1):
        return None
    if exponent == -1 and sig >= PI_BY_4_SIG:
        return None
    raw = h58.RawPoint(
        index=0,
        sign=se >> 15,
        exponent=exponent,
        sig=sig,
        hw=DUMMY_HW,
    )
    return 0, h58.prepare(raw), False


def reduced_table_input(
    se: int,
    sig: int,
) -> tuple[int, h58.PreparedPoint, bool] | None:
    exponent_field = se & 0x7FFF
    exponent = exponent_field - 16383
    sign = se >> 15
    if (
        sig == 0
        or exponent_field == 0x7FFF
        or exponent >= 63
        or exponent < -1
    ):
        return None
    if exponent == -1 and sig < PI_BY_4_SIG:
        return None
    shift = 191 - exponent
    n_magnitude = h60.nearest_quotient(
        sig * h60.TWO_OVER_PI, shift
    )
    input_integer = sig << (exponent + 2)
    multiple_integer = n_magnitude * h60.M66
    magnitude_integer = abs(input_integer - multiple_integer)
    if not magnitude_integer:
        return None
    magnitude = (0, magnitude_integer, -65)
    width = magnitude_integer.bit_length()
    residual_exponent = width - 1 - 65
    if residual_exponent not in (-2, -1):
        return None
    residual_sign = int(input_integer < multiple_integer) ^ sign
    signed_n = -n_magnitude if sign else n_magnitude
    if residual_exponent == -1:
        point = h67.prepare_magnitude(
            magnitude,
            residual_sign,
            h58.BASE_PRODUCER,
        )
    else:
        normalized_sig = magnitude_integer << (64 - width)
        raw = h58.RawPoint(
            index=0,
            sign=residual_sign,
            exponent=residual_exponent,
            sig=normalized_sig,
            hw=DUMMY_HW,
        )
        point = h58.prepare(raw)
        if point.a != h58.add_exact(
            magnitude, (1, point.cell, -6)
        ):
            raise AssertionError("narrow reduced magnitude lost precision")
    return signed_n, point, True


def active_table_input(
    se: int,
    sig: int,
) -> tuple[int, h58.PreparedPoint, bool] | None:
    return direct_table_input(se, sig) or reduced_table_input(se, sig)


def candidate_outputs(
    signed_n: int,
    point: h58.PreparedPoint,
    rc: str,
) -> tuple[tuple[int, int], tuple[int, int]]:
    numerator = 5 if point.wide else 4
    values = h79.values(point, h79.BASE, numerator)
    return tuple(
        h58.x87_round(value, rc)
        for value in h60.rotate(values, signed_n)
    )


def run_model(
    binary: pathlib.Path,
    input_text: str,
    rc: str,
    candidate: bool,
) -> list[tuple[tuple[int, int], tuple[int, int]] | str]:
    command = [str(binary), "--batch", f"--rc={rc}"]
    if candidate:
        command.append("--round21-table-bias")
    completed = subprocess.run(
        command,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    )
    return [
        h60.parse_output(line)
        for line in completed.stdout.splitlines()
    ]


def check(binary: pathlib.Path, inputs: list[pathlib.Path]) -> None:
    input_lines = [
        line
        for path in inputs
        for line in path.read_text().splitlines()
        if line.strip()
    ]
    parsed = [
        (int(fields[0], 16), int(fields[1], 16))
        for fields in (line.split() for line in input_lines)
    ]
    active = [
        active_table_input(se, sig) for se, sig in parsed
    ]
    input_text = "\n".join(input_lines) + "\n"
    direct = sum(
        item is not None and not item[2] for item in active
    )
    reduced = sum(
        item is not None and item[2] for item in active
    )

    parity_checks = 0
    inactive_checks = 0
    for rc in h58.RCS:
        baseline = run_model(binary, input_text, rc, False)
        candidate = run_model(binary, input_text, rc, True)
        if len(baseline) != len(parsed) or len(candidate) != len(parsed):
            raise SystemExit("model/input line counts differ")
        for index, item in enumerate(active):
            if item is None:
                if candidate[index] != baseline[index]:
                    raise SystemExit(
                        f"inactive path changed at line {index + 1}, {rc}"
                    )
                inactive_checks += 1
                continue
            signed_n, point, _ = item
            expected = candidate_outputs(signed_n, point, rc)
            if candidate[index] != expected:
                raise SystemExit(
                    f"C/Python mismatch at line {index + 1}, {rc}: "
                    f"C={candidate[index]} Python={expected}"
                )
            parity_checks += 1
    print(
        f"loaded {len(parsed)} inputs from {len(inputs)} files; "
        f"candidate-active={direct} direct + {reduced} reduced"
    )
    print(
        f"PASS: {parity_checks} candidate results match the Python oracle; "
        f"{inactive_checks} inactive results match the default model"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=pathlib.Path)
    parser.add_argument(
        "inputs",
        nargs="*",
        type=pathlib.Path,
        default=[
            ROOT / "capture-kit" / "inputs" / "dense_qn.txt",
            ROOT / "capture-kit" / "inputs" / "sweep_inputs.txt",
            ROOT / "capture-kit" / "inputs" / "constraint_narrow_h59.txt",
            ROOT / "capture-kit" / "inputs"
            / "constraint_wide_producer_h67.txt",
        ],
    )
    args = parser.parse_args()
    check(args.binary.resolve(), args.inputs)


if __name__ == "__main__":
    main()
