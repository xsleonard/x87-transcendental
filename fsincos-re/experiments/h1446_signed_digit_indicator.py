#!/usr/bin/env python3
"""Audit the signed discarded-chunk indicator disclosed by US5042001.

US5042001 (Cyrix, 1991) describes a transcendental polynomial engine built
around a 69-by-18-bit rectangular multiplier.  A full 69-by-71-bit product is
formed low-first in four passes over multiplier quadrants 18, 18, 18, and 17
bits wide.  Unlike an ordinary sticky-bit path, each retired low chunk is kept
in redundant signed-digit form.  A two-bit indicator remembers whether any
retired chunk was nonzero and the sign of the most-significant nonzero chunk.
The final signed-digit converter decrements the retained result when that
discarded value is negative.

This is a genuinely different observable from the exact-carry and OR-sticky
families already audited.  The implementation below is literal and checked
before labels are scored:

* digits are {-1, 0, +1};
* every adder uses the patent's Figure-4 borrow/carry truth table;
* six radix-8 Booth rows feed the published three-level 72/75/81/88-bit tree;
* the 71-bit multiplier is consumed as 18/18/18/17 low-first quadrants;
* product bits above each retired 18-bit chunk remain redundant feedback;
* the last pass retires 12 bits and applies the published negative decrement;
* the retired-chunk identity reconstructs the complete 69-by-71-bit product.

Both operand-port orientations are included because multiplication is
numerically symmetric but this rectangular representation is not.  Only the
source's named indicator, Booth-boundary, and converter signals are scored.
There are no operand identities, thresholds, interval searches, learned
trees, or x87 executions.  This establishes an exact Cyrix representation
and a possible isomorphism; it is not Intel or Skylake provenance.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

import h1425_p5_public_mux_signals as h1425
import h1432_multiformat_split_adder_logic as h1432
import h1441_iterative_multiplier_feedback as h1441
from h1110_carry_gate_mine import GATE_NAMES


PATENT = "US5042001A"
PATENT_URL = "https://patents.google.com/patent/US5042001A/en"
SOURCE_VENDOR = "Cyrix"
FMUL_STAGES = h1441.FMUL_STAGES
ROLES = ("written", "swapped")
MULTIPLICAND_WIDTH = 69
MULTIPLIER_WIDTH = 71
QUADRANT_WIDTH = 18
FINAL_QUADRANT_WIDTH = 17
PRODUCT_WIDTH = 88
RESULT_WIDTH = 87
FINAL_RETIRED_WIDTH = 12


# Figure 4, in x/y order (-1,-1), (-1,0), (-1,+1), (0,-1), ...,
# for each (borrow-in, carry-in).  Each entry is
# (borrow-out, carry-out, result-digit).
FIGURE4_ORDER = tuple(
    (left, right) for left in (-1, 0, 1) for right in (-1, 0, 1)
)
FIGURE4_ROWS = {
    (0, 0): (
        (1, 0, 0), (1, 1, -1), (1, 1, 0),
        (1, 1, -1), (0, 0, 0), (0, 1, -1),
        (1, 1, 0), (0, 1, -1), (0, 1, 0),
    ),
    (0, 1): (
        (1, 0, 1), (1, 1, 0), (1, 1, 1),
        (1, 1, 0), (0, 0, 1), (0, 1, 0),
        (1, 1, 1), (0, 1, 0), (0, 1, 1),
    ),
    (1, 0): (
        (1, 0, -1), (1, 0, 0), (1, 1, -1),
        (1, 0, 0), (0, 0, -1), (0, 0, 0),
        (1, 1, -1), (0, 0, 0), (0, 1, -1),
    ),
    (1, 1): (
        (1, 0, 0), (1, 0, 1), (1, 1, 0),
        (1, 0, 1), (0, 0, 0), (0, 0, 1),
        (1, 1, 0), (0, 0, 1), (0, 1, 0),
    ),
}

# Figure 4's six explicitly modified most-significant cells suppress a
# redundant leading carry/borrow pair.  The listed value is the replacement
# result digit; no higher output digit is retained.
TOP_OVERRIDES = {
    (0, 0, 0, 1): 1,
    (0, 0, 1, 0): 1,
    (0, 1, -1, -1): -1,
    (1, 0, 1, 1): 1,
    (1, 1, -1, 0): -1,
    (1, 1, 0, -1): -1,
}


def validate_figure4_table() -> None:
    """Check the transcribed table's arithmetic and stated independences."""
    for borrow in (0, 1):
        for carry in (0, 1):
            rows = FIGURE4_ROWS[(borrow, carry)]
            if len(rows) != len(FIGURE4_ORDER):
                raise RuntimeError("incomplete Figure-4 transcription")
            for index, (left, right) in enumerate(FIGURE4_ORDER):
                borrow_out, carry_out, result = rows[index]
                if left + right + carry - borrow != (
                    result + 2 * carry_out - 2 * borrow_out
                ):
                    raise RuntimeError("Figure-4 cell changed arithmetic")
                if borrow_out != FIGURE4_ROWS[(0, carry)][index][0]:
                    raise RuntimeError("Figure-4 borrow depends on borrow-in")
                if carry_out != FIGURE4_ROWS[(borrow, 0)][index][1]:
                    raise RuntimeError("Figure-4 carry depends on carry-in")


