#!/usr/bin/env python3
"""Transfer solved operation classes to FPTAN's polynomial branch.

The polynomial branch evaluates the six-coefficient sine and cosine chains,
forms sine and cosine of the reduced residual, rotates them by the reduction
quadrant, and performs FPTAN's final quotient.  The graph is fixed; this pass
compares exact arithmetic with the operation classes independently selected
by F2XM1 and the h260 FPTAN table reconstruction:

* ordinary FMUL: magnitude chop67;
* ordinary FADD: RN64;
* multiply-class scaling operation: RN64;
* ordinary FSUB: magnitude chop67.
"""

from __future__ import annotations

import dataclasses
import pathlib

import h58_constraint_search as h58
import h60_round16_parity as h60
import h110_fsin_standalone as h110
import h245_fptan_shared_state as h245
import h246_fptan_operation_search as h246


ROOT = pathlib.Path(__file__).resolve().parents[1]
INPUTS = {
    "dense": ROOT / "capture-kit" / "inputs" / "dense_qn.txt",
    "sweep": ROOT / "capture-kit" / "inputs" / "sweep_inputs.txt",
}


@dataclasses.dataclass(frozen=True)
class Candidate:
    ordinary_mul: str = "chop67"
    ordinary_add: str = "rn64"
    scale_mul: str = "rn64"
    subtract: str = "chop67"
    tiny_direct_cutoff: int | None = -69

    def short(self) -> str:
        return (
            f"FMUL={self.ordinary_mul} FADD={self.ordinary_add} "
            f"MUL769={self.scale_mul} FSUB={self.subtract} "
            f"tiny<={self.tiny_direct_cutoff}"
        )


EXACT = Candidate("exact", "exact", "exact", "exact", None)
TRANSFER = Candidate()


@dataclasses.dataclass(frozen=True)
class Point:
    dataset: str
    index: int
    signed_n: int
    residual_sign: int
    residual: h58.FP
    hardware: dict[str, tuple[tuple[int, int] | None, int]]


def quantize(value: h58.FP, action: str) -> h58.FP:
    if action == "exact":
        return value
    return h110.quantize(
        value, h110.Quant(int(action[-2:]), action[:-2])
    )


def mul(left: h58.FP, right: h58.FP, action: str) -> h58.FP:
    return quantize(h58.mul_exact(left, right), action)


def add(left: h58.FP, right: h58.FP, action: str) -> h58.FP:
    return quantize(h58.add_exact(left, right), action)


def sub(left: h58.FP, right: h58.FP, action: str) -> h58.FP:
    return quantize(h58.add_exact(left, h58.neg(right)), action)


def horner(
    rows: tuple[int, ...], square: h58.FP, candidate: Candidate
) -> h58.FP:
    value = h58.ROM[rows[0]]
    for row in rows[1:]:
        value = mul(value, square, candidate.ordinary_mul)
        value = add(value, h58.ROM[row], candidate.ordinary_add)
    return value


def local_values(point: Point, candidate: Candidate):
    a = point.residual
    exponent = a[2] + a[1].bit_length() - 1
    if (
        candidate.tiny_direct_cutoff is not None
        and point.signed_n == 0
        and exponent <= candidate.tiny_direct_cutoff
    ):
        sine = h58.neg(a) if point.residual_sign else a
        return sine, h58.ONE

    square = mul(a, a, candidate.ordinary_mul)
    p = horner(h58.S6, square, candidate)
    q = horner(h58.C6, square, candidate)
    p_square = mul(square, p, candidate.scale_mul)
    q_square = mul(square, q, candidate.ordinary_mul)
    sine_tail = mul(a, p_square, candidate.ordinary_mul)

    # Coefficients already carry their signs.  The sine correction is
    # negative and the cosine tail is negative over this domain.
    sine = add(a, sine_tail, candidate.subtract)
    cosine = add(h58.ONE, q_square, candidate.subtract)
    if point.residual_sign:
        sine = h58.neg(sine)
    return h60.rotate((sine, cosine), point.signed_n)


def metric(point: Point, candidate: Candidate) -> tuple[int, int, int]:
    numerator, denominator = local_values(point, candidate)
    modes = 0
    c1 = 0
    for rc in h58.RCS:
        predicted, increment = h245.round_div(numerator, denominator, rc)
        expected, sw = point.hardware[rc]
        if expected is None:
            raise AssertionError("polynomial FPTAN returned C2")
        modes += predicted != expected
        if predicted == expected:
            c1 += increment != bool(sw & 0x0200)
    return modes, bool(modes), c1


def score(points: list[Point], candidate: Candidate):
    result = (0, 0, 0)
    for point in points:
        result = h246.add(result, metric(point, candidate))
    return result


def polynomial_residual(se: int, sig: int):
    exponent_field = se & 0x7FFF
    exponent = exponent_field - 16383
    if not sig or exponent_field == 0x7FFF or exponent >= 63:
        return None
    if exponent < -1:
        if exponent > -3:
            return None
        return 0, se >> 15, (0, sig, exponent - 63)

    reduced = h60.reduced_kernel_input(se, sig)
    if reduced is None:
        return None
    signed_n, r_se, r_sig, c_nonzero = reduced
    r_exponent = (r_se & 0x7FFF) - 16383
    if not r_sig or r_exponent > -3:
        return None
    if c_nonzero:
        raise AssertionError("polynomial residual unexpectedly has c")
    return signed_n, r_se >> 15, (0, r_sig, r_exponent - 63)


def points(name: str) -> list[Point]:
    operands = [
        tuple(int(field, 16) for field in line.split())
        for line in INPUTS[name].read_text().splitlines()
    ]
    captures = {
        rc: [
            h245.parse(line)
            for line in (
                h245.CAPTURE / f"{name}_fptan_{rc}_status.txt"
            ).read_text().splitlines()
        ]
        for rc in h58.RCS
    }
    result = []
    for index, (se, sig) in enumerate(operands):
        residual = polynomial_residual(se, sig)
        if residual is None:
            continue
        signed_n, residual_sign, value = residual
        result.append(
            Point(
                name,
                index,
                signed_n,
                residual_sign,
                value,
                {rc: captures[rc][index] for rc in h58.RCS},
            )
        )
    return result


def main() -> None:
    all_points = []
    for name in ("dense", "sweep"):
        selected = points(name)
        all_points.extend(selected)
        print(
            f"{name}: points={len(selected)} exact={score(selected, EXACT)} "
            f"transfer={score(selected, TRANSFER)}"
        )
    print(
        f"combined: points={len(all_points)} exact={score(all_points, EXACT)} "
        f"transfer={score(all_points, TRANSFER)}"
    )
    for cutoff in (-70, -69, -68):
        candidate = dataclasses.replace(TRANSFER, tiny_direct_cutoff=cutoff)
        print(f"  cutoff {cutoff}: {score(all_points, candidate)}")


if __name__ == "__main__":
    main()
