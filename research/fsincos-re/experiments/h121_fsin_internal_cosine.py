#!/usr/bin/env python3
"""Constrain FSIN's cosine producer after odd-quadrant range reduction.

The full structured sweep contains reduced inputs for which sin(x) is
reconstructed as +/-cos(r).  These observations distinguish an FSIN-internal
cosine producer from both FSINCOS and standalone FCOS without requiring any
new hardware data.
"""

from __future__ import annotations

import dataclasses

import h58_constraint_search as h58
import h60_round16_parity as h60
import h64_poly_constraints as h64
import h110_fsin_standalone as h110
import h119_fcos_standalone as h119


ROOT = h110.ROOT
INPUTS = ROOT / "capture-kit" / "inputs" / "sweep_inputs.txt"
CAPTURE = ROOT / "capture-kit-captures" / "skylake-fsin-h110"

FSIN_INTERNAL_COSINE = dataclasses.replace(
    h119.FCOS_SURVIVOR,
    square=h110.Quant(67, "away"),
)


@dataclasses.dataclass(frozen=True)
class Point:
    observed: h119.Observed
    negate: bool


def load_points() -> list[Point]:
    inputs = [
        tuple(int(field, 16) for field in line.split())
        for line in INPUTS.read_text().splitlines()
    ]
    lines = [
        (
            CAPTURE / f"sweep_fsin_{rc}_status.txt"
        ).read_text().splitlines()
        for rc in h58.RCS
    ]
    result = []
    for index, (se, sig) in enumerate(inputs):
        reduced = h60.reduced_kernel_input(se, sig)
        if reduced is None:
            continue
        signed_n, r_se, r_sig, c_nonzero = reduced
        quadrant = signed_n & 3
        exponent = (r_se & 0x7FFF) - 16383
        if not (quadrant & 1) or r_sig == 0 or exponent >= -2:
            continue
        if c_nonzero:
            raise AssertionError("polynomial residual unexpectedly has c")
        outputs = []
        c1 = []
        for mode in lines:
            fields = mode[index].split()
            if (
                len(fields) != 5
                or fields[0] != "OK"
                or fields[3] != "SW"
            ):
                raise ValueError(mode[index])
            outputs.append((int(fields[1], 16), int(fields[2], 16)))
            c1.append(bool(int(fields[4], 16) & 0x0200))
        raw = h64.PolyRaw(
            index=index,
            sign=0,
            exponent=exponent,
            sig=r_sig,
            sincos=(((0, 0), (0, 0)),) * 3,
            standalone=((0, 0), (0, 0)),
        )
        observed = h119.Observed(raw, tuple(outputs), tuple(c1))
        result.append(Point(observed, bool((quadrant >> 1) & 1)))
    return result


def score(
    points: list[Point], schedule: h119.Schedule
) -> h110.Score:
    result = h110.Score()
    for point in points:
        hidden = h119.hidden_value(point.observed, schedule)
        if point.negate:
            hidden = h58.neg(hidden)
        result.total += 1
        any_miss = False
        for index, rc in enumerate(h58.RCS):
            predicted = h58.x87_round(hidden, rc)
            expected = point.observed.outputs[index]
            mismatch = predicted != expected
            result.mode_misses += mismatch
            any_miss |= mismatch
            if not mismatch:
                predicted_c1 = (
                    h110.compare_magnitude(expected, hidden) > 0
                )
                result.c1_misses += (
                    predicted_c1 != point.observed.c1[index]
                )
        result.output_misses += any_miss
    return result


def is_train(point: Point) -> bool:
    raw = point.observed.raw
    return not (
        (
            raw.sig
            ^ (raw.sig >> 19)
            ^ (raw.sig >> 43)
            ^ raw.index
        )
        & 1
    )


def optimize(
    train: list[Point],
    heldout: list[Point],
    start: h119.Schedule,
    passes: int = 4,
) -> h119.Schedule:
    current = start
    for pass_index in range(passes):
        print(f"\ncoordinate pass {pass_index + 1}")
        changed = False
        for coordinate in h119.coordinates():
            candidates = tuple(dict.fromkeys(coordinate.candidates(current)))
            ranked = sorted(
                (
                    score(train, candidate).rank(),
                    candidate.short(),
                    candidate,
                )
                for candidate in candidates
            )
            train_base = score(train, current)
            heldout_base = score(heldout, current)
            accepted = None
            for _, _, candidate in ranked[:8]:
                train_score = score(train, candidate)
                heldout_score = score(heldout, candidate)
                if (
                    h110.no_worse(train_score, train_base)
                    and h110.no_worse(heldout_score, heldout_base)
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
                f"  {coordinate.name:13s} -> "
                f"train {train_score.describe()}; "
                f"heldout {heldout_score.describe()}"
            )
            print(f"    {current.short()}")
        if not changed:
            break
    return current


def main() -> None:
    points = load_points()
    train = [point for point in points if is_train(point)]
    heldout = [point for point in points if not is_train(point)]
    print(
        f"loaded {len(points)} FSIN odd-quadrant polynomial residuals: "
        f"{len(train)} train, {len(heldout)} held out"
    )
    for name, candidate in (
        ("shared", h119.SHARED_START),
        ("h64 FCOS", h119.H64_START),
        ("h119 FCOS", h119.FCOS_SURVIVOR),
        ("FSIN cosine", FSIN_INTERNAL_COSINE),
    ):
        print(
            f"{name:10s} train {score(train, candidate).describe()}; "
            f"heldout {score(heldout, candidate).describe()}; "
            f"complete {score(points, candidate).describe()}"
        )
    winner = optimize(train, heldout, h119.FCOS_SURVIVOR)
    print("\nvalidated FSIN-internal cosine survivor")
    print(f"  {winner.short()}")
    print(f"  train    {score(train, winner).describe()}")
    print(f"  heldout  {score(heldout, winner).describe()}")
    print(f"  complete {score(points, winner).describe()}")


if __name__ == "__main__":
    main()