validate_figure4_table()


@dataclass(frozen=True)
class SignedDigits:
    """One-hot positive and negative masks for {-1,0,+1} digits."""

    positive: int
    negative: int
    width: int

    def __post_init__(self) -> None:
        mask = (1 << self.width) - 1
        if self.positive & self.negative:
            raise ValueError("signed-digit masks overlap")
        if (self.positive | self.negative) & ~mask:
            raise ValueError("signed-digit mask exceeds declared width")

    def value(self) -> int:
        return self.positive - self.negative

    def slice(self, low: int, high: int) -> "SignedDigits":
        if not 0 <= low <= high <= self.width:
            raise ValueError("invalid signed-digit slice")
        width = high - low
        mask = (1 << width) - 1
        return SignedDigits(
            (self.positive >> low) & mask,
            (self.negative >> low) & mask,
            width,
        )


@dataclass(frozen=True)
class PreparedRow:
    row: dict[str, str]
    current: int
    required: int
    target: bool
    signals: bytes
    trace: tuple[tuple[object, ...], ...]


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def unsigned_digits(value: int, width: int) -> SignedDigits:
    if value < 0 or value.bit_length() > width:
        raise ValueError("unsigned value does not fit signed-digit port")
    return SignedDigits(value, 0, width)


def digit_masks(value: SignedDigits, offset: int, width: int) -> dict[int, int]:
    if offset < 0 or value.width + offset > width:
        raise ValueError("signed-digit alignment exceeds output")
    mask = (1 << width) - 1
    positive = value.positive << offset
    negative = value.negative << offset
    return {
        -1: negative,
        0: mask & ~(positive | negative),
        1: positive,
    }


