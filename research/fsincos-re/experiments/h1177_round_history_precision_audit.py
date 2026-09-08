#!/usr/bin/env python3
"""Test exact discarded-error coordinates as R59 rounding history.

Intel US5612909 describes carrying both a coarse rounding direction and a
"precision difference" from one micro-operation to the next.  The coarse
direction tags do not make the remaining upper-binade R59 cells monotone.
This cached-label audit asks the stronger question: does an exact signed
discarded-error coordinate, combined with the already-derived R60 M value,
restore one monotone separator per discrete digit cell?

No hardware is captured.  Exact values are Python integers representing
dyadic rationals; all inputs and labels come from frozen TSV artifacts.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import defaultdict
from pathlib import Path


CELL = ("theta", "ce", "s4", "side", "low3", "dist", "rsh", "b1", "b2")

# (sign, binary exponent, integer significand) for P5C6_1..P5C6_6.
COEFFICIENTS = (
    (-1, -68, (7 << 64) | 0xFFFFFFFFFFFFFFFE),
    (+1, -71, (5 << 64) | 0x5555555555554277),
    (-1, -76, (5 << 64) | 0xB05B05B05A18A1BA),
    (+1, -82, (6 << 64) | 0x80680675B559F2CF),
    (-1, -88, (4 << 64) | 0x9F93AF61F5349300),
    (+1, -95, (4 << 64) | 0x7A4F2483514C1AF8),
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def signed128(text: str) -> int:
    value = int(text, 16)
    return value - (1 << 128) if value >> 127 else value


def signed_value(row: dict[str, str], name: str) -> tuple[int, int]:
    significand = int(row[f"tc_{name}_sig"], 16)
    if int(row[f"tc_{name}_sign"]):
        significand = -significand
    return significand, int(row[f"tc_{name}_exp"])


def scaled_floor(terms: list[tuple[int, int]], exponent: int) -> int:
    """Return floor(sum(n*2**e) / 2**exponent), exactly."""
    common = min(term_exponent for _, term_exponent in terms)
    numerator = sum(value << (term_exponent - common)
                    for value, term_exponent in terms)
    shift = common - exponent
    return numerator << shift if shift >= 0 else numerator // (1 << -shift)


def coordinates(row: dict[str, str]) -> dict[str, int]:
    magnitude = int(row["tc_mag_sig"], 16)
    magnitude_exponent = int(row["tc_mag_exp"])
    ideal_terms = [
        (sign * significand * magnitude ** (2 * index),
         coefficient_exponent + 2 * index * magnitude_exponent)
        for index, (sign, coefficient_exponent, significand)
        in enumerate(COEFFICIENTS, 1)
    ]
    staged_terms = [signed_value(row, "left"), signed_value(row, "right")]
    full_product_terms = []
    for first, second in (("mul", "lf"), ("f4", "rf")):
        first_value, first_exponent = signed_value(row, first)
        second_value, second_exponent = signed_value(row, second)
        full_product_terms.append((first_value * second_value,
                                   first_exponent + second_exponent))
    payload = int(row["tc_payload"])
    if payload:
        left_sign = int(row["tc_left_sign"])
        payload_value = -payload if left_sign else payload
        payload_term = (payload_value, int(row["tc_left_exp"]) - 8)
        staged_terms.append(payload_term)
        full_product_terms.append(payload_term)

    # The terminal retained unit is 2**(rscale+k).  Multiplying by 2**66
    # expresses a discarded-error displacement in the native M coordinate.
    retained_exponent = int(row["rscale"]) + int(row["k"])
    scale_exponent = retained_exponent - 66
    ideal = scaled_floor(ideal_terms, scale_exponent)
    staged = scaled_floor(staged_terms, scale_exponent)
    full_products = scaled_floor(full_product_terms, scale_exponent)
    return {
        "M": signed128(row["Mreg"]),
        "ideal": ideal,
        "ideal_minus_staged": ideal - staged,
        "products_minus_staged": full_products - staged,
        "ideal_minus_products": ideal - full_products,
    }


def monotonicity(groups: dict[tuple[int, ...], list[tuple[int, int]]],
                 coordinate: str, coefficient: int = 0,
                 shift: int = 0) -> tuple[int, int]:
    mixed = 0
    nonmonotone = 0
    for key, entries in groups.items():
        values = []
        for label, item in entries:
            value = item["M"]
            if coordinate != "M":
                correction = item[coordinate]
                correction = (correction << shift if shift >= 0
                              else correction // (1 << -shift))
                value += coefficient * correction
            values.append((value, label))
        fires = [value for value, label in values if label]
        cleans = [value for value, label in values if not label]
        if not fires or not cleans:
            continue
        mixed += 1
        separable = (max(fires) < min(cleans) if key[0] >= 0
                     else max(cleans) < min(fires))
        nonmonotone += not separable
    return mixed, nonmonotone


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("physical_rows", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    with args.features.open(newline="") as source:
        features = {(row["mode"], row["op"]): row for row in
                    csv.DictReader(source, delimiter="\t")}
    groups: dict[tuple[int, ...], list[tuple[int, dict[str, int]]]] = defaultdict(list)
    row_count = 0
    with args.physical_rows.open(newline="") as source:
        for physical in csv.DictReader(source, delimiter="\t"):
            if physical["physical_status"] != "constraining":
                continue
            row = features[(physical["mode"], physical["op"])]
            key = tuple(int(physical[field]) for field in CELL)
            groups[key].append((int(physical["physical_label"]), coordinates(row)))
            row_count += 1

    base_results = {}
    for coordinate in ("M", "ideal", "ideal_minus_staged",
                       "products_minus_staged", "ideal_minus_products"):
        if coordinate == "M":
            result = monotonicity(groups, coordinate)
        else:
            # Pure error coordinate, without M.
            pure_groups = {
                key: [(label, {"M": item[coordinate]})
                      for label, item in entries]
                for key, entries in groups.items()
            }
            result = monotonicity(pure_groups, "M")
        base_results[coordinate] = result

    search_results = {}
    for coordinate in ("ideal_minus_staged", "products_minus_staged",
                       "ideal_minus_products"):
        candidates = []
        for coefficient in range(-32, 33):
            for shift in range(-8, 9):
                mixed, nonmonotone = monotonicity(
                    groups, coordinate, coefficient, shift)
                candidates.append((nonmonotone, mixed, coefficient, shift))
        search_results[coordinate] = sorted(candidates)[:30]

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("w") as target:
        target.write(f"features_sha256\t{digest(args.features)}\n")
        target.write(f"physical_rows_sha256\t{digest(args.physical_rows)}\n")
        target.write(f"constraining_rows\t{row_count}\n")
        target.write(f"cells\t{len(groups)}\n")
        target.write("\n[base]\n")
        target.write("coordinate\tmixed\tnonmonotone\n")
        for coordinate, (mixed, nonmonotone) in base_results.items():
            target.write(f"{coordinate}\t{mixed}\t{nonmonotone}\n")
        for coordinate, candidates in search_results.items():
            target.write(f"\n[best M+k*{coordinate}*2^shift]\n")
            target.write("nonmonotone\tmixed\tk\tshift\n")
            for nonmonotone, mixed, coefficient, shift in candidates:
                target.write(f"{nonmonotone}\t{mixed}\t{coefficient}\t{shift}\n")

    best = min(candidate for candidates in search_results.values()
               for candidate in candidates)
    print(f"rows={row_count} cells={len(groups)} "
          f"M_nonmonotone={base_results['M'][1]} "
          f"best_nonmonotone={best[0]} report={args.report}")


if __name__ == "__main__":
    main()
