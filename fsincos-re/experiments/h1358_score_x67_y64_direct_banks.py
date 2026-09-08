#!/usr/bin/env python3
"""Score the fixed X67/Y64 fourth-power model on all direct hardware banks.

h1357 identifies the arithmetic recurrence from factor labels.  This audit
checks its compiled C implementation against the original one-shot hardware
words for every captured mode/operand leg in the three disjoint banks.  It
also verifies that the newly compiled predecessor is value-identical to the
historical predecessor executable on the same finite domain.

No hardware instruction is executed by this program.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from pathlib import Path

from h1210_stagea_residual_reframe import run


MODES = ("rn", "rd", "ru")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("historical_predecessor", type=Path)
    parser.add_argument("compiled_predecessor", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--direct-label", action="append", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    rows = []
    seen: dict[tuple[str, str], str] = {}
    for bank, path in enumerate(args.direct_label):
        with path.open(newline="") as source:
            for row in csv.DictReader(source, delimiter="\t"):
                mode = row["mode"].lower()
                if mode not in MODES:
                    raise ValueError(f"unexpected mode {mode} in {path}")
                operand = row["op"].lower()
                hardware = row["hardware"].lower()
                key = mode, operand
                previous = seen.setdefault(key, hardware)
                if previous != hardware:
                    raise RuntimeError(f"hardware conflict for {key}")
                rows.append((mode, operand, hardware, bank))

    counts = Counter()
    diagnostics = []
    outputs = {}
    for mode in MODES:
        operands = sorted({operand for row_mode, operand, _, _ in rows if row_mode == mode})
        for name, model in (
            ("historical", args.historical_predecessor),
            ("compiled", args.compiled_predecessor),
            ("candidate", args.candidate),
        ):
            values, _ = run(model, mode, operands)
            outputs.update({(name, mode, operand): value for operand, value in zip(operands, values)})

    for mode, operand, hardware, bank in rows:
        historical = outputs["historical", mode, operand]
        compiled = outputs["compiled", mode, operand]
        candidate = outputs["candidate", mode, operand]
        counts["legs"] += 1
        counts[f"bank{bank}.legs"] += 1
        counts["predecessor_rebuild_differences"] += historical != compiled
        counts["historical_errors"] += historical != hardware
        counts["candidate_errors"] += candidate != hardware
        counts[f"bank{bank}.candidate_errors"] += candidate != hardware
        counts["candidate_changes"] += candidate != historical
        counts["candidate_changes_correct"] += candidate != historical and candidate == hardware
        if candidate != hardware or historical != compiled:
            diagnostics.append(
                (mode, operand, hardware, historical, compiled, candidate, bank)
            )

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        for name, path in (
            ("historical_predecessor", args.historical_predecessor),
            ("compiled_predecessor", args.compiled_predecessor),
            ("candidate", args.candidate),
        ):
            output.write(f"{name}_sha256\t{digest(path)}\n")
        for index, path in enumerate(args.direct_label):
            output.write(f"direct_labels_sha256.{index}\t{digest(path)}\n")
        output.write("hardware_policy\tfrozen_one_shot_labels_no_x87_execution\n")
        output.write("candidate_policy\tunconditional_X67_times_chop64_fourth_power\n")
        output.write("\n[counts]\n")
        for name, value in sorted(counts.items()):
            output.write(f"{name}\t{value}\n")
        output.write("\n[diagnostics]\n")
        output.write(
            "mode\top\thardware\thistorical_predecessor\t"
            "compiled_predecessor\tcandidate\tbank\n"
        )
        for item in diagnostics:
            output.write("\t".join(map(str, item)) + "\n")

    print(
        f"wrote {args.report}: legs={counts['legs']} "
        f"changes={counts['candidate_changes']} "
        f"candidate_errors={counts['candidate_errors']} "
        f"rebuild_differences={counts['predecessor_rebuild_differences']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
