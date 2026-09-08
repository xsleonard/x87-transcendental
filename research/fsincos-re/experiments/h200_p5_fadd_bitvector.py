#!/usr/bin/env python3
"""Test the patent-level P5 FADD carrier in the shared P/Q Horner chains.

h173-h199 materialize each intermediate as a scalar floating-point value.
US 5,257,215 exposes a different state for FADD: a 68-bit FAMUBUS holding
an overflow bit, the 64-bit extended mantissa, and G/R/S.  The far path
first appends another low position, aligns the smaller operand with a
right shifter and sticky generator, and performs the X2 subtraction before
compressing the result back onto FAMUBUS.  A sticky one can consequently
launch a borrow through the retained word; that state cannot be represented
by selecting a scalar width and rounding mode after an exact addition.

Every wide P/Q Horner addition in the measured corpus is an unlike-sign far
subtraction with exponent difference at least eleven, so this experiment
implements only the patent-backed path that is actually exercised.  It
tests two readings of the diagram's separate shifted-mantissa/sticky wires:

* ``jam-sub``: jam the discarded tail into bit zero before subtraction;
* ``mark-after``: subtract the truncated alignment and preserve the tail in
  the outgoing sticky bit.

For each reading, a five-bit mask selects which FADD stages bypass FRND
rounding and retain the raw 67-bit normalized carrier.  Unselected stages
still traverse the literal FADD path before applying the currently validated
RN64 or terminal Round-35 materialization.  P-only, Q-only, and coordinated
P/Q masks are grouped by exact observed sample profile, then checked on the
complete sweep.  Any survivor is additionally gated on dense and fresh
h183/h185/h189 joint-lane captures.  No hardware output is consulted while
constructing the candidates.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import functools
import hashlib

import h58_constraint_search as h58
import h79_table_state_bias as h79
import h110_fsin_standalone as h110
import h131_fsin_table_c1_search as h131
import h134_fsin_table_per_edge_search as h134
import h136_tang_reconstruction_search as h136
import h170_fsin_table_correction_search as h170
import h173_fsin_table_fadd_topology as h173
import h182_table_joint_terminal_edges as h182
import h183_table_joint_product_discriminator as h183
import h184_table_lookup_firc_routes as h184
import h185_table_lookup_firc_discriminator as h185
import h188_table_stage_local_pairs as h188
import h189_table_stage_local_discriminator as h189
import h190_table_stage_local_c_parity as h190


Metric = h173.Metric
JointMetric = tuple[Metric, Metric]
RN64 = h110.Quant(64, "rn")
AWAY64 = h110.Quant(64, "away")
CHOP65 = h110.Quant(65, "chop")
ROUND34 = h184.Candidate(p_product="rn64")
FADD_MODES = ("jam-sub", "mark-after")
STAGES = 5


@dataclasses.dataclass(frozen=True)
class Bus:
    """FAMUBUS magnitude: J is bit 66 and G/R/S are bits 2/1/0.

    J may be zero only when FRND normalization is explicitly disabled.
    """

    sign: int
    exponent: int
    word: int

    def value(self) -> h58.FP:
        if not self.word:
            return h58.ZERO
        return self.sign, self.word, self.exponent - 66


@dataclasses.dataclass(frozen=True)
class Candidate:
    mode: str = "scalar"
    p_mask: int | None = None
    q_mask: int | None = None
    normalize_retained: bool = True

    def short(self) -> str:
        if self.mode == "scalar":
            return "current Round35 scalar"

        def show(name: str, mask: int | None) -> str:
            if mask is None:
                return f"{name}=scalar"
            stages = "".join(
                str(index + 1)
                for index in range(STAGES)
                if mask & (1 << index)
            )
            return f"{name}=literal-retain[{stages or '-'}]"

        normalization = "norm" if self.normalize_retained else "raw"
        return (
            f"{self.mode}/{normalization} "
            f"{show('P', self.p_mask)} {show('Q', self.q_mask)}"
        )


CURRENT = Candidate()


def normalized_bus(value: h58.FP) -> Bus:
    """Place an already materialized <=67-bit value on FAMUBUS."""
    sign, significand, scale = value
    if not significand:
        return Bus(sign, 0, 0)
    width = significand.bit_length()
    if width > 67:
        raise ValueError(f"FAMUBUS input has {width} significant bits")
    return Bus(sign, scale + width - 1, significand << (67 - width))


def shift_right(value: int, amount: int) -> tuple[int, bool]:
    """Return a truncated shift and whether any discarded bit was one."""
    if amount <= 0:
        return value << -amount, False
    if amount >= value.bit_length():
        return 0, bool(value)
    mask = (1 << amount) - 1
    return value >> amount, bool(value & mask)


def fadd_far_sub(
    big: Bus, small: Bus, mode: str, normalize: bool = True
) -> Bus:
    """Replay FIG. 2's right-shifter/X2-adder far-subtraction path.

    FAX1NS and FAX1RS occupy bits 68:1, leaving bit zero for the
    alignment sticky.  The ordinary normalized result has its J bit at raw
    position 67, so the FAMUBUS interface performs a one-position jammed
    compression after the subtraction.
    """
    if big.sign == small.sign:
        raise ValueError("h200 only implements the exercised subtraction path")
    difference = big.exponent - small.exponent
    if difference <= 1:
        raise ValueError(f"h200 received near subtraction d={difference}")
    shifted, discarded = shift_right(small.word << 1, difference)
    if mode == "jam-sub":
        if discarded:
            shifted |= 1
        raw = (big.word << 1) - shifted
        outgoing_sticky = False
    elif mode == "borrow-sticky":
        # FAX1RS occupies 68:1 while FAX1STK is drawn separately.  In a
        # subtract path that wire can supply the two's-complement borrow-in:
        # subtract the next integer when a discarded tail exists, then keep
        # sticky set because the exact remainder is (1 - discarded_tail).
        raw = (big.word << 1) - shifted - int(discarded)
        outgoing_sticky = discarded
    elif mode == "borrow-clear":
        # Companion falsifier: same borrow-in, but no complemented-tail
        # sticky retention.
        raw = (big.word << 1) - shifted - int(discarded)
        outgoing_sticky = False
    elif mode == "mark-after":
        raw = (big.word << 1) - shifted
        outgoing_sticky = discarded
    else:
        raise ValueError(mode)
    if raw <= 0 or raw.bit_length() not in (67, 68):
        raise ValueError(
            f"far result is not normalized: d={difference} raw={raw:#x}"
        )
    if raw.bit_length() == 68:
        word = raw >> 1
        if (raw & 1) or outgoing_sticky:
            word |= 1
        exponent = big.exponent
    elif normalize:
        # A power-of-two coefficient minus any nonzero aligned product is
        # the patent's one-bit-left-normalization case.  Raw bit 66 already
        # occupies the outgoing J position, and FEXP lowers the exponent.
        word = raw
        if outgoing_sticky:
            word |= 1
        exponent = big.exponent - 1
    else:
        # FRND permits normalization and rounding to be disabled
        # independently.  With normalization off, compress X2 onto
        # FAMUBUS without the one-bit-left adjustment; J remains zero.
        word = raw >> 1
        if (raw & 1) or outgoing_sticky:
            word |= 1
        exponent = big.exponent
    expected_width = 67 if normalize or raw.bit_length() == 68 else 66
    if word.bit_length() != expected_width:
        raise ValueError(f"bad FAMUBUS result {word:#x}")
    return Bus(big.sign, exponent, word)


def fadd_bus(
    left: Bus, right: Bus, mode: str, normalize: bool = True
) -> Bus:
    """Dispatch the observed unlike-sign, far-subtraction FADD case."""
    if left.sign == right.sign:
        raise ValueError("unexpected like-sign Horner addition")
    if (left.exponent, left.word) >= (right.exponent, right.word):
        return fadd_far_sub(left, right, mode, normalize)
    return fadd_far_sub(right, left, mode, normalize)


def materialize_bus(bus: Bus, quant: h110.Quant) -> Bus:
    return normalized_bus(h110.quantize(bus.value(), quant))


def literal_horner(
    rows: tuple[int, ...],
    square: h58.FP,
    coefficients: tuple[h110.Quant, ...],
    products: tuple[h110.Quant, ...],
    sums: tuple[h110.Quant, ...],
    mask: int,
    mode: str,
    normalize_retained: bool = True,
) -> h58.FP:
    value = normalized_bus(h134.coefficient(rows[0], coefficients[0]))
    for index, row in enumerate(rows[1:]):
        # The retained FADD carrier occupies FMUL's 67-bit X input; the
        # already-RN64 square occupies Y.  FMUL's validated writeback mode
        # remains the path schedule's product materialization.
        product = h110.quantize(
            h58.mul_exact(value.value(), square), products[index]
        )
        product_bus = normalized_bus(product)
        coefficient = normalized_bus(
            h134.coefficient(row, coefficients[index + 1])
        )
        retain = bool(mask & (1 << index))
        value = fadd_bus(
            product_bus,
            coefficient,
            mode,
            normalize=normalize_retained or not retain,
        )
        if not retain:
            value = materialize_bus(value, sums[index])
    return value.value()


@functools.lru_cache(maxsize=None)
def p_value(
    point: h188.Point,
    mask: int | None,
    mode: str,
    normalize_retained: bool = True,
) -> h58.FP:
    if mask is None:
        return h188.producer(point, h189.CANDIDATES[1])
    schedule = point.base
    return literal_horner(
        h58.S6,
        point.square,
        (*schedule.p_coefficients[:-1], AWAY64),
        schedule.p_products,
        (*schedule.p_sums[:-1], CHOP65),
        mask,
        mode,
        normalize_retained,
    )


@functools.lru_cache(maxsize=None)
def q_value(
    point: h188.Point,
    mask: int | None,
    mode: str,
    shared: bool,
    normalize_retained: bool = True,
) -> h58.FP:
    schedule = h134.CURRENT if shared else point.base
    if mask is None:
        return h134.horner(
            h58.C6,
            point.square,
            schedule.q_coefficients,
            schedule.q_products,
            schedule.q_sums,
        )
    return literal_horner(
        h58.C6,
        point.square,
        schedule.q_coefficients,
        schedule.q_products,
        schedule.q_sums,
        mask,
        mode,
        normalize_retained,
    )


def hidden_values(
    point: h188.Point, candidate: Candidate
) -> tuple[h58.FP, h58.FP]:
    if candidate == CURRENT:
        return h190.hidden_values(point, True)
    prepared = point.joint.observed.point
    p = p_value(
        point,
        candidate.p_mask,
        candidate.mode,
        candidate.normalize_retained,
    )

    p_square = h110.quantize(h58.mul_exact(p, point.square), RN64)
    correction = h110.quantize(
        h58.mul_exact(p_square, prepared.a), RN64
    )
    sine_a = h110.quantize(
        h58.add_exact(prepared.a, correction), RN64
    )
    sine_a = h79.bias_toward_zero(sine_a, 5)
    sine_correction = h58.add_exact(sine_a, h58.neg(prepared.a))

    def state(q: h58.FP) -> h136.State:
        tail = h110.quantize(h58.mul_exact(q, point.square), RN64)
        return h136.State(prepared.a, sine_correction, tail)

    sine_q = q_value(
        point,
        candidate.q_mask,
        candidate.mode,
        False,
        candidate.normalize_retained,
    )
    shared_q = q_value(
        point,
        candidate.q_mask,
        candidate.mode,
        True,
        candidate.normalize_retained,
    )
    sine = h184.values(
        h184.Point(point.joint, state(sine_q), None), ROUND34
    )[0]
    cosine = h184.values(
        h184.Point(point.joint, state(shared_q), None), ROUND34
    )[1]
    return sine, cosine


def point_metric(point: h188.Point, candidate: Candidate) -> JointMetric:
    sine, cosine = hidden_values(point, candidate)
    return (
        h170.point_metric(point.joint.observed, sine),
        h182.point_metric(
            point.joint.cosine_outputs,
            point.joint.cosine_c1,
            cosine,
        ),
    )


def add(left: JointMetric, right: JointMetric) -> JointMetric:
    return tuple(
        h170.add(old, new) for old, new in zip(left, right)
    )  # type: ignore[return-value]


def score_signature(
    datasets: list[tuple[str, list[h188.Point]]], candidate: Candidate
) -> tuple[list[JointMetric], bytes]:
    digest = hashlib.sha256()
    values = []
    for name, points in datasets:
        digest.update(name.encode("ascii"))
        result: JointMetric = ((0, 0, 0), (0, 0, 0))
        for point in points:
            metric = point_metric(point, candidate)
            digest.update(bytes((*metric[0], *metric[1])))
            result = add(result, metric)
        values.append(result)
    return values, digest.digest()


def no_worse(value: JointMetric, baseline: JointMetric) -> bool:
    return all(
        h173.no_worse(new, old) for new, old in zip(value, baseline)
    )


def objective(values: list[JointMetric]) -> tuple[int, int, int]:
    return tuple(
        sum(metric[index] for value in values for metric in value)
        for index in (0, 2, 1)
    )


def candidates() -> tuple[Candidate, ...]:
    result = [CURRENT]
    for mode in FADD_MODES:
        result.extend(Candidate(mode, mask, None) for mask in range(32))
        result.extend(Candidate(mode, None, mask) for mask in range(32))
        result.extend(
            Candidate(mode, p_mask, q_mask)
            for p_mask in range(32)
            for q_mask in range(32)
        )
    return tuple(dict.fromkeys(result))


def partitions(name: str) -> list[tuple[str, list[h188.Point]]]:
    points = [
        h188.prepare(point)
        for point in h184.dataset(name)
        if point.observed.family == "wide"
    ]
    return [
        (
            f"{name}-{split}",
            [
                point
                for point in points
                if h131.is_train(point.joint.observed)
                == (split == "train")
            ],
        )
        for split in ("train", "held")
    ]


def assert_baseline(points: list[tuple[str, list[h188.Point]]]) -> None:
    for name, selected in points:
        for point in selected:
            if point_metric(point, CURRENT) != h190.metric(point, True):
                observed = point.joint.observed
                raise SystemExit(
                    f"h200 baseline mismatch: {name} line {observed.index + 1}"
                )


def fresh_datasets() -> list[tuple[str, list[h188.Point]]]:
    result: list[tuple[str, list[h188.Point]]] = []
    result.append(
        (
            "h183",
            [
                h188.prepare(point)
                for point in h183.load_capture(
                    h183.DEFAULT_OUTPUT,
                    h183.ROOT
                    / "capture-kit-captures"
                    / "skylake-fsin-h183",
                )
                if point.observed.family == "wide"
            ],
        )
    )
    result.append(
        (
            "h185",
            [
                h188.prepare(point)
                for point in h185.load_capture(
                    h185.DEFAULT_OUTPUT,
                    h185.ROOT
                    / "capture-kit-captures"
                    / "skylake-fsin-h185",
                )
                if point.observed.family == "wide"
            ],
        )
    )
    result.append(
        (
            "h189",
            h189.load_capture(
                h189.DEFAULT_OUTPUT,
                h189.ROOT
                / "capture-kit-captures"
                / "skylake-fsin-h189",
            ),
        )
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sample-controls",
        type=int,
        default=400,
        help="correct controls retained per sweep half",
    )
    args = parser.parse_args()

    sweep = partitions("sweep")
    assert_baseline(sweep)
    sample = h194_sample = []
    # Keep every currently wrong point and a deterministic independent
    # control set, matching h194's selection without importing its mutable
    # candidate implementation into the literal carrier.
    for name, points in sweep:
        constrained = []
        controls = []
        for point in points:
            target = (
                constrained
                if point_metric(point, CURRENT)
                != ((0, 0, 0), (0, 0, 0))
                else controls
            )
            target.append(point)
        controls.sort(
            key=lambda point: (
                point.joint.observed.point.raw.sig
                ^ (point.joint.observed.point.raw.sig >> 23)
                ^ point.joint.observed.index
                ^ point.joint.observed.signed_n
            )
        )
        h194_sample.append(
            (name, constrained + controls[: args.sample_controls])
        )
    sample = h194_sample

    sample_baselines, baseline_signature = score_signature(sample, CURRENT)
    print(
        f"h200 literal FADD: candidates={len(candidates())} "
        f"wide-sweep={sum(len(points) for _, points in sweep)} "
        f"sample={sum(len(points) for _, points in sample)}"
    )
    for (name, points), baseline in zip(sweep, score_signature(sweep, CURRENT)[0]):
        print(
            f"  baseline {name:11s} n={len(points):5d} "
            f"sine={baseline[0]} cosine={baseline[1]}"
        )

    profiles: dict[bytes, list[tuple]] = collections.defaultdict(list)
    raw_ranked = []
    for candidate in candidates()[1:]:
        values, signature = score_signature(sample, candidate)
        item = (*objective(values), candidate.short(), candidate, values)
        raw_ranked.append(item)
        if (
            signature != baseline_signature
            and all(
                no_worse(value, baseline)
                for value, baseline in zip(values, sample_baselines)
            )
            and any(
                value != baseline
                for value, baseline in zip(values, sample_baselines)
            )
        ):
            profiles[signature].append(item)
    raw_ranked.sort()
    representatives = sorted(min(items) for items in profiles.values())
    print("  leading raw sample candidates:")
    for item in raw_ranked[:12]:
        print(
            f"    modes/c1/inputs={item[0]}/{item[1]}/{item[2]} "
            f"{item[4].short()}"
        )
    print(
        f"h200 sample gate: {sum(len(items) for items in profiles.values())} "
        f"survivors in {len(representatives)} exact profiles"
    )
    if not representatives:
        print("h200 complete sweep gate: 0 survivors")
        print("h200 dense/fresh gate: 0 survivors")
        return

    complete_baselines = score_signature(sweep, CURRENT)[0]
    complete_survivors = []
    complete_ranked = []
    for item in representatives:
        candidate = item[4]
        values, _ = score_signature(sweep, candidate)
        complete_ranked.append(
            (*objective(values), candidate.short(), candidate, values)
        )
        if all(
            no_worse(value, baseline)
            for value, baseline in zip(values, complete_baselines)
        ) and any(
            value != baseline
            for value, baseline in zip(values, complete_baselines)
        ):
            complete_survivors.append(
                (*objective(values), candidate.short(), candidate, values)
            )
    complete_ranked.sort()
    complete_survivors.sort()
    print("  complete sweep profile representatives:")
    for item in complete_ranked:
        print(
            f"    modes/c1/inputs={item[0]}/{item[1]}/{item[2]} "
            f"{item[4].short()} values={item[5]}"
        )
    print(
        f"h200 complete sweep gate: {len(complete_survivors)} survivors"
    )
    for item in complete_survivors[:12]:
        print(
            f"  modes/c1/inputs={item[0]}/{item[1]}/{item[2]} "
            f"{item[4].short()}"
        )
    if not complete_survivors:
        print("h200 dense/fresh gate: 0 survivors")
        return

    # Bound the expensive final pass by exact complete-sweep profiles.
    dense_and_fresh = [*partitions("dense"), *fresh_datasets()]
    assert_baseline(dense_and_fresh)
    final_baselines = score_signature(dense_and_fresh, CURRENT)[0]
    final = []
    for item in complete_survivors:
        candidate = item[4]
        values, _ = score_signature(dense_and_fresh, candidate)
        if all(
            no_worse(value, baseline)
            for value, baseline in zip(values, final_baselines)
        ) and any(
            value != baseline
            for value, baseline in zip(values, final_baselines)
        ):
            final.append((candidate, values))
    print(f"h200 dense/fresh gate: {len(final)} survivors")
    for candidate, values in final:
        print(f"  {candidate.short()}")
        for (name, _), baseline, value in zip(
            dense_and_fresh, final_baselines, values
        ):
            if value != baseline:
                print(f"    {name:11s} {baseline}->{value}")


if __name__ == "__main__":
    main()
