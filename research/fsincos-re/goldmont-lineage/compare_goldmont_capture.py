#!/usr/bin/env python3
"""Compare one Goldmont capture directory with the frozen P6/SKL vectors."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, Dict, List, Tuple


EXPECTED_COLUMNS = [
    "case_id",
    "instruction",
    "mode",
    "input_se",
    "input_sig",
    "result0_se",
    "result0_sig",
    "result1_se",
    "result1_sig",
    "skylake_sw",
    "provenance",
]


def parse_args() -> argparse.Namespace:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture_directory", type=Path)
    parser.add_argument(
        "--expected", type=Path, default=here / "p6-expected.tsv"
    )
    parser.add_argument(
        "--allow-non-goldmont",
        action="store_true",
        help="skip the default family/model/stepping guard (for tool tests only)",
    )
    return parser.parse_args()


def verify_goldmont_cpu(path: Path) -> None:
    text = path.read_text()
    fields = {}
    for name in ("vendor_id", "cpu family", "model", "stepping", "microcode"):
        match = re.search(rf"^{re.escape(name)}\s*:\s*(\S+)", text, re.MULTILINE)
        if not match:
            raise ValueError(f"{path}: missing {name}")
        fields[name] = match.group(1)
    try:
        family = int(fields["cpu family"], 0)
        model = int(fields["model"], 0)
        stepping = int(fields["stepping"], 0)
    except ValueError as error:
        raise ValueError(f"{path}: malformed CPU identity: {fields}") from error
    if (
        fields["vendor_id"] != "GenuineIntel"
        or family != 6
        or model != 0x5C
        or stepping not in (9, 10)
    ):
        raise ValueError(
            f"{path}: not Goldmont CPUID 506C9/506CA: "
            f"vendor={fields['vendor_id']} family={family} "
            f"model={model} stepping={stepping}"
        )
    print(
        f"CPU Goldmont family {family} model {model} stepping {stepping}; "
        f"microcode {fields['microcode']}"
    )


def load_expected(path: Path) -> DefaultDict[Tuple[str, str], List[Dict[str, str]]]:
    groups: DefaultDict[Tuple[str, str], List[Dict[str, str]]] = defaultdict(list)
    with path.open(newline="") as source:
        reader = csv.DictReader(source, delimiter="\t")
        if reader.fieldnames != EXPECTED_COLUMNS:
            raise ValueError(f"{path}: unexpected TSV columns: {reader.fieldnames}")
        for row in reader:
            groups[(row["instruction"], row["mode"])].append(row)
    if len(groups) != 16 or any(len(rows) != 6 for rows in groups.values()):
        raise ValueError(f"{path}: expected 16 groups of six rows")
    return groups


def parse_actual(line: str) -> Tuple[List[str], str]:
    fields = line.split()
    if not fields or fields[0] != "OK":
        raise ValueError(f"unexpected capture row: {line}")
    if len(fields) < 5 or fields[-2] != "SW":
        raise ValueError(f"capture row has no status: {line}")
    return fields[1:-2], fields[-1]


def main() -> int:
    args = parse_args()
    if not args.allow_non_goldmont:
        verify_goldmont_cpu(args.capture_directory / "cpu_info.txt")
    expected = load_expected(args.expected)
    total_result_matches = 0
    total_status_matches = 0
    total_status_compared = 0
    total_rows = 0

    for instruction in ("fsincos", "fsin", "fcos", "fptan"):
        for mode in ("rn", "rd", "ru", "rz"):
            rows = expected[(instruction, mode)]
            capture_path = args.capture_directory / f"{instruction}_{mode}.txt"
            actual_lines = capture_path.read_text().splitlines()
            if len(actual_lines) != len(rows):
                raise ValueError(
                    f"{capture_path}: expected {len(rows)} rows, "
                    f"found {len(actual_lines)}"
                )

            result_matches = 0
            status_matches = 0
            status_compared = 0
            for row, line in zip(rows, actual_lines):
                actual_values, actual_status = parse_actual(line)
                expected_values = [row["result0_se"], row["result0_sig"]]
                if row["result1_se"] != "-":
                    expected_values.extend([row["result1_se"], row["result1_sig"]])
                if actual_values == expected_values:
                    result_matches += 1
                else:
                    print(
                        f"RESULT DIFF {row['case_id']} {instruction} {mode} "
                        f"input={row['input_se']}:{row['input_sig']} "
                        f"p6={' '.join(expected_values)} "
                        f"goldmont={' '.join(actual_values)}"
                    )
                if row["skylake_sw"] != "-":
                    status_compared += 1
                    if actual_status == row["skylake_sw"]:
                        status_matches += 1
                    else:
                        print(
                            f"STATUS DIFF {row['case_id']} {instruction} {mode} "
                            f"input={row['input_se']}:{row['input_sig']} "
                            f"p6={row['skylake_sw']} goldmont={actual_status}"
                        )

            total_rows += len(rows)
            total_result_matches += result_matches
            total_status_matches += status_matches
            total_status_compared += status_compared
            status_summary = (
                f", status {status_matches}/{status_compared}"
                if status_compared else ", status reference unavailable"
            )
            print(
                f"{instruction:7} {mode}: results {result_matches}/{len(rows)}"
                f"{status_summary}"
            )

    print(
        f"TOTAL results {total_result_matches}/{total_rows}; "
        f"status {total_status_matches}/{total_status_compared}"
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
