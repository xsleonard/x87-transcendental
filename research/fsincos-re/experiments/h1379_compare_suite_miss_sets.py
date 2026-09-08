#!/usr/bin/env python3
"""Compare matched predecessor/candidate ledger-off suite miss sets."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def rows(path: Path) -> set[str]:
    values = {line for line in path.read_text().splitlines() if line}
    if len(values) != sum(1 for line in path.read_text().splitlines() if line):
        raise RuntimeError(f"duplicate miss row in {path}")
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("predecessor_misses", type=Path)
    parser.add_argument("candidate_misses", type=Path)
    parser.add_argument("predecessor_binary", type=Path)
    parser.add_argument("candidate_binary", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    predecessor = rows(args.predecessor_misses)
    candidate = rows(args.candidate_misses)
    fixes = sorted(predecessor - candidate)
    regressions = sorted(candidate - predecessor)
    survivors = sorted(candidate & predecessor)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        for name, path in (
            ("predecessor_misses", args.predecessor_misses),
            ("candidate_misses", args.candidate_misses),
            ("predecessor_binary", args.predecessor_binary),
            ("candidate_binary", args.candidate_binary),
        ):
            output.write(f"{name}_sha256\t{digest(path)}\n")
        output.write("hardware_policy\tcached_suite_files_only_no_x87_execution\n")
        output.write("ledger_policy\tG_ROUND84=0\n")
        output.write(f"predecessor_misses\t{len(predecessor)}\n")
        output.write(f"candidate_misses\t{len(candidate)}\n")
        output.write(f"fixes\t{len(fixes)}\n")
        output.write(f"regressions\t{len(regressions)}\n")
        output.write(f"survivors\t{len(survivors)}\n")
        output.write("\n[fixes]\n")
        for row in fixes:
            output.write(row + "\n")
        output.write("\n[regressions]\n")
        for row in regressions:
            output.write(row + "\n")
        output.write("\n[survivors]\n")
        for row in survivors:
            output.write(row + "\n")

    print(
        f"wrote {args.report}: predecessor={len(predecessor)} "
        f"candidate={len(candidate)} fixes={len(fixes)} "
        f"regressions={len(regressions)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
