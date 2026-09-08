#!/usr/bin/env python3
"""Build fresh separators for h174's structural FADD path gates.

The six candidates are frozen before hardware capture.  Three vary the
narrow cosine-lane nonlinear carrier; three test which architectural gate,
if any, selects a chop69 nonlinear carrier.  Inputs mix direct table
arguments with random large M66-reduced arguments.
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
import h110_fsin_standalone as h110
import h131_fsin_table_c1_search as h131
import h135_fsin_table_terminal_discriminator as h135
import h147_fsin_cosine_boolean_discriminator as h147
import h171_fsin_table_correction_discriminator as h171
import h173_fsin_table_fadd_topology as h173
import h174_fsin_table_path_gate as h174


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_fsin_table_path_gate_h175.txt"
)
DEFAULT_METADATA = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_fsin_table_path_gate_h175.meta.txt"
)
SEED = 0xF175C5
RN67 = h110.Quant(67, "rn")


@dataclasses.dataclass(frozen=True)
class Conditional:
    name: str
    gate: h174.Gate
    candidate: h173.Candidate


def correction(
    name: str, gate: h174.Gate, first: h110.Quant
) -> Conditional:
    return Conditional(
        name,
        gate,
        h173.Candidate("correction", first, RN67),
    )


CANDIDATES = (
    correction(
        "narrow-cos-nonlinear-rn64",
        h174.Gate("narrow-cosine", family="narrow", parity=1),
        h110.Quant(64, "rn"),
    ),
    correction(
        "narrow-cos-nonlinear-away67",
        h174.Gate("narrow-cosine", family="narrow", parity=1),
        h110.Quant(67, "away"),
    ),
    correction(
        "narrow-cos-nonlinear-odd67",
        h174.Gate("narrow-cosine", family="narrow", parity=1),
        h110.Quant(67, "odd"),
    ),
    correction(
        "wide-nonlinear-chop69",
        h174.Gate("wide", family="wide"),
        h110.Quant(69, "chop"),
    ),
    correction(
        "cosine-nonlinear-chop69",
        h174.Gate("cosine-lane", parity=1),
        h110.Quant(69, "chop"),
    ),
    correction(
        "reduced-wide-nonlinear-chop69",
        h174.Gate(
            "reduced-wide", source="reduced", family="wide"
        ),
        h110.Quant(69, "chop"),
    ),
)


def construct_table_input(
    rng: random.Random,
) -> tuple[int, int, int] | None:
    """Construct an odd-quadrant M66 input with table residual."""

    exponent = rng.randrange(4, 62)
    unit = 1 << exponent
    low_n = (7 * unit + 9) // 10
    high_n = (6 * unit) // 5
    n = rng.randrange(low_n, high_n) | 1
    if n >= high_n:
        n -= 2
    shift = exponent + 2
    modulus = 1 << shift
    positive_residual = bool(rng.getrandbits(1))
    residue = (
        (-n * h60.M66) % modulus
        if positive_residual
        else (n * h60.M66) % modulus
    )
    minimum = 1 << 63
    maximum = (h60.PI_BY_4_SIG << 1) - 1
    first = max(
        0, (minimum - residue + modulus - 1) // modulus
    )
    last = (maximum - residue) // modulus
    if first > last:
        return None
    magnitude = residue + rng.randrange(first, last + 1) * modulus
    input_integer = (
        n * h60.M66 + magnitude
        if positive_residual
        else n * h60.M66 - magnitude
    )
    if input_integer <= 0 or input_integer % modulus:
        return None
    sig = input_integer // modulus
    if not (1 << 63 <= sig < 1 << 64):
        return None
    return exponent + 16383, sig, n


def profile(
    terms: h173.Terms, candidate: Conditional | None
) -> tuple[tuple[tuple[int, int], bool], ...]:
    selected = (
        candidate is not None
        and candidate.gate.selected(terms.point)
    )
    schedule = (
        candidate.candidate if selected else h173.CURRENT
    )
    value = h173.hidden(terms, schedule)
    return tuple(
        (
            output := h58.x87_round(value, rc),
            h110.compare_magnitude(output, value) > 0,
        )
        for rc in h58.RCS
    )


def generate(
    output: pathlib.Path,
    metadata: pathlib.Path,
    per_candidate: int,
    scan_limit: int,
) -> None:
    rng = random.Random(SEED)
    rows = []
    meta = []
    counts: collections.Counter[str] = collections.Counter()
    states = set()
    for scan_index in range(scan_limit):
        constructed = None
        if rng.randrange(4) == 0:
            family = "narrow" if rng.getrandbits(1) else "wide"
            se, sig = h135.direct_operand(rng, family)
        else:
            constructed = construct_table_input(rng)
            if constructed is None:
                continue
            se, sig = constructed[:2]
        point = h171.observed_from_input(scan_index, se, sig)
        if point is None:
            continue
        if constructed is not None and abs(point.signed_n) != constructed[2]:
            continue
        key = (
            point.source,
            point.signed_n & 3,
            point.point.cell,
            point.point.a,
        )
        if key in states:
            continue
        active = [
            candidate
            for candidate in CANDIDATES
            if counts[candidate.name] < per_candidate
            and candidate.gate.selected(point)
        ]
        if not active:
            continue
        terms = h173.make_terms(point)
        baseline = profile(terms, None)
        separated = []
        masks = []
        for candidate in active:
            mask = h147.difference_mask(
                baseline, profile(terms, candidate)
            )
            if mask:
                separated.append(candidate)
                masks.append(mask)
        if not separated:
            continue
        states.add(key)
        rows.append(f"{se:04x} {sig:016x}")
        labels = ",".join(
            f"{candidate.name}:{mask:02x}"
            for candidate, mask in zip(separated, masks)
        )
        meta.append(
            f"{scan_index} {point.source} "
            f"{point.signed_n} {point.point.cell} {labels}"
        )
        for candidate in separated:
            counts[candidate.name] += 1
        if all(
            counts[candidate.name] >= per_candidate
            for candidate in CANDIDATES
        ):
            break
    missing = {
        candidate.name: counts[candidate.name]
        for candidate in CANDIDATES
        if counts[candidate.name] < per_candidate
    }
    if missing:
        raise SystemExit(
            f"h175 stopped after {scan_limit} scans; "
            f"incomplete={missing}"
        )
    output.write_text("\n".join(rows) + "\n")
    metadata.write_text("\n".join(meta) + "\n")
    print(
        f"h175: selected {len(rows)} inputs from "
        f"{scan_index + 1} scans; "
        f"per-candidate={dict(sorted(counts.items()))}; "
        f"seed={SEED:#x}",
        file=sys.stderr,
    )


def load_capture(
    inputs: pathlib.Path, capture: pathlib.Path
) -> list[h131.Observed]:
    operands = [
        tuple(int(field, 16) for field in line.split())
        for line in inputs.read_text().splitlines()
    ]
    modes = [
        (
            capture
            / f"constraint_fsin_table_path_gate_h175_{rc}_status.txt"
        ).read_text().splitlines()
        for rc in h58.RCS
    ]
    if any(len(lines) != len(operands) for lines in modes):
        raise SystemExit("h175 input/capture line counts differ")
    result = []
    for index, (se, sig) in enumerate(operands):
        point = h171.observed_from_input(index, se, sig)
        if point is None:
            raise SystemExit(
                f"h175 input {index + 1} is not active"
            )
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
            outputs.append(
                (int(fields[1], 16), int(fields[2], 16))
            )
            c1.append(bool(int(fields[4], 16) & 0x0200))
        result.append(
            dataclasses.replace(
                point,
                outputs=tuple(outputs),
                c1=tuple(c1),
            )
        )
    return result


def score(
    points: list[h131.Observed],
    candidate: Conditional | None,
) -> h110.Score:
    result = h110.Score()
    for point in points:
        terms = h173.make_terms(point)
        schedule = (
            candidate.candidate
            if candidate is not None
            and candidate.gate.selected(point)
            else h173.CURRENT
        )
        value = h173.hidden(terms, schedule)
        result.total += 1
        any_miss = False
        for index, rc in enumerate(h58.RCS):
            output = h58.x87_round(value, rc)
            mismatch = output != point.outputs[index]
            result.mode_misses += mismatch
            any_miss |= mismatch
            if not mismatch:
                c1 = (
                    h110.compare_magnitude(output, value) > 0
                )
                result.c1_misses += c1 != point.c1[index]
        result.output_misses += any_miss
    return result


def componentwise(
    value: h110.Score, baseline: h110.Score
) -> bool:
    return all(
        candidate <= old
        for candidate, old in zip(
            value.rank(), baseline.rank()
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--score", type=pathlib.Path)
    parser.add_argument("--per-candidate", type=int, default=64)
    parser.add_argument(
        "--scan-limit", type=int, default=30_000_000
    )
    parser.add_argument(
        "--output", type=pathlib.Path, default=DEFAULT_OUTPUT
    )
    parser.add_argument(
        "--metadata",
        type=pathlib.Path,
        default=DEFAULT_METADATA,
    )
    args = parser.parse_args()
    if args.generate:
        generate(
            args.output,
            args.metadata,
            args.per_candidate,
            args.scan_limit,
        )
    if args.score is not None:
        points = load_capture(args.output, args.score)
        metadata = args.metadata.read_text().splitlines()
        print(
            f"loaded {len(points)} fresh h175 separators"
        )
        for candidate in CANDIDATES:
            targeted = [
                point
                for point, line in zip(points, metadata)
                if any(
                    item.split(":", 1)[0] == candidate.name
                    for item in line.split()[-1].split(",")
                )
            ]
            baseline = score(targeted, None)
            value = score(targeted, candidate)
            status = (
                "PASS"
                if componentwise(value, baseline)
                else "FAIL"
            )
            print(
                f"{status} {candidate.name:36s} "
                f"n={len(targeted):3d} "
                f"{baseline.describe()} -> "
                f"{value.describe()}"
            )
    if not args.generate and args.score is None:
        parser.error(
            "select --generate and/or --score CAPTURE_DIRECTORY"
        )


if __name__ == "__main__":
    main()
