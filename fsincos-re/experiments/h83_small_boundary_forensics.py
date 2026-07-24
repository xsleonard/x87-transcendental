#!/usr/bin/env python3
"""Extract the residual Round-21 small-kernel failures from the master sweep.

The master sweep captures only RN.  This script runs the current C candidate,
separates table and polynomial inputs using their exact dispatch predicates,
and maps every remaining reduced-small input back to its direct kernel
argument.  Replaying those direct arguments with x87_capture removes range
reduction and quadrant rotation from the experiment.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess

import h58_constraint_search as h58
import h60_round16_parity as h60
import h66_round18_parity as h66
import h80_round21_parity as h80


ROOT = pathlib.Path(__file__).resolve().parents[1]
INPUTS = ROOT / "capture-kit" / "inputs" / "sweep_inputs.txt"
CAPTURE = ROOT / "capture-kit-captures" / "pentiumII" / "sweep_rn.txt"
MODEL = ROOT / "src" / "fsincos_skylake"


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


def direct_small_argument(se: int, sig: int) -> tuple[int, int, int]:
    """Return signed reduction quadrant and the direct small-r encoding."""
    exponent = (se & 0x7FFF) - 16383
    if exponent < -3:
        return 0, se, sig
    reduced = h60.reduced_kernel_input(se, sig)
    if reduced is None:
        raise AssertionError("non-direct residual is not reducible")
    signed_n, r_se, r_sig, c_nonzero = reduced
    r_exponent = (r_se & 0x7FFF) - 16383
    if r_sig == 0 or r_exponent >= -3:
        raise AssertionError("residual did not dispatch to nonzero small_r")
    if c_nonzero:
        raise AssertionError("small reduction unexpectedly has a c residual")
    return signed_n, r_se, r_sig


def format_output(
    value: tuple[tuple[int, int], tuple[int, int]] | str,
) -> str:
    if value == "C2":
        return "C2"
    assert not isinstance(value, str)
    return " ".join(
        (
            f"{value[0][0]:04x}",
            f"{value[0][1]:016x}",
            f"{value[1][0]:04x}",
            f"{value[1][1]:016x}",
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", nargs="?", type=pathlib.Path, default=MODEL)
    args = parser.parse_args()

    input_lines = INPUTS.read_text().splitlines()
    inputs = [
        tuple(int(field, 16) for field in line.split())
        for line in input_lines
    ]
    hardware = [
        h60.parse_output(line)
        for line in CAPTURE.read_text().splitlines()
    ]
    candidate = run_candidate(
        args.binary.resolve(),
        "\n".join(input_lines) + "\n",
    )
    if len(candidate) != len(inputs) or len(hardware) != len(inputs):
        raise SystemExit("master input/output line counts differ")

    failures = [
        index
        for index, (actual, expected) in enumerate(zip(candidate, hardware))
        if actual != expected
    ]
    table = [
        index
        for index in failures
        if h80.active_table_input(*inputs[index]) is not None
    ]
    poly = [
        index
        for index in failures
        if h66.active_kernel_input(*inputs[index]) is not None
    ]
    residual = [
        index
        for index in failures
        if index not in set(table) | set(poly)
    ]
    direct = [
        (*direct_small_argument(*inputs[index]), index)
        for index in residual
    ]
    if len(failures) != 205 or len(table) != 195 or poly:
        raise SystemExit(
            "unexpected current candidate partition: "
            f"all={len(failures)} table={len(table)} "
            f"poly={len(poly)} residual={len(residual)}"
        )

    print(
        f"master failures: {len(failures)} = {len(table)} table + "
        f"{len(poly)} polynomial + {len(residual)} reduced-small"
    )
    print(f"unique direct small arguments: {len(set(item[:3] for item in direct))}")
    print()
    print("direct-small inputs (constraint_small_h83.txt):")
    for _, r_se, r_sig, _ in direct:
        print(f"{r_se:04x} {r_sig:016x}")
    print()
    print("mapping and RN evidence:")
    for signed_n, r_se, r_sig, index in direct:
        se, sig = inputs[index]
        print(
            f"line={index + 1:5d} x={se:04x}:{sig:016x} "
            f"N={signed_n:+d} r={r_se:04x}:{r_sig:016x} "
            f"model={format_output(candidate[index])} "
            f"hardware={format_output(hardware[index])}"
        )


if __name__ == "__main__":
    main()
