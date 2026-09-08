#!/usr/bin/env python3
"""Search an exact cross-dword Pentium Pro opcode-bit permutation.

H1493 exhausted only mappings obtained from the published later-P6 wiring by
whole-dword permutations and conventional within-dword transforms.  This
audit drops that serialization assumption while retaining two structural
requirements: every logical opcode bit is one physical bit, and distinct
logical opcode positions use distinct physical channels.  It asks whether
all nineteen MSRAM lines of the recovered 0x611/0x612 bodies can decode to
opcodes in the public P6 opcode map.

Dword bit 31 is excluded because the public later-P6 descrambler never consumes
it and it is exactly zero in both early bodies' first eighteen lines.  The
nineteenth MSRAM line remains in the opcode constraints even though its bit-31
surface differs.  No hardware, capture label, or private ledger is involved.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import subprocess
from pathlib import Path

import z3

import h1490_ppro_core_permutation_transfer as later


SIGNATURES = ("611", "612")
TRANSFER_SIGNATURES = ("611", "612", "617", "619")
DATA_GROUPS = 19
DWORDS = 8
BITS_PER_DWORD = 31
LANES = 3
OPCODE_BITS = 12
SOURCE_BITS = 8
RANDOM_SEEDS = (0x243F6A88, 0x13198A2E, 0x9E3779B9, 0xD1B54A32)


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
    for signature in TRANSFER_SIGNATURES:
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
        if signature in SIGNATURES and any(
            (word >> 31) & 1 for row in rows[:18] for word in row
        ):
            raise RuntimeError(
                f"0x{signature} does not preserve the first-18-line bit-31 wall"
            )
        result[signature] = rows
    return result


def recognized(opcode: z3.BitVecRef) -> z3.BoolRef:
    def masked_in(mask: int, values: set[int]) -> z3.BoolRef:
        return z3.Or(
            *tuple(
                (opcode & z3.BitVecVal(mask, OPCODE_BITS))
                == z3.BitVecVal(value, OPCODE_BITS)
                for value in sorted(values)
            )
        )

    arithmetic = z3.And(
        masked_in(0xC7F, later.ARITHMETIC),
        masked_in(0x380, later.DATA_SIZES),
    )
    exact = z3.Or(
        *tuple(
            opcode == z3.BitVecVal(value, OPCODE_BITS)
            for value in sorted(later.EXACT_UOPS)
        )
    )
    conditional = masked_in(0xFF0, later.CC_BASES)
    memory = z3.And(
        masked_in(0xC4F, later.MEMORY_BASES),
        masked_in(0x380, later.DATA_SIZES),
    )
    return z3.Or(arithmetic, exact, conditional, memory)


def solve(
    rows_by_signature: dict[str, tuple[tuple[int, ...], ...]],
    signatures: tuple[str, ...],
    lane_count: int,
    timeout_ms: int,
    smt2_path: Path | None = None,
    allow_inversion: bool = False,
    max_unrecognized: int = 0,
) -> dict[str, object]:
    channels = physical_channels()
    rows = tuple(
        (signature, group, row)
        for signature in signatures
        for group, row in enumerate(rows_by_signature[signature])
    )
    sources = tuple(
        tuple(
            z3.BitVec(f"source_l{lane}_b{bit}", SOURCE_BITS)
            for bit in range(OPCODE_BITS)
        )
        for lane in range(lane_count)
    )
    polarities = tuple(
        tuple(
            z3.Bool(f"invert_l{lane}_b{bit}")
            for bit in range(OPCODE_BITS)
        )
        for lane in range(lane_count)
    )
    solver = z3.Solver()
    solver.set(timeout=timeout_ms)
    flattened = tuple(source for lane in sources for source in lane)
    solver.add(
        *(
            z3.ULT(source, z3.BitVecVal(len(channels), SOURCE_BITS))
            for source in flattened
        )
    )
    solver.add(z3.Distinct(*flattened))
    solver.add(
        *(
            z3.ULT(sources[lane][0], sources[lane + 1][0])
            for lane in range(lane_count - 1)
        )
    )

    opcodes: dict[tuple[str, int, int], z3.BitVecRef] = {}
    ordered_opcodes = tuple(
        tuple(
            z3.BitVec(f"opcode_r{row_index}_l{lane}", OPCODE_BITS)
            for lane in range(lane_count)
        )
        for row_index in range(len(rows))
    )
    recognition_flags = []
    for row_index, (signature, group, _) in enumerate(rows):
        for lane in range(lane_count):
            opcode = ordered_opcodes[row_index][lane]
            opcodes[(signature, group, lane)] = opcode
            recognition_flags.append(recognized(opcode))

    if max_unrecognized < 0 or max_unrecognized > len(recognition_flags):
        raise ValueError("max_unrecognized is outside the candidate-uop count")
    if max_unrecognized == 0:
        solver.add(*recognition_flags)
    else:
        count_bits = math.ceil(math.log2(len(recognition_flags) + 1))
        count = z3.BitVecVal(0, count_bits)
        for flag in recognition_flags:
            count = count + z3.If(
                flag,
                z3.BitVecVal(1, count_bits),
                z3.BitVecVal(0, count_bits),
            )
        solver.add(
            z3.UGE(
                count,
                z3.BitVecVal(
                    len(recognition_flags) - max_unrecognized, count_bits
                ),
            )
        )

    physical_patterns = tuple(
        sum(
            ((row[dword] >> bit) & 1) << row_index
            for row_index, (_, _, row) in enumerate(rows)
        )
        for dword, bit in channels
    )
    for lane in range(lane_count):
        for bit in range(OPCODE_BITS):
            pattern = z3.Concat(
                *tuple(
                    z3.Extract(bit, bit, ordered_opcodes[row_index][lane])
                    for row_index in reversed(range(len(rows)))
                )
            )
            alternatives = []
            mask = (1 << len(rows)) - 1
            for channel, value in enumerate(physical_patterns):
                source_match = sources[lane][bit] == z3.BitVecVal(
                    channel, SOURCE_BITS
                )
                alternatives.append(
                    z3.And(
                        pattern == z3.BitVecVal(value, len(rows)),
                        source_match,
                        z3.Not(polarities[lane][bit]),
                    )
                )
                if allow_inversion:
                    alternatives.append(
                        z3.And(
                            pattern == z3.BitVecVal(value ^ mask, len(rows)),
                            source_match,
                            polarities[lane][bit],
                        )
                    )
            solver.add(z3.Or(*alternatives))
            if not allow_inversion:
                solver.add(z3.Not(polarities[lane][bit]))

    if smt2_path is not None:
        if smt2_path.exists():
            raise RuntimeError(f"refusing to overwrite {smt2_path}")
        smt2_path.write_text(
            "(set-logic QF_BV)\n"
            + solver.sexpr()
            + "\n(check-sat)\n(get-model)\n"
        )
    status = solver.check()
    result: dict[str, object] = {
        "signatures": list(signatures),
        "data_groups_per_signature": DATA_GROUPS,
        "lane_count": lane_count,
        "candidate_micro_operations": len(rows) * lane_count,
        "physical_channel_domain": {
            "count": len(channels),
            "coordinates": "eight dwords times bits 0..30",
            "excluded": "all eight dword bit-31 zero-padding channels",
        },
        "logical_opcode_positions": lane_count * OPCODE_BITS,
        "constraints": {
            "one_physical_channel_per_logical_opcode_bit": True,
            "all_sources_distinct": True,
            "fixed_xor_polarity": allow_inversion,
            "maximum_unrecognized_candidate_opcodes": max_unrecognized,
            "lane_symmetry_break_only": "source[lane,bit0] strictly increasing",
        },
        "timeout_ms": timeout_ms,
        "status": str(status).upper(),
        "reason_unknown": solver.reason_unknown() if status == z3.unknown else None,
    }
    if status == z3.sat:
        model = solver.model()
        mapping = []
        decoded = {}
        for lane in range(lane_count):
            lane_mapping = []
            for bit in range(OPCODE_BITS):
                index = model.eval(sources[lane][bit]).as_long()
                dword, physical_bit = channels[index]
                lane_mapping.append(
                    {
                        "logical_opcode_bit": bit,
                        "physical_channel_index": index,
                        "dword": dword,
                        "bit": physical_bit,
                        "inverted": z3.is_true(
                            model.eval(polarities[lane][bit])
                        ),
                    }
                )
            mapping.append(lane_mapping)
        for signature in signatures:
            decoded[signature] = [
                [
                    f"{model.eval(opcodes[(signature, group, lane)]).as_long():03X}"
                    for lane in range(lane_count)
                ]
                for group in range(DATA_GROUPS)
            ]
        transfer = {}
        for signature in rows_by_signature:
            values = []
            for row in rows_by_signature[signature]:
                for lane_mapping in mapping:
                    opcode_value = sum(
                        (
                            ((row[int(item["dword"])] >> int(item["bit"])) & 1)
                            ^ int(bool(item["inverted"]))
                        )
                        << int(item["logical_opcode_bit"])
                        for item in lane_mapping
                    )
                    values.append(opcode_value)
            transfer[signature] = {
                "recognized": sum(
                    later.recognized_opcode(value) is not None for value in values
                ),
                "candidate_micro_operations": len(values),
            }
        result["model_mapping"] = mapping
        result["decoded_opcodes"] = decoded
        result["model_transfer_score"] = transfer
    return result


def padding_surface(
    rows: dict[str, tuple[tuple[int, ...], ...]]
) -> dict[str, object]:
    result = {}
    for signature, groups in rows.items():
        first_eighteen = [
            (group, dword)
            for group, row in enumerate(groups[:18])
            for dword, word in enumerate(row)
            if (word >> 31) & 1
        ]
        final_group = [
            dword for dword, word in enumerate(groups[18]) if (word >> 31) & 1
        ]
        result[signature] = {
            "set_bit31_positions_first_18_groups": [
                {"group": group, "dword": dword}
                for group, dword in first_eighteen
            ],
            "set_bit31_count_first_18_groups": len(first_eighteen),
            "set_bit31_dwords_final_group": final_group,
            "set_bit31_count_final_group": len(final_group),
        }
    return result


def run_bitwuzla(
    solver_path: Path, smt2_path: Path, timeout_ms: int, output_path: Path
) -> dict[str, object]:
    if output_path.exists():
        raise RuntimeError(f"refusing to overwrite {output_path}")
    version = subprocess.run(
        [str(solver_path), "-V"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    completed = subprocess.run(
        [str(solver_path), "-t", str(timeout_ms), "-m", str(smt2_path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_ms / 1000 + 30,
    )
    output_path.write_text(completed.stdout)
    first_line = completed.stdout.splitlines()[0] if completed.stdout else ""
    if first_line not in ("sat", "unsat", "unknown"):
        raise RuntimeError(
            f"unexpected Bitwuzla result {first_line!r}: {completed.stderr}"
        )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Bitwuzla exited {completed.returncode}: {completed.stderr}"
        )
    return {
        "status": first_line.upper(),
        "timeout_ms": timeout_ms,
        "solver": "Bitwuzla",
        "solver_version": version,
        "solver_sha256": digest(solver_path),
        "smt2_name": smt2_path.name,
        "smt2_bytes": smt2_path.stat().st_size,
        "smt2_sha256": digest(smt2_path),
        "solver_output_name": output_path.name,
        "solver_output_sha256": digest(output_path),
        "stderr": completed.stderr,
    }


def random_control_rows(seed: int) -> dict[str, tuple[tuple[int, ...], ...]]:
    generator = random.Random(seed)
    return {
        f"random_{seed:08X}": tuple(
            tuple(generator.getrandbits(31) for _ in range(DWORDS))
            for _ in range(DATA_GROUPS)
        )
    }


def build_report(
    path: Path, artifact_dir: Path, solver_path: Path, timeout_ms: int
) -> dict[str, object]:
    source = json.loads(path.read_text())
    rows = load_rows(source)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    individual_fits = {
        signature: solve(rows, (signature,), LANES, timeout_ms)
        for signature in SIGNATURES
    }
    if any(row["status"] != "SAT" for row in individual_fits.values()):
        raise RuntimeError("expected single-body opcode fits did not reproduce")

    controls = {}
    for seed in RANDOM_SEEDS:
        control_rows = random_control_rows(seed)
        fit = solve(control_rows, tuple(control_rows), LANES, timeout_ms)
        controls[f"{seed:08X}"] = {
            "status": fit["status"],
            "candidate_micro_operations": fit["candidate_micro_operations"],
            "recognized": next(iter(fit.get("model_transfer_score", {}).values()))[
                "recognized"
            ] if fit["status"] == "SAT" else None,
        }
    if any(row["status"] != "SAT" for row in controls.values()):
        raise RuntimeError(
            f"expected random-control opcode fits did not reproduce: {controls}"
        )

    no_invert_smt2 = artifact_dir / "h1504_joint_single_lane_noinvert.smt2"
    no_invert_output = artifact_dir / "h1504_joint_single_lane_noinvert.bitwuzla.txt"
    z3_no_invert = solve(
        rows, SIGNATURES, 1, 1, no_invert_smt2, allow_inversion=False
    )
    no_invert = run_bitwuzla(
        solver_path, no_invert_smt2, timeout_ms, no_invert_output
    )
    if no_invert["status"] != "UNSAT":
        raise RuntimeError("exact joint non-inverting UNSAT result did not reproduce")

    invert_smt2 = artifact_dir / "h1504_joint_single_lane_invert.smt2"
    invert_output = artifact_dir / "h1504_joint_single_lane_invert.bitwuzla.txt"
    z3_invert = solve(
        rows, SIGNATURES, 1, 1, invert_smt2, allow_inversion=True
    )
    invert = run_bitwuzla(solver_path, invert_smt2, timeout_ms, invert_output)

    return {
        "query": "pentium_pro_exact_cross_dword_opcode_bit_permutation",
        "status": "exact_noninverting_transfer_wall_inverting_query_bounded",
        "physical_bit31_surface": padding_surface(rows),
        "single_body_three_lane_fits": individual_fits,
        "random_single_body_controls": {
            "construction": (
                "nineteen independent eight-dword rows with 31 random low bits "
                "and dword bit 31 fixed to zero"
            ),
            "results": controls,
        },
        "joint_single_lane_searches": {
            "noninverting": {
                "z3_one_millisecond_generation_status": z3_no_invert["status"],
                **no_invert,
            },
            "independent_fixed_per_opcode_bit_inversion": {
                "z3_one_millisecond_generation_status": z3_invert["status"],
                **invert,
            },
        },
        "proof": {
            "noninverting_single_lane": (
                "UNSAT: no injective selection of twelve physical channels from "
                "the 248 non-bit31 channels makes all 38 address-aligned 0x611/0x612 "
                "values recognized public-P6 opcodes"
            ),
            "three_lane_implication": (
                "a three-lane mapping satisfying the same every-opcode condition "
                "would contain a satisfying single lane, so it is also impossible"
            ),
            "single_body_fit_control": (
                "each body and all four deterministic random controls admit 57/57 "
                "three-lane opcode fits, so isolated SAT is a multiple-choice fit"
            ),
        },
        "interpretation": {
            "confirmed": [
                "the early 0x611/0x612 bit31 surface differs exactly from 0x617/0x619",
                "arbitrary single-body opcode-bit mappings fit random data and do not transfer",
                (
                    "the two early bodies have no shared non-inverting injective "
                    "opcode-bit mapping under the every-opcode-recognized condition"
                ),
            ],
            "not_claimed": [
                "the public P6 opcode map is complete for Pentium Pro patches",
                "valid patch bodies contain no unknown opcodes",
                "all fixed-inversion mappings are impossible when that query is UNKNOWN",
                "all Pentium Pro physical-to-logical mappings are impossible",
                "an R59 selector or absolute base-ROM state",
            ],
        },
        "dependencies": {
            "h1467_report_sha256": digest(path),
            "z3_version": z3.get_version_string(),
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1467", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("artifact_dir", type=Path)
    parser.add_argument("--bitwuzla", type=Path, required=True)
    parser.add_argument("--timeout-ms", type=int, default=60_000)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")
    report = build_report(
        arguments.h1467,
        arguments.artifact_dir,
        arguments.bitwuzla,
        arguments.timeout_ms,
    )
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(text)
    print(
        json.dumps(
            {
                "output": str(arguments.output),
                "report_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "status": report["status"],
                "joint_noninverting": report["joint_single_lane_searches"]
                ["noninverting"]["status"],
                "joint_inverting": report["joint_single_lane_searches"]
                ["independent_fixed_per_opcode_bit_inversion"]["status"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
