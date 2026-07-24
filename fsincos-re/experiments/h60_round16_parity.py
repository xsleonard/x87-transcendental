#!/usr/bin/env python3
"""Prove the C Round-16 path matches its exact-integer Python oracle.

The candidate is active only for the four narrow table cells.  This checker
also reconstructs the C model's M66 reduction, maps reduced kernel results
through their quadrant, and proves that every inactive input remains
byte-identical to the default model.  In particular, a nonzero 65th-bit
reduction residual implies |r| >= 0.5 and therefore the unchanged wide path.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess

import h58_constraint_search as h58


TWO_OVER_PI = (
    (0xA2F9836E4E441529 << 64) | 0xFC2757D1F534DDC0
)
M66 = (3 << 64) | 0x243F6A8885A308D3
PI_BY_4_SIG = 0xC90FDAA22168C234


def nearest_quotient(numerator: int, shift: int) -> int:
    quotient, remainder = divmod(numerator, 1 << shift)
    half = 1 << (shift - 1)
    if remainder > half or (remainder == half and (quotient & 1)):
        quotient += 1
    return quotient


def reduced_kernel_input(
    se: int, sig: int
) -> tuple[int, int, int, bool] | None:
    """Return (signed N, r exponent, r significand, c_nonzero)."""
    exponent_field = se & 0x7FFF
    exponent = exponent_field - 16383
    sign = se >> 15
    if (
        sig == 0
        or exponent_field == 0x7FFF
        or exponent >= 63
        or exponent < -1
        or (exponent == -1 and sig < PI_BY_4_SIG)
    ):
        return None

    shift = 191 - exponent
    n_magnitude = nearest_quotient(sig * TWO_OVER_PI, shift)
    input_integer = sig << (exponent + 2)
    multiple_integer = n_magnitude * M66
    magnitude = abs(input_integer - multiple_integer)
    r_sign = int(input_integer < multiple_integer) ^ sign
    if magnitude == 0:
        return (
            (-n_magnitude if sign else n_magnitude),
            r_sign << 15,
            0,
            False,
        )

    width = magnitude.bit_length()
    c_nonzero = False
    if width == 65:
        kept = magnitude >> 1
        guard = magnitude & 1
        if guard and (kept & 1):
            kept += 1
        r_exponent = -1
        r_sig = kept
        c_nonzero = bool(guard)
    elif width <= 64:
        r_exponent = width - 1 - 65
        r_sig = magnitude << (64 - width)
    else:
        raise AssertionError(f"reduced magnitude has {width} bits")

    r_se = (r_sign << 15) | (r_exponent + 16383)
    signed_n = -n_magnitude if sign else n_magnitude
    return signed_n, r_se, r_sig, c_nonzero


def active_kernel_input(
    se: int, sig: int
) -> tuple[int, int, int, bool] | None:
    """Return (signed N, r se, r sig, was_reduced) for candidate cells."""
    exponent = (se & 0x7FFF) - 16383
    if exponent == -2:
        return 0, se, sig, False
    reduced = reduced_kernel_input(se, sig)
    if reduced is None:
        return None
    signed_n, r_se, r_sig, _ = reduced
    if (r_se & 0x7FFF) - 16383 != -2:
        return None
    return signed_n, r_se, r_sig, True


def rotate(values: tuple[h58.FP, h58.FP], quadrant: int) -> tuple[h58.FP, h58.FP]:
    sine, cosine = values
    quadrant &= 3
    if quadrant == 0:
        return sine, cosine
    if quadrant == 1:
        return cosine, h58.neg(sine)
    if quadrant == 2:
        return h58.neg(sine), h58.neg(cosine)
    return h58.neg(cosine), sine


def candidate_outputs(
    signed_n: int, r_se: int, r_sig: int, rc: str
) -> tuple[tuple[int, int], tuple[int, int]]:
    raw = h58.RawPoint(
        index=0,
        sign=r_se >> 15,
        exponent=(r_se & 0x7FFF) - 16383,
        sig=r_sig,
        hw=dummy_hw(),
    )
    prepared = h58.prepare(raw, h58.BASE_PRODUCER)
    values = h58.table_tail(prepared, h58.NARROW_TAIL)
    return tuple(h58.x87_round(value, rc) for value in rotate(values, signed_n))


def dummy_hw() -> tuple[
    tuple[tuple[int, int], tuple[int, int]],
    tuple[tuple[int, int], tuple[int, int]],
    tuple[tuple[int, int], tuple[int, int]],
]:
    return (((0, 0), (0, 0)),) * 3


def parse_output(line: str) -> tuple[tuple[int, int], tuple[int, int]] | str:
    fields = line.split()
    if fields == ["C2"]:
        return "C2"
    if len(fields) != 5 or fields[0] != "OK":
        raise ValueError(line)
    return (
        (int(fields[1], 16), int(fields[2], 16)),
        (int(fields[3], 16), int(fields[4], 16)),
    )


def run_model(
    binary: pathlib.Path, input_text: str, rc: str, candidate: bool
) -> list[tuple[tuple[int, int], tuple[int, int]] | str]:
    command = [str(binary), "--batch", f"--rc={rc}"]
    if candidate:
        command.append("--round16-narrow")
    completed = subprocess.run(
        command,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    )
    return [parse_output(line) for line in completed.stdout.splitlines()]


def center_neighbor_lines() -> list[str]:
    lines = []
    for sign in (0, 1):
        se = (sign << 15) | 0x3FFD
        for cell in (18, 22, 26, 30):
            center_sig = cell << 59
            for delta in range(-2, 3):
                lines.append(f"{se:04x} {center_sig + delta:016x}")
    return lines


def check(
    binary: pathlib.Path,
    inputs: list[pathlib.Path],
    include_center_neighbors: bool,
) -> None:
    input_lines = [
        line
        for path in inputs
        for line in path.read_text().splitlines()
        if line.strip()
    ]
    if include_center_neighbors:
        input_lines.extend(center_neighbor_lines())
    parsed_inputs = [
        (int(fields[0], 16), int(fields[1], 16))
        for fields in (line.split() for line in input_lines)
    ]
    input_text = "\n".join(input_lines) + "\n"

    active = [active_kernel_input(se, sig) for se, sig in parsed_inputs]
    direct_count = sum(point is not None and not point[3] for point in active)
    reduced_count = sum(point is not None and point[3] for point in active)
    residual_count = sum(
        bool(reduced and reduced[3])
        for se, sig in parsed_inputs
        if (reduced := reduced_kernel_input(se, sig)) is not None
    )

    parity_checks = 0
    inactive_checks = 0
    for rc in h58.RCS:
        baseline = run_model(binary, input_text, rc, False)
        candidate = run_model(binary, input_text, rc, True)
        if len(baseline) != len(parsed_inputs) or len(candidate) != len(parsed_inputs):
            raise SystemExit("model/input line counts differ")
        for index, point in enumerate(active):
            if point is None:
                if candidate[index] != baseline[index]:
                    raise SystemExit(
                        f"inactive path changed at {inputs}: line {index + 1}, {rc}"
                    )
                inactive_checks += 1
                continue
            signed_n, r_se, r_sig, _ = point
            expected = candidate_outputs(signed_n, r_se, r_sig, rc)
            if candidate[index] != expected:
                raise SystemExit(
                    f"C/Python mismatch at line {index + 1}, {rc}: "
                    f"C={candidate[index]} Python={expected}"
                )
            parity_checks += 1

    generated = 40 if include_center_neighbors else 0
    print(
        f"loaded {len(parsed_inputs)} inputs from {len(inputs)} file(s)"
        + (f" plus {generated} generated table-center neighbors" if generated else "")
    )
    print(
        f"candidate-active: {direct_count} direct + "
        f"{reduced_count} reduced narrow inputs"
    )
    print(
        f"nonzero 65th-bit residuals: {residual_count}; "
        "all dispatch to the unchanged wide path"
    )
    print(f"C/Python candidate parity: {parity_checks}/{parity_checks}")
    print(f"inactive default/candidate identity: {inactive_checks}/{inactive_checks}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=pathlib.Path)
    parser.add_argument("inputs", type=pathlib.Path, nargs="+")
    parser.add_argument(
        "--include-center-neighbors",
        action="store_true",
        help="also test +/-2 significand units around all four table centers",
    )
    args = parser.parse_args()
    check(args.binary.resolve(), args.inputs, args.include_center_neighbors)


if __name__ == "__main__":
    main()
