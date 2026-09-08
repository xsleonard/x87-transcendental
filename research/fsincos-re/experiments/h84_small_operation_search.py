#!/usr/bin/env python3
"""Search operation-level explanations for the h83 RN-only small misses.

The h83 direct replay proves that the model and Skylake hidden values occupy
the same RD/RU interval but opposite RN halves for ten outputs.  This pass
reconstructs small_r with exact integers and varies one internal operation at
a time: significant width, rounding direction, or fused versus split
multiply-add.  Candidates are scored on all h83 modes and on every direct
small input in the independent master sweep.
"""

from __future__ import annotations

import dataclasses
import pathlib

import h58_constraint_search as h58
import h60_round16_parity as h60


ROOT = pathlib.Path(__file__).resolve().parents[1]
MASTER_INPUTS = ROOT / "capture-kit" / "inputs" / "sweep_inputs.txt"
MASTER_CAPTURE = (
    ROOT / "capture-kit-captures" / "pentiumII" / "sweep_rn.txt"
)
H83_INPUTS = ROOT / "capture-kit" / "inputs" / "constraint_small_h83.txt"
H83_CAPTURE = ROOT / "capture-kit-captures" / "skylake-h83-small-boundary"


def constant(sign: int, exponent_field: int, significand: int) -> h58.FP:
    return sign, significand, exponent_field - 16383 - 63


ONE = constant(0, 0x3FFF, 0x8000000000000000)
ZERO = h58.ZERO
S = (
    constant(1, 0x3FFC, 0xAAAAAAAAAAAAAAAA),
    constant(0, 0x3FF8, 0x88888888888868DB),
    constant(1, 0x3FF2, 0xD00D00D0055EFD4B),
    constant(0, 0x3FEC, 0xB8EF1C5D839730B9),
    constant(1, 0x3FE5, 0xD71EA3A4E5B3F492),
)
C = (
    constant(1, 0x3FFD, 0xFFFFFFFFFFFFFFFE),
    constant(0, 0x3FFA, 0xAAAAAAAAAAAA719F),
    constant(1, 0x3FF5, 0xB60B60B60356F994),
    constant(0, 0x3FEF, 0xD00CFFD5B2385EA9),
    constant(1, 0x3FE9, 0x93E4BD18292A14CD),
)

SITES = (
    "rsq",
    "z_square",
    "z_times_r",
    "z_times_rsq",
    "pl_first",
    "ph_first",
    "pl_second",
    "ph_times_rsq",
    "z_times_pl",
    "ph_times_r",
    "poly_add",
)


@dataclasses.dataclass(frozen=True)
class Variant:
    site: str = ""
    bits: int = 64
    mode: str = "rn"
    split: bool = False
    default_bits: int = 64
    default_mode: str = "rn"

    def label(self) -> str:
        if not self.site:
            return "baseline"
        topology = "split" if self.split else self.mode
        prefix = (
            ""
            if (self.default_bits, self.default_mode) == (64, "rn")
            else f"all:{self.default_bits}:{self.default_mode}+"
        )
        return f"{prefix}{self.site}:{self.bits}:{topology}"


def operation(
    site: str,
    a: h58.FP,
    b: h58.FP,
    c: h58.FP,
    variant: Variant,
) -> h58.FP:
    if variant.site not in (site, "*"):
        return h58.ffma(
            a, b, c, variant.default_bits, variant.default_mode
        )
    if variant.split:
        product = h58.fmul(a, b, variant.bits, variant.mode)
        return h58.fadd(product, c, variant.bits, variant.mode)
    return h58.ffma(a, b, c, variant.bits, variant.mode)


def small_value(
    se: int,
    sig: int,
    cosine: bool,
    variant: Variant,
) -> h58.FP:
    exponent = (se & 0x7FFF) - 16383
    r = (se >> 15, sig, exponent - 63)
    coefficients = C if cosine else S
    rsq = operation("rsq", r, r, ZERO, variant)
    z = operation("z_square", rsq, rsq, ZERO, variant)
    if not cosine:
        z = operation("z_times_r", z, r, ZERO, variant)
    z = operation("z_times_rsq", z, rsq, ZERO, variant)
    pl = operation(
        "pl_first", rsq, coefficients[4], coefficients[3], variant
    )
    ph = operation(
        "ph_first", rsq, coefficients[1], coefficients[0], variant
    )
    pl = operation(
        "pl_second", rsq, pl, coefficients[2], variant
    )
    ph = operation("ph_times_rsq", ph, rsq, ZERO, variant)
    poly = operation("z_times_pl", z, pl, ZERO, variant)
    if not cosine:
        ph = operation("ph_times_r", r, ph, ZERO, variant)
    poly = operation("poly_add", poly, ONE, ph, variant)
    return h58.add_exact(ONE if cosine else r, poly)


def outputs(
    se: int,
    sig: int,
    rc: str,
    variant: Variant,
) -> tuple[tuple[int, int], tuple[int, int]]:
    return (
        h58.x87_round(small_value(se, sig, False, variant), rc),
        h58.x87_round(small_value(se, sig, True, variant), rc),
    )


def parse_capture(path: pathlib.Path) -> list[
    tuple[tuple[int, int], tuple[int, int]]
]:
    result = []
    for line in path.read_text().splitlines():
        parsed = h60.parse_output(line)
        if parsed == "C2":
            raise AssertionError("small input returned C2")
        assert not isinstance(parsed, str)
        result.append(parsed)
    return result


