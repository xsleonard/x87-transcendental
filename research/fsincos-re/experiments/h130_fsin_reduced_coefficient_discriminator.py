#!/usr/bin/env python3
"""Freshly test the reduced-FSIN penultimate-coefficient survivor.

h129 found that an effective -256-unit adjustment at S6 coefficient 5
removes one full-sweep disagreement without hurting either deterministic
half.  That is too little evidence to change the model: the adjustment may
simply have selected one captured boundary by chance.

Generation is independent of hardware.  It scans deterministic large x87
operands, applies the already-proven M66 reducer, and retains only even-
quadrant polynomial residuals for which the old and adjusted hidden-state
models predict different FSIN output or C1 observations.  Scoring compares
both hypotheses with a fresh RN/RD/RU standalone-FSIN status capture.

The delta is an effective downstream correction.  It is not a claim that
Intel's stored polynomial coefficient differs from the decoded ROM value.
"""

from __future__ import annotations

import argparse
import collections
import pathlib
import random
import sys

import h58_constraint_search as h58
import h60_round16_parity as h60
import h64_poly_constraints as h64
import h110_fsin_standalone as h110
import h114_fsin_coefficient_delta as h114
import h122_fsin_reduced_sine as h122


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_fsin_reduced_coefficient_h130.txt"
)
DEFAULT_METADATA = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_fsin_reduced_coefficient_h130.meta.txt"
)
SEED = 0xF130C5
BASELINE = h122.FSIN_REDUCED_SINE
CANDIDATE = h114.with_delta(BASELINE, 4, -256)


def point_from_input(
    index: int, se: int, sig: int
) -> tuple[h110.Observed, int, int, int] | None:
    reduced = h60.reduced_kernel_input(se, sig)
    if reduced is None:
        return None
    signed_n, r_se, r_sig, c_nonzero = reduced
    quadrant = signed_n & 3
    exponent = (r_se & 0x7FFF) - 16383
    if (
        quadrant & 1
        or r_sig == 0
        or exponent >= -2
        or exponent < -32
        or c_nonzero
    ):
        return None
    output_sign = (r_se >> 15) ^ ((quadrant >> 1) & 1)
    raw = h64.PolyRaw(
        index=index,
        sign=output_sign,
        exponent=exponent,
        sig=r_sig,
        sincos=(((0, 0), (0, 0)),) * 3,
        standalone=((0, 0), (0, 0)),
    )
    return (
        h110.Observed(raw, ((0, 0),) * 3, (False,) * 3),
        signed_n,
        r_se,
        r_sig,
    )


def profile(
    point: h110.Observed, schedule: h110.Schedule
) -> tuple[tuple[tuple[int, int], bool], ...]:
    hidden = h110.hidden_value(point, schedule)
    result = []
    for rc in h58.RCS:
        output = h58.x87_round(hidden, rc)
        c1 = h110.compare_magnitude(output, hidden) > 0
        result.append((output, c1))
    return tuple(result)


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
        old = profile(point, BASELINE)
        new = profile(point, CANDIDATE)
        mask = difference_mask(old, new)
        if not mask:
            continue
        residuals.add(key)
        masks[mask] += 1
        exponents[point.raw.exponent] += 1
        rows.append(f"{se:04x} {sig:016x}")
        meta.append(
            f"{scan_index} {signed_n} {r_se:04x} {r_sig:016x} "
            f"{mask:02x}"
        )
        if len(rows) >= count:
            break
    if len(rows) < count:
        raise SystemExit(
            f"h130 selected {len(rows)} inputs after {scan_limit} scans; "
            f"wanted {count}"
        )
    output.write_text("\n".join(rows) + "\n")
    metadata.write_text("\n".join(meta) + "\n")
    print(
        f"h130: selected {len(rows)} separators from {scan_index + 1} "
        f"scans; masks={dict(sorted(masks.items()))}; "
        f"residual exponents={dict(sorted(exponents.items()))}; "
        f"seed={SEED:#x}",
        file=sys.stderr,
    )


def load_capture(
    inputs: pathlib.Path,
    capture: pathlib.Path,
) -> list[h110.Observed]:
    input_rows = [
        tuple(int(field, 16) for field in line.split())
        for line in inputs.read_text().splitlines()
    ]
    modes = [
        (
            capture
            / f"constraint_fsin_reduced_coefficient_{rc}_status.txt"
        ).read_text().splitlines()
        for rc in h58.RCS
    ]
    if any(len(lines) != len(input_rows) for lines in modes):
        raise SystemExit("h130 input/capture line counts differ")
    result = []
    for index, (se, sig) in enumerate(input_rows):
        prepared = point_from_input(index, se, sig)
        if prepared is None:
            raise SystemExit(f"h130 input {index + 1} is not active")
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
        result.append(
            h110.Observed(point.raw, tuple(outputs), tuple(c1))
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--score", type=pathlib.Path)
    parser.add_argument("--count", type=int, default=512)
    parser.add_argument("--scan-limit", type=int, default=20_000_000)
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--metadata", type=pathlib.Path, default=DEFAULT_METADATA
    )
    args = parser.parse_args()
    if args.generate:
        generate(args.output, args.metadata, args.count, args.scan_limit)
    if args.score is not None:
        points = load_capture(args.output, args.score)
        print(f"loaded {len(points)} fresh reduced-FSIN separators")
        print(f"baseline  {h110.score(points, BASELINE).describe()}")
        print(f"candidate {h110.score(points, CANDIDATE).describe()}")
    if not args.generate and args.score is None:
        parser.error("select --generate and/or --score CAPTURE_DIRECTORY")


if __name__ == "__main__":
    main()
