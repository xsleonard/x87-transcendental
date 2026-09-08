#!/usr/bin/env python3
"""Prove the C Round-18 polynomial path matches its integer Python oracle.

The checker covers direct and M66-reduced polynomial inputs under RN/RD/RU,
rotates the exact kernel values through the reduction quadrant, and verifies
that every inactive result remains byte-identical to the default C model.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess

import h58_constraint_search as h58
import h60_round16_parity as h60
import h64_poly_constraints as h64
import h65_poly_discriminator as h65


ROOT = pathlib.Path(__file__).resolve().parents[1]
P5_POLY_MODEL_MIN_EXP = -32


def active_kernel_input(
    se: int, sig: int
) -> tuple[int, int, int, bool] | None:
    exponent = (se & 0x7FFF) - 16383
    if sig and P5_POLY_MODEL_MIN_EXP <= exponent <= -3:
        return 0, se, sig, False
    reduced = h60.reduced_kernel_input(se, sig)
    if reduced is None:
        return None
    signed_n, r_se, r_sig, _ = reduced
    r_exponent = (r_se & 0x7FFF) - 16383
    if (
        not r_sig
        or r_exponent > -3
        or r_exponent < P5_POLY_MODEL_MIN_EXP
    ):
        return None
    return signed_n, r_se, r_sig, True


def candidate_outputs(
    signed_n: int, r_se: int, r_sig: int, rc: str
) -> tuple[tuple[int, int], tuple[int, int]]:
    raw = h64.PolyRaw(
        index=0,
        sign=r_se >> 15,
        exponent=(r_se & 0x7FFF) - 16383,
        sig=r_sig,
        sincos=h65.DUMMY_SINCOS,
        standalone=h65.DUMMY_OUTPUT,
    )
    point = h64.prepare(
        raw,
        h65.CANDIDATE_PRODUCER,
        h65.CANDIDATE_Q_FINAL_PRODUCT_BITS,
    )
    values = (
        h64.poly_value(point, 0, h65.CANDIDATE_SIN),
        h64.poly_value(point, 1, h65.CANDIDATE_COS),
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
        command.append("--round18-poly")
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
            signed_n, r_se, r_sig, _ = point
            expected = candidate_outputs(
                signed_n, r_se, r_sig, rc
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
            ROOT / "capture-kit" / "inputs" / "constraint_poly_h65.txt",
            ROOT / "capture-kit" / "inputs" / "constraint_poly_round75_h71.txt",
            ROOT / "capture-kit" / "inputs" / "constraint_poly_product_h74.txt",
            ROOT / "capture-kit" / "inputs" / "constraint_small_h83.txt",
            ROOT
            / "capture-kit"
            / "inputs"
            / "constraint_small_width_h85.txt",
            ROOT
            / "capture-kit"
            / "inputs"
            / "constraint_small_chop_h87.txt",
            ROOT
            / "capture-kit"
            / "inputs"
            / "constraint_small_deep_h89.txt",
        ],
    )
    args = parser.parse_args()
    check(args.binary.resolve(), args.inputs)


if __name__ == "__main__":
    main()
