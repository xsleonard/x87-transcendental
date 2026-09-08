#!/usr/bin/env python3
"""Gate h242 on standalone FCOS and paired FSINCOS sine-state paths."""

from __future__ import annotations

import dataclasses
import pathlib

import h58_constraint_search as h58
import h60_round16_parity as h60
import h64_poly_constraints as h64
import h110_fsin_standalone as h110
import h122_fsin_reduced_sine as h122
import h242_fsin_sine_split_graph as h242


ROOT = pathlib.Path(__file__).resolve().parents[1]
INPUTS = ROOT / "capture-kit" / "inputs" / "sweep_inputs.txt"
SINGLE = ROOT / "capture-kit-captures" / "skylake-fsin-h110"
PAIRED = ROOT / "capture-kit-captures" / "skylake-fsin-h177"
NATIVE_COEFFICIENTS = dataclasses.replace(
    h110.H64_START,
    coefficient=h110.EXACT,
    coefficient_overrides=(),
)


def observed(
    index: int,
    exponent: int,
    significand: int,
    outputs: list[tuple[int, int]],
) -> h110.Observed:
    raw = h64.PolyRaw(
        index=index,
        sign=outputs[0][0] >> 15,
        exponent=exponent,
        sig=significand,
        sincos=(((0, 0), (0, 0)),) * 3,
        standalone=((0, 0), (0, 0)),
    )
    return h110.Observed(raw, tuple(outputs), (False, False, False))


def load_single() -> dict[str, list[tuple[int, int] | None]]:
    result = {}
    for rc in h58.RCS:
        rows = []
        for line in (
            SINGLE / f"sweep_fcos_{rc}_status.txt"
        ).read_text().splitlines():
            fields = line.split()
            rows.append(
                None
                if fields[0] == "C2"
                else (int(fields[1], 16), int(fields[2], 16))
            )
        result[rc] = rows
    return result


def load_paired() -> dict[
    str,
    list[
        tuple[tuple[int, int], tuple[int, int]] | None
    ],
]:
    result = {}
    for rc in h58.RCS:
        rows = []
        for line in (
            PAIRED / f"sweep_fsincos_{rc}_status.txt"
        ).read_text().splitlines():
            fields = line.split()
            rows.append(
                None
                if fields[0] == "C2"
                else (
                    (int(fields[1], 16), int(fields[2], 16)),
                    (int(fields[3], 16), int(fields[4], 16)),
                )
            )
        result[rc] = rows
    return result


def load_points() -> tuple[
    list[h110.Observed],
    list[h110.Observed],
    list[h110.Observed],
]:
    inputs = [
        tuple(int(field, 16) for field in line.split())
        for line in INPUTS.read_text().splitlines()
    ]
    single = load_single()
    paired = load_paired()
    fcos_reduced = []
    paired_direct = []
    paired_reduced = []
    for index, (se, sig) in enumerate(inputs):
        reduced = h60.reduced_kernel_input(se, sig)
        if reduced is None:
            exponent = (se & 0x7FFF) - 16383
            if sig and -32 <= exponent < -2:
                outputs = [
                    paired[rc][index][0]  # type: ignore[index]
                    for rc in h58.RCS
                ]
                paired_direct.append(
                    observed(index, exponent, sig, outputs)
                )
            continue

        signed_n, r_se, r_sig, c_nonzero = reduced
        exponent = (r_se & 0x7FFF) - 16383
        if (
            not r_sig
            or not (-32 <= exponent < -2)
            or c_nonzero
        ):
            continue
        if signed_n & 1:
            fcos_outputs = [
                single[rc][index]  # type: ignore[list-item]
                for rc in h58.RCS
            ]
            fcos_reduced.append(
                observed(index, exponent, r_sig, fcos_outputs)
            )
            paired_outputs = [
                paired[rc][index][1]  # type: ignore[index]
                for rc in h58.RCS
            ]
        else:
            paired_outputs = [
                paired[rc][index][0]  # type: ignore[index]
                for rc in h58.RCS
            ]
        paired_reduced.append(
            observed(index, exponent, r_sig, paired_outputs)
        )
    return fcos_reduced, paired_direct, paired_reduced


def mode_misses(
    points: list[h110.Observed],
    coefficients: h110.Schedule,
) -> int:
    misses = 0
    for point in points:
        hidden = h242.hidden_value(
            point, h242.FSIN_SINE_SPLIT_SURVIVOR, coefficients
        )
        for index, rc in enumerate(h58.RCS):
            misses += (
                h58.x87_round(hidden, rc) != point.outputs[index]
            )
    return misses


def main() -> None:
    fcos_reduced, paired_direct, paired_reduced = load_points()
    fcos_misses = mode_misses(
        fcos_reduced, h122.FSIN_REDUCED_SINE
    )
    paired_direct_misses = mode_misses(
        paired_direct, NATIVE_COEFFICIENTS
    )
    paired_reduced_misses = mode_misses(
        paired_reduced, NATIVE_COEFFICIENTS
    )
    print(
        f"standalone FCOS reduced sine state: {fcos_misses}/"
        f"{3 * len(fcos_reduced)} mode misses"
    )
    print(
        f"paired FSINCOS direct sine state: {paired_direct_misses}/"
        f"{3 * len(paired_direct)} mode misses"
    )
    print(
        f"paired FSINCOS reduced sine state: {paired_reduced_misses}/"
        f"{3 * len(paired_reduced)} mode misses"
    )
    if fcos_misses:
        raise SystemExit("h242 does not transfer to standalone FCOS")
    if paired_direct_misses or paired_reduced_misses:
        print(
            "paired application rejected: retain its existing polynomial "
            "schedule"
        )


if __name__ == "__main__":
    main()
