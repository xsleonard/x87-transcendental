#!/usr/bin/env python3
"""Reconstruct the standalone Intel FSIN direct-polynomial datapath.

The Pentium II and Skylake standalone RN results are identical on all
240,000 dense inputs.  The extended Skylake capture adds standalone RD/RU
results and C1, which says whether the final significand was incremented.
Together these constrain the hidden pre-round value much more tightly than
the historical RN-only PII capture.

This pass starts from h64's cross-validated standalone survivor and performs
a coordinate search over independently quantized square, coefficient,
per-Horner-edge product/sum, and sine-tail operations.  Search choices are
made on a weighted sample of disagreements plus controls; every accepted
change must independently improve both complete training and held-out halves.
"""

from __future__ import annotations

import dataclasses
import pathlib
from collections.abc import Callable, Iterable

import h58_constraint_search as h58
import h64_poly_constraints as h64


ROOT = pathlib.Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "capture-kit-captures" / "skylake-fsin-h110"


@dataclasses.dataclass(frozen=True)
class Quant:
    bits: int
    mode: str

    def short(self) -> str:
        return "exact" if self.bits == 0 else f"{self.bits}{self.mode[0]}"


EXACT = Quant(0, "exact")


@dataclasses.dataclass(frozen=True)
class Schedule:
    square: Quant
    coefficient: Quant
    products: tuple[Quant, ...]
    sums: tuple[Quant, ...]
    m: Quant
    correction: Quant
    topology: str = "direct"
    one_plus_m: Quant = EXACT
    final_product: Quant = EXACT
    coefficient_overrides: tuple[Quant, ...] = ()
    coefficient_deltas: tuple[int, ...] = ()

    def short(self) -> str:
        products = ",".join(value.short() for value in self.products)
        sums = ",".join(value.short() for value in self.sums)
        tail = (
            f"m={self.m.short()}/corr={self.correction.short()}"
            if self.topology == "direct"
            else (
                f"m={self.m.short()}/u={self.one_plus_m.short()}"
                f"/final={self.final_product.short()}"
            )
        )
        return (
            f"sq={self.square.short()}/c={self.coefficient.short()}"
            + (
                "/ci=[" + ",".join(
                    value.short()
                    for value in self.coefficient_overrides
                ) + "]"
                if self.coefficient_overrides
                else ""
            )
            + (
                "/cd=[" + ",".join(
                    str(value) for value in self.coefficient_deltas
                ) + "]"
                if any(self.coefficient_deltas)
                else ""
            )
            + f"/prod=[{products}]/sum=[{sums}]/{self.topology}:{tail}"
        )


H64_START = Schedule(
    square=Quant(66, "rn"),
    coefficient=Quant(67, "rn"),
    products=(Quant(69, "rn"),) * 5,
    sums=(Quant(69, "rn"),) * 5,
    m=Quant(65, "chop"),
    correction=EXACT,
)

MULTISTART = Schedule(
    square=Quant(67, "chop"),
    coefficient=Quant(67, "rn"),
    products=(
        Quant(69, "rn"),
        Quant(69, "rn"),
        Quant(69, "rn"),
        Quant(69, "rn"),
        Quant(64, "away"),
    ),
    sums=(
        Quant(69, "rn"),
        Quant(69, "rn"),
        Quant(69, "rn"),
        Quant(64, "away"),
        Quant(67, "rn"),
    ),
    m=Quant(64, "rn"),
    correction=Quant(67, "chop"),
)

FSIN_SURVIVOR = dataclasses.replace(
    MULTISTART,
    coefficient_overrides=(
        Quant(67, "rn"),
        Quant(67, "rn"),
        Quant(67, "rn"),
        Quant(67, "rn"),
        Quant(64, "away"),
        Quant(67, "rn"),
    ),
    sums=(
        Quant(69, "rn"),
        Quant(69, "rn"),
        Quant(69, "rn"),
        Quant(64, "rn"),
        Quant(67, "rn"),
    ),
)


@dataclasses.dataclass(frozen=True)
class Observed:
    raw: h64.PolyRaw
    outputs: tuple[tuple[int, int], ...]
    c1: tuple[bool, ...]


@dataclasses.dataclass
class Score:
    mode_misses: float = 0
    output_misses: float = 0
    c1_misses: float = 0
    total: float = 0

    def rank(self) -> tuple[float, float, float]:
        return self.mode_misses, self.output_misses, self.c1_misses

    def describe(self) -> str:
        return (
            f"mode={self.mode_misses:.0f}/{3 * self.total:.0f} "
            f"output={self.output_misses:.0f}/{self.total:.0f} "
            f"C1={self.c1_misses:.0f}/{3 * self.total:.0f}"
        )