def figure4_add(
    left: SignedDigits,
    right: SignedDigits,
    width: int,
    left_offset: int = 0,
    right_offset: int = 0,
) -> SignedDigits:
    """Apply the complete Figure-4 digit recurrence in parallel."""
    mask = (1 << width) - 1
    left_masks = digit_masks(left, left_offset, width)
    right_masks = digit_masks(right, right_offset, width)

    # Borrow-out is independent of borrow-in and carry-in in the published
    # table, so the complete borrow-in vector is known immediately.
    borrow_out = left_masks[-1] | right_masks[-1]
    borrow_in = (borrow_out << 1) & mask

    # Carry-out is independent of carry-in.  Use the literal table after the
    # borrow vector has been established.
    carry_out = 0
    borrow_masks = {0: mask & ~borrow_in, 1: borrow_in}
    for borrow in (0, 1):
        for left_digit, right_digit in FIGURE4_ORDER:
            index = FIGURE4_ORDER.index((left_digit, right_digit))
            expected_borrow, carry, _ = FIGURE4_ROWS[(borrow, 0)][index]
            if expected_borrow != int(left_digit < 0 or right_digit < 0):
                raise RuntimeError("Figure-4 borrow independence changed")
            if carry:
                carry_out |= (
                    borrow_masks[borrow]
                    & left_masks[left_digit]
                    & right_masks[right_digit]
                )
    carry_in = (carry_out << 1) & mask
    carry_masks = {0: mask & ~carry_in, 1: carry_in}

    positive = 0
    negative = 0
    for borrow in (0, 1):
        for carry in (0, 1):
            rows = FIGURE4_ROWS[(borrow, carry)]
            for index, (left_digit, right_digit) in enumerate(FIGURE4_ORDER):
                expected_borrow, expected_carry, result = rows[index]
                if expected_borrow != int(left_digit < 0 or right_digit < 0):
                    raise RuntimeError("Figure-4 borrow output mismatch")
                # The paper states carry-out is independent of carry-in.
                if expected_carry != FIGURE4_ROWS[(borrow, 0)][index][1]:
                    raise RuntimeError("Figure-4 carry independence changed")
                positions = (
                    borrow_masks[borrow]
                    & carry_masks[carry]
                    & left_masks[left_digit]
                    & right_masks[right_digit]
                )
                if result > 0:
                    positive |= positions
                elif result < 0:
                    negative |= positions

    top = width - 1
    top_bit = 1 << top
    top_key = (
        int(bool(borrow_in & top_bit)),
        int(bool(carry_in & top_bit)),
        -1 if left_masks[-1] & top_bit else
        1 if left_masks[1] & top_bit else 0,
        -1 if right_masks[-1] & top_bit else
        1 if right_masks[1] & top_bit else 0,
    )
    if top_key in TOP_OVERRIDES:
        positive &= ~top_bit
        negative &= ~top_bit
        replacement = TOP_OVERRIDES[top_key]
        if replacement > 0:
            positive |= top_bit
        elif replacement < 0:
            negative |= top_bit

    result = SignedDigits(positive & mask, negative & mask, width)
    expected = (
        (left.value() << left_offset)
        + (right.value() << right_offset)
    )
    if result.value() != expected:
        raise RuntimeError(
            "Figure-4 adder lost arithmetic: "
            f"width={width} offsets={left_offset},{right_offset} "
            f"got={result.value()} expected={expected} top={top_key}"
        )
    return result


def negate(value: SignedDigits) -> SignedDigits:
    return SignedDigits(value.negative, value.positive, value.width)


def shifted(value: SignedDigits, amount: int, width: int) -> SignedDigits:
    if value.width + amount > width:
        raise ValueError("shifted signed-digit value exceeds width")
    return SignedDigits(value.positive << amount, value.negative << amount, width)


def booth_digits(chunk: int, carry_in: int) -> tuple[int, ...]:
    if not 0 <= chunk < (1 << QUADRANT_WIDTH) or carry_in not in (0, 1):
        raise ValueError("invalid radix-8 Booth quadrant")
    digits = []
    for index in range(6):
        triad = (chunk >> (3 * index)) & 7
        overlap = carry_in if index == 0 else (
            (chunk >> (3 * index - 1)) & 1
        )
        digit = (triad - 8 if triad & 4 else triad) + overlap
        if not -4 <= digit <= 4:
            raise RuntimeError("radix-8 Booth digit out of range")
        digits.append(digit)
    expected = chunk - (((chunk >> 17) & 1) << 18) + carry_in
    represented = sum(digit << (3 * index)
                      for index, digit in enumerate(digits))
    if represented != expected:
        raise RuntimeError("radix-8 Booth boundary identity failed")
    return tuple(digits)


def partial_products(
    multiplicand: SignedDigits, chunk: int, carry_in: int,
) -> tuple[tuple[SignedDigits, ...], tuple[int, ...]]:
    if multiplicand.width != 70:
        raise ValueError("Cyrix multiplicand port must include 70 digits")
    times_one = shifted(multiplicand, 0, 72)
    times_two = shifted(multiplicand, 1, 72)
    times_three = figure4_add(
        multiplicand, multiplicand, 72, right_offset=1
    )
    times_four = shifted(multiplicand, 2, 72)
    multiples = {
        0: unsigned_digits(0, 72),
        1: times_one,
        2: times_two,
        3: times_three,
        4: times_four,
    }
    encoded = booth_digits(chunk, carry_in)
    products = tuple(
        negate(multiples[-digit]) if digit < 0 else multiples[digit]
        for digit in encoded
    )
    for digit, product in zip(encoded, products):
        expected = digit * multiplicand.value()
        if product.value() != expected:
            raise RuntimeError("partial-product generator changed arithmetic")
    return products, encoded


