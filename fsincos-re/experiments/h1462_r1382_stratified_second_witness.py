#!/usr/bin/env python3
"""Search fresh, globally distributed software separators for R1382.

The earlier R1382 search covered one contiguous d0d0 neighborhood and 64
thin strata across the normalized 3ffc binade.  This analysis uses the
midpoints of a distinct 128-stratum partition, proves that its intervals do
not overlap either earlier surface, and runs the existing exact integer
scanner.  Only theta-zero, low3-three, s4=66/67 events are replayed through
the incumbent and R1382 candidate executables in all nonredundant modes.

This is a deterministic software search, not an exhaustive-domain proof.
It does not execute x87 hardware, inspect private labels, freeze a manifest,
or modify emulator defaults.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
H1384_PATH = HERE / "h1384_merge_s4_adversarial_bank.py"
H1384_SPEC = importlib.util.spec_from_file_location("h1384_merge", H1384_PATH)
if H1384_SPEC is None or H1384_SPEC.loader is None:  # pragma: no cover
    raise SystemExit(f"cannot load {H1384_PATH}")
h1384 = importlib.util.module_from_spec(H1384_SPEC)
sys.modules[H1384_SPEC.name] = h1384
H1384_SPEC.loader.exec_module(h1384)


BIN_FIRST = 1 << 63
BIN_LAST = (1 << 64) - 1
OLD_STRATA = 64
OLD_STRATUM_RADIUS = 100_000_000
OLD_D0D0 = 0xD0D000000CC0B3F8
OLD_D0D0_RADIUS = (1 << 31) - 1
OLD_D0D0_OPERAND = "3ffc d0d000000cc0b3f8"
MODES = ("rn", "rd", "ru")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def midpoint(strata: int, index: int) -> int:
    return BIN_FIRST + ((2 * index + 1) * (1 << 63)) // (2 * strata)


def intervals(strata: int, radius: int) -> list[tuple[int, int]]:
    return [
        (max(BIN_FIRST, midpoint(strata, index) - radius),
         min(BIN_LAST, midpoint(strata, index) + radius))
        for index in range(strata)
    ]


def overlaps(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return max(left[0], right[0]) <= min(left[1], right[1])


def replay_rows(
    current: Path, candidate: Path, rows: list[dict[str, object]]
) -> tuple[list[dict[str, Any]], int]:
    if not rows:
        return [], 0
    operands = [str(row["op"]) for row in rows]
    outputs: dict[tuple[str, str], list[str]] = {}
    for mode in MODES:
        outputs[mode, "current"], _ = h1384.run(current, mode, operands)
        outputs[mode, "candidate"], _ = h1384.run(candidate, mode, operands)

    separators = []
    changed_legs = 0
    for index, row in enumerate(rows):
        changed_modes = [
            mode
            for mode in MODES
            if outputs[mode, "current"][index]
            != outputs[mode, "candidate"][index]
        ]
        if not changed_modes:
            continue
        changed_legs += len(changed_modes)
        separators.append({
            **row,
            "changed_modes": changed_modes,
            "outputs": {
                mode: {
                    "current": outputs[mode, "current"][index],
                    "candidate": outputs[mode, "candidate"][index],
                }
                for mode in MODES
            },
        })
    return separators, changed_legs


def replay_known_anchor(current: Path, candidate: Path) -> dict[str, Any]:
    outputs: dict[str, dict[str, str]] = {}
    changed_modes = []
    for mode in MODES:
        current_rows, _ = h1384.run(current, mode, [OLD_D0D0_OPERAND])
        candidate_rows, _ = h1384.run(candidate, mode, [OLD_D0D0_OPERAND])
        outputs[mode] = {
            "current": current_rows[0],
            "candidate": candidate_rows[0],
        }
        if current_rows[0] != candidate_rows[0]:
            changed_modes.append(mode)
    if changed_modes != ["rd"]:
        raise AssertionError(
            f"incumbent/candidate pair lost known d0d0 response: {changed_modes}"
        )
    return {
        "operand": OLD_D0D0_OPERAND,
        "changed_nonredundant_modes": changed_modes,
        "outputs": outputs,
    }


def write_new(path: Path, report: dict[str, Any]) -> None:
    if path.exists():
        raise SystemExit(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True)
        target.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("scanner", type=Path)
    parser.add_argument("current", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--strata", type=int, default=128)
    parser.add_argument("--radius", type=int, default=50_000_000)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    if args.strata != 2 * OLD_STRATA:
        raise SystemExit("this audit's non-overlap proof requires 128 strata")
    if args.radius <= 0 or args.radius > 50_000_000:
        raise SystemExit("radius must be in 1..50,000,000")
    if args.workers <= 0:
        raise SystemExit("workers must be positive")
    for path in (args.scanner, args.current, args.candidate):
        if not path.is_file():
            raise SystemExit(f"missing executable {path}")

    new_intervals = intervals(args.strata, args.radius)
    old_intervals = intervals(OLD_STRATA, OLD_STRATUM_RADIUS)
    old_d0d0_interval = (
        OLD_D0D0 - OLD_D0D0_RADIUS,
        OLD_D0D0 + OLD_D0D0_RADIUS,
    )
    overlap_pairs = [
        (new_index, old_index)
        for new_index, new_interval in enumerate(new_intervals)
        for old_index, old_interval in enumerate(old_intervals)
        if overlaps(new_interval, old_interval)
    ]
    d0d0_overlaps = [
        index
        for index, interval in enumerate(new_intervals)
        if overlaps(interval, old_d0d0_interval)
    ]
    if overlap_pairs or d0d0_overlaps:
        raise AssertionError(
            f"new surface overlaps prior scan: strata={overlap_pairs} "
            f"d0d0={d0d0_overlaps}"
        )

    anchors = [midpoint(args.strata, index) for index in range(args.strata)]
    with ThreadPoolExecutor(max_workers=min(args.workers, args.strata)) as pool:
        scanned_lists = list(pool.map(
            lambda interval: h1384.scan_interval(
                args.scanner, interval, anchors
            ),
            new_intervals,
        ))
    events_by_operand: dict[str, dict[str, object]] = {}
    events_by_stratum: dict[int, int] = {}
    for stratum, rows in enumerate(scanned_lists):
        events_by_stratum[stratum] = len(rows)
        for row in rows:
            events_by_operand[str(row["op"])] = row
    events = sorted(events_by_operand.values(), key=lambda row: str(row["op"]))
    known_anchor = replay_known_anchor(args.current, args.candidate)
    separators, changed_legs = replay_rows(args.current, args.candidate, events)

    report: dict[str, Any] = {
        "experiment": "h1462_r1382_stratified_second_witness",
        "selection": (
            "128 midpoint strata distinct from prior 64-stratum surface; "
            "software-only theta=0 low3=3 s4=66/67 events"
        ),
        "strata": args.strata,
        "radius": args.radius,
        "workers": args.workers,
        "input_significands": sum(last - first + 1
                                  for first, last in new_intervals),
        "nonoverlap_with_prior_64_strata": not overlap_pairs,
        "nonoverlap_with_prior_d0d0_slice": not d0d0_overlaps,
        "old_strata": OLD_STRATA,
        "old_stratum_radius": OLD_STRATUM_RADIUS,
        "old_d0d0_radius": OLD_D0D0_RADIUS,
        "scanner": str(args.scanner),
        "scanner_sha256": sha256(args.scanner),
        "current": str(args.current),
        "current_sha256": sha256(args.current),
        "candidate": str(args.candidate),
        "candidate_sha256": sha256(args.candidate),
        "known_anchor_replay": known_anchor,
        "structural_events": len(events),
        "eventful_strata": {
            str(index): count
            for index, count in events_by_stratum.items() if count
        },
        "architectural_separators": len(separators),
        "architectural_separator_legs": changed_legs,
        "separators": separators,
        "result": "SAT_SOFTWARE_SEPARATOR" if separators else "NO_SEPARATOR",
        "scope_boundary": (
            "deterministic finite software search, not exhaustive-domain "
            "proof and not a hardware label"
        ),
        "hardware_execution": "none",
        "private_ledger_access": "none",
        "capture_manifest": "none",
        "emulator_change": "none",
    }
    write_new(args.output, report)
    print(json.dumps({
        "output": str(args.output),
        "input_significands": report["input_significands"],
        "structural_events": report["structural_events"],
        "architectural_separators": report["architectural_separators"],
        "result": report["result"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
