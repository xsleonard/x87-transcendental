#!/usr/bin/env python3
"""Run official Kissat on H1532's exact prime-implicate mapper CNF.

This is a genuinely different SAT implementation from the CaDiCaL backend
used by H1526/H1532.  A SAT result is decoded and independently checked against
the recovered physical rows and public recognized-opcode predicate.  UNKNOWN
is preserved literally.  No hardware or capture label is used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

import h1490_ppro_core_permutation_transfer as later


LOGICAL_BITS = 12
POLARITIES = 2
OPTIONS_PER_BIT = 496
EXPECTED_CNF_SHA256 = (
    "5cfd3b8f5b10a9358d80e9faf47f0371ae6275a90c1a22f097148e33ad020af8"
)
EXPECTED_H1467_SHA256 = (
    "63d32e546726b602e0c55b87a6e89792dab2d9ad3ce8938dec123b023cb4fa74"
)
EXPECTED_SOURCE_ARCHIVE_SHA256 = (
    "bfe93eaa6323b48011e4b1fcf74b3f2e20f9de544767e728009e5b2018296193"
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_rows(report: dict[str, object]):
    result = {}
    for signature in ("611", "612"):
        groups = report["patches"][signature]["recovery"]["decrypted_body"][
            "physical_groups"
        ]
        result[signature] = tuple(
            tuple(int(word, 16) for word in group["physical_dwords"])
            for group in groups
        )
    return result


def parse_solver(text: str) -> tuple[str, set[int]]:
    status = None
    true_variables: set[int] = set()
    for line in text.splitlines():
        if line == "s SATISFIABLE":
            status = "SAT"
        elif line == "s UNSATISFIABLE":
            status = "UNSAT"
        elif line == "s UNKNOWN":
            status = "UNKNOWN"
        elif line.startswith("v "):
            true_variables.update(
                literal for literal in map(int, line[2:].split())
                if literal > 0
            )
    if status is None:
        raise RuntimeError(f"missing Kissat status: {text[-1000:]!r}")
    return status, true_variables


def decode_and_validate(true_variables: set[int], rows) -> dict[str, object]:
    channels = tuple((dword, bit) for dword in range(8) for bit in range(31))
    mapping = []
    used = set()
    for logical_bit in range(LOGICAL_BITS):
        first = 1 + logical_bit * OPTIONS_PER_BIT
        selected = [
            option for option in range(OPTIONS_PER_BIT)
            if first + option in true_variables
        ]
        if len(selected) != 1:
            raise RuntimeError(
                f"logical bit {logical_bit}: {len(selected)} selected options"
            )
        option = selected[0]
        channel = option // POLARITIES
        if channel in used:
            raise RuntimeError("Kissat model reused a physical channel")
        used.add(channel)
        dword, physical_bit = channels[channel]
        mapping.append({
            "logical_opcode_bit": logical_bit,
            "physical_channel_index": channel,
            "dword": dword,
            "bit": physical_bit,
            "inverted": bool(option & 1),
        })

    decoded = {}
    for signature, signature_rows in rows.items():
        values = []
        for row in signature_rows:
            opcode = sum(
                (
                    ((row[item["dword"]] >> item["bit"]) & 1)
                    ^ int(item["inverted"])
                ) << item["logical_opcode_bit"]
                for item in mapping
            )
            if later.recognized_opcode(opcode) is None:
                raise RuntimeError(f"model decoded unrecognized opcode {opcode:03x}")
            values.append(f"{opcode:03X}")
        decoded[signature] = values
    return {"mapping": mapping, "decoded_opcodes": decoded}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("kissat", type=Path)
    parser.add_argument("source_archive", type=Path)
    parser.add_argument("cnf", type=Path)
    parser.add_argument("h1467", type=Path)
    parser.add_argument("solver_output", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    arguments = parser.parse_args()
    for path in (arguments.solver_output, arguments.output):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")
    if digest(arguments.cnf) != EXPECTED_CNF_SHA256:
        raise RuntimeError("H1532 prime CNF hash changed")
    if digest(arguments.h1467) != EXPECTED_H1467_SHA256:
        raise RuntimeError("H1467 report hash changed")
    if digest(arguments.source_archive) != EXPECTED_SOURCE_ARCHIVE_SHA256:
        raise RuntimeError("official Kissat source archive hash changed")

    version = subprocess.run(
        [str(arguments.kissat), "--version"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if version != "4.0.4":
        raise RuntimeError(f"unexpected Kissat version {version!r}")

    started = time.monotonic()
    process = subprocess.run(
        [
            str(arguments.kissat), "--quiet",
            f"--time={arguments.timeout_seconds}", str(arguments.cnf),
        ],
        check=False, capture_output=True, text=True,
        timeout=arguments.timeout_seconds + 60,
    )
    elapsed = time.monotonic() - started
    arguments.solver_output.parent.mkdir(parents=True, exist_ok=True)
    arguments.solver_output.write_text(process.stdout)
    status, true_variables = parse_solver(process.stdout)
    expected_returncode = {"SAT": 10, "UNSAT": 20, "UNKNOWN": 0}[status]
    if process.returncode != expected_returncode:
        raise RuntimeError(
            f"Kissat {status} exit {process.returncode}: {process.stderr[:1000]}"
        )
    if status != "SAT" and true_variables:
        raise RuntimeError(f"unexpected model literals for {status}")

    report: dict[str, object] = {
        "query": "h1532_prime_cnf_official_kissat_crosscheck",
        "status": status,
        "solver": {
            "name": "Kissat",
            "version": version,
            "timeout_seconds": arguments.timeout_seconds,
            "elapsed_seconds": elapsed,
            "binary_sha256": digest(arguments.kissat),
            "source_archive_sha256": digest(arguments.source_archive),
            "output_sha256": digest(arguments.solver_output),
            "returncode": process.returncode,
            "stderr": process.stderr,
        },
        "cnf": {
            "variables": 12_348,
            "clauses": 329_722,
            "sha256": digest(arguments.cnf),
        },
        "dependencies": {"h1467_report_sha256": digest(arguments.h1467)},
        "claim_boundary": (
            "SAT or UNSAT decides only H1505's injective fixed-polarity "
            "twelve-channel mapping under the current 459-value public P6 "
            "recognized-opcode condition."
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
    if status == "SAT":
        source = json.loads(arguments.h1467.read_text())
        report["model"] = decode_and_validate(true_variables, load_rows(source))
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    arguments.output.write_text(text)
    print(json.dumps({
        "output": str(arguments.output),
        "report_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "status": status,
        "solver_seconds": elapsed,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