def multiplier_core(
    multiplicand: SignedDigits,
    chunk: int,
    carry_in: int,
    feedback: SignedDigits,
) -> tuple[SignedDigits, tuple[int, ...]]:
    """The published 72/75/81/88-bit three-level multiplier tree."""
    if feedback.width != PRODUCT_WIDTH:
        raise ValueError("feedback port width changed")
    products, encoded = partial_products(multiplicand, chunk, carry_in)
    level1_left = figure4_add(products[0], products[1], 75, right_offset=3)
    level1_middle = figure4_add(products[2], products[3], 75, right_offset=3)
    level1_right = figure4_add(products[4], products[5], 75, right_offset=3)

    # ADDER INPUT is zero for ordinary full-precision multiplication.  It is
    # nevertheless passed through the disclosed fourth level-one adder so
    # that the redundant representation, not just its integer value, is kept.
    feedback_path = figure4_add(
        unsigned_digits(0, PRODUCT_WIDTH), feedback, PRODUCT_WIDTH
    )
    level2_left = figure4_add(
        level1_left, level1_middle, 81, right_offset=6
    )
    # The third PPG pair begins at radix-8 column 12.  This is the unique
    # numerical alignment that preserves the Booth expansion; the patent's
    # prose describes the buses as MSB-aligned because their leading digit is
    # an overflow/sign digit.
    level2_right = figure4_add(
        level1_right, feedback_path, PRODUCT_WIDTH, left_offset=12
    )
    product = figure4_add(level2_left, level2_right, PRODUCT_WIDTH)

    segment = sum(digit << (3 * index)
                  for index, digit in enumerate(encoded))
    expected = multiplicand.value() * segment + feedback.value()
    if product.value() != expected:
        raise RuntimeError("published multiplier tree changed arithmetic")
    return product, encoded


def result_latch(product: SignedDigits) -> SignedDigits:
    """Apply the patent's corrected truncation of the top overflow digit."""
    if product.width != PRODUCT_WIDTH:
        raise ValueError("unexpected multiplier product width")
    top = product.slice(RESULT_WIDTH, PRODUCT_WIDTH)
    positive = product.positive & ((1 << RESULT_WIDTH) - 1)
    negative = product.negative & ((1 << RESULT_WIDTH) - 1)
    if top.value():
        # The patent's leading-one correction drops the overflow digit and
        # inverts the sign of the next digit.  A leading (+1,-1) pair becomes
        # +1 and a leading (-1,+1) pair becomes -1, preserving the value.
        next_bit = 1 << (RESULT_WIDTH - 1)
        next_digit = (
            1 if positive & next_bit else -1 if negative & next_bit else 0
        )
        if next_digit != -top.value():
            raise RuntimeError(
                "overflow digit is not followed by the published leading-one pair"
            )
        positive &= ~next_bit
        negative &= ~next_bit
        if top.value() > 0:
            positive |= next_bit
        else:
            negative |= next_bit
    result = SignedDigits(positive, negative, RESULT_WIDTH)
    if result.value() != product.value():
        raise RuntimeError("result-latch truncation changed arithmetic")
    return result


