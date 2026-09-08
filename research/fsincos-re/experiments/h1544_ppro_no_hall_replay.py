#!/usr/bin/env python3
"""Replay H1543's exact mapper search with Hall pruning disabled.

This cross-check has two obligations:

1. compare H1543's bipartite-matching predicate with an independent exhaustive
   matcher on deterministic randomized small graphs; and
2. run the complete opcode-mapper CSP with the Hall predicate replaced by the
   constant true predicate.

The second obligation ensures that H1543's UNSAT result does not depend on the
new Hall pruning.  The shared row-domain search is inherited from H1506; only
its completeness-preserving ambiguity tie break remains active.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

import h1543_ppro_hall_csp as h1543


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exhaustive_matching(domains: list[int]) -> bool:
    ordered = sorted(domains, key=int.bit_count)

    def search(variable: int, used: int) -> bool:
        if variable == len(ordered):
            return True
        choices = ordered[variable] & ~used
        while choices:
            low = choices & -choices
            choices ^= low
            if search(variable + 1, used | low):
                return True
        return False

    return search(0, 0)


def randomized_matching_crosscheck() -> dict[str, object]:
    seed = 0x1544A11
    trials = 10_000
    generator = random.Random(seed)
    for trial in range(trials):
        channel_count = generator.randrange(1, 10)
        variable_count = generator.randrange(0, 9)
        domains = [
            generator.randrange(1 << channel_count)
            for _ in range(variable_count)
        ]
        expected = exhaustive_matching(domains)
        actual = h1543.has_channel_matching(domains)
        if actual != expected:
            raise RuntimeError(
                f"matching disagreement at trial {trial}: {domains}"
            )
    return {
        "seed": seed,
        "trials": trials,
        "channel_count_range": [1, 9],
        "variable_count_range": [0, 8],
        "result": "pass",
        "reference": "independent exhaustive injection enumeration",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1467", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")
    if digest(arguments.h1467) != h1543.EXPECTED_H1467_SHA256:
        raise RuntimeError("H1467 report hash changed")

    h1543.selftest()
    matching_crosscheck = randomized_matching_crosscheck()
    rows = h1543.load_rows(json.loads(arguments.h1467.read_text()))
    original_matching = h1543.has_channel_matching
    try:
        h1543.has_channel_matching = lambda domains: True
        replay = h1543.solve(rows, arguments.timeout_seconds)
    finally:
        h1543.has_channel_matching = original_matching

    report = {
        "schema": "fsincos-h1544-ppro-no-hall-replay-v1",
        "query": "h1543_exact_mapper_replay_without_hall_pruning",
        "status": replay["status"],
        "timeout_seconds": replay["timeout_seconds"],
        "elapsed_seconds": replay["elapsed_seconds"],
        "search": {
            **replay["search"],
            "hall_pruning": "disabled_constant_true_predicate",
        },
        "problem": replay["problem"],
        "matching_predicate_crosscheck": matching_crosscheck,
        "dependencies": {
            "h1467_report_sha256": digest(arguments.h1467),
            "h1543_script_sha256": digest(Path(h1543.__file__)),
            "script_sha256": digest(Path(__file__)),
        },
        "claim_boundary": (
            "UNSAT proves only H1504's injective fixed-polarity twelve-channel "
            "mapping under the current 459-value public P6 recognized-opcode "
            "condition; it is not a general Pentium Pro decoder impossibility."
        ),
        "execution": {
            "hardware": "none",
            "x87_instructions": "none",
            "capture_labels_opened": "none",
            "private_capture_ledger": "not accessed",
            "h1488_state": "FROZEN_UNOPENED",
            "emulator_change": "none",
            "paper_change": "none",
        },
    }
    if "model" in replay:
        report["model"] = replay["model"]
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    arguments.output.write_text(text)
    print(json.dumps({
        "output": str(arguments.output),
        "report_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "status": report["status"],
        "matching_trials": matching_crosscheck["trials"],
        **report["search"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
