#!/usr/bin/env python3
"""Audit arithmetic-isomorphic P5 multiplier representations.

The literal P5 tree used by the R59 experiments fixes several details that
the public patent does not uniquely determine: row grouping, the distinguished
input of each 4:2 compressor, correction-bit routing, the square low-digit
merge point, truncation width, and the point at which product normalization
observes the carry network.  This cached-only audit varies each assumption
around the patent transcription before asking whether a conventional fixed-
width carry recurrence can supply the nine still-open R59 carries.

Every representation must first reconstruct the exact integer product on
edge cases and on every cached row.  A failed arithmetic gate prevents all
label mining for that representation.  The candidate grammar contains no
operand constants or thresholds: a carry is propagated from a fixed reset
boundary to one of three fixed normalization attachments, then used directly
or as a fixed set/drop/toggle event on the incumbent carry.

The optional adversarial score files are prior one-shot hardware results.
Their operands are re-dumped only through the supplied software model; this
script never executes x87 hardware capture code.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from pathlib import Path

from h1386_current_r59_feature_bank import dump


TREE_BITS = 136
TREE_MASK = (1 << TREE_BITS) - 1
PRODUCT_MASK = (1 << 131) - 1
SQUARE_MASK = (1 << 134) - 1
PP_BITS = 70
PP_MASK = (1 << PP_BITS) - 1
BOOTH8 = (0, 1, 1, 2, 2, 3, 3, 4,
          -4, -3, -3, -2, -2, -1, -1, 0)
BRANCHES = ("band", "tie", "corner")
WIDTHS = tuple(range(1, 65))
ALIGNMENTS = ("suffix", "absolute", "p5")
ATTACHMENTS = (-1, 0, 1)
TRANSFORMS = (
    "block",
    "not_block",
    "current_xor_reset_error",
    "current_drop_on_reset_error",
    "current_set_on_reset_error",
    "current_xor_block",
    "current_and_block",
    "current_or_block",
)


@dataclass(frozen=True)
class TreeConfig:
    correction: str = "next_row"
    input_order: str = "natural"
    pairing: tuple[tuple[int, int], ...] = ((0, 1), (2, 3), (4, 5))
    hold: int = 2
    d_slots: tuple[int, int, int, int] = (0, 0, 0, 0)
    stage_width: int = TREE_BITS


@dataclass(frozen=True)
class Representation:
    name: str
    axis: str
    source: str
    kind: str
    config: TreeConfig = TreeConfig()
    parameter: int = 0


@dataclass
class AuditRow:
    fields: dict[str, str]
    role: str
    truth: int | None
    current: int
    branch: str


@dataclass(frozen=True)
class Candidate:
    representation: str
    axis: str
    source: str
    attachment: int
    width: int
    alignment: str
    seed: int
    transform: str
    target_miss: int
    band_miss: int
    tie_miss: int
    corner_miss: int


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        return list(csv.DictReader(source, delimiter="\t"))


def allmode_allowed(path: Path) -> dict[str, set[int]]:
    responses = defaultdict(list)
    for row in read_tsv(path):
        matches = ({int(value) - 3 for value in row["matches"].split(",")}
                   if row["matches"] != "-" else set())
        responses[row["op"]].append(matches)
    result = {}
    for operand, mode_sets in responses.items():
        if len(mode_sets) != 4:
            raise RuntimeError(f"expected four modes for {operand}")
        exact = set.intersection(*mode_sets)
        if not exact:
            raise RuntimeError(f"empty all-mode delta set for {operand}")
        result[operand] = exact
    return result


def extract_carry_state(
        row: dict[str, str], allowed_delta: set[int]
        ) -> tuple[int, int, int, set[int]]:
    s_value = int(row["S"], 16)
    b_value = int(row["B"], 16)
    cut = int(row["k"])
    mask = (1 << cut) - 1
    borrow = int((s_value & mask) < (b_value & mask))
    current_delta = (int(row["br_r"], 16)
                     - (int(row["umag"], 16) >> cut))
    current_carry = current_delta - borrow + 1
    if current_carry not in (0, 1):
        raise RuntimeError(f"incumbent is not a carry for {row['op']}")
    allowed_carry = {delta - borrow + 1 for delta in allowed_delta}
    allowed_carry.intersection_update((0, 1))
    return borrow, current_delta, current_carry, allowed_carry


def booth_code(multiplier: int, row: int) -> int:
    code = 0
    for output, source in enumerate(range(3 * row - 1, 3 * row + 3)):
        if 0 <= source < 64:
            code |= ((multiplier >> source) & 1) << output
    return code


def booth_digits(multiplier: int) -> tuple[int, ...]:
    if not 0 <= multiplier < (1 << 64):
        raise ValueError("multiplier does not fit the P5 64-bit port")
    return tuple(BOOTH8[booth_code(multiplier, row)] for row in range(22))


def encoded_pp(multiplicand: int, digit: int) -> int:
    if not (1 << 66) <= multiplicand < (1 << 67):
        raise ValueError("multiplicand does not fit the normalized P5 port")
    magnitude = abs(digit) * multiplicand
    if magnitude >= (1 << 69):
        raise ArithmeticError("partial-product magnitude overflow")
    positive = (1 << 69) | magnitude
    return ((~positive) & PP_MASK) if digit < 0 else positive


def physical_inputs(
        multiplicand: int, multiplier: int, correction: str
        ) -> tuple[list[int], int | None]:
    """Return 24 arithmetic-equivalent physical tree inputs.

    ``zero_index`` identifies the spare input that an integrated square can
    replace with its external low radix-8 digit.
    """
    digits = booth_digits(multiplier)
    raw_rows = [
        ((encoded_pp(multiplicand, digit) | (3 << 70)) << (3 * index))
        & TREE_MASK
        for index, digit in enumerate(digits)
    ]
    corrections = [(index, 1 << (3 * index))
                   for index, digit in enumerate(digits) if digit < 0]
    w = 1 << 69
    if correction == "next_row":
        rows = list(raw_rows)
        for index, digit in enumerate(digits[:-1]):
            if digit < 0:
                rows[index + 1] += 1 << (3 * index)
        return rows + [w, 0], 23
    if correction == "source_row":
        rows = list(raw_rows)
        for index, digit in enumerate(digits):
            if digit < 0:
                rows[index] += 1 << (3 * index)
        return rows + [w, 0], 23
    if correction == "single_bus":
        bus = sum(value for _, value in corrections)
        return raw_rows + [w + bus, 0], 23
    if correction == "split_bus":
        even = sum(value for index, value in corrections
                   if index % 2 == 0)
        odd = sum(value for index, value in corrections
                  if index % 2 == 1)
        return raw_rows + [w + even, odd], None
    raise AssertionError(correction)


def csa3(a: int, b: int, c: int, mask: int = TREE_MASK) -> tuple[int, int]:
    return ((a ^ b ^ c) & mask,
            (((a & b) | (a & c) | (b & c)) << 1) & mask)


def csa42(
        inputs: tuple[int, int, int, int] | list[int], d_slot: int,
        mask: int = TREE_MASK) -> tuple[int, int]:
    ordered = list(inputs)
    distinguished = ordered.pop(d_slot)
    first_sum, first_carry = csa3(*ordered, mask=mask)
    return csa3(distinguished, first_sum, first_carry, mask=mask)


def input_permutation(name: str) -> list[int]:
    natural = list(range(24))
    if name == "natural":
        return natural
    if name == "reverse_groups":
        return list(itertools.chain.from_iterable(
            natural[start:start + 4]
            for start in range(20, -1, -4)))
    if name == "reverse_lanes":
        return list(itertools.chain.from_iterable(
            reversed(natural[start:start + 4])
            for start in range(0, 24, 4)))
    if name == "even_odd":
        return natural[0::2] + natural[1::2]
    if name == "interleave_halves":
        return list(itertools.chain.from_iterable(zip(range(12), range(12, 24))))
    if name == "radix_columns":
        return [offset + 6 * group for offset in range(6) for group in range(4)]
    raise AssertionError(name)


def reduce_tree(inputs: list[int], config: TreeConfig) -> tuple[int, int]:
    if len(inputs) != 24:
        raise ValueError("the four-level P5 tree requires 24 inputs")
    if not 1 <= config.stage_width <= TREE_BITS:
        raise ValueError("invalid stage width")
    mask = (1 << config.stage_width) - 1
    ordered = [inputs[index] & TREE_MASK
               for index in input_permutation(config.input_order)]
    level1 = [
        csa42(ordered[start:start + 4], config.d_slots[0], mask)
        for start in range(0, 24, 4)
    ]
    level2 = [
        csa42(level1[left] + level1[right], config.d_slots[1], mask)
        for left, right in config.pairing
    ]
    remaining = [index for index in range(3) if index != config.hold]
    level3 = csa42(
        level2[remaining[0]] + level2[remaining[1]],
        config.d_slots[2], mask)
    return csa42(level3 + level2[config.hold], config.d_slots[3], mask)


def pairings(values: tuple[int, ...]) -> list[tuple[tuple[int, int], ...]]:
    if not values:
        return [()]
    first = values[0]
    result = []
    for offset in range(1, len(values)):
        second = values[offset]
        rest = values[1:offset] + values[offset + 1:]
        for suffix in pairings(rest):
            result.append(((first, second),) + suffix)
    return result


def tree_variants() -> list[tuple[str, str, TreeConfig]]:
    base = TreeConfig()
    variants = [("patent", "baseline", base)]
    for slot in (1, 2, 3):
        variants.append((f"d_uniform{slot}", "compressor_order",
                         replace(base, d_slots=(slot,) * 4)))
    for stage, stage_name in enumerate(("l1", "l2", "l3", "l4")):
        for slot in (1, 2, 3):
            d_slots = list(base.d_slots)
            d_slots[stage] = slot
            variants.append((f"d_{stage_name}_{slot}", "compressor_order",
                             replace(base, d_slots=tuple(d_slots))))
    variants.extend((
        ("d_rotate0123", "compressor_order",
         replace(base, d_slots=(0, 1, 2, 3))),
        ("d_rotate3210", "compressor_order",
         replace(base, d_slots=(3, 2, 1, 0))),
    ))
    for order in ("reverse_groups", "reverse_lanes", "even_odd",
                  "interleave_halves", "radix_columns"):
        variants.append(("order_" + order, "compressor_grouping",
                         replace(base, input_order=order)))
    for pairing in pairings(tuple(range(6))):
        for hold in range(3):
            if pairing == base.pairing and hold == base.hold:
                continue
            encoded = "_".join(f"{left}{right}" for left, right in pairing)
            variants.append((f"pair_{encoded}_hold{hold}",
                             "compressor_grouping",
                             replace(base, pairing=pairing, hold=hold)))
    for correction in ("source_row", "single_bus", "split_bus"):
        variants.append(("correction_" + correction, "booth_correction",
                         replace(base, correction=correction)))
    names = [name for name, _, _ in variants]
    if len(names) != len(set(names)):
        raise AssertionError("duplicate tree-variant name")
    return variants


def representations() -> list[Representation]:
    variants = tree_variants()
    result = []
    for source in ("L", "R", "QX"):
        for name, axis, config in variants:
            result.append(Representation(
                f"{source}.tree.{name}", axis, source, "tree", config))

    base = TreeConfig()
    for slot in range(24):
        result.append(Representation(
            f"QX.low_inline.slot{slot:02d}", "low_digit_merge", "QX",
            "low_inline", base, slot))
    for slot in range(4):
        result.append(Representation(
            f"QX.low_post42.d{slot}", "low_digit_merge", "QX",
            "low_post42", base, slot))
    for kind in ("core_cpa", "full_cpa", "add_to_sum", "add_to_carry"):
        result.append(Representation(
            f"QX.{kind}", "normalization_attachment", "QX", kind, base))
    for source in ("L", "R"):
        result.append(Representation(
            f"{source}.full_cpa", "normalization_attachment", source,
            "full_cpa", base))
    for width in range(127, TREE_BITS):
        result.append(Representation(
            f"QX.stage_width{width}", "stage_truncation", "QX", "tree",
            replace(base, stage_width=width)))
    result.extend((
        Representation("QX.core_chop67", "normalization_attachment", "QX",
                       "core_chop67", base),
        Representation("QX.full_chop67", "normalization_attachment", "QX",
                       "full_chop67", base),
    ))
    names = [item.name for item in result]
    if len(names) != len(set(names)):
        raise AssertionError("duplicate representation name")
    return result


def source_values(row: dict[str, str], source: str) -> tuple[int, int, int]:
    if source == "L":
        left = int(row["tc_mul_sig"], 16)
        right = int(row["tc_lf_sig"], 16)
        return left, right, left * right
    if source == "R":
        left = int(row["tc_f4_sig"], 16)
        right = int(row["tc_rf_sig"], 16)
        return left, right, left * right
    if source == "QX":
        left = int(row["tc_mul_sig"], 16)
        return left, left >> 3, left * left
    raise AssertionError(source)


def representation_state(
        representation: Representation, row: dict[str, str]
        ) -> tuple[int, int, int, int]:
    left, right, exact = source_values(row, representation.source)
    cut = exact.bit_length() - 67
    if representation.source != "QX":
        if representation.kind == "full_cpa":
            return exact, 0, cut, exact
        inputs, _ = physical_inputs(left, right, representation.config.correction)
        sum_vector, carry_vector = reduce_tree(inputs, representation.config)
        return sum_vector, carry_vector, cut, exact

    core = left * right
    low_product = left * (left & 7)
    if representation.kind == "full_cpa":
        return exact, 0, cut, exact
    if representation.kind == "core_cpa":
        return (core << 3) & TREE_MASK, low_product, cut, exact
    if representation.kind == "core_chop67":
        core_cut = core.bit_length() - 67
        chopped = (core >> core_cut) << core_cut
        return (chopped << 3) & TREE_MASK, low_product, cut, exact
    if representation.kind == "full_chop67":
        return (exact >> cut) << cut, 0, cut, exact
    if representation.kind == "low_inline":
        inputs, zero_index = physical_inputs(left, right, "next_row")
        if zero_index is None:
            raise AssertionError("inline merge requires a spare input")
        contributions = [value << 3 for index, value in enumerate(inputs)
                         if index != zero_index]
        contributions.insert(representation.parameter, low_product)
        sum_vector, carry_vector = reduce_tree(contributions, representation.config)
        return sum_vector, carry_vector, cut, exact

    inputs, _ = physical_inputs(left, right, representation.config.correction)
    core_sum, core_carry = reduce_tree(inputs, representation.config)
    core_sum = (core_sum << 3) & TREE_MASK
    core_carry = (core_carry << 3) & TREE_MASK
    if representation.kind == "tree":
        sum_vector, carry_vector = csa3(
            core_sum, core_carry, low_product)
    elif representation.kind == "low_post42":
        sum_vector, carry_vector = csa42(
            (core_sum, core_carry, low_product, 0),
            representation.parameter)
    elif representation.kind == "add_to_sum":
        sum_vector = (core_sum + low_product) & TREE_MASK
        carry_vector = core_carry
    elif representation.kind == "add_to_carry":
        sum_vector = core_sum
        carry_vector = (core_carry + low_product) & TREE_MASK
    else:
        raise AssertionError(representation.kind)
    return sum_vector, carry_vector, cut, exact


def synthetic_rows(source: str) -> list[dict[str, str]]:
    xs = (
        1 << 66,
        (1 << 66) + 1,
        0x55555555555555555,
        0x6aaaaaaaaaaaaaaaa,
        (1 << 67) - 2,
        (1 << 67) - 1,
    )
    ys = (
        0, 1, 2, 3, 7, 8, 15, 31, 63,
        0x1249249249249249, 0x2492492492492492,
        0x5555555555555555, 0xaaaaaaaaaaaaaaaa,
        0x7fffffffffffffff, 0x8000000000000000,
        0xfffffffffffffff0, 0xffffffffffffffff,
    )
    rows = []
    if source == "QX":
        for left in xs:
            rows.append({
                "tc_mul_sig": f"{left:x}",
                "tc_lf_sig": "8000000000000000",
                "tc_f4_sig": f"{left:x}",
                "tc_rf_sig": "8000000000000000",
                "op": f"synthetic {left:x}",
            })
    else:
        for left in xs:
            for right in ys:
                rows.append({
                    "tc_mul_sig": f"{left:x}",
                    "tc_lf_sig": f"{right:x}",
                    "tc_f4_sig": f"{left:x}",
                    "tc_rf_sig": f"{right:x}",
                    "op": f"synthetic {left:x}*{right:x}",
                })
    return rows


def exact_gate(
        representation: Representation, cached_rows: list[dict[str, str]]
        ) -> tuple[bool, tuple[str, str, int, int] | None,
                   list[tuple[int, int, int, int]]]:
    target_states = []
    for phase, rows in (("synthetic", synthetic_rows(representation.source)),
                        ("cached", cached_rows)):
        for row in rows:
            try:
                sum_vector, carry_vector, cut, exact = representation_state(
                    representation, row)
            except (ArithmeticError, ValueError) as error:
                return False, (phase, row.get("op", "-"), 0, 0), []
            arithmetic_mask = (SQUARE_MASK if representation.source == "QX"
                               else PRODUCT_MASK)
            got = (sum_vector + carry_vector) & arithmetic_mask
            if got != exact:
                return False, (phase, row.get("op", "-"), got, exact), []
            if phase == "cached" and row.get("label") == "POS" \
                    and row.get("branch") in BRANCHES:
                target_states.append((sum_vector, carry_vector, cut, exact))
    return True, None, target_states


def carry_relations(
        sum_vector: int, carry_vector: int, end: int
        ) -> tuple[list[int], list[int]]:
    """Return carry into ``end`` for reset zero/one at every start."""
    zero = [0] * (end + 1)
    one = [0] * (end + 1)
    zero[end], one[end] = 0, 1
    relation_g, relation_p = 0, 1
    for position in range(end - 1, -1, -1):
        a = (sum_vector >> position) & 1
        b = (carry_vector >> position) & 1
        bit_g, bit_p = a & b, a ^ b
        relation_g = relation_g | (relation_p & bit_g)
        relation_p &= bit_p
        zero[position] = relation_g
        one[position] = relation_g | relation_p
    return zero, one


def recurrence_start(end: int, width: int, alignment: str) -> int:
    if end <= 0:
        return 0
    if alignment == "suffix":
        return max(0, end - width)
    origin = 0 if alignment == "absolute" else 2
    if end <= origin:
        return 0
    return max(0, origin + ((end - 1 - origin) // width) * width)


def transform_value(
        transform: str, current: int, block: int, exact: int) -> int:
    error = block ^ exact
    if transform == "block":
        return block
    if transform == "not_block":
        return 1 ^ block
    if transform == "current_xor_reset_error":
        return current ^ error
    if transform == "current_drop_on_reset_error":
        return current & (1 ^ error)
    if transform == "current_set_on_reset_error":
        return current | error
    if transform == "current_xor_block":
        return current ^ block
    if transform == "current_and_block":
        return current & block
    if transform == "current_or_block":
        return current | block
    raise AssertionError(transform)


def candidate_output(
        descriptor: Candidate, state: tuple[int, int, int, int],
        current: int) -> int:
    sum_vector, carry_vector, cut, _ = state
    end = cut + descriptor.attachment
    if end < 0:
        end = 0
    zero, one = carry_relations(sum_vector, carry_vector, end)
    start = recurrence_start(end, descriptor.width, descriptor.alignment)
    block = (zero if descriptor.seed == 0 else one)[start]
    exact = zero[0]
    return transform_value(descriptor.transform, current, block, exact)


def mine_targets(
        representation: Representation,
        states: list[tuple[int, int, int, int]],
        targets: list[AuditRow]) -> list[Candidate]:
    if len(states) != len(targets):
        raise AssertionError("target-state order mismatch")
    prepared = []
    for state, row in zip(states, targets):
        sum_vector, carry_vector, cut, _ = state
        by_attachment = {}
        for attachment in ATTACHMENTS:
            end = max(0, cut + attachment)
            by_attachment[attachment] = carry_relations(
                sum_vector, carry_vector, end)
        prepared.append((row, cut, by_attachment))

    best = []
    minimum = len(targets) + 1
    for attachment in ATTACHMENTS:
        for width in WIDTHS:
            for alignment in ALIGNMENTS:
                for seed in (0, 1):
                    for transform in TRANSFORMS:
                        errors = Counter()
                        for row, cut, relations in prepared:
                            end = max(0, cut + attachment)
                            zero, one = relations[attachment]
                            start = recurrence_start(end, width, alignment)
                            block = (zero if seed == 0 else one)[start]
                            exact = zero[0]
                            output = transform_value(
                                transform, row.current, block, exact)
                            if output != row.truth:
                                errors[row.branch] += 1
                        total = sum(errors.values())
                        candidate = Candidate(
                            representation.name, representation.axis,
                            representation.source, attachment, width,
                            alignment, seed, transform, total,
                            errors["band"], errors["tie"], errors["corner"])
                        if total < minimum:
                            minimum = total
                            best = [candidate]
                        elif total == minimum:
                            best.append(candidate)
    return best


def read_score_rows(path: Path) -> list[dict[str, str]]:
    lines = path.read_text().splitlines()
    for index, line in enumerate(lines):
        if line.startswith("mode\top\tcurrent\tcandidate\t"):
            return list(csv.DictReader(lines[index:], delimiter="\t"))
    raise RuntimeError(f"score table missing in {path}")


def adversarial_rows(
        model: Path, score_paths: list[Path]) -> list[AuditRow]:
    labels = {}
    for path in score_paths:
        for row in read_score_rows(path):
            if row["verdict"] != "current" or row["hardware"] != row["current"]:
                raise RuntimeError(f"non-incumbent adversarial label in {path}")
            key = row["mode"], row["op"].lower()
            prior = labels.setdefault(key, row["current"].lower())
            if prior != row["current"].lower():
                raise RuntimeError(f"conflicting cached label for {key}")
    result = []
    by_mode = defaultdict(list)
    for mode, operand in sorted(labels):
        by_mode[mode].append(operand)
    for mode, operands in sorted(by_mode.items()):
        for start in range(0, len(operands), 2000):
            chunk = operands[start:start + 2000]
            records = dump(str(model), mode, chunk)
            for operand, record in zip(chunk, records):
                if record["op"] != operand:
                    raise RuntimeError("adversarial software dump desynchronized")
                if record["model"].lower() != labels[mode, operand]:
                    raise RuntimeError(
                        f"software model no longer matches cached incumbent: "
                        f"{mode} {operand}")
                state = extract_carry_state(record, set(range(-8, 9)))
                record["label"] = "ADV"
                record["mode"] = mode
                result.append(AuditRow(
                    record, "adversarial", state[2], state[2],
                    record["branch"]))
    return result


def feature_rows(
        path: Path, positive_path: Path, control_path: Path
        ) -> list[AuditRow]:
    positive = allmode_allowed(positive_path)
    controls = allmode_allowed(control_path)
    result = []
    with path.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            bank = positive if row["label"] == "POS" else controls
            state = extract_carry_state(row, bank[row["op"]])
            truth = next(iter(state[3])) if len(state[3]) == 1 else None
            role = ("target" if row["label"] == "POS" else
                    "control" if truth is not None else "neutral")
            result.append(AuditRow(
                row, role, truth, state[2], row["branch"]))
    return result


def score_shortlist(
        candidates: list[Candidate], by_name: dict[str, Representation],
        rows: list[AuditRow]) -> list[tuple]:
    grouped = defaultdict(list)
    for candidate in candidates:
        grouped[candidate.representation].append(candidate)
    scores = []
    for name, group in grouped.items():
        representation = by_name[name]
        states = []
        scored_rows = []
        for row in rows:
            if row.truth is None or row.role == "target":
                continue
            state = representation_state(representation, row.fields)
            arithmetic_mask = (SQUARE_MASK if representation.source == "QX"
                               else PRODUCT_MASK)
            if ((state[0] + state[1]) & arithmetic_mask) != state[3]:
                raise AssertionError("post-gate arithmetic mismatch")
            states.append(state)
            scored_rows.append(row)
        errors_by_candidate = [Counter() for _ in group]
        attachments = sorted({candidate.attachment for candidate in group})
        for state, row in zip(states, scored_rows):
            sum_vector, carry_vector, cut, _ = state
            relations = {
                attachment: carry_relations(
                    sum_vector, carry_vector, max(0, cut + attachment))
                for attachment in attachments
            }
            for candidate, errors in zip(group, errors_by_candidate):
                end = max(0, cut + candidate.attachment)
                zero, one = relations[candidate.attachment]
                start = recurrence_start(
                    end, candidate.width, candidate.alignment)
                block = (zero if candidate.seed == 0 else one)[start]
                exact = zero[0]
                output = transform_value(
                    candidate.transform, row.current, block, exact)
                if output != row.truth:
                    errors[row.role] += 1
                    errors[row.branch] += 1
        for candidate, errors in zip(group, errors_by_candidate):
            scores.append((
                candidate.target_miss + errors["control"]
                + errors["adversarial"],
                candidate.target_miss,
                errors["control"],
                errors["adversarial"],
                candidate.band_miss, candidate.tie_miss,
                candidate.corner_miss, candidate.representation,
                candidate.axis, candidate.source, candidate.attachment,
                candidate.width, candidate.alignment, candidate.seed,
                candidate.transform,
            ))
    scores.sort()
    return scores


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("positive_allmode", type=Path)
    parser.add_argument("control_allmode", type=Path)
    parser.add_argument("model", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--adversarial-score", type=Path, action="append",
                        default=[])
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    base_rows = feature_rows(
        args.features, args.positive_allmode, args.control_allmode)
    adversarial = adversarial_rows(args.model, args.adversarial_score)
    rows = base_rows + adversarial
    targets = [row for row in base_rows
               if row.role == "target" and row.branch in BRANCHES]
    if len(targets) != 9:
        raise RuntimeError(f"expected nine current R59 targets, got {len(targets)}")
    target_fields = [row.fields for row in targets]
    # Preserve the target order after the label-free exact gate sees all rows.
    cached_fields = [row.fields for row in rows]
    reps = representations()
    by_name = {item.name: item for item in reps}
    passed = []
    rejected = []
    best_candidates = []
    signatures = defaultdict(set)
    for index, representation in enumerate(reps, 1):
        ok, failure, target_states = exact_gate(representation, cached_fields)
        if not ok:
            rejected.append((representation, failure))
            print(f"gate {index}/{len(reps)} reject {representation.name}",
                  flush=True)
            continue
        if len(target_states) != len(target_fields):
            raise AssertionError("exact gate lost target states")
        passed.append(representation)
        signature = hashlib.sha256()
        for state in target_states:
            signature.update(("%x,%x,%d;" % state[:3]).encode())
        signatures[representation.axis].add(signature.hexdigest())
        mined = mine_targets(representation, target_states, targets)
        best_candidates.extend(mined)
        print(
            f"gate {index}/{len(reps)} pass {representation.name} "
            f"best_target_miss={mined[0].target_miss} aliases={len(mined)}",
            flush=True)

    if not passed:
        raise RuntimeError("every representation failed exact arithmetic")
    global_minimum = min(item.target_miss for item in best_candidates)
    exact_target = [item for item in best_candidates if item.target_miss == 0]
    if exact_target:
        shortlist = exact_target
    else:
        shortlist = sorted(best_candidates, key=lambda item: (
            item.target_miss, max(item.band_miss, item.tie_miss,
                                  item.corner_miss),
            item.representation, item.attachment, item.width,
            item.alignment, item.seed, item.transform))[:64]
        # Keep each source and representation axis visible even if the global
        # top 64 happens to alias one redundant encoding.
        for key_function in (
                lambda item: item.source,
                lambda item: item.axis):
            selected = {}
            for item in sorted(best_candidates, key=lambda candidate: (
                    candidate.target_miss, candidate.representation,
                    candidate.width, candidate.transform)):
                selected.setdefault(key_function(item), item)
            shortlist.extend(selected.values())
    cut_sets = {
        source: sorted({source_values(row.fields, source)[2].bit_length() - 67
                        for row in rows})
        for source in ("L", "R", "QX")
    }
    unique = {}
    for item in shortlist:
        boundary_signature = tuple(
            (max(0, cut + item.attachment),
             recurrence_start(max(0, cut + item.attachment),
                              item.width, item.alignment))
            for cut in cut_sets[item.source]
        )
        key = (item.representation, item.attachment, item.seed,
               item.transform, boundary_signature)
        prior = unique.get(key)
        if prior is None or (item.width, item.alignment) < (
                prior.width, prior.alignment):
            unique[key] = item
    shortlist = list(unique.values())
    scores = score_shortlist(shortlist, by_name, rows)
    exact_global = [item for item in scores if item[0] == 0]

    axis_counts = defaultdict(Counter)
    best_axis = {}
    for representation in reps:
        axis_counts[representation.axis]["total"] += 1
    for representation in passed:
        axis_counts[representation.axis]["exact"] += 1
    for representation, _ in rejected:
        axis_counts[representation.axis]["rejected"] += 1
    for candidate in best_candidates:
        key = candidate.axis
        prior = best_axis.get(key)
        if prior is None or candidate.target_miss < prior:
            best_axis[key] = candidate.target_miss

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        for name, path in (
            ("features", args.features),
            ("positive_allmode", args.positive_allmode),
            ("control_allmode", args.control_allmode),
            ("software_model", args.model),
        ):
            target.write(f"{name}_sha256\t{digest(path)}\n")
        for index, path in enumerate(args.adversarial_score):
            target.write(f"adversarial_score_{index}_sha256\t{digest(path)}\n")
        role_counts = Counter(row.role for row in rows)
        target.write("hardware_policy\tcached_labels_only_no_x87_execution\n")
        target.write("representation_policy\tone_axis_perturbations_around_patent_tree\n")
        target.write("arithmetic_gate\tsynthetic_edges_plus_every_cached_row_before_label_mining\n")
        target.write(f"cached_rows\t{len(rows)}\n")
        for role in ("target", "control", "neutral", "adversarial"):
            target.write(f"{role}_rows\t{role_counts[role]}\n")
        target.write(f"representations\t{len(reps)}\n")
        target.write(f"arithmetic_exact\t{len(passed)}\n")
        target.write(f"arithmetic_rejected\t{len(rejected)}\n")
        target.write(f"fixed_widths\t{len(WIDTHS)}\n")
        target.write(f"normalization_attachments\t{len(ATTACHMENTS)}\n")
        target.write(f"reset_alignments\t{len(ALIGNMENTS)}\n")
        target.write(f"fixed_transforms\t{len(TRANSFORMS)}\n")
        target.write(f"best_target_miss\t{global_minimum}\n")
        target.write(f"target_exact_candidates\t{len(exact_target)}\n")
        target.write(f"scored_recurrence_equivalence_classes\t{len(shortlist)}\n")
        target.write(f"global_exact_candidates\t{len(exact_global)}\n")

        target.write("\n[axis census]\n")
        target.write("axis\ttotal\tarithmetic_exact\trejected\t"
                     "distinct_target_encodings\tbest_target_miss\n")
        for axis in sorted(axis_counts):
            counts = axis_counts[axis]
            target.write("\t".join(map(str, (
                axis, counts["total"], counts["exact"], counts["rejected"],
                len(signatures[axis]), best_axis.get(axis, "-")))) + "\n")

        target.write("\n[arithmetic-gate rejections]\n")
        target.write("representation\taxis\tphase\top\tgot\twant\n")
        for representation, failure in rejected:
            phase, operand, got, want = failure
            target.write(f"{representation.name}\t{representation.axis}\t"
                         f"{phase}\t{operand}\t{got:x}\t{want:x}\n")

        target.write("\n[best fixed-width recurrence ranking]\n")
        target.write("total_miss\ttarget_miss\tcontrol_miss\tadversarial_miss\t"
                     "band_miss\ttie_miss\tcorner_miss\trepresentation\taxis\t"
                     "source\tattachment\twidth\talignment\tseed\ttransform\n")
        for score in scores[:256]:
            target.write("\t".join(map(str, score)) + "\n")

        target.write("\n[exact transferable candidates]\n")
        if not exact_global:
            target.write("none\n")
        else:
            for score in exact_global:
                target.write("\t".join(map(str, score)) + "\n")

        target.write("\n[claim boundary]\n")
        target.write(
            "Arithmetic-isomorphic means only that the redundant words sum "
            "to the exact product; it does not identify the physical Skylake "
            "routing.  A zero target count would still require zero cached "
            "control/adversarial errors and a separately frozen fresh "
            "separator before promotion.\n")

    print(
        f"wrote {args.report}: representations={len(reps)} "
        f"exact={len(passed)} rejected={len(rejected)} "
        f"best_target_miss={global_minimum} "
        f"target_exact={len(exact_target)} global_exact={len(exact_global)}",
        flush=True)


if __name__ == "__main__":
    main()
