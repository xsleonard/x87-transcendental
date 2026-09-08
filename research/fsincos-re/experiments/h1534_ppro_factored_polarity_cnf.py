#!/usr/bin/env python3
"""Factor H1532's channel/polarity options and solve the exact mapper CNF.

Each logical opcode bit selects one of 248 physical channels and has one
separate fixed polarity bit.  This is bijective with H1505/H1532's 496 signed
options, but reduces the all-different encoding and exposes the shared polarity
across all 38 rows directly.  Recognition uses H1532's truth-table-validated
prime implicates.  Official Kissat is invoked once; UNKNOWN stays UNKNOWN.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path

import h1490_ppro_core_permutation_transfer as later
import h1532_ppro_prime_implicate_cnf as h1532


EXPECTED_H1467_SHA256 = h1532.EXPECTED_H1467_SHA256
EXPECTED_SOURCE_ARCHIVE_SHA256 = (
    "bfe93eaa6323b48011e4b1fcf74b3f2e20f9de544767e728009e5b2018296193"
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_cnf(rows_by_signature, primes):
    channels = h1532.physical_channels()
    rows = tuple(
        (signature, group, row)
        for signature in h1532.SIGNATURES
        for group, row in enumerate(rows_by_signature[signature])
    )
    patterns = tuple(
        tuple((row[dword] >> bit) & 1 for _, _, row in rows)
        for dword, bit in channels
    )

    cnf = h1532.Cnf()
    selections = tuple(
        tuple(cnf.variable() for _ in channels)
        for _ in range(h1532.LOGICAL_BITS)
    )
    for choices in selections:
        cnf.exactly_one_sequential(choices)

    polarities = tuple(cnf.variable() for _ in range(h1532.LOGICAL_BITS))
    decoded_bits = tuple(
        tuple(cnf.variable() for _ in range(h1532.LOGICAL_BITS))
        for _ in rows
    )

    for channel in range(len(channels)):
        for first_bit in range(h1532.LOGICAL_BITS):
            for second_bit in range(first_bit + 1, h1532.LOGICAL_BITS):
                cnf.add(
                    -selections[first_bit][channel],
                    -selections[second_bit][channel],
                )

    # selected -> decoded == physical XOR polarity.  Two ternary clauses are
    # the exact equivalence under the selected-channel guard.
    for row_index in range(len(rows)):
        for logical_bit in range(h1532.LOGICAL_BITS):
            decoded = decoded_bits[row_index][logical_bit]
            polarity = polarities[logical_bit]
            for channel, pattern in enumerate(patterns):
                selected = selections[logical_bit][channel]
                if pattern[row_index] == 0:
                    cnf.add(-selected, polarity, -decoded)
                    cnf.add(-selected, -polarity, decoded)
                else:
                    cnf.add(-selected, polarity, decoded)
                    cnf.add(-selected, -polarity, -decoded)

    for row_bits in decoded_bits:
        for mask, value in primes:
            cnf.add(*tuple(
                -row_bits[bit] if (value >> bit) & 1 else row_bits[bit]
                for bit in range(h1532.LOGICAL_BITS)
                if (mask >> bit) & 1
            ))
    metadata = {
        "channels": channels,
        "selections": selections,
        "polarities": polarities,
    }
    return cnf, metadata


def parse_solver(text: str) -> tuple[str, set[int]]:
    status = None
    true_variables = set()
    for line in text.splitlines():
        if line == "s SATISFIABLE":
            status = "SAT"
        elif line == "s UNSATISFIABLE":
            status = "UNSAT"
        elif line == "s UNKNOWN":
            status = "UNKNOWN"
        elif line.startswith("v "):
            true_variables.update(
                literal for literal in map(int, line[2:].split()) if literal > 0
            )
    if status is None:
        raise RuntimeError(f"missing Kissat status: {text[-1000:]!r}")
    return status, true_variables


def decode_and_validate(true_variables, metadata, rows_by_signature):
    mapping = []
    used = set()
    for logical_bit, choices in enumerate(metadata["selections"]):
        selected = [
            channel for channel, variable in enumerate(choices)
            if variable in true_variables
        ]
        if len(selected) != 1:
            raise RuntimeError(f"logical bit {logical_bit}: bad selection count")
        channel = selected[0]
        if channel in used:
            raise RuntimeError("factored model reused a physical channel")
        used.add(channel)
        dword, physical_bit = metadata["channels"][channel]
        mapping.append({
            "logical_opcode_bit": logical_bit,
            "physical_channel_index": channel,
            "dword": dword,
            "bit": physical_bit,
            "inverted": metadata["polarities"][logical_bit] in true_variables,
        })

    decoded = {}
    for signature, rows in rows_by_signature.items():
        values = []
        for row in rows:
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
    parser.add_argument("h1467", type=Path)
    parser.add_argument("cnf", type=Path)
    parser.add_argument("solver_output", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    arguments = parser.parse_args()
    for path in (arguments.cnf, arguments.solver_output, arguments.output):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")
    if digest(arguments.h1467) != EXPECTED_H1467_SHA256:
        raise RuntimeError("H1467 report hash changed")
    if digest(arguments.source_archive) != EXPECTED_SOURCE_ARCHIVE_SHA256:
        raise RuntimeError("official Kissat source archive hash changed")

    source = json.loads(arguments.h1467.read_text())
    rows = h1532.load_rows(source)
    allowed = h1532.recognized_values()
    primes = h1532.prime_forbidden_cubes(allowed)
    h1532.validate_prime_language(allowed, primes)
    cnf, metadata = build_cnf(rows, primes)
    if cnf.variable_count != 6_408 or len(cnf.clauses) != 271_690:
        raise RuntimeError(
            f"factored CNF census changed: {cnf.variable_count}/{len(cnf.clauses)}"
        )
    arguments.cnf.parent.mkdir(parents=True, exist_ok=True)
    h1532.write_dimacs(cnf, arguments.cnf)

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
        "query": "h1505_exact_factored_channel_polarity_prime_cnf",
        "status": status,
        "equivalence": {
            "signed_options_original": 496,
            "factored_channel_options": 248,
            "fixed_polarity_bits": 12,
            "bijection": "signed option 2*c+p maps exactly to channel c and polarity p",
            "recognized_truth_table_checked": 4096,
            "all_selected_channels_distinct": True,
        },
        "cnf": {
            "variables": cnf.variable_count,
            "clauses": len(cnf.clauses),
            "h1532_variables": 12_348,
            "h1532_clauses": 329_722,
            "sha256": digest(arguments.cnf),
        },
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
        report["model"] = decode_and_validate(true_variables, metadata, rows)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    arguments.output.write_text(text)
    print(json.dumps({
        "output": str(arguments.output),
        "report_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "status": status,
        "variables": cnf.variable_count,
        "clauses": len(cnf.clauses),
        "solver_seconds": elapsed,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
