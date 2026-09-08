#!/usr/bin/env python3
"""Search compact phase-factor bases for the h1135 threshold intervals.

The eight observed outer states are exactly the cube of three binary phase
coordinates:

    e = -ce - 74,  a = s4 - 66,  h = rsh - 63.

This script asks which low-degree products of those physical phase bits and
the theta direction/magnitude can place one threshold inside every observed
integer interval.  It uses cyclic half-space projections as a feasibility
test.  A zero-violation basis is only a representation candidate; a compact
integer recurrence and an unseen-bank validation are still required.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class Cell:
    e: int
    a: int
    h: int
    theta: int
    payload: int
    b1: int
    b2: int
    low: int | None
    high: int | None


def load_cells(path: Path) -> list[Cell]:
    cells = []
    with path.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            low_value = int(row["F_low"])
            high_value = int(row["F_high"])
            cells.append(Cell(
                e=-int(row["ce"]) - 74,
                a=int(row["s4"]) - 66,
                h=int(row["rsh"]) - 63,
                theta=int(row["theta"]),
                payload=int(row["low3"]) + 8 - int(row["dist"]),
                b1=int(row["b1"]),
                b2=int(row["b2"]),
                low=None if low_value <= -999 else low_value,
                high=None if high_value >= 999 else high_value,
            ))
    return cells


def phase_terms(cell: Cell, degree: int) -> dict[str, float]:
    values = {"e": cell.e, "a": cell.a, "h": cell.h}
    terms = {"1": 1.0, **{name: float(value) for name, value in values.items()}}
    if degree >= 2:
        terms.update({
            "ea": float(cell.e * cell.a),
            "eh": float(cell.e * cell.h),
            "ah": float(cell.a * cell.h),
        })
    if degree >= 3:
        terms["eah"] = float(cell.e * cell.a * cell.h)
    return terms


def theta_terms(cell: Cell, form: str) -> dict[str, float]:
    theta = cell.theta
    if form == "affine":
        return {"1": 1.0, "t": float(theta)}
    if form == "quadratic":
        return {"1": 1.0, "t": float(theta), "t2": float(theta * theta)}
    if form == "direction":
        return {
            "1": 1.0,
            "dn": float(theta > 0),
            "up": float(theta < 0),
            "th": float(abs(theta)),
        }
    if form == "onehot":
        return {f"t{value}": float(theta == value) for value in range(-2, 3)}
    raise ValueError(form)


def add_products(target: dict[str, float], prefix: str,
                 left: dict[str, float], right: dict[str, float]) -> None:
    for lname, lvalue in left.items():
        for rname, rvalue in right.items():
            name = prefix
            if lname != "1":
                name += ":" + lname
            if rname != "1":
                name += ":" + rname
            target[name] = lvalue * rvalue


def add_carrier_products(target: dict[str, float], prefix: str, value: float,
                         left: dict[str, float], right: dict[str, float]) -> None:
    before = set(target)
    add_products(target, prefix, left, right)
    for name in set(target) - before:
        target[name] *= value


def row_features(cell: Cell, recipe: str) -> dict[str, float]:
    phase1 = phase_terms(cell, 1)
    phase2 = phase_terms(cell, 2)
    phase3 = phase_terms(cell, 3)
    theta_affine = theta_terms(cell, "affine")
    theta_quadratic = theta_terms(cell, "quadratic")
    theta_direction = theta_terms(cell, "direction")
    theta_onehot = theta_terms(cell, "onehot")
    carrier = {
        "i": 1.0,
        "p": float(cell.payload),
        "b1": float(cell.b1),
        "b2": float(cell.b2),
        "lp": float(cell.payload & 1),
    }
    result: dict[str, float] = {}
    if recipe == "affine2":
        add_products(result, "i", phase2, theta_quadratic)
        for name in ("p", "b1", "b2", "lp"):
            result[name] = carrier[name]
    elif recipe == "carrier_phase1_theta_direction":
        for name in ("i", "p", "b1", "b2", "lp"):
            add_carrier_products(
                result, name, carrier[name], phase1, theta_direction)
    elif recipe == "carrier_phase2_theta_affine":
        for name in ("i", "p", "b1", "b2", "lp"):
            add_carrier_products(
                result, name, carrier[name], phase2, theta_affine)
    elif recipe == "intercept_phase3_theta_direction":
        add_products(result, "i", phase3, theta_direction)
        add_products(result, "p", phase3, {"1": 1.0})
        add_products(result, "p", {"1": 1.0}, theta_direction)
        add_products(result, "b1", {"1": 1.0}, theta_direction)
        add_products(result, "b2", {"1": 1.0}, theta_direction)
        result["lp"] = carrier["lp"]
        for key in list(result):
            if key.startswith("p"):
                result[key] *= carrier["p"]
            elif key.startswith("b1"):
                result[key] *= carrier["b1"]
            elif key.startswith("b2"):
                result[key] *= carrier["b2"]
    elif recipe == "full_phase2_theta_direction":
        for name in ("i", "p", "b1", "b2", "lp"):
            add_carrier_products(
                result, name, carrier[name], phase2, theta_direction)
    elif recipe == "full_phase3_theta_direction":
        for name in ("i", "p", "b1", "b2", "lp"):
            add_carrier_products(
                result, name, carrier[name], phase3, theta_direction)
    elif recipe == "full_phase3_theta_onehot":
        for name in ("i", "p", "b1", "b2", "lp"):
            add_carrier_products(
                result, name, carrier[name], phase3, theta_onehot)
    else:
        raise ValueError(recipe)
    return result


def constraints(cells: list[Cell], recipe: str):
    dictionaries = [row_features(cell, recipe) for cell in cells]
    names = sorted({name for row in dictionaries for name in row})
    index = {name: offset for offset, name in enumerate(names)}
    matrix = np.zeros((len(cells), len(names)), dtype=np.float64)
    for row_index, row in enumerate(dictionaries):
        for name, value in row.items():
            matrix[row_index, index[name]] = value
    halves = []
    for row_index, cell in enumerate(cells):
        if cell.low is not None:
            halves.append((matrix[row_index], float(cell.low), row_index, "low"))
        if cell.high is not None:
            halves.append((-matrix[row_index], float(-cell.high), row_index, "high"))
    return names, halves


def project(halves, width: int, epochs: int, seed: int):
    rng = np.random.default_rng(seed)
    weights = np.zeros(width, dtype=np.float64)
    order = np.arange(len(halves))
    all_vectors = np.stack([item[0] for item in halves])
    all_bounds = np.array([item[1] for item in halves])
    best = None
    stale = 0
    for epoch in range(epochs):
        rng.shuffle(order)
        for offset in order:
            vector, bound, _, _ = halves[offset]
            shortfall = bound - float(vector @ weights)
            if shortfall > 0.0:
                norm = float(vector @ vector)
                weights += (shortfall + 1e-9) / norm * vector
        shortfalls = all_bounds - all_vectors @ weights
        bad = np.flatnonzero(shortfalls > 1e-7)
        violations = [
            (float(shortfalls[offset]), halves[offset][2], halves[offset][3])
            for offset in bad
        ]
        score = (len(violations), max((item[0] for item in violations), default=0.0))
        if best is None or score < best[0]:
            best = (score, weights.copy(), list(violations), epoch)
            stale = 0
        else:
            stale += 1
        if not violations or stale >= 5000:
            break
    assert best is not None
    return best


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("thresholds", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--epochs", type=int, default=30000)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--recipes", nargs="*")
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")
    cells = load_cells(args.thresholds)
    recipes = args.recipes or (
        "affine2",
        "carrier_phase1_theta_direction",
        "carrier_phase2_theta_affine",
        "intercept_phase3_theta_direction",
        "full_phase2_theta_direction",
        "full_phase3_theta_direction",
        "full_phase3_theta_onehot",
    )
    results = []
    for recipe in recipes:
        names, halves = constraints(cells, recipe)
        attempts = [project(halves, len(names), args.epochs, seed)
                    for seed in range(args.attempts)]
        best = min(attempts, key=lambda result: result[0])
        results.append((recipe, names, halves, best))
        print(f"{recipe}: width={len(names)} constraints={len(halves)} "
              f"violations={best[0][0]} max={best[0][1]:.6g}", flush=True)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("w") as target:
        target.write(f"cells\t{len(cells)}\n")
        target.write("recipe\twidth\tconstraints\tviolations\tmax_shortfall\tepoch\n")
        for recipe, names, halves, best in results:
            target.write(
                f"{recipe}\t{len(names)}\t{len(halves)}\t{best[0][0]}\t"
                f"{best[0][1]:.12g}\t{best[3] + 1}\n"
            )
        for recipe, names, _, best in results:
            target.write(f"\n[{recipe}-weights]\n")
            target.write("feature\tweight\n")
            for name, weight in sorted(zip(names, best[1]),
                                       key=lambda item: (-abs(item[1]), item[0])):
                target.write(f"{name}\t{weight:.12g}\n")
            target.write(f"[{recipe}-violations]\n")
            for shortfall, row_index, side in sorted(best[2], reverse=True)[:40]:
                target.write(f"{shortfall:.12g}\t{row_index}\t{side}\t{cells[row_index]}\n")


if __name__ == "__main__":
    main()
