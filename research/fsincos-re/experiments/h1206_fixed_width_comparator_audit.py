#!/usr/bin/env python3
"""Test fixed-width comparator isomorphisms for the residual R59 selector.

The incumbent uses exact signed comparisons of ``Mreg`` against integer
multiples of 2**66, but its remaining physical carry errors are not monotone
in that scalar coordinate.  A real finite-width subtractor could nevertheless
make those regions look nonmonotone when reconstructed with unbounded signed
arithmetic.  This audit tests that concrete alternative.

Three label-independent comparator realizations are evaluated at widths
64..86 and 128: the sign of the wrapped difference, signed comparison of the
truncated operands, and unsigned comparison of the truncated operands.  The
boundaries are either the incumbent R59 integer boundary, zero, or the fixed
h1158 radix recurrence transferred periodically.  Boundary scales 63..68 are
included to expose an alignment error.  Only Boolean compositions that agree
with the incumbent when both inputs agree (AND, candidate, incumbent, OR) are
eligible, so rows outside a boundary's domain cannot be changed silently.

This is a cached-label falsifier.  It performs no hardware capture and learns
no operand constants or per-cell thresholds.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from pathlib import Path


WIDTHS = tuple(range(64, 87)) + (128,)
SCALES = range(63, 69)
STABLE_GATES = (0x8, 0xA, 0xC, 0xE)
GATE_NAMES = {0x8: "and", 0xA: "candidate", 0xC: "incumbent", 0xE: "or"}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def signed128(text: str) -> int:
    value = int(text, 16)
    return value - (1 << 128) if value >> 127 else value


def signed_width(value: int, width: int) -> int:
    value &= (1 << width) - 1
    return value - (1 << width) if value >> (width - 1) else value


def incumbent_fire(row: dict[str, str]) -> int:
    branch = row["branch"]
    if branch == "tie":
        return int(row.get("br_tfire", "0") or 0)
    if branch in ("band", "corner"):
        return int(row.get("br_fire", "0") or 0)
    if branch == "q67th2":
        return 0
    raise RuntimeError(f"unsupported R59 branch {branch}: {row['op']}")


def incumbent_threshold(row: dict[str, str]) -> int | None:
    if row["branch"] == "tie" and row.get("br_u0", "") != "":
        return int(row["br_u0"])
    if row["branch"] == "band" and row.get("br_uu", "") != "":
        return int(row["br_uu"])
    return None


def periodic_threshold(row: dict[str, str]) -> int | None:
    """Return the parameter-free h1158 threshold in the upper phase."""
    ce = int(row["ce"])
    a = int(row["s4"]) - 66
    h = int(row["rsh"]) - 63
    e = (-ce - 74) & 1
    if a not in (0, 1) or h not in (0, 1):
        return None
    expected_distance = -ce - int(row["s4"]) + 2 + (64 - int(row["rsh"]))
    if int(row["side"]) != 1 - e or int(row["dist"]) != expected_distance:
        return None

    theta = int(row["theta"])
    if theta not in (-2, -1, 0, 1, 2):
        return None
    payload = int(row["low3"]) + 8 - int(row["dist"])
    b1, b2 = int(row["b1"]), int(row["b2"])
    slope = 2 + 3 * a + h * (1 - a)
    intercept0 = -1 - a - (1 - e) * (h + 2 * a)
    tap1 = tap2 = 0
    intercept = intercept0
    if theta == -2:
        tap1 = (2 * a * (1 - e * (1 - h))
                + (1 - e) * h * (1 - a))
        intercept = -1 - a + a * h * (3 - e)
    elif theta == -1:
        tap2 = a * h * (2 - e)
        intercept += (1 - e) * (2 * a + h) + a * h
    elif theta == 0:
        tap1 = (1 - e) * h * (1 + a)
    elif theta == 1:
        tap2 = (1 - e) * (1 + a * (1 - h))
        intercept -= tap2
    else:
        tap1 = a + (1 - e) * (1 - a) * (1 - h)
        intercept -= (2 * (1 - e) * (1 + a * (1 - h))
                      + 3 * a * h + a * e * (1 - h))
    return slope * payload + tap1 * b1 + tap2 * b2 + intercept


def compare(m_value: int, boundary: int, theta: int, width: int,
            realization: str) -> int:
    mask = (1 << width) - 1
    if realization == "difference_sign":
        less = signed_width(m_value - boundary, width) < 0
    elif realization == "signed_operands":
        less = signed_width(m_value, width) < signed_width(boundary, width)
    elif realization == "unsigned_operands":
        less = (m_value & mask) < (boundary & mask)
    else:
        raise AssertionError(realization)
    return int(less if theta >= 0 else not less)


def gate_value(gate: int, incumbent: int, candidate: int) -> int:
    return (gate >> (2 * incumbent + candidate)) & 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("physical_rows", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    rows = []
    with args.physical_rows.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            if row["physical_status"] != "constraining":
                continue
            rows.append(row)

    boundary_functions = {
        "incumbent": incumbent_threshold,
        "periodic_h1158": periodic_threshold,
        "zero": lambda row: 0,
    }
    realizations = (
        "difference_sign", "signed_operands", "unsigned_operands")
    baseline = Counter()
    prepared = []
    for row in rows:
        old = incumbent_fire(row)
        truth = int(row["physical_label"])
        kind = "target" if row["label"] == "POS" else "control"
        baseline[f"{kind}_miss"] += old != truth
        baseline[f"{kind}_rows"] += 1
        prepared.append((
            kind, old, truth, int(row["theta"]), signed128(row["Mreg"]),
            {name: function(row)
             for name, function in boundary_functions.items()},
        ))

    rankings = []
    for boundary_name in boundary_functions:
        for scale in SCALES:
            for width in WIDTHS:
                for realization in realizations:
                    contingency = Counter()
                    out_of_domain = 0
                    for kind, old, truth, theta, m_value, boundary_values in prepared:
                        units = boundary_values[boundary_name]
                        if units is None:
                            candidate = old
                            out_of_domain += 1
                        else:
                            candidate = compare(
                                m_value, units << scale, theta, width,
                                realization)
                        contingency[(kind, old, candidate, truth)] += 1
                    for gate in STABLE_GATES:
                        counts = Counter()
                        counts["out_of_domain"] = out_of_domain
                        for (kind, old, candidate, truth), count in contingency.items():
                            predicted = gate_value(gate, old, candidate)
                            counts[f"{kind}_miss"] += count * (predicted != truth)
                            counts[f"{kind}_change"] += count * (predicted != old)
                            counts[f"{kind}_candidate_diff"] += count * (candidate != old)
                        total_miss = counts["target_miss"] + counts["control_miss"]
                        rankings.append((
                            total_miss, counts["target_miss"],
                            counts["control_miss"], counts["control_change"],
                            counts["target_change"], boundary_name, scale,
                            width, realization, gate, counts,
                        ))
    rankings.sort(key=lambda item: item[:10])

    exact = [item for item in rankings if item[0] == 0]
    improvements = [item for item in rankings
                    if item[2] == 0 and item[1] < baseline["target_miss"]]
    nontrivial = [item for item in rankings if item[3] + item[4] > 0]
    best_by_boundary = {}
    best_nontrivial_by_boundary = {}
    for item in rankings:
        best_by_boundary.setdefault(item[5], item)
    for item in nontrivial:
        best_nontrivial_by_boundary.setdefault(item[5], item)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"physical_rows_sha256\t{digest(args.physical_rows)}\n")
        target.write(f"rows\t{len(rows)}\n")
        for key in sorted(baseline):
            target.write(f"baseline.{key}\t{baseline[key]}\n")
        target.write(f"candidates\t{len(rankings)}\n")
        target.write(f"exact_candidates\t{len(exact)}\n")
        target.write(f"zero_control_improvements\t{len(improvements)}\n")
        target.write("\n[best by boundary]\n")
        target.write("total_miss\ttarget_miss\tcontrol_miss\tcontrol_change\t"
                     "target_change\tboundary\tscale\twidth\trealization\tgate\t"
                     "out_of_domain\n")
        for name in boundary_functions:
            item = best_by_boundary[name]
            target.write("\t".join(map(str, item[:9])) + "\t"
                         + GATE_NAMES[item[9]] + "\t"
                         + str(item[10]["out_of_domain"]) + "\n")
        target.write("\n[best nontrivial by boundary]\n")
        target.write("total_miss\ttarget_miss\tcontrol_miss\tcontrol_change\t"
                     "target_change\tboundary\tscale\twidth\trealization\tgate\t"
                     "out_of_domain\n")
        for name in boundary_functions:
            item = best_nontrivial_by_boundary[name]
            target.write("\t".join(map(str, item[:9])) + "\t"
                         + GATE_NAMES[item[9]] + "\t"
                         + str(item[10]["out_of_domain"]) + "\n")
        target.write("\n[global ranking]\n")
        target.write("total_miss\ttarget_miss\tcontrol_miss\tcontrol_change\t"
                     "target_change\tboundary\tscale\twidth\trealization\tgate\t"
                     "out_of_domain\tcandidate_target_diff\t"
                     "candidate_control_diff\n")
        for item in rankings[:500]:
            counts = item[10]
            target.write("\t".join(map(str, item[:9])) + "\t"
                         + GATE_NAMES[item[9]] + "\t"
                         + str(counts["out_of_domain"]) + "\t"
                         + str(counts["target_candidate_diff"]) + "\t"
                         + str(counts["control_candidate_diff"]) + "\n")
        target.write("\n[nontrivial ranking]\n")
        target.write("total_miss\ttarget_miss\tcontrol_miss\tcontrol_change\t"
                     "target_change\tboundary\tscale\twidth\trealization\tgate\t"
                     "out_of_domain\tcandidate_target_diff\t"
                     "candidate_control_diff\n")
        for item in nontrivial[:500]:
            counts = item[10]
            target.write("\t".join(map(str, item[:9])) + "\t"
                         + GATE_NAMES[item[9]] + "\t"
                         + str(counts["out_of_domain"]) + "\t"
                         + str(counts["target_candidate_diff"]) + "\t"
                         + str(counts["control_candidate_diff"]) + "\n")
        target.write("\n[zero-control improvements]\n")
        for item in improvements:
            counts = item[10]
            target.write("\t".join(map(str, item[:9])) + "\t"
                         + GATE_NAMES[item[9]] + "\t"
                         + str(counts["out_of_domain"]) + "\n")

    best = rankings[0]
    print(
        f"rows={len(rows)} candidates={len(rankings)} "
        f"baseline_miss={baseline['target_miss'] + baseline['control_miss']} "
        f"best_miss={best[0]} target_miss={best[1]} control_miss={best[2]} "
        f"exact={len(exact)} zero_control_improvements={len(improvements)} "
        f"report={args.report}")


if __name__ == "__main__":
    main()
