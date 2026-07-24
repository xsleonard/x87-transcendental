#!/usr/bin/env python3
"""Build fresh separators for h170's table correction rules.

Six distinct correction materialization/selector mechanisms are declared
before hardware capture.  Random direct and M66-reduced table inputs are
kept only when a selected mechanism changes standalone FSIN output or C1
relative to the current RN67 Tang correction.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import pathlib
import random
import sys

import h58_constraint_search as h58
import h80_round21_parity as h80
import h110_fsin_standalone as h110
import h131_fsin_table_c1_search as h131
import h135_fsin_table_terminal_discriminator as h135
import h147_fsin_cosine_boolean_discriminator as h147
import h169_fsin_table_round33_tomography as h169
import h170_fsin_table_correction_search as h170


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_fsin_table_correction_h171.txt"
)
DEFAULT_METADATA = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_fsin_table_correction_h171.meta.txt"
)
SEED = 0xF171C5


@dataclasses.dataclass(frozen=True)
class Conditional:
    name: str
    quant: h110.Quant
    predicates: tuple[
        tuple[str, int], tuple[str, int]
    ]


CANDIDATES = (
    Conditional(
        "away69-if-cell44-q2",
        h110.Quant(69, "away"),
        (("cell", 44), ("quadrant", 2)),
    ),
    Conditional(
        "away69-if-q2-cross4",
        h110.Quant(69, "away"),
        (("quadrant", 2), ("cross.low3", 4)),
    ),
    Conditional(
        "chop66-if-lead5-qnorm1",
        h110.Quant(66, "chop"),
        (("lead.low3", 5), ("q-product.norm2", 1)),
    ),
    Conditional(
        "chop68-if-wide-q2",
        h110.Quant(68, "chop"),
        (("wide", 1), ("quadrant", 2)),
    ),
    Conditional(
        "away69-if-reduced-cross4",
        h110.Quant(69, "away"),
        (("reduced", 1), ("cross.low3", 4)),
    ),
    Conditional(
        "rn70-if-lead5-qnorm1",
        h110.Quant(70, "rn"),
        (("lead.low3", 5), ("q-product.norm2", 1)),
    ),
)


def selected(
    features: dict[str, int], candidate: Conditional
) -> bool:
    return all(
        features[name] == value
        for name, value in candidate.predicates
    )


def observed_from_input(
    index: int, se: int, sig: int
) -> h131.Observed | None:
    active = h80.active_table_input(se, sig)
    if active is None:
        return None
    signed_n, point, reduced = active
    return h131.Observed(
        index,
        "reduced" if reduced else "direct",
        signed_n,
        point,
        ((0, 0),) * len(h58.RCS),
        (False,) * len(h58.RCS),
    )


def random_input(
    rng: random.Random,
) -> tuple[int, int]:
    if rng.getrandbits(1):
        family = "narrow" if rng.getrandbits(1) else "wide"
        return h135.direct_operand(rng, family)
    exponent = rng.randrange(0, 63)
    sign = rng.getrandbits(1)
    return (
        (sign << 15) | (exponent + 16383),
        rng.randrange(1 << 63, 1 << 64),
    )


def profile_value(
    value: h58.FP,
) -> tuple[tuple[tuple[int, int], bool], ...]:
    return tuple(
        (
            output := h58.x87_round(value, rc),
            h110.compare_magnitude(output, value) > 0,
        )
        for rc in h58.RCS
    )


def profile(
    point: h131.Observed,
    candidate: Conditional | None,
) -> tuple[tuple[tuple[int, int], bool], ...]:
    prepared = h170.pipeline(point)
    features = h169.features(point)
    quant = (
        candidate.quant
        if candidate is not None
        and selected(features, candidate)
        else h170.CURRENT
    )
    return profile_value(h170.hidden(prepared, quant))


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
        se, sig = random_input(rng)
        point = observed_from_input(scan_index, se, sig)
        if point is None:
            continue
        key = (
            point.source,
            point.signed_n & 3,
            point.point.cell,
            point.point.a,
        )
        if key in states:
            continue
        prepared = h170.pipeline(point)
        features = h169.features(point)
        baseline_value = h170.hidden(
            prepared, h170.CURRENT
        )
        baseline = profile_value(baseline_value)
        separated = []
        masks = []
        for candidate in CANDIDATES:
            if (
                counts[candidate.name] >= per_candidate
                or not selected(features, candidate)
            ):
                continue
            value = h170.hidden(prepared, candidate.quant)
            mask = h147.difference_mask(
                baseline, profile_value(value)
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
            f"h171 stopped after {scan_limit} scans; "
            f"incomplete={missing}"
        )
    output.write_text("\n".join(rows) + "\n")
    metadata.write_text("\n".join(meta) + "\n")
    print(
        f"h171: selected {len(rows)} inputs from "
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
            / f"constraint_fsin_table_correction_h171_{rc}_status.txt"
        ).read_text().splitlines()
        for rc in h58.RCS
    ]
    if any(len(lines) != len(operands) for lines in modes):
        raise SystemExit("h171 input/capture line counts differ")
    result = []
    for index, (se, sig) in enumerate(operands):
        point = observed_from_input(index, se, sig)
        if point is None:
            raise SystemExit(
                f"h171 input {index + 1} is not active"
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
        prepared = h170.pipeline(point)
        feature_row = h169.features(point)
        quant = (
            candidate.quant
            if candidate is not None
            and selected(feature_row, candidate)
            else h170.CURRENT
        )
        value = h170.hidden(prepared, quant)
        result.total += 1
        any_miss = False
        for index, rc in enumerate(h58.RCS):
            output = h58.x87_round(value, rc)
            mismatch = output != point.outputs[index]
            result.mode_misses += mismatch
            any_miss |= mismatch
            if not mismatch:
                c1 = h110.compare_magnitude(output, value) > 0
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
            f"loaded {len(points)} fresh h171 separators"
        )
        for candidate in CANDIDATES:
            targeted = [
                point
                for point, line in zip(points, metadata)
                if any(
                    item.split(":", 1)[0]
                    == candidate.name
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
                f"{status} {candidate.name:29s} "
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
