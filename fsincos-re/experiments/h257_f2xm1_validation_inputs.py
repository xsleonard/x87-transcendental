#!/usr/bin/env python3
"""Generate fresh hardware-blind F2XM1 boundary and class separators."""

from __future__ import annotations

import argparse
import collections
import hashlib
import pathlib

import h251_f2xm1_exact_baseline as h251
import h252_f2xm1_literal_graph as h252
import h254_f2xm1_operation_search as h254
import h256_f2xm1_long_transfer as h256


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "capture-kit" / "inputs" / "f2xm1_validation_h257.txt"
DEFAULT_METADATA = DEFAULT_OUTPUT.with_suffix(".meta.txt")
LEADER = h256.CANDIDATE
ALTERNATIVES = (
    h254.Candidate(),
    h254.Candidate("chop66", "rn64", "rn64"),
    h254.Candidate("chop68", "rn64", "rn64"),
    h254.Candidate("rn67", "rn64", "rn64"),
    h254.Candidate("away67", "rn64", "rn64"),
    h254.Candidate("chop67", "rn65", "rn64"),
    h254.Candidate("chop67", "rn64", "exact"),
    h254.Candidate("chop67", "rn64", "rn65"),
)


def predictions(se: int, sig: int, candidate, table: bool):
    x = h252.input_fp(se, sig)
    if table:
        point = h254.Point("generated", 0, se, sig, ((0, 0),) * 3)
        value = h254.value(point, candidate)
    else:
        value = h256.long_value(x, candidate)
    return tuple(h252.rounded(value, rc) for rc in h251.RCS)


def operands():
    values: set[tuple[int, int]] = set()
    categories = collections.Counter()

    # Densify the exact tiny/long boundary with an unrelated seed.
    state = 0xA0761D6478BD642F
    for exponent in range(-73, -61):
        for _ in range(256):
            state = (
                state * 0xE7037ED1A0B428DB + 0x8EBC6AF09C88C6E3
            ) & ((1 << 64) - 1)
            sig = (1 << 63) | (state >> 1)
            for sign in (0, 1):
                values.add(((sign << 15) | (exponent + 16383), sig))
                categories["tiny_boundary"] += 1

    # Exact path/table anchors and their adjacent representable operands.
    for numerator in range(-128, 129):
        if numerator == 0:
            values.update(((0, 0), (0x8000, 0)))
            continue
        sign = int(numerator < 0)
        magnitude = abs(numerator)
        top = magnitude.bit_length() - 1
        exponent = top - 7
        base = magnitude << (63 - top)
        se = (sign << 15) | (exponent + 16383)
        for delta in (-16, -4, -1, 0, 1, 4, 16):
            candidate_sig = base + delta
            if 1 << 63 <= candidate_sig < 1 << 64:
                values.add((se, candidate_sig))
                categories["anchors"] += 1

    # Select fresh operation-class separators without consulting hardware.
    separator_counts = collections.Counter()
    state = 0x243F6A8885A308D3
    for _ in range(400000):
        state = (
            state * 0xD1342543DE82EF95 + 0xC6BC279692B5CC83
        ) & ((1 << 64) - 1)
        table = bool(state & 1)
        exponent = -2 + ((state >> 1) & 1) if table else -3 - ((state >> 2) % 62)
        sig = (1 << 63) | (state >> 1)
        sign = (state >> 63) & 1
        se = (sign << 15) | (exponent + 16383)
        leader = predictions(se, sig, LEADER, table)
        for index, alternative in enumerate(ALTERNATIVES):
            if separator_counts[index] >= 128:
                continue
            if predictions(se, sig, alternative, table) != leader:
                values.add((se, sig))
                separator_counts[index] += 1
        if all(separator_counts[index] >= 128 for index in range(len(ALTERNATIVES))):
            break
    if any(separator_counts[index] < 128 for index in range(len(ALTERNATIVES))):
        raise SystemExit(f"insufficient separators: {dict(separator_counts)}")
    categories["class_separators"] = sum(separator_counts.values())
    return sorted(values), categories, separator_counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--metadata", type=pathlib.Path, default=DEFAULT_METADATA)
    args = parser.parse_args()
    rows, categories, separators = operands()
    text = "".join(f"{se:04x} {sig:016x}\n" for se, sig in rows)
    digest = hashlib.sha256(text.encode()).hexdigest()
    args.output.write_text(text)
    args.metadata.write_text(
        "h257 hardware-blind F2XM1 validation inputs\n"
        f"rows: {len(rows)}\n"
        f"sha256: {digest}\n"
        f"categories before deduplication: {dict(categories)}\n"
        f"128 separators per alternative: {dict(separators)}\n"
        "tiny boundary: 256 deterministic significands per exponent "
        "-73..-62, both signs\n"
        "anchors: every k/128 in [-1,1] with significand deltas "
        "{-16,-4,-1,0,1,4,16}\n"
    )
    print(f"wrote {len(rows)} rows to {args.output}")
    print(f"sha256 {digest}")
    print(f"separators {dict(separators)}")


if __name__ == "__main__":
    main()
