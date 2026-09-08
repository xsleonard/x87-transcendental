#!/usr/bin/env python3
"""Prove the C Round-19 wide-q path matches its integer Python oracle.

The checker covers direct and M66-reduced wide table inputs under RN/RD/RU,
rotates the exact kernel values through the reduction quadrant, and verifies
that every inactive result remains byte-identical to the default C model.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess

import h58_constraint_search as h58
import h60_round16_parity as h60
import h67_wide_producer_discriminator as h67


ROOT = pathlib.Path(__file__).resolve().parents[1]
PI_BY_4_SIG = 0xC90FDAA22168C234


def active_kernel_input(
    se: int, sig: int
) -> tuple[int, h58.FP, int, bool] | None:
    exponent = (se & 0x7FFF) - 16383
    if exponent == -1 and sig < PI_BY_4_SIG:
        return 0, (0, sig, -64), se >> 15, False
    exponent_field = se & 0x7FFF
    sign = se >> 15
    if (
        sig == 0
        or exponent_field == 0x7FFF
        or exponent >= 63
        or exponent < -1
    ):
        return None
    shift = 191 - exponent
    n_magnitude = h60.nearest_quotient(
        sig * h60.TWO_OVER_PI, shift
    )
    input_integer = sig << (exponent + 2)
    multiple_integer = n_magnitude * h60.M66
    magnitude_integer = abs(input_integer - multiple_integer)
    if (
        magnitude_integer.bit_length() != 65
        or magnitude_integer >= (PI_BY_4_SIG << 1)
    ):
        return None
    residual_sign = int(input_integer < multiple_integer) ^ sign
    signed_n = -n_magnitude if sign else n_magnitude
    return (
        signed_n,
        (0, magnitude_integer, -65),
        residual_sign,
        True,
    )


def candidate_outputs(
    signed_n: int,
    magnitude: h58.FP,
    residual_sign: int,
    rc: str,
) -> tuple[tuple[int, int], tuple[int, int]]:
    values = h67.values_from_magnitude(
        magnitude, residual_sign, "q-only"
    )
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
        command.append("--round19-wide-q")
    completed = subprocess.run(
        command,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    )
    return [h60.parse_output(line) for line in completed.stdout.splitlines()]


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
    input_text = "\n".join(input_lines) + "\n"
    active = [active_kernel_input(se, sig) for se, sig in parsed]
    direct = sum(point is not None and not point[3] for point in active)
    reduced = sum(point is not None and point[3] for point in active)

    parity_checks = 0
    inactive_checks = 0
    for rc in h58.RCS:
        baseline = run_model(binary, input_text, rc, False)
        candidate = run_model(binary, input_text, rc, True)
        if len(baseline) != len(parsed) or len(candidate) != len(parsed):
            raise SystemExit("model/input line counts differ")
        for index, point in enumerate(active):
            if point is None:
                if candidate[index] != baseline[index]:
                    raise SystemExit(
                        f"inactive path changed at line {index + 1}, {rc}"
                    )
                inactive_checks += 1
                continue
            signed_n, magnitude, residual_sign, _ = point
            expected = candidate_outputs(
                signed_n, magnitude, residual_sign, rc
            )
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
            ROOT / "capture-kit" / "inputs"
            / "constraint_wide_producer_h67.txt",
        ],
    )
    args = parser.parse_args()
    check(args.binary.resolve(), args.inputs)


if __name__ == "__main__":
    main()