def round_to_odd(value: h58.FP, bits: int) -> h58.FP:
    sign, significand, scale = value
    shift = significand.bit_length() - bits
    if shift <= 0:
        return value
    top = significand >> shift
    if significand & ((1 << shift) - 1):
        top |= 1
    return sign, top, scale + shift


def quantize(value: h58.FP, quant: Quant) -> h58.FP:
    if quant.bits == 0:
        return value
    if quant.mode == "odd":
        return round_to_odd(value, quant.bits)
    if quant.mode == "ru":
        return h58.round_fp(
            value,
            quant.bits,
            "away" if not value[0] else "chop",
        )
    if quant.mode == "rd":
        return h58.round_fp(
            value,
            quant.bits,
            "away" if value[0] else "chop",
        )
    return h58.round_fp(value, quant.bits, quant.mode)


def load_observed() -> list[Observed]:
    raw = h64.load_raw()
    paths = [CAPTURE / f"dense_fsin_{rc}_status.txt" for rc in h58.RCS]
    for path in paths:
        if not path.exists():
            raise SystemExit(f"missing extended standalone capture: {path}")
    lines = [path.read_text().splitlines() for path in paths]
    if any(len(mode) != 240000 for mode in lines):
        raise SystemExit("extended standalone capture line count differs")
    result = []
    for point in raw:
        outputs = []
        c1 = []
        for mode in lines:
            fields = mode[point.index].split()
            if (
                len(fields) != 5
                or fields[0] != "OK"
                or fields[3] != "SW"
            ):
                raise ValueError(mode[point.index])
            outputs.append((int(fields[1], 16), int(fields[2], 16)))
            c1.append(bool(int(fields[4], 16) & 0x0200))
        if outputs[0] != point.standalone[0]:
            raise SystemExit(
                f"Skylake/PII standalone RN mismatch at {point.index}"
            )
        result.append(
            Observed(point, tuple(outputs), tuple(c1))
        )
    return result


def coefficient(
    row: int, schedule: Schedule, index: int
) -> h58.FP:
    quant = (
        schedule.coefficient_overrides[index]
        if schedule.coefficient_overrides
        else schedule.coefficient
    )
    raw = h58.ROM[row]
    delta = (
        schedule.coefficient_deltas[index]
        if schedule.coefficient_deltas
        else 0
    )
    adjusted = raw[0], raw[1] + delta, raw[2]
    return quantize(adjusted, quant)


def hidden_value(point: Observed, schedule: Schedule) -> h58.FP:
    raw = point.raw
    magnitude: h58.FP = (0, raw.sig, raw.exponent - 63)
    square = quantize(
        h58.mul_exact(magnitude, magnitude), schedule.square
    )
    value = coefficient(h58.S6[0], schedule, 0)
    for index, row in enumerate(h58.S6[1:]):
        product = quantize(
            h58.mul_exact(value, square), schedule.products[index]
        )
        value = quantize(
            h58.add_exact(
                product, coefficient(row, schedule, index + 1)
            ),
            schedule.sums[index],
        )
    m = quantize(h58.mul_exact(value, square), schedule.m)
    if schedule.topology == "direct":
        correction = quantize(
            h58.mul_exact(m, magnitude), schedule.correction
        )
        result = h58.add_exact(magnitude, correction)
    elif schedule.topology == "factored":
        factor = quantize(
            h58.add_exact(h58.ONE, m), schedule.one_plus_m
        )
        result = quantize(
            h58.mul_exact(magnitude, factor), schedule.final_product
        )
    else:
        raise ValueError(schedule.topology)
    return h58.neg(result) if raw.sign else result


def compare_magnitude(output: tuple[int, int], hidden: h58.FP) -> int:
    se, significand = output
    output_scale = (se & 0x7FFF) - 16383 - 63
    scale = min(output_scale, hidden[2])
    output_integer = significand << (output_scale - scale)
    hidden_integer = hidden[1] << (hidden[2] - scale)
    return (
        (output_integer > hidden_integer)
        - (output_integer < hidden_integer)
    )


