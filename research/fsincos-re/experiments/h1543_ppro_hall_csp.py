#!/usr/bin/env python3
"""Exact Pentium Pro opcode mapper CSP with Hall propagation.

H1506 maintains the recognized-opcode domain of every recovered physical row
but treats distinct physical-channel selection only as an already-used test.
This solver adds an exact bipartite perfect-matching check over every remaining
logical-bit/channel domain.  It also breaks MRV ties by the current ambiguity
of the logical opcode bit rather than by bit number.

The search is still exact.  SAT returns a fully replayed mapping, exhausting
the tree returns UNSAT, and the wall-clock limit returns UNKNOWN.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import h1490_ppro_core_permutation_transfer as later


SIGNATURES = ("611", "612")
DATA_GROUPS = 19
DWORDS = 8
BITS_PER_DWORD = 31
LOGICAL_BITS = 12
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
            raise RuntimeError(
                f"0x{signature} has {len(groups)} rather than 19 physical groups"
            )
        rows = tuple(
            tuple(int(word, 16) for word in group["physical_dwords"])
            for group in groups
        )
        if any((word >> 31) & 1 for row in rows[:18] for word in row):
            raise RuntimeError(
                f"0x{signature} does not preserve the first-18-line bit-31 wall"
            )
        result[signature] = rows
    return result


def recognized_values() -> tuple[int, ...]:
    return tuple(
        value
        for value in range(1 << LOGICAL_BITS)
        if later.recognized_opcode(value) is not None
    )


def has_channel_matching(channel_domains: list[int]) -> bool:
    """Return whether the remaining logical bits have distinct channels."""

    ordered = sorted(channel_domains, key=int.bit_count)
    matched_by_channel: dict[int, int] = {}

    def augment(variable: int, seen: set[int]) -> bool:
        choices = ordered[variable]
        while choices:
            low = choices & -choices
            choices ^= low
            channel = low.bit_length() - 1
            if channel in seen:
                continue
            seen.add(channel)
            owner = matched_by_channel.get(channel)
            if owner is None or augment(owner, seen):
                matched_by_channel[channel] = variable
                return True
        return False

    return all(augment(variable, set()) for variable in range(len(ordered)))


def solve(
    rows_by_signature: dict[str, tuple[tuple[int, ...], ...]],
    timeout_seconds: float,
) -> dict[str, object]:
    channels = physical_channels()
    rows = tuple(
        (signature, group, row)
        for signature in SIGNATURES
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
    hall_checks = 0
    hall_failures = 0
    domain_failures = 0
    solution: tuple[int, ...] | None = None

    def domains_for_state(
        unassigned: int, used_channels: int, masks: tuple[int, ...]
    ) -> tuple[list[tuple[int, list[int], int]], bool]:
        """Return (bit, signed-literal domain, ambiguity) triples."""

        triples = []
        for logical_bit in range(LOGICAL_BITS):
            if not ((unassigned >> logical_bit) & 1):
                continue
            zero_values, one_values = allowed_by_bit_value[logical_bit]
            forced_zero = 0
            forced_one = 0
            ambiguity = 0
            for row_index, mask in enumerate(masks):
                zero_count = (mask & zero_values).bit_count()
                one_count = (mask & one_values).bit_count()
                if not zero_count and not one_count:
                    raise RuntimeError("empty row domain escaped pruning")
                if not zero_count:
                    forced_one |= 1 << row_index
                elif not one_count:
                    forced_zero |= 1 << row_index
                else:
                    ambiguity += min(zero_count, one_count)
            domain = [
                literal
                for literal, pattern in enumerate(literal_patterns)
                if not ((used_channels >> (literal // 2)) & 1)
                and not (pattern & forced_zero)
                and (pattern & forced_one) == forced_one
            ]
            if not domain:
                return [], False
            triples.append((logical_bit, domain, ambiguity))
        return triples, True

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
        nonlocal hall_checks, hall_failures, domain_failures
        nodes += 1
        depth = LOGICAL_BITS - unassigned.bit_count()
        maximum_depth = max(maximum_depth, depth)
        if (nodes & 0x3FFF) == 0 and time.monotonic() >= deadline:
            timed_out = True
            return False
        if not unassigned:
            solution = assignment
            return True

        triples, viable = domains_for_state(unassigned, used_channels, masks)
        if not viable:
            dead_ends += 1
            domain_failures += 1
            return False

        channel_domains = []
        for _, domain, _ in triples:
            channel_mask = 0
            for literal in domain:
                channel_mask |= 1 << (literal // 2)
            channel_domains.append(channel_mask)
        hall_checks += 1
        if not has_channel_matching(channel_domains):
            dead_ends += 1
            hall_failures += 1
            return False

        chosen_bit, chosen_domain, _ = min(
            triples, key=lambda item: (len(item[1]), item[2], item[0])
        )
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
        return False

    found = search(
        (1 << LOGICAL_BITS) - 1,
        0,
        tuple(all_allowed for _ in rows),
        tuple(-1 for _ in range(LOGICAL_BITS)),
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
            "domain_failures": domain_failures,
            "hall_checks": hall_checks,
            "hall_failures": hall_failures,
            "branching": (
                "MRV logical bit, current-ambiguity tie break, then minimum "
                "remaining opcode mass"
            ),
            "domain_filter": "exact forced-zero/forced-one 38-row bit masks",
            "all_different_filter": "exact bipartite channel perfect matching",
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
        decoded = {signature: [] for signature in SIGNATURES}
        for logical_bit, literal in enumerate(solution):
            channel = literal // 2
            polarity = literal & 1
            dword, physical_bit = channels[channel]
            mapping.append({
                "logical_opcode_bit": logical_bit,
                "physical_channel_index": channel,
                "dword": dword,
                "bit": physical_bit,
                "inverted": bool(polarity),
            })
        if len({item["physical_channel_index"] for item in mapping}) != LOGICAL_BITS:
            raise RuntimeError("CSP returned a non-injective model")
        for signature in SIGNATURES:
            for row in rows_by_signature[signature]:
                opcode = sum(
                    (
                        ((row[item["dword"]] >> item["bit"]) & 1)
                        ^ int(item["inverted"])
                    ) << item["logical_opcode_bit"]
                    for item in mapping
                )
                if later.recognized_opcode(opcode) is None:
                    raise RuntimeError(f"CSP decoded unknown opcode {opcode:03X}")
                decoded[signature].append(f"{opcode:03X}")
        result["model"] = {"mapping": mapping, "decoded_opcodes": decoded}
    return result


def selftest() -> None:
    if not has_channel_matching([0b0011, 0b0110]):
        raise RuntimeError("Hall selftest rejected a valid matching")
    if has_channel_matching([0b0001, 0b0001]):
        raise RuntimeError("Hall selftest admitted a channel collision")
    if has_channel_matching([0b0011, 0b0011, 0b1100, 0b1100, 0b0011]):
        raise RuntimeError("Hall selftest missed a deficient subset")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1467", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")
    if digest(arguments.h1467) != EXPECTED_H1467_SHA256:
        raise RuntimeError("H1467 report hash changed")

    selftest()
    rows = load_rows(json.loads(arguments.h1467.read_text()))
    report = {
        "schema": "fsincos-h1543-ppro-hall-csp-v1",
        "query": "h1504_fixed_polarity_exact_table_csp_with_hall",
        **solve(rows, arguments.timeout_seconds),
        "dependencies": {
            "h1467_report_sha256": digest(arguments.h1467),
            "script_sha256": digest(Path(__file__)),
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
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    arguments.output.write_text(text)
    print(json.dumps({
        "output": str(arguments.output),
        "report_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "status": report["status"],
        **report["search"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