def full_multiply(
    left: h1441.Value,
    right: h1441.Value,
    role: str,
) -> tuple[dict[str, int], tuple[object, ...]]:
    if role == "swapped":
        left, right = right, left
    elif role != "written":
        raise ValueError(role)

    a = h1441.normalized_significand(left, MULTIPLICAND_WIDTH)
    b = h1441.normalized_significand(right, MULTIPLIER_WIDTH)
    multiplicand = unsigned_digits(a, 70)  # appended zero overflow digit
    chunks = (
        b & ((1 << 18) - 1),
        (b >> 18) & ((1 << 18) - 1),
        (b >> 36) & ((1 << 18) - 1),
        (b >> 54) & ((1 << 17) - 1),
    )
    carry_ins = (0, (b >> 17) & 1, (b >> 35) & 1, (b >> 53) & 1)

    values: dict[str, int] = {}
    feedback = unsigned_digits(0, PRODUCT_WIDTH)
    indicator_nonzero = 0
    indicator_negative = 0
    discarded = 0
    trace = []

    for pass_index, (chunk, carry_in) in enumerate(
        zip(chunks, carry_ins), start=1
    ):
        product, encoded = multiplier_core(
            multiplicand, chunk, carry_in, feedback
        )
        result = result_latch(product)
        retire_width = (
            FINAL_RETIRED_WIDTH if pass_index == 4 else QUADRANT_WIDTH
        )
        retired = result.slice(0, retire_width)
        retired_value = retired.value()
        retired_nonzero = int(retired_value != 0)
        retired_negative = int(retired_value < 0)
        if retired_nonzero:
            indicator_nonzero = 1
            indicator_negative = retired_negative

        shift = QUADRANT_WIDTH * (pass_index - 1)
        discarded += retired_value << shift
        prefix = f"pass{pass_index}"
        local = {
            "booth.carry_in": carry_in,
            "booth.top_negative": int(encoded[-1] < 0),
            "booth.any_negative": int(any(digit < 0 for digit in encoded)),
            "product.lsb_positive": product.positive & 1,
            "product.lsb_negative": product.negative & 1,
            "retired.any": retired_nonzero,
            "retired.negative": retired_negative,
            "retired.positive": int(retired_value > 0),
            "indicator.nonzero": indicator_nonzero,
            "indicator.negative": indicator_negative,
        }
        values.update({f"{prefix}.{name}": value
                       for name, value in local.items()})
        trace.append((
            pass_index,
            chunk,
            carry_in,
            encoded,
            retired_value,
            indicator_nonzero,
            indicator_negative,
        ))

        if pass_index < 4:
            feedback_low = result.slice(QUADRANT_WIDTH, RESULT_WIDTH)
            feedback = SignedDigits(
                feedback_low.positive,
                feedback_low.negative,
                PRODUCT_WIDTH,
            )
            values[f"{prefix}.feedback.lsb_positive"] = (
                feedback.positive & 1
            )
            values[f"{prefix}.feedback.lsb_negative"] = (
                feedback.negative & 1
            )
        else:
            retained = result.slice(FINAL_RETIRED_WIDTH, RESULT_WIDTH)

    exact_product = a * b
    retained_shift = 3 * QUADRANT_WIDTH + FINAL_RETIRED_WIDTH
    if retained_shift != 66:
        raise RuntimeError("Cyrix retained-product alignment changed")
    if exact_product != discarded + (retained.value() << retained_shift):
        raise RuntimeError("retired signed chunks do not reconstruct product")
    if indicator_nonzero != int(discarded != 0):
        raise RuntimeError("indicator nonzero recurrence lost discarded value")
    if indicator_negative != int(discarded < 0):
        raise RuntimeError("indicator sign recurrence lost discarded value")
    corrected = retained.value() - indicator_negative
    if corrected != exact_product >> retained_shift:
        raise RuntimeError("published negative-decrement conversion is not exact")

    values.update({
        "final.discarded_nonzero": int(discarded != 0),
        "final.discarded_negative": int(discarded < 0),
        "final.converter_decrement": indicator_negative,
        "final.retained_lsb": retained.value() & 1,
        "final.corrected_lsb": corrected & 1,
    })
    return values, (role, a, b, discarded, retained.value(), corrected, tuple(trace))


def source_signals(
    row: dict[str, str],
) -> tuple[dict[str, int], tuple[tuple[object, ...], ...]]:
    values: dict[str, int] = {}
    traces = []
    for stage, operands in h1441.fmul_inputs(row).items():
        for role in ROLES:
            local, trace = full_multiply(*operands, role)
            stem = f"{stage}.{role}"
            values.update({f"{stem}.{name}": value
                           for name, value in local.items()})
            traces.append((stage, trace))
    return values, tuple(traces)


def prepare(args: argparse.Namespace) -> tuple[
    list[PreparedRow], list[dict[str, str]], tuple[str, ...]
]:
    base, source_rows, _, _ = h1425.prepare(args)
    prepared = []
    names: tuple[str, ...] | None = None
    for row_index, item in enumerate(base):
        values, trace = source_signals(item.row)
        if names is None:
            names = tuple(sorted(values))
        elif set(values) != set(names):
            raise RuntimeError("signed-digit indicator schema changed")
        prepared.append(PreparedRow(
            row=item.row,
            current=item.current,
            required=item.required,
            target=item.target,
            signals=bytes(values[name] for name in names),
            trace=trace if item.target else (),
        ))
        if row_index and row_index % 4000 == 0:
            print(f"  reconstructed {row_index}/{len(base)} rows", flush=True)
    if names is None:
        raise RuntimeError("no constraining rows")
    return prepared, source_rows, names


