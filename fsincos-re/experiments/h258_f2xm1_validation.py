#!/usr/bin/env python3
"""Verify the complete F2XM1 model on the fresh h257 Skylake capture."""

from __future__ import annotations

import hashlib
import pathlib

import h58_constraint_search as h58
import h251_f2xm1_exact_baseline as h251
import h252_f2xm1_literal_graph as h252
import h254_f2xm1_operation_search as h254
import h256_f2xm1_long_transfer as h256
import h257_f2xm1_validation_inputs as h257


ROOT = pathlib.Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "capture-kit-captures" / "skylake-f2xm1-h257"
INPUT = ROOT / "capture-kit" / "inputs" / "f2xm1_validation_h257.txt"


def verify_manifest() -> None:
    rows = CAPTURE.joinpath("SHA256SUMS").read_text().splitlines()
    for row in rows:
        digest, name = row.split(None, 1)
        path = CAPTURE / name.strip().lstrip("*")
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise SystemExit(f"checksum mismatch: {path.name}")
    print(f"manifest: {len(rows)} payloads verified")


def model_value(
    se: int,
    sig: int,
    candidate: h254.Candidate,
    cutoff: int,
) -> tuple[h58.FP | None, tuple[int, int] | None]:
    x_fraction = h251.decode_input(se, sig)
    if abs(x_fraction) > 1:
        return None, (se, sig)
    if x_fraction == 1:
        return None, (0x3FFF, 0x8000000000000000)
    if x_fraction == -1:
        return None, (0xBFFE, 0x8000000000000000)
    x = h252.input_fp(se, sig)
    if abs(x_fraction) >= h256.QUARTER:
        point = h254.Point("h257", 0, se, sig, ((0, 0),) * 3)
        return h254.value(point, candidate), None
    exponent_field = se & 0x7FFF
    exponent = (
        exponent_field - 16383
        if sig and exponent_field
        else h251.MIN_NORMAL_EXP
    )
    if exponent >= cutoff:
        return h256.long_value(x, candidate), None
    return h256.linear_value(x), None


def prediction(
    se: int,
    sig: int,
    rc: str,
    candidate: h254.Candidate,
    cutoff: int,
) -> tuple[tuple[int, int], bool]:
    value, special = model_value(se, sig, candidate, cutoff)
    if special is not None:
        return special, False
    assert value is not None
    return h251.round_x87(
        h252.fp_fraction(value), rc, se >> 15 if not sig else 0
    )


def score(inputs, captures, candidate, cutoff):
    mode_misses = 0
    input_misses = 0
    c1_misses = 0
    c1_total = 0
    for index, (se, sig) in enumerate(inputs):
        row_miss = False
        value, special = model_value(se, sig, candidate, cutoff)
        for rc in h251.RCS:
            if special is not None:
                predicted, increment = special, False
            else:
                assert value is not None
                predicted, increment = h251.round_x87(
                    h252.fp_fraction(value),
                    rc,
                    se >> 15 if not sig else 0,
                )
            actual, status = captures[rc][index]
            mismatch = predicted != actual
            mode_misses += mismatch
            row_miss |= mismatch
            if not mismatch:
                c1_total += 1
                c1_misses += increment != bool(status & 0x0200)
        input_misses += row_miss
    return mode_misses, input_misses, c1_misses, c1_total


def main() -> None:
    verify_manifest()
    inputs = [
        tuple(int(field, 16) for field in line.split())
        for line in INPUT.read_text().splitlines()
    ]
    captures = {
        rc: [
            h251.parse_output(line)
            for line in CAPTURE.joinpath(
                f"f2xm1_validation_h257_{rc}_status.txt"
            ).read_text().splitlines()
        ]
        for rc in h251.RCS
    }
    if any(len(rows) != len(inputs) for rows in captures.values()):
        raise SystemExit("h257 input/output row-count mismatch")

    leader = score(inputs, captures, h256.CANDIDATE, -68)
    print(
        f"leader {h256.CANDIDATE.short()} cutoff=-68: "
        f"mode/input misses={leader[:2]}, "
        f"C1 misses={leader[2]}/{leader[3]}"
    )
    for cutoff in (-69, -67):
        result = score(inputs, captures, h256.CANDIDATE, cutoff)
        print(f"cutoff={cutoff}: mode/input misses={result[:2]}")
    for alternative in h257.ALTERNATIVES:
        result = score(inputs, captures, alternative, -68)
        print(f"alternative {alternative.short()}: mode/input misses={result[:2]}")


if __name__ == "__main__":
    main()
