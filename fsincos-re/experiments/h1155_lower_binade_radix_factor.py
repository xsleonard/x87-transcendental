#!/usr/bin/env python3
"""Factor the h1135 integer-threshold surface into small radix terms.

This is a structural search, not a candidate selector.  It asks which small
integer slopes/taps admit one intercept over each observed outer/theta group,
then tests whether the surviving terms factor by theta or by the physical
square/right-shift phase.  A per-group intercept is reported only as a
diagnostic; it is not accepted as a closed form.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


INF = 10**6


def bounds(text_low: str, text_high: str) -> tuple[int, int]:
    low = int(text_low)
    high = int(text_high)
    return (-INF if low <= -999 else low, INF if high >= 999 else high)


def intercept_interval(cells, slope: int, tap1: int, tap2: int):
    lower, upper = -INF, INF
    for payload, b1, b2, low, high in cells:
        base = slope * payload + tap1 * b1 + tap2 * b2
        lower = max(lower, low - base)
        upper = min(upper, high - base)
        if lower > upper:
            return None
    return lower, upper


def complexity(candidate: tuple[int, int, int]) -> tuple[int, tuple[int, int, int]]:
    return sum(abs(value) for value in candidate), candidate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("thresholds", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--slope-min", type=int, default=-2)
    parser.add_argument("--slope-max", type=int, default=10)
    parser.add_argument("--tap-radius", type=int, default=6)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    groups = defaultdict(list)
    outer_meta = {}
    with args.thresholds.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            outer = tuple(int(row[name]) for name in
                          ("ce", "s4", "side", "dist", "rsh"))
            theta = int(row["theta"])
            low, high = bounds(row["F_low"], row["F_high"])
            payload = int(row["low3"]) + 8 - int(row["dist"])
            groups[(outer, theta)].append((
                payload, int(row["b1"]), int(row["b2"]), low, high,
            ))
            outer_meta[outer] = {
                "phase_slope": (1 << (int(row["s4"]) - 65))
                               + int(row["rsh"]) - 63,
                "radix_slope": 2 + 3 * (int(row["s4"]) - 66)
                              + (int(row["rsh"]) - 63)
                                * (67 - int(row["s4"])),
            }

    candidates = [
        (slope, tap1, tap2)
        for slope in range(args.slope_min, args.slope_max + 1)
        for tap1 in range(-args.tap_radius, args.tap_radius + 1)
        for tap2 in range(-args.tap_radius, args.tap_radius + 1)
    ]
    feasible = {
        key: {
            candidate: interval
            for candidate in candidates
            if (interval := intercept_interval(cells, *candidate)) is not None
        }
        for key, cells in groups.items()
    }
    thetas = sorted({theta for _, theta in groups})
    outers = sorted({outer for outer, _ in groups})

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("w") as target:
        target.write(f"groups\t{len(groups)}\n")
        target.write(f"candidates\t{len(candidates)}\n")
        target.write("\n[group-survivors]\n")
        target.write("outer\ttheta\tcount\tbest_slope\tbest_b1\tbest_b2\t"
                     "intercept_low\tintercept_high\n")
        for key in sorted(groups):
            choices = sorted(feasible[key], key=complexity)
            best = choices[0]
            interval = feasible[key][best]
            target.write(
                f"{'/'.join(map(str, key[0]))}\t{key[1]}\t{len(choices)}\t"
                f"{best[0]}\t{best[1]}\t{best[2]}\t"
                f"{interval[0]}\t{interval[1]}\n"
            )

        target.write("\n[shared-by-theta]\n")
        target.write("theta\tcount\tbest_slope\tbest_b1\tbest_b2\n")
        for theta in thetas:
            common = set(candidates)
            for outer in outers:
                common &= feasible[(outer, theta)].keys()
            ordered = sorted(common, key=complexity)
            if ordered:
                best = ordered[0]
                target.write(
                    f"{theta}\t{len(ordered)}\t{best[0]}\t{best[1]}\t{best[2]}\n"
                )
            else:
                target.write(f"{theta}\t0\t\t\t\n")

        target.write("\n[shared-by-outer]\n")
        target.write("outer\tphase_slope\tcount\tbest_slope\tbest_b1\tbest_b2\n")
        for outer in outers:
            common = set(candidates)
            for theta in thetas:
                common &= feasible[(outer, theta)].keys()
            ordered = sorted(common, key=complexity)
            phase_slope = outer_meta[outer]["phase_slope"]
            if ordered:
                best = ordered[0]
                target.write(
                    f"{'/'.join(map(str, outer))}\t{phase_slope}\t{len(ordered)}\t"
                    f"{best[0]}\t{best[1]}\t{best[2]}\n"
                )
            else:
                target.write(
                    f"{'/'.join(map(str, outer))}\t{phase_slope}\t0\t\t\t\n"
                )

        target.write("\n[phase-slope-theta-taps]\n")
        target.write("theta\tcount\tbest_b1\tbest_b2\n")
        for theta in thetas:
            taps = []
            for tap1 in range(-args.tap_radius, args.tap_radius + 1):
                for tap2 in range(-args.tap_radius, args.tap_radius + 1):
                    if all(
                        intercept_interval(
                            groups[(outer, theta)],
                            outer_meta[outer]["phase_slope"], tap1, tap2,
                        ) is not None
                        for outer in outers
                    ):
                        taps.append((tap1, tap2))
            taps.sort(key=lambda value: (abs(value[0]) + abs(value[1]), value))
            if taps:
                target.write(f"{theta}\t{len(taps)}\t{taps[0][0]}\t{taps[0][1]}\n")
            else:
                target.write(f"{theta}\t0\t\t\n")

        target.write("\n[fixed-phase-slope-groups]\n")
        target.write("outer\ttheta\tphase_slope\tcount\tbest_b1\tbest_b2\t"
                     "intercept_low\tintercept_high\n")
        for key in sorted(groups):
            outer, theta = key
            slope = outer_meta[outer]["phase_slope"]
            choices = []
            for tap1 in range(-args.tap_radius, args.tap_radius + 1):
                for tap2 in range(-args.tap_radius, args.tap_radius + 1):
                    interval = intercept_interval(
                        groups[key], slope, tap1, tap2)
                    if interval is not None:
                        choices.append((
                            abs(tap1) + abs(tap2), tap1, tap2, interval,
                        ))
            choices.sort()
            if choices:
                _, tap1, tap2, interval = choices[0]
                target.write(
                    f"{'/'.join(map(str, outer))}\t{theta}\t{slope}\t"
                    f"{len(choices)}\t{tap1}\t{tap2}\t"
                    f"{interval[0]}\t{interval[1]}\n"
                )
            else:
                target.write(
                    f"{'/'.join(map(str, outer))}\t{theta}\t{slope}\t0\t\t\t\t\n"
                )

        target.write("\n[fixed-radix-slope-groups]\n")
        target.write("outer\ttheta\tradix_slope\tcount\tbest_b1\tbest_b2\t"
                     "intercept_low\tintercept_high\n")
        for key in sorted(groups):
            outer, theta = key
            slope = outer_meta[outer]["radix_slope"]
            choices = []
            for tap1 in range(-args.tap_radius, args.tap_radius + 1):
                for tap2 in range(-args.tap_radius, args.tap_radius + 1):
                    interval = intercept_interval(
                        groups[key], slope, tap1, tap2)
                    if interval is not None:
                        choices.append((
                            abs(tap1) + abs(tap2), tap1, tap2, interval,
                        ))
            choices.sort()
            if choices:
                _, tap1, tap2, interval = choices[0]
                target.write(
                    f"{'/'.join(map(str, outer))}\t{theta}\t{slope}\t"
                    f"{len(choices)}\t{tap1}\t{tap2}\t"
                    f"{interval[0]}\t{interval[1]}\n"
                )
            else:
                target.write(
                    f"{'/'.join(map(str, outer))}\t{theta}\t{slope}\t0\t\t\t\t\n"
                )

    print(f"groups={len(groups)} report={args.report}")


if __name__ == "__main__":
    main()