def structural_pairs(names: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    available = set(names)
    pairs = []
    for stage in FMUL_STAGES:
        prefix = f"{stage}.written."
        for name in names:
            if not name.startswith(prefix):
                continue
            suffix = name[len(prefix):]
            pair = (name, f"{stage}.swapped.{suffix}")
            if pair[1] in available:
                pairs.append(pair)
    return tuple(pairs)


def history_collisions(
    prepared: list[PreparedRow], names: tuple[str, ...]
) -> tuple[list[tuple[object, ...]], int]:
    indices = {name: index for index, name in enumerate(names)}
    suffixes = tuple(sorted({
        name.split(".", 2)[2]
        for name in names
        if name.startswith(FMUL_STAGES[0] + ".")
    }))
    results = []
    exact = 0
    for suffix in suffixes:
        columns = tuple(
            indices[f"{stage}.{role}.{suffix}"]
            for stage in FMUL_STAGES
            for role in ROLES
        )
        groups = defaultdict(lambda: [[], []])
        for item in prepared:
            history = bytes(item.signals[index] for index in columns)
            groups[(item.row["branch"], item.current, history)][
                item.required
            ].append(item)
        mixed = 0
        targets_in_mixed = 0
        witnesses = []
        for members in groups.values():
            if not members[0] or not members[1]:
                continue
            mixed += 1
            targets = [item for side in members for item in side if item.target]
            targets_in_mixed += len(targets)
            if len(witnesses) < 3:
                witnesses.append((
                    tuple((item.row["mode"], item.row["op"])
                          for item in targets),
                    (members[0][0].row["mode"], members[0][0].row["op"]),
                    (members[1][0].row["mode"], members[1][0].row["op"]),
                ))
        exact += mixed == 0
        results.append((suffix, mixed, targets_in_mixed, tuple(witnesses)))
    return results, exact


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("positive_allmode", type=Path)
    parser.add_argument("control_allmode", type=Path)
    parser.add_argument("model", type=Path)
    parser.add_argument("misses", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--extra-op", default=h1425.EXTRA_OP)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    prepared, source_rows, names = prepare(args)
    matrix = np.frombuffer(
        b"".join(item.signals for item in prepared), dtype=np.uint8
    ).reshape(len(prepared), len(names))
    current = np.asarray([item.current for item in prepared], dtype=np.uint8)
    required = np.asarray([item.required for item in prepared], dtype=np.uint8)
    target = np.asarray([item.target for item in prepared], dtype=bool)
    target_count = int(target.sum())

    gate_ranking = []
    for signal_index, name in enumerate(names):
        signal = matrix[:, signal_index]
        selector = 2 * current + signal
        for gate in range(16):
            prediction = ((gate >> selector) & 1).astype(np.uint8)
            changed = prediction != current
            gate_ranking.append((
                *h1432.score_prediction(prediction, required, target),
                int(changed[~target].sum()),
                GATE_NAMES[gate],
                gate,
                name,
            ))
    gate_ranking.sort()
    gate_exact = [item for item in gate_ranking if item[0] == 0]
    gate_improvements = [
        item for item in gate_ranking
        if item[2] == 0 and item[1] < target_count
    ]
    nonidentity_gates = [item for item in gate_ranking if item[5] != 12]

    indices = {name: index for index, name in enumerate(names)}
    pair_ranking = []
    pairs = structural_pairs(names)
    for left_name, right_name in pairs:
        selector = (
            4 * current
            + 2 * matrix[:, indices[left_name]]
            + matrix[:, indices[right_name]]
        )
        for gate in range(256):
            prediction = ((gate >> selector) & 1).astype(np.uint8)
            wrong = prediction != required
            changed = prediction != current
            pair_ranking.append((
                int(wrong.sum()),
                int(wrong[target].sum()),
                int(wrong[~target].sum()),
                int(changed[~target].sum()),
                f"0x{gate:02x}",
                left_name,
                right_name,
            ))
    pair_ranking.sort()
    pair_exact = [item for item in pair_ranking if item[0] == 0]
    pair_improvements = [
        item for item in pair_ranking
        if item[2] == 0 and item[1] < target_count
    ]
    nonidentity_pairs = [
        item for item in pair_ranking if item[4] != "0xf0"
    ]

    histories, exact_histories = history_collisions(prepared, names)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        for label, path in (
            ("features", args.features),
            ("positive_allmode", args.positive_allmode),
            ("control_allmode", args.control_allmode),
            ("model", args.model),
            ("misses", args.misses),
        ):
            output.write(f"{label}_sha256\t{digest(path)}\n")
        output.write("hardware_policy\timmutable_cached_labels_no_x87_execution\n")
        output.write(
            f"primary_source\t{PATENT}\t{PATENT_URL}\tsource_vendor={SOURCE_VENDOR}\n"
        )
        output.write(
            "source_scope\texact_Cyrix_signed_digit_representation_possible_"
            "isomorphism_not_Intel_or_Skylake_provenance\n"
        )
        output.write(
            "candidate_policy\tsource_named_indicator_Booth_boundary_and_"
            "converter_signals_only_no_operand_fitting\n"
        )
        output.write(
            "arithmetic_identity\tretired18x3_plus_retired12_plus_"
            "retained75_reconstructs_69x71_product\n"
        )
        output.write(
            "converter_identity\tretained75-indicator_negative="
            "floor(product/2^66)\n"
        )
        output.write("operand_ports\t69x71\n")
        output.write("operand_roles\twritten,swapped\n")
        output.write("quadrants\t18,18,18,17\n")
        output.write("fmul_stages\t" + ",".join(FMUL_STAGES) + "\n")
        output.write(f"source_rows\t{len(source_rows)}\n")
        output.write(f"constraining_mode_rows\t{len(prepared)}\n")
        output.write(f"target_mode_rows\t{target_count}\n")
        output.write(f"control_mode_rows\t{len(prepared) - target_count}\n")
        output.write(f"candidate_signals\t{len(names)}\n")
        output.write(f"global_gate_programs\t{len(gate_ranking)}\n")
        output.write(f"global_gate_exact\t{len(gate_exact)}\n")
        output.write(
            "global_gate_zero_control_improvements\t"
            f"{len(gate_improvements)}\n"
        )
        output.write(
            "best_nonidentity_global_gate\t"
            + "\t".join(map(str, nonidentity_gates[0])) + "\n"
        )
        output.write(f"structural_pairs\t{len(pairs)}\n")
        output.write(f"structural_pair_gate_programs\t{len(pair_ranking)}\n")
        output.write(f"structural_pair_gate_exact\t{len(pair_exact)}\n")
        output.write(
            "structural_pair_gate_zero_control_improvements\t"
            f"{len(pair_improvements)}\n"
        )
        output.write(
            "best_nonidentity_structural_pair_gate\t"
            + "\t".join(map(str, nonidentity_pairs[0])) + "\n"
        )
        output.write(f"history_streams\t{len(histories)}\n")
        output.write(f"collision_free_history_streams\t{exact_histories}\n")

        output.write("\n[best global gates]\n")
        output.write(
            "errors\ttarget_errors\tcontrol_errors\tcontrol_changes\t"
            "gate\tgate_mask\tsignal\n"
        )
        for item in gate_ranking[:256]:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[best nonidentity global gates]\n")
        for item in nonidentity_gates[:64]:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[zero-control global improvements]\n")
        for item in gate_improvements:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[best written/swapped pair gates]\n")
        output.write(
            "errors\ttarget_errors\tcontrol_errors\tcontrol_changes\t"
            "gate_mask\twritten_signal\tswapped_signal\n"
        )
        for item in pair_ranking[:256]:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[best nonidentity written/swapped pair gates]\n")
        for item in nonidentity_pairs[:64]:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[zero-control written/swapped improvements]\n")
        for item in pair_improvements:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[complete indicator-history collisions]\n")
        output.write("suffix\tmixed_groups\ttargets_in_mixed\twitnesses\n")
        for item in histories:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[target signed-digit traces]\n")
        output.write("mode\top\tcurrent\trequired\ttraces\n")
        for item in prepared:
            if item.target:
                output.write("\t".join((
                    item.row["mode"],
                    item.row["op"],
                    str(item.current),
                    str(item.required),
                    repr(item.trace),
                )) + "\n")

        output.write("\n[result]\n")
        if gate_exact or pair_exact:
            output.write("signed_digit_indicator_selector\tCANDIDATE_ONLY\n")
        else:
            output.write("signed_digit_indicator_selector\tno_exact_program\n")


if __name__ == "__main__":
    main()
