#!/usr/bin/env python3
"""Distinguish h162's fifth-product and coefficient equivalence classes.

h161 rejects extending Round 32 at the fifth sum, but exposes a small,
cross-gated improvement one operation earlier.  h162 leaves 32 product
and seven coefficient grids observationally tied.  This pass predeclares
those grids and constructs large architectural inputs from randomized
odd range-reduction quotients.  It keeps only inputs where a grid changes
an output or C1 prediction relative to Round 32.
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
import h119_fcos_standalone as h119
import h121_fsin_internal_cosine as h121
import h147_fsin_cosine_boolean_discriminator as h147
import h150_fsin_cosine_boolean_round30 as h150
import h162_fsin_cosine_round32_residual_search as h162


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_fsin_cosine_product_h163.txt"
)
DEFAULT_METADATA = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_fsin_cosine_product_h163.meta.txt"
)
SEED = 0xF163C5


@dataclasses.dataclass(frozen=True)
class Candidate:
    name: str
    variant: h162.Variant
    kind: str
    quant: h110.Quant


@dataclasses.dataclass(frozen=True)
class State:
    point: h121.Point
    schedule: h119.Schedule
    square: h58.FP
    prefix3: h58.FP
    sum4: h58.FP
    product5_exact: h58.FP


def product_quants() -> tuple[h110.Quant, ...]:
    return (
        h110.Quant(64, "away"),
        h110.Quant(64, "odd"),
        h110.Quant(65, "away"),
        h110.Quant(65, "odd"),
        h110.Quant(66, "rn"),
        h110.Quant(66, "odd"),
        h110.Quant(66, "away"),
        *tuple(
            h110.Quant(bits, mode)
            for bits in range(67, 73)
            for mode in ("rn", "chop", "odd", "away")
        ),
        h110.EXACT,
    )


def coefficient_quants() -> tuple[h110.Quant, ...]:
    return (
        h110.Quant(64, "rn"),
        h110.Quant(64, "odd"),
        h110.Quant(64, "away"),
        h110.Quant(65, "rn"),
        h110.Quant(65, "away"),
        h110.Quant(66, "rn"),
        h110.Quant(66, "away"),
    )


def make_candidates() -> tuple[Candidate, ...]:
    result = []
    for quant in product_quants():
        schedule = dataclasses.replace(
            h162.CURRENT,
            products=h110.replace_tuple(
                h162.CURRENT.products, 4, quant
            ),
        )
        result.append(
            Candidate(
                f"product5-{quant.short()}",
                h162.Variant(
                    f"product5-{quant.short()}",
                    schedule,
                    "product-5",
                ),
                "product",
                quant,
            )
        )
    for quant in coefficient_quants():
        overrides = h110.replace_tuple(
            h162.CURRENT.coefficient_overrides,
            4,
            quant,
        )
        schedule = dataclasses.replace(
            h162.CURRENT,
            coefficient_overrides=overrides,
        )
        result.append(
            Candidate(
                f"coefficient5-{quant.short()}",
                h162.Variant(
                    f"coefficient5-{quant.short()}",
                    schedule,
                    "coefficient-5",
                ),
                "coefficient",
                quant,
            )
        )
    return tuple(result)


CANDIDATES = make_candidates()


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


def prepare_state(point: h121.Point) -> State:
    schedule = h150.base_schedule(point)
    magnitude: h58.FP = (
        0,
        point.observed.raw.sig,
        point.observed.raw.exponent - 63,
    )
    square = h110.quantize(
        h58.mul_exact(magnitude, magnitude),
        schedule.square,
    )
    value = h119.coefficient(h58.C6[0], schedule, 0)
    for index, row in enumerate(h58.C6[1:4]):
        product = h110.quantize(
            h58.mul_exact(value, square),
            schedule.products[index],
        )
        value = h110.quantize(
            h58.add_exact(
                product,
                h119.coefficient(
                    row, schedule, index + 1
                ),
            ),
            schedule.sums[index],
        )
    prefix3 = value
    product4 = h110.quantize(
        h58.mul_exact(prefix3, square),
        schedule.products[3],
    )
    sum4 = h110.quantize(
        h58.add_exact(
            product4,
            h119.coefficient(h58.C6[4], schedule, 4),
        ),
        schedule.sums[3],
    )
    return State(
        point,
        schedule,
        square,
        prefix3,
        sum4,
        h58.mul_exact(sum4, square),
    )


def selected(state: State) -> bool:
    exact = state.product5_exact
    shift = exact[1].bit_length() - 65
    top = exact[1] >> shift if shift > 0 else exact[1] << -shift
    remainder = (
        exact[1] & ((1 << shift) - 1)
        if shift > 0
        else 0
    )
    sticky = bool(
        remainder & ((1 << (shift - 1)) - 1)
    ) if shift > 1 else False
    normalized_high = (
        exact[1].bit_length()
        == state.sum4[1].bit_length()
        + state.square[1].bit_length()
    )
    round32 = not normalized_high and sticky
    second = not (top & 1) and (state.square[1] & 7) == 3
    return second and not round32


def finish(
    state: State,
    sum4: h58.FP,
    product_quant: h110.Quant,
) -> h58.FP:
    product5 = h110.quantize(
        h58.mul_exact(sum4, state.square),
        product_quant,
    )
    sum5 = h110.quantize(
        h58.add_exact(
            product5,
            h119.coefficient(
                h58.C6[5], state.schedule, 5
            ),
        ),
        state.schedule.sums[4],
    )
    tail_exact = h58.mul_exact(sum5, state.square)
    shift = tail_exact[1].bit_length() - 72
    top = (
        tail_exact[1] >> shift
        if shift > 0
        else tail_exact[1] << -shift
    )
    tail_quant = (
        h110.Quant(71, "chop")
        if top & 1
        else state.schedule.tail
    )
    tail = h110.quantize(tail_exact, tail_quant)
    value = h110.quantize(
        h58.add_exact(h58.ONE, tail),
        state.schedule.final_sum,
    )
    return h58.neg(value) if state.point.negate else value


def hidden(
    state: State, candidate: Candidate | None
) -> h58.FP:
    if candidate is None or candidate.kind == "product":
        product_quant = (
            state.schedule.products[4]
            if candidate is None
            else candidate.quant
        )
        return finish(state, state.sum4, product_quant)
    product4 = h110.quantize(
        h58.mul_exact(state.prefix3, state.square),
        state.schedule.products[3],
    )
    coefficient4 = h110.quantize(
        h58.ROM[h58.C6[4]], candidate.quant
    )
    sum4 = h110.quantize(
        h58.add_exact(product4, coefficient4),
        state.schedule.sums[3],
    )
    return finish(
        state, sum4, state.schedule.products[4]
    )


def profile(
    state: State, candidate: Candidate | None
) -> tuple[tuple[tuple[int, int], bool], ...]:
    return profile_value(hidden(state, candidate))


def construct_input(
    rng: random.Random, index: int
) -> tuple[int, int, h121.Point, int, int, int] | None:
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
    minimum = 1 << 33
    maximum = (1 << 63) - 1
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
    se = exponent + 16383
    prepared = h147.point_from_input(index, se, sig)
    if prepared is None or abs(prepared[1]) != n:
        return None
    point, signed_n, r_se, r_sig = prepared
    return se, sig, point, signed_n, r_se, r_sig


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
    residuals = set()
    for scan_index in range(scan_limit):
        prepared = construct_input(rng, scan_index)
        if prepared is None:
            continue
        se, sig, point, signed_n, r_se, r_sig = prepared
        state = prepare_state(point)
        if not selected(state):
            continue
        key = signed_n & 3, r_se, r_sig
        if key in residuals:
            continue
        baseline = profile(state, None)
        separated = []
        masks = []
        for candidate in CANDIDATES:
            if counts[candidate.name] >= per_candidate:
                continue
            candidate_profile = profile(state, candidate)
            mask = h147.difference_mask(
                baseline, candidate_profile
            )
            if mask:
                separated.append(candidate)
                masks.append(mask)
        if not separated:
            continue
        residuals.add(key)
        rows.append(f"{se:04x} {sig:016x}")
        labels = ",".join(
            f"{candidate.name}:{mask:02x}"
            for candidate, mask in zip(separated, masks)
        )
        meta.append(
            f"{scan_index} {signed_n} {r_se:04x} "
            f"{r_sig:016x} {labels}"
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
            f"h163 stopped after {scan_limit} scans; "
            f"incomplete={missing}"
        )
    output.write_text("\n".join(rows) + "\n")
    metadata.write_text("\n".join(meta) + "\n")
    print(
        f"h163: selected {len(rows)} inputs from "
        f"{scan_index + 1} constructed scans; "
        f"per-candidate={dict(sorted(counts.items()))}; "
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
            / f"constraint_fsin_cosine_product_h163_{rc}_status.txt"
        ).read_text().splitlines()
        for rc in h58.RCS
    ]
    if any(len(lines) != len(input_rows) for lines in modes):
        raise SystemExit("h163 input/capture line counts differ")
    result = []
    for index, (se, sig) in enumerate(input_rows):
        prepared = h147.point_from_input(index, se, sig)
        if prepared is None:
            raise SystemExit(
                f"h163 input {index + 1} is not active"
            )
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
            outputs.append(
                (int(fields[1], 16), int(fields[2], 16))
            )
            c1.append(bool(int(fields[4], 16) & 0x0200))
        result.append(
            dataclasses.replace(
                point,
                observed=dataclasses.replace(
                    point.observed,
                    outputs=tuple(outputs),
                    c1=tuple(c1),
                ),
            )
        )
    return result


def score(
    points: list[h121.Point],
    candidate: Candidate | None,
) -> h110.Score:
    result = h110.Score()
    for point in points:
        state = prepare_state(point)
        if not selected(state):
            raise SystemExit(
                "h163 capture contains a point outside E && !D"
            )
        value = hidden(state, candidate)
        result.total += 1
        any_miss = False
        for index, rc in enumerate(h58.RCS):
            output = h58.x87_round(value, rc)
            mismatch = output != point.observed.outputs[index]
            result.mode_misses += mismatch
            any_miss |= mismatch
            if not mismatch:
                c1 = h110.compare_magnitude(output, value) > 0
                result.c1_misses += (
                    c1 != point.observed.c1[index]
                )
        result.output_misses += any_miss
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--score", type=pathlib.Path)
    parser.add_argument("--per-candidate", type=int, default=16)
    parser.add_argument(
        "--scan-limit", type=int, default=20_000_000
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
        if len(metadata) != len(points):
            raise SystemExit(
                "h163 metadata/capture line counts differ"
            )
        baseline = score(points, None)
        print(
            f"loaded {len(points)} fresh h163 separators"
        )
        print(f"baseline {baseline.describe()}")
        survivors = []
        for candidate in CANDIDATES:
            value = score(points, candidate)
            if h110.no_worse(value, baseline):
                survivors.append(
                    (
                        value.rank(),
                        candidate.name,
                        value,
                    )
                )
        survivors.sort()
        print(
            f"h163: {len(survivors)}/{len(CANDIDATES)} "
            "candidates are componentwise no worse"
        )
        for _, name, value in survivors:
            print(f"  {name:20s} {value.describe()}")
        train = [
            point for point in points if h121.is_train(point)
        ]
        heldout = [
            point
            for point in points
            if not h121.is_train(point)
        ]
        transfer = []
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
            gates = (
                (train, score(train, None)),
                (heldout, score(heldout, None)),
                (targeted, score(targeted, None)),
            )
            values = tuple(
                score(dataset, candidate)
                for dataset, _ in gates
            )
            if all(
                h110.no_worse(value, base)
                for value, (_, base) in zip(values, gates)
            ):
                transfer.append(candidate)
        print(
            f"h163 transfer gates: {len(transfer)}/"
            f"{len(CANDIDATES)} candidates survive "
            "train/heldout/targeted subsets"
        )
        equivalence: dict[
            tuple[
                tuple[
                    tuple[tuple[int, int], bool], ...
                ],
                ...,
            ],
            list[str],
        ] = {}
        for candidate in transfer:
            signature = tuple(
                profile(prepare_state(point), candidate)
                for point in points
            )
            equivalence.setdefault(signature, []).append(
                candidate.name
            )
        groups = sorted(
            equivalence.values(),
            key=lambda names: (-len(names), names),
        )
        print(
            f"h163 prediction equivalence: "
            f"{len(groups)} classes"
        )
        for names in groups:
            representative = next(
                candidate
                for candidate in transfer
                if candidate.name == names[0]
            )
            print(
                f"  {score(points, representative).describe()} "
                f"{','.join(names)}"
            )
    if not args.generate and args.score is None:
        parser.error(
            "select --generate and/or --score CAPTURE_DIRECTORY"
        )


if __name__ == "__main__":
    main()
