#!/usr/bin/env python3
"""Fresh discriminator for h146's guarded final-Horner-sum rule.

Generation is hardware-independent.  Deterministic large x87 operands are
reduced with the solved M66 reducer; only odd-quadrant polynomial residuals
where the current h121 producer and the guarded sum-5 candidate predict a
different FSIN output or C1 observation are retained.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import pathlib
import random
import sys

import h58_constraint_search as h58
import h60_round16_parity as h60
import h64_poly_constraints as h64
import h110_fsin_standalone as h110
import h119_fcos_standalone as h119
import h121_fsin_internal_cosine as h121
import h146_fsin_cosine_boolean_search as h146


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_fsin_cosine_boolean_h147.txt"
)
DEFAULT_METADATA = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_fsin_cosine_boolean_h147.meta.txt"
)
SEED = 0xF147C5
BASELINE = h121.FSIN_INTERNAL_COSINE
CANDIDATE = dataclasses.replace(
    BASELINE,
    sums=h110.replace_tuple(
        BASELINE.sums, 4, h110.Quant(65, "chop")
    ),
)


def point_from_input(
    index: int, se: int, sig: int
) -> tuple[h121.Point, int, int, int] | None:
    reduced = h60.reduced_kernel_input(se, sig)
    if reduced is None:
        return None
    signed_n, r_se, r_sig, c_nonzero = reduced
    quadrant = signed_n & 3
    exponent = (r_se & 0x7FFF) - 16383
    if (
        not (quadrant & 1)
        or r_sig == 0
        or exponent >= -2
        or exponent < -32
        or c_nonzero
    ):
        return None
    raw = h64.PolyRaw(
        index=index,
        sign=0,
        exponent=exponent,
        sig=r_sig,
        sincos=(((0, 0), (0, 0)),) * 3,
        standalone=((0, 0), (0, 0)),
    )
    observed = h119.Observed(
        raw, ((0, 0),) * len(h58.RCS), (False,) * len(h58.RCS)
    )
    return (
        h121.Point(observed, bool((quadrant >> 1) & 1)),
        signed_n,
        r_se,
        r_sig,
    )


def hidden(point: h121.Point, candidate: bool) -> h58.FP:
    use_candidate = (
        candidate and h146.trace(point)["sum-5.guard"] == 1
    )
    value = h119.hidden_value(
        point.observed, CANDIDATE if use_candidate else BASELINE
    )
    return h58.neg(value) if point.negate else value


def profile(
    point: h121.Point, candidate: bool
) -> tuple[tuple[tuple[int, int], bool], ...]:
    value = hidden(point, candidate)
    return tuple(
        (
            output := h58.x87_round(value, rc),
            h110.compare_magnitude(output, value) > 0,
        )
        for rc in h58.RCS
    )


def difference_mask(
    left: tuple[tuple[tuple[int, int], bool], ...],
    right: tuple[tuple[tuple[int, int], bool], ...],
) -> int:
    mask = 0
    for index, (old, new) in enumerate(zip(left, right)):
        if old[0] != new[0]:
            mask |= 1 << index
        if old[1] != new[1]:
            mask |= 1 << (index + 3)
    return mask


def generate(
    output: pathlib.Path,
    metadata: pathlib.Path,
    count: int,
    scan_limit: int,
) -> None:
    rng = random.Random(SEED)
    rows = []
    meta = []
    masks: collections.Counter[int] = collections.Counter()
    exponents: collections.Counter[int] = collections.Counter()
    residuals = set()
    for scan_index in range(scan_limit):
        exponent = rng.randrange(0, 63)
        sig = rng.randrange(1 << 63, 1 << 64)
        sign = rng.getrandbits(1)
        se = (sign << 15) | (exponent + 16383)
        prepared = point_from_input(scan_index, se, sig)
        if prepared is None:
            continue
        point, signed_n, r_se, r_sig = prepared
        key = signed_n & 3, r_se, r_sig
        if key in residuals:
            continue
        old = profile(point, False)
        new = profile(point, True)
        mask = difference_mask(old, new)
        if not mask:
            continue
        residuals.add(key)
        masks[mask] += 1
        exponents[point.observed.raw.exponent] += 1
        rows.append(f"{se:04x} {sig:016x}")
        meta.append(
            f"{scan_index} {signed_n} {r_se:04x} {r_sig:016x} "
            f"{mask:02x}"
        )
        if len(rows) >= count:
            break
    if len(rows) < count:
        raise SystemExit(
            f"h147 selected {len(rows)} inputs after {scan_limit} scans; "
            f"wanted {count}"
        )
    output.write_text("\n".join(rows) + "\n")
    metadata.write_text("\n".join(meta) + "\n")
    print(
        f"h147: selected {len(rows)} separators from {scan_index + 1} "
        f"scans; masks={dict(sorted(masks.items()))}; "
        f"residual exponents={dict(sorted(exponents.items()))}; "
        f"seed={SEED:#x}",
        file=sys.stderr,
    )


def load_capture(
    inputs: pathlib.Path, capture: pathlib.Path
) -> list[h121.Point]:
    input_rows = [
        tuple(int(field, 16) for field in line.split())
        for line in inputs.read_text().splitlines()
    ]
    modes = [
        (
            capture
            / f"constraint_fsin_cosine_boolean_{rc}_status.txt"
        ).read_text().splitlines()
        for rc in h58.RCS
    ]
    if any(len(lines) != len(input_rows) for lines in modes):
        raise SystemExit("h147 input/capture line counts differ")
    result = []
    for index, (se, sig) in enumerate(input_rows):
        prepared = point_from_input(index, se, sig)
        if prepared is None:
            raise SystemExit(f"h147 input {index + 1} is not active")
        point = prepared[0]
        outputs = []
        c1 = []
        for lines in modes:
            fields = lines[index].split()
            if (
                len(fields) != 5
                or fields[0] != "OK"
                or fields[3] != "SW"
            ):
                raise ValueError(lines[index])
            outputs.append((int(fields[1], 16), int(fields[2], 16)))
            c1.append(bool(int(fields[4], 16) & 0x0200))
        observed = dataclasses.replace(
            point.observed,
            outputs=tuple(outputs),
            c1=tuple(c1),
        )
        result.append(dataclasses.replace(point, observed=observed))
    return result


def score(points: list[h121.Point], candidate: bool) -> h110.Score:
    result = h110.Score()
    for point in points:
        value = hidden(point, candidate)
        result.total += 1
        any_miss = False
        for index, rc in enumerate(h58.RCS):
            expected = point.observed.outputs[index]
            output = h58.x87_round(value, rc)
            mismatch = output != expected
            result.mode_misses += mismatch
            any_miss |= mismatch
            if not mismatch:
                c1 = h110.compare_magnitude(output, value) > 0
                result.c1_misses += c1 != point.observed.c1[index]
        result.output_misses += any_miss
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--score", type=pathlib.Path)
    parser.add_argument("--count", type=int, default=128)
    parser.add_argument("--scan-limit", type=int, default=20_000_000)
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--metadata", type=pathlib.Path, default=DEFAULT_METADATA
    )
    args = parser.parse_args()
    if args.generate:
        generate(
            args.output, args.metadata, args.count, args.scan_limit
        )
    if args.score is not None:
        points = load_capture(args.output, args.score)
        print(f"loaded {len(points)} fresh h147 separators")
        print(f"baseline  {score(points, False).describe()}")
        print(f"candidate {score(points, True).describe()}")
    if not args.generate and args.score is None:
        parser.error("select --generate and/or --score CAPTURE_DIRECTORY")


if __name__ == "__main__":
    main()
