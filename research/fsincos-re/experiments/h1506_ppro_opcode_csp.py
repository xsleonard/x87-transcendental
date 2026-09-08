#!/usr/bin/env python3
"""Exact table-CSP solver for H1504's fixed-polarity opcode query.

The solver branches on the twelve logical opcode positions rather than on a
bit-blasted one-hot circuit.  For each of the 38 recovered rows it maintains
the exact subset of the 459 recognized opcodes still compatible with the
partial assignment.  Forward checking removes any physical literal that
would empty one of those row subsets, and the next logical position is chosen
by minimum remaining domain.  Reaching a leaf is a SAT witness; exhausting
the tree is an UNSAT proof for the same bounded H1504 condition; reaching the
wall-clock bound is UNKNOWN.

This is a software-only analysis.  It does not use hardware or capture labels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import h1490_ppro_core_permutation_transfer as later
import h1504_ppro_opcode_permutation_smt as h1504


LOGICAL_BITS = 12


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recognized_values() -> tuple[int, ...]:
    return tuple(
        value
        for value in range(1 << LOGICAL_BITS)
        if later.recognized_opcode(value) is not None
    )


def solve(
    rows_by_signature: dict[str, tuple[tuple[int, ...], ...]],
    timeout_seconds: float,
) -> dict[str, object]:
    channels = h1504.physical_channels()
    rows = tuple(
        (signature, group, row)
        for signature in h1504.SIGNATURES
        for group, row in enumerate(rows_by_signature[signature])
    )
    physical_patterns = tuple(
        sum(
            ((row[dword] >> bit) & 1) << row_index
            for row_index, (_, _, row) in enumerate(rows)
        )
        for dword, bit in channels
    )
    row_mask = (1 << len(rows)) - 1
    literal_patterns = tuple(
        pattern if polarity == 0 else pattern ^ row_mask
        for pattern in physical_patterns
        for polarity in range(2)
    )
    allowed = recognized_values()
    all_allowed = (1 << len(allowed)) - 1
    allowed_by_bit_value = tuple(
        tuple(
            sum(
                1 << index
                for index, opcode in enumerate(allowed)
                if ((opcode >> bit) & 1) == value
            )
            for value in range(2)
        )
        for bit in range(LOGICAL_BITS)
    )

    started = time.monotonic()
    deadline = started + timeout_seconds
    nodes = 0
    dead_ends = 0
    maximum_depth = 0
    timed_out = False
    solution: tuple[int, ...] | None = None

    # The cache records exact failed subproblems.  It is intentionally bounded
    # by the process memory available to this isolated experiment.
    failed: set[tuple[int, int, tuple[int, ...]]] = set()

    def forced_row_values(
        logical_bit: int, masks: tuple[int, ...]
    ) -> tuple[int, int]:
        """Return row-bit masks that force this opcode bit to zero or one."""

        forced_zero = 0
        forced_one = 0
        zero_values, one_values = allowed_by_bit_value[logical_bit]
        for row_index, mask in enumerate(masks):
            has_zero = bool(mask & zero_values)
            has_one = bool(mask & one_values)
            if not has_zero and not has_one:
                raise RuntimeError("an empty per-row opcode domain escaped pruning")
            if not has_zero:
                forced_one |= 1 << row_index
            elif not has_one:
                forced_zero |= 1 << row_index
        return forced_zero, forced_one

    def restricted_masks(
        logical_bit: int, literal: int, masks: tuple[int, ...]
    ) -> tuple[int, ...]:
        pattern = literal_patterns[literal]
        values = allowed_by_bit_value[logical_bit]
        return tuple(
            mask & values[(pattern >> row_index) & 1]
            for row_index, mask in enumerate(masks)
        )

    def search(
        unassigned: int,
        used_channels: int,
        masks: tuple[int, ...],
        assignment: tuple[int, ...],
    ) -> bool:
        nonlocal nodes, dead_ends, maximum_depth, timed_out, solution
        nodes += 1
        depth = LOGICAL_BITS - unassigned.bit_count()
        maximum_depth = max(maximum_depth, depth)
        if (nodes & 0x3FFF) == 0 and time.monotonic() >= deadline:
            timed_out = True
            return False
        if not unassigned:
            solution = assignment
            return True

        key = (unassigned, used_channels, masks)
        if key in failed:
            return False

        chosen_bit = -1
        chosen_domain: list[int] | None = None
        for logical_bit in range(LOGICAL_BITS):
            if not ((unassigned >> logical_bit) & 1):
                continue
            forced_zero, forced_one = forced_row_values(logical_bit, masks)
            domain = [
                literal
                for literal in range(len(literal_patterns))
                if not ((used_channels >> (literal // 2)) & 1)
                and not (literal_patterns[literal] & forced_zero)
                and (literal_patterns[literal] & forced_one) == forced_one
            ]
            if not domain:
                dead_ends += 1
                failed.add(key)
                return False
            if chosen_domain is None or len(domain) < len(chosen_domain):
                chosen_bit = logical_bit
                chosen_domain = domain

        assert chosen_domain is not None and chosen_bit >= 0

        # Try the literals that most strongly reduce the remaining opcode sets
        # first.  This is only a search order; it does not alter completeness.
        ranked = []
        for literal in chosen_domain:
            child_masks = restricted_masks(chosen_bit, literal, masks)
            score = sum(mask.bit_count() for mask in child_masks)
            ranked.append((score, literal, child_masks))
        ranked.sort(key=lambda item: (item[0], item[1]))

        next_unassigned = unassigned & ~(1 << chosen_bit)
        for _, literal, child_masks in ranked:
            values = list(assignment)
            values[chosen_bit] = literal
            if search(
                next_unassigned,
                used_channels | (1 << (literal // 2)),
                child_masks,
                tuple(values),
            ):
                return True
            if timed_out:
                return False
        dead_ends += 1
        failed.add(key)
        return False

    initial_assignment = tuple(-1 for _ in range(LOGICAL_BITS))
    found = search(
        (1 << LOGICAL_BITS) - 1,
        0,
        tuple(all_allowed for _ in rows),
        initial_assignment,
    )
    elapsed = time.monotonic() - started
    status = "SAT" if found else ("UNKNOWN" if timed_out else "UNSAT")

    result: dict[str, object] = {
        "status": status,
        "timeout_seconds": timeout_seconds,
        "elapsed_seconds": elapsed,
        "search": {
            "nodes": nodes,
            "dead_ends": dead_ends,
            "maximum_depth": maximum_depth,
            "cached_failed_subproblems": len(failed),
            "branching": "MRV logical bit, then minimum remaining opcode mass",
            "domain_filter": "exact forced-zero/forced-one 38-row bit masks",
        },
        "problem": {
            "physical_channels": len(channels),
            "signed_literals": len(literal_patterns),
            "logical_opcode_bits": LOGICAL_BITS,
            "decoded_rows": len(rows),
            "recognized_opcodes": len(allowed),
            "all_selected_channels_distinct": True,
            "claim": (
                "exactly H1504's joint one-lane fixed-per-bit-polarity query "
                "under the same public recognized-opcode condition"
            ),
        },
    }
    if solution is not None:
        mapping = []
        decoded = {signature: [] for signature in h1504.SIGNATURES}
        for logical_bit, literal in enumerate(solution):
            channel = literal // 2
            polarity = literal & 1
            dword, physical_bit = channels[channel]
            mapping.append(
                {
                    "logical_opcode_bit": logical_bit,
                    "physical_channel_index": channel,
                    "dword": dword,
                    "bit": physical_bit,
                    "inverted": bool(polarity),
                }
            )
        if len({item["physical_channel_index"] for item in mapping}) != LOGICAL_BITS:
            raise RuntimeError("CSP returned a non-injective model")
        for signature in h1504.SIGNATURES:
            for row in rows_by_signature[signature]:
                opcode = sum(
                    (
                        ((row[item["dword"]] >> item["bit"]) & 1)
                        ^ int(item["inverted"])
                    )
                    << item["logical_opcode_bit"]
                    for item in mapping
                )
                if later.recognized_opcode(opcode) is None:
                    raise RuntimeError(f"CSP model decoded unknown opcode {opcode:03X}")
                decoded[signature].append(f"{opcode:03X}")
        result["model"] = {"mapping": mapping, "decoded_opcodes": decoded}
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1467", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")

    source = json.loads(arguments.h1467.read_text())
    rows = h1504.load_rows(source)
    report = {
        "query": "h1504_fixed_polarity_exact_table_csp",
        **solve(rows, arguments.timeout_seconds),
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
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    arguments.output.write_text(text)
    print(
        json.dumps(
            {
                "output": str(arguments.output),
                "report_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "status": report["status"],
                **report["search"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
