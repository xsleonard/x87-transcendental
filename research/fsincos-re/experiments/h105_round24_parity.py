#!/usr/bin/env python3
"""Prove the C Round-24 RN67 table correction matches exact Python.

Both sides enable Rounds 18, 21, and 23.  Round 24 changes every table
result to:

    architectural_round(T1 + RN67(T1*t +/- T2*S))

where S includes Round 21's equivalent correction.  Direct and reduced
narrow/wide table inputs must match the exact h104 oracle under RN/RD/RU;
all non-table paths must remain byte-identical to the Round-23 C model.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess

import h58_constraint_search as h58
import h60_round16_parity as h60
import h80_round21_parity as h80
import h104_table_final_partial_search as h104


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODEL = ROOT / "src" / "fsincos_skylake"
DEFAULT_INPUTS = (
    ROOT / "capture-kit" / "inputs" / "dense_qn.txt",
    ROOT / "capture-kit" / "inputs" / "sweep_inputs.txt",
    ROOT / "capture-kit" / "inputs" / "constraint_narrow_h59.txt",
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_wide_producer_h67.txt",
    ROOT / "capture-kit" / "inputs" / "constraint_paired_table_h78.txt",
    ROOT / "capture-kit" / "inputs" / "constraint_table_residual_h93.txt",
    ROOT / "capture-kit" / "inputs" / "constraint_table_local_h95.txt",
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_narrow_coefficient_h97.txt",
)
VARIANT = h104.Variant("delta-correction", 67, "rn")


def run_model(
    binary: pathlib.Path,
    input_text: str,
    rc: str,
    candidate: bool,
) -> list[tuple[tuple[int, int], tuple[int, int]] | str]:
    command = [
        str(binary),
        "--batch",
        f"--rc={rc}",
        "--round18-poly",
        "--round21-table-bias",
        "--round23-narrow-coefficient",
    ]
    if candidate:
        command.append("--round24-table-delta-rn67")
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


def expected_output(
    signed_n: int,
    point: h58.PreparedPoint,
    rc: str,
) -> tuple[tuple[int, int], tuple[int, int]]:
    values = h104.values(point, VARIANT)
    return tuple(
        h58.x87_round(value, rc)
        for value in h60.rotate(values, signed_n)
    )


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
        h80.active_table_input(se, sig)
        for se, sig in parsed
    ]
    input_text = "\n".join(input_lines) + "\n"
    table = sum(item is not None for item in active)

    parity_checks = 0
    unchanged_checks = 0
    for rc in h58.RCS:
        baseline = run_model(binary, input_text, rc, False)
        candidate = run_model(binary, input_text, rc, True)
        if len(baseline) != len(parsed) or len(candidate) != len(parsed):
            raise SystemExit("model/input line counts differ")
        for index, item in enumerate(active):
            if item is None:
                if candidate[index] != baseline[index]:
                    raise SystemExit(
                        f"non-table path changed at line {index + 1}, {rc}"
                    )
                unchanged_checks += 1
                continue
            signed_n, point, _ = item
            expected = expected_output(signed_n, point, rc)
            if candidate[index] != expected:
                raise SystemExit(
                    f"C/Python mismatch at line {index + 1}, {rc}: "
                    f"C={candidate[index]} Python={expected}"
                )
            parity_checks += 1
    print(
        f"loaded {len(parsed)} inputs from {len(inputs)} files; "
        f"round24-active={table}; unchanged-per-mode={len(parsed) - table}"
    )
    print(
        f"PASS: {parity_checks} table results match Python; "
        f"{unchanged_checks} non-table results match Round23"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=pathlib.Path, nargs="?", default=MODEL)
    parser.add_argument(
        "--inputs",
        nargs="*",
        type=pathlib.Path,
        default=list(DEFAULT_INPUTS),
    )
    args = parser.parse_args()
    check(args.binary.resolve(), args.inputs)


if __name__ == "__main__":
    main()
