#!/usr/bin/env python3
"""Solve H1504's fixed-polarity opcode mapping as an exact CNF problem.

H1504's generic QF_BV encoding left the polarity-enabled query UNKNOWN.  This
script removes the bit-vector multiplexers entirely.  Each logical opcode bit
chooses exactly one of 496 literals (248 physical channels, either polarity),
the twelve choices use distinct physical channels, and every one of the 38
decoded opcodes must belong to the same public P6 recognized set used by
H1504.  The generated DIMACS instance is equisatisfiable with that bounded
query and is intended for a Boolean SAT engine.

No hardware, capture label, private ledger, emulator path, or paper is used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import h1490_ppro_core_permutation_transfer as later
import h1504_ppro_opcode_permutation_smt as h1504


LOGICAL_BITS = 12
POLARITIES = 2


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Cnf:
    def __init__(self) -> None:
        self.variable_count = 0
        self.clauses: list[tuple[int, ...]] = []

    def variable(self) -> int:
        self.variable_count += 1
        return self.variable_count

    def add(self, *literals: int) -> None:
        if not literals:
            raise ValueError("empty clauses are not expected in this encoding")
        self.clauses.append(tuple(literals))

    def exactly_one_sequential(self, variables: tuple[int, ...]) -> None:
        """Sinz sequential at-most-one plus one at-least-one clause."""

        if len(variables) < 2:
            raise ValueError("sequential encoding requires at least two variables")
        self.add(*variables)
        prefix = tuple(self.variable() for _ in range(len(variables) - 1))
        self.add(-variables[0], prefix[0])
        for index in range(1, len(variables) - 1):
            self.add(-variables[index], prefix[index])
            self.add(-prefix[index - 1], prefix[index])
            self.add(-variables[index], -prefix[index - 1])
        self.add(-variables[-1], -prefix[-1])


def recognized_values() -> tuple[int, ...]:
    return tuple(
        value
        for value in range(1 << LOGICAL_BITS)
        if later.recognized_opcode(value) is not None
    )


def build_cnf(
    rows_by_signature: dict[str, tuple[tuple[int, ...], ...]],
    distinct_channels: bool = True,
) -> tuple[Cnf, dict[str, object]]:
    channels = h1504.physical_channels()
    rows = tuple(
        (signature, group, row)
        for signature in h1504.SIGNATURES
        for group, row in enumerate(rows_by_signature[signature])
    )
    patterns = tuple(
        tuple((row[dword] >> bit) & 1 for _, _, row in rows)
        for dword, bit in channels
    )
    allowed = recognized_values()
    allowed_set = set(allowed)
    forbidden = tuple(
        value for value in range(1 << LOGICAL_BITS) if value not in allowed_set
    )

    cnf = Cnf()
    option_count = len(channels) * POLARITIES
    selections = tuple(
        tuple(cnf.variable() for _ in range(option_count))
        for _ in range(LOGICAL_BITS)
    )
    for bit_selections in selections:
        cnf.exactly_one_sequential(bit_selections)

    # One physical channel cannot feed two logical opcode positions, even if
    # the two positions request opposite polarities.
    if distinct_channels:
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

    # Exclude every unrecognized 12-bit word on every decoded row.  Each
    # clause is the disjunction of bit positions that differ from that word.
    for row_bits in decoded_bits:
        for value in forbidden:
            cnf.add(
                *tuple(
                    -row_bits[bit] if ((value >> bit) & 1) else row_bits[bit]
                    for bit in range(LOGICAL_BITS)
                )
            )

    metadata: dict[str, object] = {
        "rows": [
            {"signature": signature, "group": group}
            for signature, group, _ in rows
        ],
        "channels": [
            {"index": index, "dword": dword, "bit": bit}
            for index, (dword, bit) in enumerate(channels)
        ],
        "selections": [list(values) for values in selections],
        "decoded_bits": [list(values) for values in decoded_bits],
        "recognized_values": list(allowed),
        "forbidden_value_count": len(forbidden),
        "distinct_channels": distinct_channels,
    }
    return cnf, metadata


def write_dimacs(cnf: Cnf, path: Path) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path}")
    with path.open("w") as stream:
        stream.write(f"p cnf {cnf.variable_count} {len(cnf.clauses)}\n")
        for clause in cnf.clauses:
            stream.write(" ".join(str(value) for value in clause))
            stream.write(" 0\n")


def parse_z3_dimacs_output(text: str) -> tuple[str, set[int]]:
    status = ""
    true_variables: set[int] = set()
    for line in text.splitlines():
        if line == "s SATISFIABLE":
            status = "SAT"
        elif line == "s UNSATISFIABLE":
            status = "UNSAT"
        elif line == "s UNKNOWN":
            status = "UNKNOWN"
        elif line == "timeout":
            status = "UNKNOWN"
        elif line.startswith("v "):
            true_variables.update(
                value
                for value in (int(token) for token in line[2:].split())
                if value > 0
            )
    if status not in {"SAT", "UNSAT", "UNKNOWN"}:
        raise RuntimeError(f"unrecognized Z3 DIMACS output: {text[:200]!r}")
    return status, true_variables


def decode_model(
    metadata: dict[str, object], true_variables: set[int], source: dict[str, object]
) -> dict[str, object]:
    channels = metadata["channels"]
    mapping = []
    selected_channels = set()
    for logical_bit, options in enumerate(metadata["selections"]):
        chosen = [index for index, variable in enumerate(options) if variable in true_variables]
        if len(chosen) != 1:
            raise RuntimeError(
                f"logical bit {logical_bit} has {len(chosen)} selected options"
            )
        option = chosen[0]
        channel = option // POLARITIES
        polarity = option % POLARITIES
        if metadata["distinct_channels"] and channel in selected_channels:
            raise RuntimeError(f"physical channel {channel} was selected twice")
        selected_channels.add(channel)
        mapping.append(
            {
                "logical_opcode_bit": logical_bit,
                **channels[channel],
                "inverted": bool(polarity),
            }
        )

    rows_by_signature = h1504.load_rows(source)
    decoded = {}
    for signature in h1504.SIGNATURES:
        values = []
        for row in rows_by_signature[signature]:
            value = sum(
                (
                    ((row[item["dword"]] >> item["bit"]) & 1)
                    ^ int(item["inverted"])
                )
                << item["logical_opcode_bit"]
                for item in mapping
            )
            if later.recognized_opcode(value) is None:
                raise RuntimeError(f"model decodes unrecognized opcode {value:03X}")
            values.append(f"{value:03X}")
        decoded[signature] = values
    return {
        "mapping": mapping,
        "decoded_opcodes": decoded,
        "distinct_physical_channels": len(selected_channels),
        "reused_channel_count": len(mapping) - len(selected_channels),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1467", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("cnf", type=Path)
    parser.add_argument("solver_output", type=Path)
    parser.add_argument("--z3", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument(
        "--summarize-existing",
        action="store_true",
        help="read an existing CNF/raw solver result without executing Z3 again",
    )
    parser.add_argument(
        "--relax-distinct-channels",
        action="store_true",
        help="diagnostic relaxation: allow logical bits to reuse a channel",
    )
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")
    if arguments.summarize_existing:
        for path in (arguments.cnf, arguments.solver_output):
            if not path.exists():
                raise SystemExit(f"missing existing artifact {path}")
    else:
        for path in (arguments.cnf, arguments.solver_output):
            if path.exists():
                raise SystemExit(f"refusing to overwrite {path}")

    source = json.loads(arguments.h1467.read_text())
    rows = h1504.load_rows(source)
    cnf, metadata = build_cnf(
        rows, distinct_channels=not arguments.relax_distinct_channels
    )
    if arguments.summarize_existing:
        header = arguments.cnf.open().readline().strip()
        expected_header = f"p cnf {cnf.variable_count} {len(cnf.clauses)}"
        if header != expected_header:
            raise RuntimeError(
                f"existing CNF header {header!r} != expected {expected_header!r}"
            )
    else:
        write_dimacs(cnf, arguments.cnf)

    version = subprocess.run(
        [str(arguments.z3), "-version"], check=True, capture_output=True, text=True
    ).stdout.strip()
    if arguments.summarize_existing:
        solver_stdout = arguments.solver_output.read_text()
        solver_stderr = ""
    else:
        completed = subprocess.run(
            [
                str(arguments.z3),
                f"-T:{arguments.timeout_seconds}",
                str(arguments.cnf),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=arguments.timeout_seconds + 30,
        )
        arguments.solver_output.write_text(completed.stdout)
        if completed.returncode not in (0, 1):
            raise RuntimeError(
                f"Z3 exited {completed.returncode}: {completed.stderr[:1000]}"
            )
        solver_stdout = completed.stdout
        solver_stderr = completed.stderr
    status, true_variables = parse_z3_dimacs_output(solver_stdout)

    report: dict[str, object] = {
        "query": "h1504_fixed_per_opcode_bit_polarity_exact_cnf",
        "status": status,
        "equivalence_boundary": {
            "physical_channels": 248,
            "literal_options_per_logical_bit": 496,
            "logical_opcode_bits": LOGICAL_BITS,
            "all_selected_channels_distinct": metadata["distinct_channels"],
            "decoded_rows": 38,
            "recognized_opcode_values": len(metadata["recognized_values"]),
            "forbidden_opcode_values_per_row": metadata["forbidden_value_count"],
            "claim": (
                (
                    "equisatisfiable with H1504's joint one-lane independent-fixed-"
                    "polarity query under the same public recognized-opcode condition"
                    if metadata["distinct_channels"]
                    else "relaxes only H1504's cross-logical-bit channel-distinctness"
                )
            ),
        },
        "cnf": {
            "variables": cnf.variable_count,
            "clauses": len(cnf.clauses),
            "path": arguments.cnf.name,
            "bytes": arguments.cnf.stat().st_size,
            "sha256": digest(arguments.cnf),
        },
        "solver": {
            "name": "Z3 DIMACS SAT frontend",
            "version": version,
            "timeout_seconds": arguments.timeout_seconds,
            "output": arguments.solver_output.name,
            "output_sha256": digest(arguments.solver_output),
            "stderr": solver_stderr,
            "summarized_existing_one_shot": arguments.summarize_existing,
        },
        "dependencies": {
            "h1467_report_sha256": digest(arguments.h1467),
            "h1504_script_sha256": digest(Path(h1504.__file__)),
        },
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
        report["model"] = decode_model(metadata, true_variables, source)
    elif true_variables:
        raise RuntimeError(f"unexpected model variables for {status}")

    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    arguments.output.write_text(text)
    print(
        json.dumps(
            {
                "output": str(arguments.output),
                "report_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "status": status,
                "variables": cnf.variable_count,
                "clauses": len(cnf.clauses),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