def load_h83() -> list[
    tuple[
        int,
        int,
        tuple[
            tuple[tuple[int, int], tuple[int, int]],
            tuple[tuple[int, int], tuple[int, int]],
            tuple[tuple[int, int], tuple[int, int]],
        ],
    ]
]:
    inputs = [
        tuple(int(field, 16) for field in line.split())
        for line in H83_INPUTS.read_text().splitlines()
    ]
    captures = [
        parse_capture(H83_CAPTURE / f"constraint_small_{rc}.txt")
        for rc in h58.RCS
    ]
    return [
        (se, sig, tuple(capture[index] for capture in captures))
        for index, (se, sig) in enumerate(inputs)
    ]


def load_master_controls() -> list[
    tuple[int, int, tuple[tuple[int, int], tuple[int, int]]]
]:
    inputs = [
        tuple(int(field, 16) for field in line.split())
        for line in MASTER_INPUTS.read_text().splitlines()
    ]
    capture = [
        h60.parse_output(line)
        for line in MASTER_CAPTURE.read_text().splitlines()
    ]
    controls = []
    for (se, sig), expected in zip(inputs, capture):
        exponent = (se & 0x7FFF) - 16383
        if sig and exponent < -3:
            if expected == "C2":
                raise AssertionError("direct small input returned C2")
            assert not isinstance(expected, str)
            controls.append((se, sig, expected))
    return controls


def score(
    variant: Variant,
    h83: list,
    controls: list,
) -> tuple[int, int, int, int, int, int, int, int]:
    h83_mode_misses = 0
    h83_rn_misses = 0
    h83_changed_results = 0
    h83_lane_misses = [0, 0]
    baseline = Variant()
    for se, sig, expected_by_mode in h83:
        for rc_index, rc in enumerate(h58.RCS):
            actual = outputs(se, sig, rc, variant)
            expected = expected_by_mode[rc_index]
            h83_mode_misses += sum(
                left != right for left, right in zip(actual, expected)
            )
            for lane, (left, right) in enumerate(zip(actual, expected)):
                h83_lane_misses[lane] += left != right
            if rc == "rn":
                h83_rn_misses += sum(
                    left != right for left, right in zip(actual, expected)
                )
            h83_changed_results += sum(
                left != right
                for left, right in zip(
                    actual, outputs(se, sig, rc, baseline)
                )
            )
    control_lane_misses = [0, 0]
    for se, sig, expected in controls:
        for lane, (actual, wanted) in enumerate(
            zip(outputs(se, sig, "rn", variant), expected)
        ):
            control_lane_misses[lane] += actual != wanted
    control_misses = sum(control_lane_misses)
    return (
        h83_mode_misses,
        control_misses,
        h83_rn_misses,
        h83_changed_results,
        *h83_lane_misses,
        *control_lane_misses,
    )


def variants() -> list[Variant]:
    result = [Variant()]
    for bits in range(60, 97):
        for mode in ("rn", "chop", "away"):
            if bits == 64 and mode == "rn":
                continue
            result.append(Variant("*", bits, mode))
    for site in SITES:
        for bits in range(60, 81):
            for mode in ("rn", "chop", "away"):
                if bits == 64 and mode == "rn":
                    continue
                result.append(Variant(site, bits, mode))
        if site in ("pl_first", "ph_first", "pl_second"):
            for bits in range(60, 81):
                for mode in ("rn", "chop", "away"):
                    result.append(Variant(site, bits, mode, True))
    return result


def main() -> None:
    h83 = load_h83()
    controls = load_master_controls()
    baseline_score = score(Variant(), h83, controls)
    if baseline_score[:3] != (10, 0, 10):
        raise SystemExit(
            f"Python baseline does not reproduce C evidence: {baseline_score}"
        )
    print(
        f"loaded {len(h83)} h83 inputs (60 mode-results) and "
        f"{len(controls)} independent master direct-small controls"
    )
    print(
        "baseline: "
        f"h83-mode-miss={baseline_score[0]} "
        f"control-miss={baseline_score[1]} "
        f"h83-RN-miss={baseline_score[2]}"
    )

    rows = [
        (*score(variant, h83, controls), variant.label())
        for variant in variants()[1:]
    ]
    rows.sort()
    print("best single-operation variants:")
    for (
        mode_miss,
        control_miss,
        rn_miss,
        changed,
        sin_miss,
        cos_miss,
        control_sin,
        control_cos,
        label,
    ) in rows[:30]:
        print(
            f"  {label:28s} h83-mode-miss={mode_miss:2d} "
            f"control-miss={control_miss:4d} "
            f"h83-RN-miss={rn_miss:2d} changed={changed:2d} "
            f"lanes={sin_miss}/{cos_miss} "
            f"controls={control_sin}/{control_cos}"
        )

    for lane, name in enumerate(("sine", "cosine")):
        lane_rows = sorted(
            rows,
            key=lambda row: (
                row[4 + lane],
                row[6 + lane],
                row[0],
                row[1],
            ),
        )
        print(f"best {name}-only variants:")
        for row in lane_rows[:16]:
            print(
                f"  {row[-1]:28s} h83-{name}-miss={row[4 + lane]:2d} "
                f"control-{name}-miss={row[6 + lane]:4d} "
                f"all-mode-miss={row[0]:2d}"
            )


if __name__ == "__main__":
    main()
