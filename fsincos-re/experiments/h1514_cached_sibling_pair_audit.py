#!/usr/bin/env python3
"""Audit every cached Skylake FSIN/FSINCOS result for a pair-A/B vote.

H1509--H1511 exhaust repository-visible standalone FCOS caches.  This audit
covers the sibling standalone-FSIN and paired-FSINCOS artifacts, including
directed-mode and precision-control captures, and verifies later archive
copies byte-for-byte.  It compares the incumbent and default-off R1382 model
in bounded batches, consulting hardware only on differing endpoints.

No x87 instruction or fresh hardware capture is executed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

from h1479_r1475_topology_isomorphism import MODES
from h1510_existing_targeted_pair_audit import configs, digest
from h1512_opened_transfer_pair_audit import (
    run_model,
    select_pattern,
    terminal_patterns,
)


CHUNK_ROWS = 100_000


def standard_outputs(directory: str, prefix: str):
    return tuple(
        (mode, mode, f"{directory}/{prefix}_{mode}_status.txt")
        for mode in MODES
    )


CASES = (
    {
        "tag": "h384-fsin",
        "instruction": "fsin",
        "input": "capture-kit/inputs/constraint_fcos_payload_h384.txt",
        "rows": 27_074,
        "outputs": standard_outputs(
            "capture-kit-captures/skylake-fcos-h384", "fsin"
        ),
    },
    {
        "tag": "h384-fsincos",
        "instruction": "fsincos",
        "input": "capture-kit/inputs/constraint_fcos_payload_h384.txt",
        "rows": 27_074,
        "outputs": standard_outputs(
            "capture-kit-captures/skylake-fcos-h384", "fsincos"
        ),
    },
    {
        "tag": "h269-fsin",
        "instruction": "fsin",
        "input": (
            "capture-kit-captures/skylake-fptan-h269/"
            "fptan_h269_mismatch_inputs.txt"
        ),
        "rows": 7,
        "outputs": standard_outputs(
            "capture-kit-captures/skylake-fptan-h269",
            "fptan_h269_mismatch_fsin",
        ),
    },
    {
        "tag": "h269-fsincos",
        "instruction": "fsincos",
        "input": (
            "capture-kit-captures/skylake-fptan-h269/"
            "fptan_h269_mismatch_inputs.txt"
        ),
        "rows": 7,
        "outputs": standard_outputs(
            "capture-kit-captures/skylake-fptan-h269",
            "fptan_h269_mismatch_fsincos",
        ),
    },
    {
        "tag": "h110-tiny-fsin",
        "instruction": "fsin",
        "input": "capture-kit/inputs/constraint_fsin_tiny_h117.txt",
        "rows": 360,
        "outputs": standard_outputs(
            "capture-kit-captures/skylake-fsin-h110", "constraint_fsin_tiny"
        ),
    },
    {
        "tag": "h110-dense-fsin",
        "instruction": "fsin",
        "input": "capture-kit/inputs/dense_qn.txt",
        "rows": 240_000,
        "outputs": standard_outputs(
            "capture-kit-captures/skylake-fsin-h110", "dense_fsin"
        ),
    },
    {
        "tag": "h110-sweep-fsin",
        "instruction": "fsin",
        "input": "capture-kit/inputs/sweep_inputs.txt",
        "rows": 50_038,
        "outputs": standard_outputs(
            "capture-kit-captures/skylake-fsin-h110", "sweep_fsin"
        ),
    },
    *(
        {
            "tag": f"{tag}-fsin",
            "instruction": "fsin",
            "input": f"capture-kit/inputs/{input_name}.txt",
            "rows": rows,
            "outputs": standard_outputs(directory, output_prefix),
        }
        for tag, input_name, rows, directory, output_prefix in (
            (
                "h130", "constraint_fsin_reduced_coefficient_h130", 512,
                "capture-kit-captures/skylake-fsin-h130",
                "constraint_fsin_reduced_coefficient",
            ),
            (
                "h135", "constraint_fsin_table_terminal_h135", 80,
                "capture-kit-captures/skylake-fsin-h135",
                "constraint_fsin_table_terminal",
            ),
            (
                "h140", "constraint_fsin_fmul_h140", 5,
                "capture-kit-captures/skylake-fsin-h140",
                "constraint_fsin_fmul",
            ),
            (
                "h147", "constraint_fsin_cosine_boolean_h147", 128,
                "capture-kit-captures/skylake-fsin-h147",
                "constraint_fsin_cosine_boolean",
            ),
            (
                "h148", "constraint_fsin_cosine_boolean_h148", 441,
                "capture-kit-captures/skylake-fsin-h148",
                "constraint_fsin_cosine_boolean_h148",
            ),
            (
                "h151", "constraint_fsin_cosine_tail_h151", 538,
                "capture-kit-captures/skylake-fsin-h151",
                "constraint_fsin_cosine_tail_h151",
            ),
            (
                "h158", "constraint_fsin_cosine_two_predicate_h158", 634,
                "capture-kit-captures/skylake-fsin-h158",
                "constraint_fsin_cosine_two_predicate_h158",
            ),
            (
                "h161", "constraint_fsin_cosine_round32_composition_h161", 256,
                "capture-kit-captures/skylake-fsin-h161",
                "constraint_fsin_cosine_round32_composition_h161",
            ),
            (
                "h163", "constraint_fsin_cosine_product_h163", 33,
                "capture-kit-captures/skylake-fsin-h163",
                "constraint_fsin_cosine_product_h163",
            ),
            (
                "h165", "constraint_fsin_cosine_product_width_h165", 1,
                "capture-kit-captures/skylake-fsin-h165",
                "constraint_fsin_cosine_product_width_h165",
            ),
            (
                "h168", "constraint_fsin_cosine_round33_operation_h168", 363,
                "capture-kit-captures/skylake-fsin-h168",
                "constraint_fsin_cosine_round33_operation_h168",
            ),
            (
                "h171", "constraint_fsin_table_correction_h171", 283,
                "capture-kit-captures/skylake-fsin-h171",
                "constraint_fsin_table_correction_h171",
            ),
            (
                "h175", "constraint_fsin_table_path_gate_h175", 243,
                "capture-kit-captures/skylake-fsin-h175",
                "constraint_fsin_table_path_gate_h175",
            ),
        )
    ),
    {
        "tag": "h172-table-pc-fsin",
        "instruction": "fsin",
        "input": "capture-kit/inputs/constraint_fsin_table_correction_h171.txt",
        "rows": 283,
        "outputs": tuple(
            (
                f"rn_{pc}",
                "rn",
                "capture-kit-captures/skylake-fsin-h172/"
                f"constraint_fsin_table_correction_h171_rn_{pc}_status.txt",
            )
            for pc in ("pc24", "pc53", "pc64")
        ),
    },
    {
        "tag": "h172-sweep-pc-fsin",
        "instruction": "fsin",
        "input": "capture-kit/inputs/sweep_inputs.txt",
        "rows": 50_038,
        "outputs": tuple(
            (
                f"rn_{pc}",
                "rn",
                "capture-kit-captures/skylake-fsin-h172/"
                f"sweep_fsin_rn_{pc}_status.txt",
            )
            for pc in ("pc24", "pc53", "pc64")
        ),
    },
    *(
        {
            "tag": f"{tag}-{instruction}",
            "instruction": instruction,
            "input": f"capture-kit/inputs/{input_name}.txt",
            "rows": rows,
            "outputs": standard_outputs(directory, f"{output_prefix}_{instruction}"),
        }
        for tag, input_name, rows, directory, output_prefix in (
            (
                "h183", "constraint_table_joint_product_h183", 43,
                "capture-kit-captures/skylake-fsin-h183",
                "constraint_table_joint_product_h183",
            ),
            (
                "h185", "constraint_table_lookup_firc_h185", 38,
                "capture-kit-captures/skylake-fsin-h185",
                "constraint_table_lookup_firc_h185",
            ),
            (
                "h189", "constraint_table_stage_local_h189", 37,
                "capture-kit-captures/skylake-fsin-h189",
                "constraint_table_stage_local_h189",
            ),
            (
                "h216", "constraint_table_fadd_microcontrol_h216", 31,
                "capture-kit-captures/skylake-fsin-h216",
                "constraint_table_fadd_microcontrol_h216",
            ),
            (
                "h221", "constraint_table_fadd_tree_h221", 49,
                "capture-kit-captures/skylake-fsin-h221",
                "constraint_table_fadd_tree_h221",
            ),
            (
                "h223", "constraint_table_fadd_tree_h223", 43,
                "capture-kit-captures/skylake-fsin-h223",
                "constraint_table_fadd_tree_h223",
            ),
            (
                "h224", "constraint_table_fadd_tree_h224", 98,
                "capture-kit-captures/skylake-fsin-h224",
                "constraint_table_fadd_tree_h224",
            ),
        )
        for instruction in ("fsin", "fsincos")
    ),
    {
        "tag": "h177-dense-fsincos",
        "instruction": "fsincos",
        "input": "capture-kit/inputs/dense_qn.txt",
        "rows": 240_000,
        "outputs": standard_outputs(
            "capture-kit-captures/skylake-fsin-h177", "dense_fsincos"
        ),
    },
    {
        "tag": "h177-sweep-fsincos",
        "instruction": "fsincos",
        "input": "capture-kit/inputs/sweep_inputs.txt",
        "rows": 50_038,
        "outputs": standard_outputs(
            "capture-kit-captures/skylake-fsin-h177", "sweep_fsincos"
        ),
    },
    *(
        {
            "tag": f"{tag}-{instruction}",
            "instruction": instruction,
            "input": f"capture-kit/inputs/{input_name}.txt",
            "rows": rows,
            "outputs": standard_outputs(directory, instruction),
        }
        for tag, input_name, rows, directory in (
            (
                "h285", "constraint_trig_sine_bias_h285", 192,
                "capture-kit-captures/skylake-trig-h285",
            ),
            (
                "h292", "constraint_trig_sine_coordinates_h292", 256,
                "capture-kit-captures/skylake-trig-h292",
            ),
            (
                "h301", "constraint_trig_sine_fraction_h301", 32,
                "capture-kit-captures/skylake-trig-h301",
            ),
            (
                "h307", "constraint_trig_narrow_sine_fraction_h307", 64,
                "capture-kit-captures/skylake-trig-h307",
            ),
            (
                "h314", "constraint_trig_narrow_sine_fraction2_h314", 24,
                "capture-kit-captures/skylake-trig-h314",
            ),
            (
                "h320", "constraint_trig_narrow_sine_fraction3_h320", 24,
                "capture-kit-captures/skylake-trig-h320",
            ),
            (
                "h347", "constraint_round49_residual_neighbors_h347", 197_044,
                "capture-kit-captures/skylake-trig-h347",
            ),
        )
        for instruction in ("fsin", "fsincos")
    ),
    {
        "tag": "h349-fsincos",
        "instruction": "fsincos",
        "input": "capture-kit/inputs/round49_broad_scan_h349.txt",
        "rows": 1_000_000,
        "outputs": standard_outputs(
            "capture-kit-captures/skylake-trig-h349", "fsincos"
        ),
    },
    {
        "tag": "h65-fsin-rn",
        "instruction": "fsin",
        "input": "capture-kit/inputs/constraint_poly_h65.txt",
        "rows": 2_000,
        "outputs": ((
            "rn", "rn",
            "capture-kit-captures/skylake-h65-poly/constraint_poly_fsin.txt",
        ),),
    },
    {
        "tag": "h65-fsincos",
        "instruction": "fsincos",
        "input": "capture-kit/inputs/constraint_poly_h65.txt",
        "rows": 2_000,
        "outputs": tuple(
            (
                mode,
                mode,
                f"capture-kit-captures/skylake-h65-poly/constraint_poly_{mode}.txt",
            )
            for mode in MODES
        ),
    },
    *(
        {
            "tag": f"vm-rz-{bank}-fsin",
            "instruction": "fsin",
            "input": input_name,
            "rows": rows,
            "outputs": ((
                "rz", "rz",
                f"capture-kit-captures/skylake-vm-r88-rz-20260826/{capture}",
            ),),
        }
        for bank, input_name, rows, capture in (
            ("dense", "capture-kit/inputs/dense_qn.txt", 240_000, "dense_fsin_rz.txt"),
            ("sweep", "capture-kit/inputs/sweep_inputs.txt", 50_038, "sweep_fsin_rz.txt"),
            (
                "h347", "capture-kit/inputs/constraint_round49_residual_neighbors_h347.txt",
                197_044, "h347_fsin_rz.txt",
            ),
        )
    ),
)


ALIASES = tuple(
    (
        f"perinsn-{instruction}-{bank}-{mode}",
        (
            "capture-kit-captures/skylake-perinsn-20260807/"
            f"{bank}_{instruction}_{mode}.txt"
        ),
        (
            f"capture-kit-captures/skylake-fsin-h{110 if instruction == 'fsin' else 177}/"
            f"{bank}_{instruction}_{mode}_status.txt"
        ),
    )
    for instruction in ("fsin", "fsincos")
    for bank in ("dense", "sweep")
    for mode in MODES
)


def parse_model_output(line: str, instruction: str) -> dict[str, str]:
    fields = line.lower().split()
    if fields == ["c2"]:
        return {"sin": "c2", **({"cos": "c2"} if instruction == "fsincos" else {})}
    expected = 5 if instruction == "fsincos" else 3
    if len(fields) != expected or fields[0] != "ok":
        raise RuntimeError(f"bad {instruction} model line: {line!r}")
    result = {"sin": f"{int(fields[1], 16):04x}:{int(fields[2], 16):016x}"}
    if instruction == "fsincos":
        result["cos"] = f"{int(fields[3], 16):04x}:{int(fields[4], 16):016x}"
    return result


def parse_hardware_output(line: str, instruction: str) -> dict[str, str]:
    fields = line.lower().split()
    if fields[:1] == ["c2"]:
        return {"sin": "c2", **({"cos": "c2"} if instruction == "fsincos" else {})}
    expected = (5, 7) if instruction == "fsincos" else (3, 5)
    if len(fields) not in expected or fields[0] != "ok":
        raise RuntimeError(f"bad {instruction} hardware line: {line!r}")
    if len(fields) == expected[1] and fields[-2] != "sw":
        raise RuntimeError(f"bad {instruction} hardware status: {line!r}")
    result = {"sin": f"{int(fields[1], 16):04x}:{int(fields[2], 16):016x}"}
    if instruction == "fsincos":
        result["cos"] = f"{int(fields[3], 16):04x}:{int(fields[4], 16):016x}"
    return result


def run_batch(
    model: Path, instruction: str, mode: str, operands: list[str]
) -> list[dict[str, str]]:
    command = [str(model), "--batch", f"--rc={mode}"]
    if instruction == "fsin":
        command.append("--fsin-standalone")
    process = subprocess.run(
        command,
        input="\n".join(operands) + "\n",
        text=True,
        capture_output=True,
        check=True,
    )
    lines = process.stdout.splitlines()
    if len(lines) != len(operands):
        raise RuntimeError(
            f"{instruction}/{mode}: output count {len(lines)} != {len(operands)}"
        )
    return [parse_model_output(line, instruction) for line in lines]


def capture_inventory(repository: Path) -> set[str]:
    root = repository / "capture-kit-captures"
    result = set()
    for candidate in root.rglob("*"):
        if not candidate.is_file() or "skylake" not in str(candidate.parent).lower():
            continue
        name = candidate.name.lower()
        if "fsin" in name or "fsincos" in name:
            result.add(str(candidate.relative_to(repository)))
    for mode in MODES:
        paired_h65 = (
            repository / "capture-kit-captures/skylake-h65-poly"
            / f"constraint_poly_{mode}.txt"
        )
        if not paired_h65.is_file():
            raise RuntimeError(f"missing H65 paired capture {paired_h65}")
        result.add(str(paired_h65.relative_to(repository)))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("incumbent", type=Path)
    parser.add_argument("r1382", type=Path)
    parser.add_argument("repository", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")

    modeled_files = {
        relative_capture
        for case in CASES
        for _, _, relative_capture in case["outputs"]
    }
    alias_files = {relative_alias for _, relative_alias, _ in ALIASES}
    inventory = capture_inventory(arguments.repository)
    if inventory != modeled_files | alias_files:
        raise RuntimeError(json.dumps({
            "unmodeled": sorted(inventory - modeled_files - alias_files),
            "missing": sorted(modeled_files | alias_files - inventory),
        }, sort_keys=True))

    signal_order, candidate_configs = configs()
    rows = []
    counts = Counter()
    case_reports = []
    file_hashes = {}
    input_hashes = {}
    architectural_rows = 0

    for case in CASES:
        input_path = arguments.repository / case["input"]
        operands = [
            line.strip().lower()
            for line in input_path.read_text().splitlines()
            if line.strip()
        ]
        if len(operands) != case["rows"]:
            raise RuntimeError(
                f"{case['tag']}: input count {len(operands)} != {case['rows']}"
            )
        input_hashes[case["tag"]] = digest(input_path)
        case_counts = Counter()
        case_rows = []
        for label, mode, relative_capture in case["outputs"]:
            capture_path = arguments.repository / relative_capture
            hardware_lines = capture_path.read_text().splitlines()
            if len(hardware_lines) != len(operands):
                raise RuntimeError(
                    f"{case['tag']}/{label}: capture count {len(hardware_lines)} "
                    f"!= {len(operands)}"
                )
            file_hashes[relative_capture] = digest(capture_path)
            architectural_rows += len(operands)
            for start in range(0, len(operands), CHUNK_ROWS):
                stop = min(start + CHUNK_ROWS, len(operands))
                selected = operands[start:stop]
                incumbent_values = run_batch(
                    arguments.incumbent, case["instruction"], mode, selected
                )
                r1382_values = run_batch(
                    arguments.r1382, case["instruction"], mode, selected
                )
                for offset, (incumbent, r1382) in enumerate(
                    zip(incumbent_values, r1382_values)
                ):
                    if incumbent == r1382:
                        continue
                    index = start + offset
                    hardware = parse_hardware_output(
                        hardware_lines[index], case["instruction"]
                    )
                    changed_lanes = [
                        lane for lane in incumbent if incumbent[lane] != r1382[lane]
                    ]
                    for lane in changed_lanes:
                        if hardware[lane] == incumbent[lane]:
                            endpoint = "incumbent"
                        elif hardware[lane] == r1382[lane]:
                            endpoint = "r1382"
                        else:
                            endpoint = "other"
                        _, stderr = run_model(
                            arguments.incumbent,
                            case["instruction"],
                            mode,
                            lane,
                            operands[index],
                            dump=True,
                        )
                        pattern, pattern_source = select_pattern(
                            case["instruction"],
                            lane,
                            terminal_patterns(stderr, candidate_configs),
                        )
                        pair_discriminator = False
                        pair_a = None
                        pair_b = None
                        pair_a_exact = None
                        pair_b_exact = None
                        if pattern is not None:
                            if pattern[0] != pattern[1] or pattern[2] != pattern[3]:
                                raise RuntimeError(
                                    f"{case['tag']}/{label}/{index}: "
                                    "H1487 within-pair equivalence changed"
                                )
                            pair_discriminator = pattern[0] != pattern[2]
                            pair_a = (
                                incumbent[lane] if pattern[0] == "1"
                                else r1382[lane]
                            )
                            pair_b = (
                                incumbent[lane] if pattern[2] == "1"
                                else r1382[lane]
                            )
                            pair_a_exact = pair_a == hardware[lane]
                            pair_b_exact = pair_b == hardware[lane]
                        row = {
                            "case": case["tag"],
                            "capture_label": label,
                            "mode": mode,
                            "instruction": case["instruction"],
                            "lane": lane,
                            "index": index,
                            "operand": operands[index].replace(" ", ":"),
                            "hardware": hardware[lane],
                            "incumbent": incumbent[lane],
                            "r1382": r1382[lane],
                            "endpoint": endpoint,
                            "candidate_pattern": pattern,
                            "candidate_pattern_source": pattern_source,
                            "pair_discriminator": pair_discriminator,
                            "pair_a": pair_a,
                            "pair_b": pair_b,
                            "pair_a_exact": pair_a_exact,
                            "pair_b_exact": pair_b_exact,
                        }
                        rows.append(row)
                        case_rows.append(row)
                        for target in (counts, case_counts):
                            target[f"endpoint.{endpoint}"] += 1
                            target[f"lane.{lane}.endpoint_separators"] += 1
                            if pattern is not None:
                                target[f"candidate_pattern.{pattern}"] += 1
                                target[
                                    "pair_discriminator."
                                    + str(pair_discriminator).lower()
                                ] += 1
            case_counts[f"capture.{label}.rows"] = len(operands)

        case_reports.append({
            "case": case["tag"],
            "instruction": case["instruction"],
            "input": case["input"],
            "input_rows": len(operands),
            "captures": len(case["outputs"]),
            "architectural_rows_scored": len(operands) * len(case["outputs"]),
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
            raise RuntimeError(f"{tag}: archive alias differs from canonical")
        alias_reports.append({
            "alias": tag,
            "alias_path": relative_alias,
            "canonical_path": relative_canonical,
            "byte_identical": True,
            "sha256": hashlib.sha256(alias_bytes).hexdigest(),
        })

    discriminators = [row for row in rows if row["pair_discriminator"]]
    ambiguous_patterns = [
        row for row in rows if row["candidate_pattern"] is None
    ]
    if ambiguous_patterns:
        verdict = "CACHED_SIBLING_ENDPOINTS_HAVE_AMBIGUOUS_PAIR_TRACE"
    elif discriminators:
        a_exact = all(row["pair_a_exact"] for row in discriminators)
        b_exact = all(row["pair_b_exact"] for row in discriminators)
        if a_exact and not b_exact:
            verdict = "CACHED_SIBLING_LABELS_FAVOR_PAIR_A"
        elif b_exact and not a_exact:
            verdict = "CACHED_SIBLING_LABELS_FAVOR_PAIR_B"
        else:
            verdict = "CACHED_SIBLING_LABELS_FALSIFY_OR_FAIL_TO_CHOOSE_PAIRS"
    else:
        verdict = "NO_CACHED_SIBLING_PAIR_DISCRIMINATOR"

    report = {
        "experiment": "h1514_cached_sibling_pair_audit",
        "status": verdict,
        "capture_inventory_reconciliation": "EXACT",
        "capture_files_scored": len(modeled_files),
        "archive_alias_files": len(alias_files),
        "cases": case_reports,
        "architectural_rows_scored": architectural_rows,
        "endpoint_separator_rows": len(rows),
        "pair_discriminator_rows": len(discriminators),
        "ambiguous_pair_trace_rows": len(ambiguous_patterns),
        "counts": dict(sorted(counts.items())),
        "candidate_signal_order": signal_order,
        "byte_identical_archive_aliases": alias_reports,
        "rows": rows,
        "claim_boundary": (
            "every repository-visible Skylake standalone-FSIN and paired-"
            "FSINCOS capture artifact; AMD/Pentium-II artifacts excluded; "
            "pair scoring requires a current/R1382 endpoint separator where "
            "the exact H1487 pair functions disagree"
        ),
        "sha256": {
            "incumbent": digest(arguments.incumbent),
            "r1382": digest(arguments.r1382),
            "inputs": input_hashes,
            "captures": file_hashes,
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
        "capture_files_scored": len(modeled_files),
        "archive_alias_files": len(alias_files),
        "architectural_rows_scored": architectural_rows,
        "endpoint_separator_rows": len(rows),
        "pair_discriminator_rows": len(discriminators),
        "ambiguous_pair_trace_rows": len(ambiguous_patterns),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
