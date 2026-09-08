#!/usr/bin/env python3
"""Complete the repository-visible cached Skylake standalone-FCOS audit.

H1509 covers the dense bank and H1510 covers every generic fcos_*_status
targeted bank.  This script covers the remaining non-alias FCOS artifacts:
the H110 sweep, the seven H269 mismatch operands, and H65's RN standalone
FCOS discriminator.  It also proves the later per-instruction dense/sweep
copies are byte-identical aliases of the H110 files.

No x87 instruction or fresh hardware capture is executed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

from h1210_stagea_residual_reframe import parse_dump, parse_output, run
from h1474_score_r1382_lattice import parse_hardware_line
from h1479_r1475_topology_isomorphism import MODES
from h1486_surviving_propagate_class import candidate_values
from h1510_existing_targeted_pair_audit import configs, digest


CASES = (
    (
        "h110-sweep",
        "capture-kit/inputs/sweep_inputs.txt",
        {
            mode: (
                "capture-kit-captures/skylake-fsin-h110/"
                f"sweep_fcos_{mode}_status.txt"
            )
            for mode in MODES
        },
        50_038,
    ),
    (
        "h269-mismatch",
        (
            "capture-kit-captures/skylake-fptan-h269/"
            "fptan_h269_mismatch_inputs.txt"
        ),
        {
            mode: (
                "capture-kit-captures/skylake-fptan-h269/"
                f"fptan_h269_mismatch_fcos_{mode}_status.txt"
            )
            for mode in MODES
        },
        7,
    ),
    (
        "h65-poly-rn",
        "capture-kit/inputs/constraint_poly_h65.txt",
        {
            "rn": (
                "capture-kit-captures/skylake-h65-poly/"
                "constraint_poly_fcos.txt"
            ),
        },
        2_000,
    ),
)


ALIASES = tuple(
    (
        f"perinsn-{bank}-{mode}",
        (
            "capture-kit-captures/skylake-perinsn-20260807/"
            f"{bank}_fcos_{mode}.txt"
        ),
        (
            "capture-kit-captures/skylake-fsin-h110/"
            f"{bank}_fcos_{mode}_status.txt"
        ),
    )
    for bank in ("dense", "sweep")
    for mode in MODES
)


def parse_cached_line(
    line: str, source: Path, line_number: int
) -> tuple[str, str | None]:
    fields = line.lower().split()
    if len(fields) == 3 and fields[0] == "ok":
        try:
            se = int(fields[1], 16)
            significand = int(fields[2], 16)
        except ValueError as error:
            raise RuntimeError(
                f"{source}:{line_number}: non-hex cached field"
            ) from error
        if se > 0xFFFF or significand > 0xFFFFFFFFFFFFFFFF:
            raise RuntimeError(
                f"{source}:{line_number}: cached field out of range"
            )
        return f"{se:04x}:{significand:016x}", None
    return parse_hardware_line(line, source, line_number)


def run_architectural(
    model: Path, mode: str, operands: list[str]
) -> list[str]:
    process = subprocess.run(
        [str(model), "--batch", f"--rc={mode}", "--fcos-standalone"],
        input="\n".join(operands) + "\n",
        text=True,
        capture_output=True,
        check=True,
    )
    values = []
    for line in process.stdout.splitlines():
        if line.strip().lower() == "c2":
            values.append("c2")
        else:
            values.append(parse_output(line))
    if len(values) != len(operands):
        raise RuntimeError(
            f"output count {len(values)} != {len(operands)} for {model}/{mode}"
        )
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("incumbent", type=Path)
    parser.add_argument("r1382", type=Path)
    parser.add_argument("repository", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")

    signal_order, candidate_configs = configs()
    counts = Counter()
    rows = []
    case_reports = []
    input_hashes = {}
    capture_hashes = {}
    architectural_rows = 0

    for tag, relative_input, mode_files, expected_rows in CASES:
        input_path = arguments.repository / relative_input
        operands = [
            line.strip().lower()
            for line in input_path.read_text().splitlines()
            if line.strip()
        ]
        if len(operands) != expected_rows:
            raise RuntimeError(
                f"{tag}: input count {len(operands)} != frozen {expected_rows}"
            )
        input_hashes[tag] = digest(input_path)
        capture_hashes[tag] = {}
        case_rows = []
        case_counts = Counter()

        for mode, relative_capture in mode_files.items():
            capture_path = arguments.repository / relative_capture
            capture_lines = capture_path.read_text().splitlines()
            if len(capture_lines) != expected_rows:
                raise RuntimeError(
                    f"{tag}/{mode}: capture count {len(capture_lines)} "
                    f"!= frozen {expected_rows}"
                )
            capture_hashes[tag][mode] = digest(capture_path)
            architectural_rows += expected_rows
            incumbent_values = run_architectural(
                arguments.incumbent, mode, operands
            )
            r1382_values = run_architectural(arguments.r1382, mode, operands)
            different = [
                index
                for index, (incumbent, candidate) in enumerate(
                    zip(incumbent_values, r1382_values)
                )
                if incumbent != candidate
            ]
            case_counts[f"mode.{mode}.endpoint_separators"] = len(different)
            counts[f"mode.{mode}.endpoint_separators"] += len(different)
            if not different:
                continue

            selected_operands = [operands[index] for index in different]
            if any(
                incumbent_values[index] == "c2"
                or r1382_values[index] == "c2"
                for index in different
            ):
                raise RuntimeError(
                    f"{tag}/{mode}: endpoint separator crosses C2 boundary"
                )
            _, stderr = run(
                arguments.incumbent, mode, selected_operands, dump=True
            )
            dumps = parse_dump(stderr, selected_operands)
            for index, dump in zip(different, dumps):
                hardware, status = parse_cached_line(
                    capture_lines[index], capture_path, index + 1
                )
                incumbent = incumbent_values[index]
                r1382 = r1382_values[index]
                if hardware == incumbent:
                    endpoint = "incumbent"
                elif hardware == r1382:
                    endpoint = "r1382"
                else:
                    endpoint = "other"
                pattern = candidate_values(
                    int(dump["tc_f4_sig"], 16),
                    int(dump["tc_rf_sig"], 16),
                    candidate_configs,
                )
                if pattern[0] != pattern[1] or pattern[2] != pattern[3]:
                    raise RuntimeError("H1487 within-pair equivalence changed")
                pair_a = incumbent if pattern[0] == "1" else r1382
                pair_b = incumbent if pattern[2] == "1" else r1382
                row = {
                    "case": tag,
                    "index": index,
                    "mode": mode,
                    "operand": operands[index].replace(" ", ":"),
                    "hardware": hardware,
                    "hardware_status": status,
                    "incumbent": incumbent,
                    "r1382": r1382,
                    "endpoint": endpoint,
                    "candidate_pattern": pattern,
                    "pair_discriminator": pattern[0] != pattern[2],
                    "pair_a": pair_a,
                    "pair_b": pair_b,
                    "pair_a_exact": pair_a == hardware,
                    "pair_b_exact": pair_b == hardware,
                    "tc_f4_sig": dump["tc_f4_sig"],
                    "tc_rf_sig": dump["tc_rf_sig"],
                }
                rows.append(row)
                case_rows.append(row)
                for target in (counts, case_counts):
                    target[f"endpoint.{endpoint}"] += 1
                    target[f"pattern.{pattern}"] += 1
                    target[
                        f"pair_a.{'exact' if row['pair_a_exact'] else 'miss'}"
                    ] += 1
                    target[
                        f"pair_b.{'exact' if row['pair_b_exact'] else 'miss'}"
                    ] += 1
                    target[
                        "pair_discriminator."
                        + str(row["pair_discriminator"]).lower()
                    ] += 1

        case_reports.append({
            "case": tag,
            "input": relative_input,
            "mode_files": mode_files,
            "operands": expected_rows,
            "architectural_rows_scored": expected_rows * len(mode_files),
            "endpoint_separator_rows": len(case_rows),
            "pair_discriminator_rows": sum(
                row["pair_discriminator"] for row in case_rows
            ),
            "counts": dict(sorted(case_counts.items())),
        })

    alias_reports = []
    for tag, relative_alias, relative_canonical in ALIASES:
        alias_path = arguments.repository / relative_alias
        canonical_path = arguments.repository / relative_canonical
        alias_bytes = alias_path.read_bytes()
        canonical_bytes = canonical_path.read_bytes()
        if alias_bytes != canonical_bytes:
            raise RuntimeError(f"{tag}: cached alias diverged from canonical")
        alias_reports.append({
            "alias": tag,
            "alias_path": relative_alias,
            "canonical_path": relative_canonical,
            "byte_identical": True,
            "sha256": hashlib.sha256(alias_bytes).hexdigest(),
        })

    discriminator_rows = [row for row in rows if row["pair_discriminator"]]
    if discriminator_rows:
        a_exact = all(row["pair_a_exact"] for row in discriminator_rows)
        b_exact = all(row["pair_b_exact"] for row in discriminator_rows)
        if a_exact and not b_exact:
            verdict = "REMAINING_CACHES_FAVOR_PAIR_A"
        elif b_exact and not a_exact:
            verdict = "REMAINING_CACHES_FAVOR_PAIR_B"
        else:
            verdict = "REMAINING_CACHES_FALSIFY_OR_FAIL_TO_CHOOSE_PAIRS"
    else:
        verdict = "NO_REMAINING_CACHED_PAIR_DISCRIMINATOR"

    report = {
        "experiment": "h1511_remaining_fcos_cache_audit",
        "status": verdict,
        "cases": case_reports,
        "architectural_rows_scored": architectural_rows,
        "endpoint_separator_rows": len(rows),
        "pair_discriminator_rows": len(discriminator_rows),
        "counts": dict(sorted(counts.items())),
        "candidate_signal_order": signal_order,
        "byte_identical_archive_aliases": alias_reports,
        "rows": rows,
        "claim_boundary": (
            "remaining repository-visible Skylake standalone-FCOS cache "
            "artifacts after H1509/H1510; AMD and Pentium-II captures excluded"
        ),
        "sha256": {
            "incumbent": digest(arguments.incumbent),
            "r1382": digest(arguments.r1382),
            "inputs": input_hashes,
            "captures": capture_hashes,
        },
        "execution": {
            "hardware": "none; cached captures read only",
            "x87_instructions": "none",
            "fresh_capture_labels_opened": "none",
            "private_capture_ledger": "not accessed",
            "h1488_state": "FROZEN_UNOPENED",
            "emulator_change": "none",
            "paper_change": "none",
        },
    }
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(text)
    print(json.dumps({
        "output": str(arguments.output),
        "report_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "status": verdict,
        "architectural_rows_scored": architectural_rows,
        "endpoint_separator_rows": len(rows),
        "pair_discriminator_rows": len(discriminator_rows),
        "archive_aliases": len(alias_reports),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
