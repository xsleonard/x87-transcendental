#!/usr/bin/env python3
"""Solve H1505 with an exact prime-implicate opcode-language encoding.

H1505 excludes 3,637 complete forbidden opcode words per recovered row.  The
same 459-word public opcode language has a much smaller prime CNF.  This script
derives that CNF exhaustively over all 4,096 twelve-bit words, proves its truth
table equivalent to the recognized-opcode predicate, substitutes it into the
otherwise unchanged injective fixed-polarity mapper problem, and invokes one
named Bitwuzla SAT backend.  It executes no x87 instruction.
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


SIGNATURES = ("611", "612")
LOGICAL_BITS = 12
DWORDS = 8
BITS_PER_DWORD = 31
POLARITIES = 2
DATA_GROUPS = 19
EXPECTED_H1467_SHA256 = (
    "63d32e546726b602e0c55b87a6e89792dab2d9ad3ce8938dec123b023cb4fa74"
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def physical_channels() -> tuple[tuple[int, int], ...]:
    return tuple(
        (dword, bit)
        for dword in range(DWORDS)
        for bit in range(BITS_PER_DWORD)
    )


def load_rows(report: dict[str, object]) -> dict[str, tuple[tuple[int, ...], ...]]:
    result = {}
    for signature in SIGNATURES:
        groups = report["patches"][signature]["recovery"]["decrypted_body"][
            "physical_groups"
        ]
        if len(groups) != DATA_GROUPS:
            raise RuntimeError(f"0x{signature}: physical-group count changed")
        rows = tuple(
            tuple(int(word, 16) for word in group["physical_dwords"])
            for group in groups
        )
        if any((word >> 31) & 1 for row in rows[:18] for word in row):
            raise RuntimeError(f"0x{signature}: bit-31 exclusion wall changed")
        result[signature] = rows
    return result


def recognized_values() -> tuple[int, ...]:
    return tuple(
        value
        for value in range(1 << LOGICAL_BITS)
        if later.recognized_opcode(value) is not None
    )


def prime_forbidden_cubes(
    allowed: tuple[int, ...],
) -> tuple[tuple[int, int], ...]:
    """Return every minimal partial assignment with no allowed completion."""

    projections = tuple(
        {value & mask for value in allowed}
        for mask in range(1 << LOGICAL_BITS)
    )
    primes = []
    for mask in range(1, 1 << LOGICAL_BITS):
        value = mask
        while True:
            if value not in projections[mask]:
                bits = tuple(1 << bit for bit in range(LOGICAL_BITS) if mask >> bit & 1)
                if all(
                    (value & ~bit) in projections[mask & ~bit]
                    for bit in bits
                ):
                    primes.append((mask, value))
            if value == 0:
                break
            value = (value - 1) & mask
    return tuple(primes)


def validate_prime_language(
    allowed: tuple[int, ...], primes: tuple[tuple[int, int], ...]
) -> None:
    allowed_set = set(allowed)
    for value in range(1 << LOGICAL_BITS):
        accepted = all((value & mask) != bits for mask, bits in primes)
        if accepted != (value in allowed_set):
            raise RuntimeError(f"prime CNF truth-table mismatch at {value:03x}")


class Cnf:
    def __init__(self) -> None:
        self.variable_count = 0
        self.clauses: list[tuple[int, ...]] = []

    def variable(self) -> int:
        self.variable_count += 1
        return self.variable_count

    def add(self, *literals: int) -> None:
        if not literals:
            raise RuntimeError("unexpected empty clause")
        self.clauses.append(tuple(literals))

    def exactly_one_sequential(self, variables: tuple[int, ...]) -> None:
        self.add(*variables)
        prefix = tuple(self.variable() for _ in range(len(variables) - 1))
        self.add(-variables[0], prefix[0])
        for index in range(1, len(variables) - 1):
            self.add(-variables[index], prefix[index])
            self.add(-prefix[index - 1], prefix[index])
            self.add(-variables[index], -prefix[index - 1])
        self.add(-variables[-1], -prefix[-1])


def build_cnf(
    rows_by_signature: dict[str, tuple[tuple[int, ...], ...]],
    primes: tuple[tuple[int, int], ...],
) -> tuple[Cnf, dict[str, object]]:
    channels = physical_channels()
    rows = tuple(
        (signature, group, row)
        for signature in SIGNATURES
        for group, row in enumerate(rows_by_signature[signature])
    )
    patterns = tuple(
        tuple((row[dword] >> bit) & 1 for _, _, row in rows)
        for dword, bit in channels
    )

    cnf = Cnf()
    option_count = len(channels) * POLARITIES
    selections = tuple(
        tuple(cnf.variable() for _ in range(option_count))
        for _ in range(LOGICAL_BITS)
    )
    for choices in selections:
        cnf.exactly_one_sequential(choices)

    for channel in range(len(channels)):
        for first_bit in range(LOGICAL_BITS):
            for second_bit in range(first_bit + 1, LOGICAL_BITS):
                for first_polarity in range(POLARITIES):
                    for second_polarity in range(POLARITIES):
                        cnf.add(
                            -selections[first_bit][
                                channel * POLARITIES + first_polarity
                            ],
                            -selections[second_bit][
                                channel * POLARITIES + second_polarity
                            ],
                        )

    decoded_bits = tuple(
        tuple(cnf.variable() for _ in range(LOGICAL_BITS)) for _ in rows
    )
    for row_index in range(len(rows)):
        for logical_bit in range(LOGICAL_BITS):
            decoded = decoded_bits[row_index][logical_bit]
            for channel, pattern in enumerate(patterns):
                physical = pattern[row_index]
                for polarity in range(POLARITIES):
                    selected = selections[logical_bit][
                        channel * POLARITIES + polarity
                    ]
                    value = physical ^ polarity
                    cnf.add(-selected, decoded if value else -decoded)

    for row_bits in decoded_bits:
        for mask, value in primes:
            clause = []
            for bit in range(LOGICAL_BITS):
                if not (mask >> bit) & 1:
                    continue
                clause.append(-row_bits[bit] if (value >> bit) & 1 else row_bits[bit])
            cnf.add(*clause)

    metadata = {
        "channels": [
            {"index": index, "dword": dword, "bit": bit}
            for index, (dword, bit) in enumerate(channels)
        ],
        "selections": [list(choices) for choices in selections],
        "rows": [
            {"signature": signature, "group": group}
            for signature, group, _ in rows
        ],
    }
    return cnf, metadata


def write_dimacs(cnf: Cnf, path: Path) -> None:
    with path.open("x") as target:
        target.write(f"p cnf {cnf.variable_count} {len(cnf.clauses)}\n")
        for clause in cnf.clauses:
            target.write(" ".join(map(str, clause)) + " 0\n")


def write_smt2(cnf: Cnf, path: Path) -> None:
    with path.open("x") as target:
        # Bitwuzla accepts Boolean-only formulas under QF_BV, but does not
        # advertise the SMT-LIB QF_SAT logic name.
        target.write("(set-logic QF_BV)\n")
        for variable in range(1, cnf.variable_count + 1):
            target.write(f"(declare-fun v{variable} () Bool)\n")
        for clause in cnf.clauses:
            expressions = [
                f"v{literal}" if literal > 0 else f"(not v{-literal})"
                for literal in clause
            ]
            if len(expressions) == 1:
                target.write(f"(assert {expressions[0]})\n")
            else:
                target.write(f"(assert (or {' '.join(expressions)}))\n")
        target.write("(check-sat)\n")


def parse_status(text: str) -> str:
    for line in text.splitlines():
        if line.strip() in ("sat", "unsat", "unknown"):
            return line.strip().upper()
    raise RuntimeError(f"missing solver status: {text[:500]!r}")


def decode_and_validate(
    solver_text: str,
    metadata: dict[str, object],
    rows_by_signature: dict[str, tuple[tuple[int, ...], ...]],
) -> dict[str, object]:
    values = {
        int(variable): state == "true"
        for variable, state in re.findall(
            r"\(define-fun v(\d+) \(\) Bool\s+(true|false)\)", solver_text
        )
    }
    mapping = []
    used = set()
    channels = metadata["channels"]
    for logical_bit, choices in enumerate(metadata["selections"]):
        selected = [index for index, variable in enumerate(choices) if values.get(variable)]
        if len(selected) != 1:
            raise RuntimeError(f"logical bit {logical_bit}: model selection count changed")
        option = selected[0]
        channel = option // POLARITIES
        if channel in used:
            raise RuntimeError("model reused a physical channel")
        used.add(channel)
        mapping.append({
            "logical_opcode_bit": logical_bit,
            **channels[channel],
            "inverted": bool(option & 1),
        })

    decoded = {}
    for signature in SIGNATURES:
        opcodes = []
        for row in rows_by_signature[signature]:
            opcode = sum(
                (
                    ((row[item["dword"]] >> item["bit"]) & 1)
                    ^ int(item["inverted"])
                ) << item["logical_opcode_bit"]
                for item in mapping
            )
            if later.recognized_opcode(opcode) is None:
                raise RuntimeError(f"solver model decoded unknown opcode {opcode:03x}")
            opcodes.append(f"{opcode:03X}")
        decoded[signature] = opcodes
    return {"mapping": mapping, "decoded_opcodes": decoded}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1467", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("cnf", type=Path)
    parser.add_argument("smt2", type=Path)
    parser.add_argument("solver_output", type=Path)
    parser.add_argument("--bitwuzla", type=Path, required=True)
    parser.add_argument(
        "--backend", choices=("cadical", "cms", "gimsatul", "kissat"),
        default="kissat",
    )
    parser.add_argument("--timeout-ms", type=int, default=300_000)
    arguments = parser.parse_args()
    for path in (arguments.output, arguments.cnf, arguments.smt2, arguments.solver_output):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")
    if digest(arguments.h1467) != EXPECTED_H1467_SHA256:
        raise RuntimeError("H1467 source report hash changed")

    source = json.loads(arguments.h1467.read_text())
    rows = load_rows(source)
    allowed = recognized_values()
    primes = prime_forbidden_cubes(allowed)
    validate_prime_language(allowed, primes)
    if len(allowed) != 459 or len(primes) != 533:
        raise RuntimeError("public opcode-language census changed")
    cnf, metadata = build_cnf(rows, primes)
    if cnf.variable_count != 12_348 or len(cnf.clauses) != 329_722:
        raise RuntimeError(
            f"prime CNF census changed: {cnf.variable_count}/{len(cnf.clauses)}"
        )
    arguments.cnf.parent.mkdir(parents=True, exist_ok=True)
    write_dimacs(cnf, arguments.cnf)
    write_smt2(cnf, arguments.smt2)

    version = subprocess.run(
        [str(arguments.bitwuzla), "--version"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    started = time.monotonic()
    process = subprocess.run(
        [
            str(arguments.bitwuzla),
            "--sat-solver", arguments.backend,
            "--time-limit", str(arguments.timeout_ms),
            "--produce-models", "--print-model",
            str(arguments.smt2),
        ],
        check=False, capture_output=True, text=True,
        timeout=arguments.timeout_ms / 1000 + 60,
    )
    elapsed = time.monotonic() - started
    arguments.solver_output.write_text(process.stdout)
    status = parse_status(process.stdout)
    if process.returncode not in (0, 10, 20):
        raise RuntimeError(
            f"Bitwuzla exited {process.returncode}: {process.stderr[:1000]}"
        )

    widths: dict[int, int] = {}
    for mask, _ in primes:
        widths[mask.bit_count()] = widths.get(mask.bit_count(), 0) + 1
    report: dict[str, object] = {
        "query": "h1505_fixed_polarity_prime_implicate_cnf",
        "status": status,
        "opcode_language": {
            "recognized_values": len(allowed),
            "unrecognized_values": (1 << LOGICAL_BITS) - len(allowed),
            "prime_implicates": len(primes),
            "prime_width_histogram": {str(k): widths[k] for k in sorted(widths)},
            "truth_table_equivalence_checked": 1 << LOGICAL_BITS,
        },
        "cnf": {
            "variables": cnf.variable_count,
            "clauses": len(cnf.clauses),
            "h1505_original_clauses": 447_674,
            "clauses_removed": 447_674 - len(cnf.clauses),
            "dimacs_sha256": digest(arguments.cnf),
            "smt2_sha256": digest(arguments.smt2),
        },
        "solver": {
            "name": "Bitwuzla",
            "version": version,
            "sat_backend": arguments.backend,
            "timeout_ms": arguments.timeout_ms,
            "elapsed_seconds": elapsed,
            "returncode": process.returncode,
            "stderr": process.stderr,
            "output_sha256": digest(arguments.solver_output),
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
        report["model"] = decode_and_validate(process.stdout, metadata, rows)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    arguments.output.write_text(text)
    print(json.dumps({
        "output": str(arguments.output),
        "report_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "status": status,
        "clauses": len(cnf.clauses),
        "solver_seconds": elapsed,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
