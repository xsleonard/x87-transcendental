#!/usr/bin/env python3
"""Constrain FSIN's sine producer after even-quadrant range reduction."""

from __future__ import annotations

import dataclasses

import h58_constraint_search as h58
import h60_round16_parity as h60
import h64_poly_constraints as h64
import h110_fsin_standalone as h110


ROOT = h110.ROOT
INPUTS = ROOT / "capture-kit" / "inputs" / "sweep_inputs.txt"
CAPTURE = ROOT / "capture-kit-captures" / "skylake-fsin-h110"

FSIN_REDUCED_SINE = h110.Schedule(
    square=h110.Quant(66, "away"),
    coefficient=h110.Quant(67, "rn"),
    products=(h110.Quant(69, "rn"),) * 5,
    sums=(
        h110.Quant(69, "rn"),
        h110.Quant(69, "rn"),
        h110.Quant(69, "rn"),
        h110.Quant(69, "rn"),
        h110.Quant(65, "rn"),
    ),
    m=h110.Quant(65, "chop"),
    correction=h110.EXACT,
)


def load_points() -> list[h110.Observed]:
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
        if (
            quadrant & 1
            or r_sig == 0
            or exponent >= -2
            or exponent < -32
        ):
            continue
        if c_nonzero:
            raise AssertionError("polynomial residual unexpectedly has c")
        output_sign = (r_se >> 15) ^ ((quadrant >> 1) & 1)
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
            sign=output_sign,
            exponent=exponent,
            sig=r_sig,
            sincos=(((0, 0), (0, 0)),) * 3,
            standalone=((0, 0), (0, 0)),
        )
        result.append(
            h110.Observed(raw, tuple(outputs), tuple(c1))
        )
    return result


def is_train(point: h110.Observed) -> bool:
    raw = point.raw
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
    train: list[h110.Observed],
    heldout: list[h110.Observed],
    start: h110.Schedule,
    passes: int = 4,
) -> h110.Schedule:
    current = start
    for pass_index in range(passes):
        print(f"\ncoordinate pass {pass_index + 1}")
        changed = False
        for coordinate in h110.coordinates():
            candidates = tuple(dict.fromkeys(coordinate.candidates(current)))
            ranked = sorted(
                (
                    h110.score(train, candidate).rank(),
                    candidate.short(),
                    candidate,
                )
                for candidate in candidates
            )
            train_base = h110.score(train, current)
            heldout_base = h110.score(heldout, current)
            accepted = None
            for _, _, candidate in ranked[:8]:
                train_score = h110.score(train, candidate)
                heldout_score = h110.score(heldout, candidate)
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
        f"loaded {len(points)} FSIN even-quadrant polynomial residuals: "
        f"{len(train)} train, {len(heldout)} held out"
    )
    for name, candidate in (
        ("h64 start", h110.H64_START),
        ("direct FSIN", h110.FSIN_SURVIVOR),
        ("reduced FSIN", FSIN_REDUCED_SINE),
    ):
        print(
            f"{name:11s} train {h110.score(train, candidate).describe()}; "
            f"heldout {h110.score(heldout, candidate).describe()}; "
            f"complete {h110.score(points, candidate).describe()}"
        )
    winner = optimize(train, heldout, h110.H64_START)
    print("\nvalidated FSIN reduced-sine survivor")
    print(f"  {winner.short()}")
    print(f"  train    {h110.score(train, winner).describe()}")
    print(f"  heldout  {h110.score(heldout, winner).describe()}")
    print(f"  complete {h110.score(points, winner).describe()}")


if __name__ == "__main__":
    main()
