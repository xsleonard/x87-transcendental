#!/usr/bin/env python3
"""Test whether Round 36's carrier bit 3 aliases another FADD signal.

h216 selects ``node0.raw.bit3`` over the fitted GRS/sign/bit alternatives.
The literal jam-sub datapath also exposes pre-normalization alignment and
borrow-chain signals that h214 did not name.  This pass reconstructs those
signals for every base-condition lane in complete and fresh datasets and
checks whether any is observationally identical to the selected bit.

An alias caused solely by the representation mapping
``normalized X2 bit 4 -> FAMUBUS word bit 3`` is expected and is reported as
structural.  Any other exact alias would justify another hardware separator.
"""

from __future__ import annotations

import collections

import h200_p5_fadd_bitvector as h200
import h206_p5_fadd_complete as h206
import h214_fadd_node0_selector as h214
import h216_fadd_microcontrol_discriminator as h216
import h220_fadd_causal_tree as h220
import h221_fadd_tree_discriminator as h221
import h223_fadd_tree_refined_discriminator as h223
import h224_fadd_tree_final_discriminator as h224


RULE = h220.CURRENT_RULE
BASE_TERMS = RULE.terms[:2]


def datasets():
    result = list(h220.partitions())
    captures = (
        (
            "h221",
            h221,
            h221.DEFAULT_OUTPUT,
            h221.ROOT / "capture-kit-captures" / "skylake-fsin-h221",
        ),
        (
            "h223",
            h223,
            h223.DEFAULT_OUTPUT,
            h223.ROOT / "capture-kit-captures" / "skylake-fsin-h223",
        ),
        (
            "h224",
            h224,
            h224.DEFAULT_OUTPUT,
            h224.ROOT / "capture-kit-captures" / "skylake-fsin-h224",
        ),
    )
    for name, module, inputs, capture in captures:
        if hasattr(module, "configure"):
            module.configure()
        else:
            h221.CAPTURE_STEM = "constraint_table_fadd_tree_h221"
        result.append((name, h221.load_capture(inputs, capture)))
    # Restore h216's original current-rule context after wrappers mutate the
    # shared h221 module globals.
    h221.RULES = h216.RULES
    return result


def borrow_into(minuend: int, subtrahend: int, bit: int) -> int:
    mask = (1 << bit) - 1
    return int((minuend & mask) < (subtrahend & mask))


def physical_features(point, cosine):
    values = h214.relevant_terms(point, RULE.candidate, cosine)
    node = h214.first_node(RULE.candidate.tree)
    left = values[node[0]]
    right = values[node[1]]
    result = {
        "input.sign-xor": left.sign ^ right.sign,
        "input.left-larger": int(h206.compare_magnitude(left, right) > 0),
    }
    exponent = max(left.exponent, right.exponent)
    aligned = []
    tails = []
    for operand in (left, right):
        word, tail = h200.shift_right(
            operand.word << 1, exponent - operand.exponent
        )
        aligned.append(word)
        tails.append(int(tail))
    result["alignment.any-discarded"] = int(any(tails))
    result["alignment.left-discarded"] = tails[0]
    result["alignment.right-discarded"] = tails[1]
    for index, word in enumerate(aligned):
        side = "left" if index == 0 else "right"
        for bit in range(9):
            result[f"aligned.{side}.bit{bit}"] = (word >> bit) & 1

    comparison = h206.compare_magnitude(left, right)
    if left.sign == right.sign or abs(left.exponent - right.exponent) <= 1:
        return result
    big, small = (left, right) if comparison > 0 else (right, left)
    difference = big.exponent - small.exponent
    shifted, discarded = h200.shift_right(small.word << 1, difference)
    jammed = shifted | int(discarded)
    minuend = big.word << 1
    raw = minuend - jammed
    result["subtract.big-is-left"] = int(big is left)
    result["subtract.discarded"] = int(discarded)
    for bit in range(1, 10):
        result[f"subtract.borrow-into{bit}"] = borrow_into(
            minuend, jammed, bit
        )
    for bit in range(10):
        result[f"subtract.shifted.bit{bit}"] = (shifted >> bit) & 1
        result[f"subtract.jammed.bit{bit}"] = (jammed >> bit) & 1
        result[f"subtract.raw-x2.bit{bit}"] = (raw >> bit) & 1

    top = raw.bit_length() - 1
    normalized = raw
    if top > 67:
        normalized, tail = h200.shift_right(raw, top - 67)
        if tail:
            normalized |= 1
    elif top < 67:
        sticky = bool(raw & 1)
        normalized <<= 67 - top
        if sticky:
            normalized |= 1
    for bit in range(10):
        result[f"normalized-x2.bit{bit}"] = (normalized >> bit) & 1
    raw_bus, _ = h206.fadd(left, right, "jam-sub", normalize=True)
    for bit in range(9):
        result[f"famubus.bit{bit}"] = (raw_bus.word >> bit) & 1
    return result


def main() -> None:
    rows = []
    census = collections.Counter()
    for name, points in datasets():
        for point in points:
            for cosine in (False, True):
                if cosine and not point.cosine_hardware:
                    continue
                features = h214.lane_features(point, RULE.candidate, cosine)
                if not all(
                    features.get(feature) == value
                    for feature, value in BASE_TERMS
                ):
                    continue
                target = features["node0.raw.bit3"]
                physical = physical_features(point, cosine)
                rows.append((target, physical))
                census[name, "cosine" if cosine else "sine", target] += 1
    names = sorted(set.intersection(*(set(values) for _, values in rows)))
    exact = []
    complement = []
    ranked = []
    for name in names:
        agreements = sum(target == values[name] for target, values in rows)
        if agreements == len(rows):
            exact.append(name)
        elif agreements == 0:
            complement.append(name)
        ranked.append((max(agreements, len(rows) - agreements), agreements, name))
    ranked.sort(reverse=True)
    print(
        f"h225 Round36 base-condition lanes={len(rows)} "
        f"target-one={sum(target for target, _ in rows)} "
        f"census={dict(sorted(census.items()))}"
    )
    print(f"  exact aliases={exact}")
    print(f"  complement aliases={complement}")
    print("  closest non-aliases:")
    shown = 0
    for best, agreements, name in ranked:
        if name in exact or name in complement:
            continue
        print(
            f"    {name}: agreement={agreements}/{len(rows)} "
            f"best-polarity={best}/{len(rows)}"
        )
        shown += 1
        if shown >= 12:
            break


if __name__ == "__main__":
    main()