def score(
    points: Iterable[Observed],
    schedule: Schedule,
    weights: dict[int, float] | None = None,
) -> Score:
    result = Score()
    for point in points:
        weight = (
            weights.get(point.raw.index, 1.0) if weights else 1.0
        )
        hidden = hidden_value(point, schedule)
        result.total += weight
        any_miss = False
        for index, rc in enumerate(h58.RCS):
            predicted = h58.x87_round(hidden, rc)
            expected = point.outputs[index]
            mismatch = predicted != expected
            result.mode_misses += mismatch * weight
            any_miss |= mismatch
            if not mismatch:
                predicted_c1 = compare_magnitude(expected, hidden) > 0
                result.c1_misses += (
                    predicted_c1 != point.c1[index]
                ) * weight
        result.output_misses += any_miss * weight
    return result


def is_train(point: Observed) -> bool:
    raw = point.raw
    return not (
        (
            raw.sig
            ^ (raw.sig >> 19)
            ^ (raw.sig >> 43)
            ^ raw.sign
        )
        & 1
    )


def sample_for_search(
    points: list[Observed], schedule: Schedule, controls: int
) -> tuple[list[Observed], dict[int, float]]:
    active = []
    exact_groups: dict[tuple[int, int], list[Observed]] = {}
    for point in points:
        point_score = score((point,), schedule)
        if point_score.mode_misses or point_score.c1_misses:
            active.append(point)
        else:
            key = point.raw.sign, (point.raw.sig >> 60) & 7
            exact_groups.setdefault(key, []).append(point)
    quota = max(1, controls // len(exact_groups))
    selected = list(active)
    weights = {point.raw.index: 1.0 for point in active}
    for key in sorted(exact_groups):
        group = exact_groups[key]
        count = min(quota, len(group))
        chosen = [
            group[(index * len(group)) // count]
            for index in range(count)
        ]
        selected.extend(chosen)
        group_weight = len(group) / count
        for point in chosen:
            weights[point.raw.index] = group_weight
    print(
        f"search sample: {len(active)} constrained + "
        f"{len(selected) - len(active)} controls "
        f"(weighted to {sum(weights.values()):.0f})"
    )
    return selected, weights


def quant_options(
    minimum: int = 64,
    maximum: int = 72,
    exact: bool = False,
) -> tuple[Quant, ...]:
    values = tuple(
        Quant(bits, mode)
        for bits in range(minimum, maximum + 1)
        for mode in ("rn", "chop", "odd", "away")
    )
    return ((EXACT,) + values) if exact else values


@dataclasses.dataclass(frozen=True)
class Coordinate:
    name: str
    candidates: Callable[[Schedule], Iterable[Schedule]]


def replace_tuple(
    values: tuple[Quant, ...], index: int, replacement: Quant
) -> tuple[Quant, ...]:
    changed = list(values)
    changed[index] = replacement
    return tuple(changed)


def coordinates() -> list[Coordinate]:
    result = [
        Coordinate(
            "square",
            lambda schedule: (
                dataclasses.replace(schedule, square=value)
                for value in quant_options()
            ),
        ),
        Coordinate(
            "coefficient",
            lambda schedule: (
                dataclasses.replace(schedule, coefficient=value)
                for value in quant_options(64, 68)
            ),
        ),
    ]
    for index in range(5):
        result.append(
            Coordinate(
                f"product-{index + 1}",
                lambda schedule, index=index: (
                    dataclasses.replace(
                        schedule,
                        products=replace_tuple(
                            schedule.products, index, value
                        ),
                    )
                    for value in quant_options(exact=True)
                ),
            )
        )
        result.append(
            Coordinate(
                f"sum-{index + 1}",
                lambda schedule, index=index: (
                    dataclasses.replace(
                        schedule,
                        sums=replace_tuple(
                            schedule.sums, index, value
                        ),
                    )
                    for value in quant_options()
                ),
            )
        )
    for index in range(6):
        result.append(
            Coordinate(
                f"coefficient-{index + 1}",
                lambda schedule, index=index: (
                    dataclasses.replace(
                        schedule,
                        coefficient_overrides=replace_tuple(
                            (
                                schedule.coefficient_overrides
                                or (schedule.coefficient,) * 6
                            ),
                            index,
                            value,
                        ),
                    )
                    for value in quant_options(64, 68)
                ),
            )
        )
    result.extend(
        (
            Coordinate(
                "m",
                lambda schedule: (
                    dataclasses.replace(schedule, m=value)
                    for value in quant_options(exact=True)
                ),
            ),
            Coordinate(
                "correction",
                lambda schedule: (
                    dataclasses.replace(schedule, correction=value)
                    for value in quant_options(exact=True)
                ),
            ),
        )
    )
    return result


def no_worse(
    candidate: Score, baseline: Score, strict: bool = False
) -> bool:
    result = candidate.rank() <= baseline.rank()
    return result and (not strict or candidate.rank() < baseline.rank())


def optimize(
    train: list[Observed],
    heldout: list[Observed],
    start: Schedule,
    controls: int,
    passes: int,
) -> Schedule:
    current = start
    train_search, train_weights = sample_for_search(
        train, start, controls
    )
    heldout_search, heldout_weights = sample_for_search(
        heldout, start, controls
    )
    for pass_index in range(passes):
        print(f"\ncoordinate pass {pass_index + 1}")
        changed = False
        for coordinate in coordinates():
            unique = tuple(dict.fromkeys(coordinate.candidates(current)))
            ranked = sorted(
                (
                    score(
                        train_search, candidate, train_weights
                    ).rank(),
                    candidate.short(),
                    candidate,
                )
                for candidate in unique
            )
            train_base = score(
                train_search, current, train_weights
            )
            heldout_base = score(
                heldout_search, current, heldout_weights
            )
            accepted = None
            for _, _, candidate in ranked[:8]:
                train_score = score(
                    train_search, candidate, train_weights
                )
                heldout_score = score(
                    heldout_search, candidate, heldout_weights
                )
                if (
                    no_worse(train_score, train_base)
                    and no_worse(heldout_score, heldout_base)
                    and (
                        train_score.rank() < train_base.rank()
                        or heldout_score.rank() < heldout_base.rank()
                    )
                ):
                    accepted = candidate, train_score, heldout_score
                    break
            if accepted is None:
                continue
            current, train_score, heldout_score = accepted
            changed = True
            print(
                f"  {coordinate.name:12s} -> "
                f"train {train_score.describe()}; "
                f"heldout {heldout_score.describe()}"
            )
            print(f"    {current.short()}")
        if not changed:
            break
    return current


def topology_candidates(schedule: Schedule) -> Iterable[Schedule]:
    for one_plus_m in quant_options(exact=True):
        yield dataclasses.replace(
            schedule,
            topology="factored",
            one_plus_m=one_plus_m,
            final_product=EXACT,
        )
    for final_product in quant_options(exact=True):
        yield dataclasses.replace(
            schedule,
            topology="factored",
            one_plus_m=EXACT,
            final_product=final_product,
        )
    yield schedule


def main() -> None:
    points = load_observed()
    train = [point for point in points if is_train(point)]
    heldout = [point for point in points if not is_train(point)]
    print(
        f"loaded {len(points)} standalone polynomial inputs: "
        f"{len(train)} train, {len(heldout)} held out"
    )
    print(f"h64 start: {H64_START.short()}")
    print(f"  complete {score(points, H64_START).describe()}")
    print(f"multistart: {MULTISTART.short()}")
    print(f"  train   {score(train, MULTISTART).describe()}")
    print(f"  heldout {score(heldout, MULTISTART).describe()}")
    print(f"  complete {score(points, MULTISTART).describe()}")

    winner = optimize(
        train, heldout, MULTISTART, controls=2500, passes=5
    )

    topology_train, topology_train_weights = sample_for_search(
        train, winner, 2500
    )
    topology_heldout, topology_heldout_weights = sample_for_search(
        heldout, winner, 2500
    )
    topology_rows = sorted(
        (
            score(
                topology_train, candidate, topology_train_weights
            ).rank(),
            score(
                topology_heldout, candidate, topology_heldout_weights
            ).rank(),
            candidate.short(),
            candidate,
        )
        for candidate in topology_candidates(winner)
    )
    train_base = score(
        topology_train, winner, topology_train_weights
    )
    heldout_base = score(
        topology_heldout, winner, topology_heldout_weights
    )
    for _, _, _, candidate in topology_rows[:12]:
        train_score = score(
            topology_train, candidate, topology_train_weights
        )
        heldout_score = score(
            topology_heldout, candidate, topology_heldout_weights
        )
        if (
            no_worse(train_score, train_base)
            and no_worse(heldout_score, heldout_base)
        ):
            winner = candidate
            break

    print("\nvalidated standalone FSIN survivor")
    print(f"  {winner.short()}")
    print(f"  train    {score(train, winner).describe()}")
    print(f"  heldout  {score(heldout, winner).describe()}")
    print(f"  complete {score(points, winner).describe()}")


if __name__ == "__main__":
    main()
