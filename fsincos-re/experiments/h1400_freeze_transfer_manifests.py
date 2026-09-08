#!/usr/bin/env python3
"""Freeze replay-safe cross-entry transfer tests for the trig core.

This generator performs no x87 execution.  It uses only existing labels,
integer arithmetic, and software-model predictions.  Every proposed operand
must be absent, in either ``se sig`` or ``se:sig`` spelling, from every
repository-visible text file outside the output directory.  This deliberately
conservative operand-level exclusion is stronger than the required
(instruction, mode, operand) exclusion for the locally visible evidence.

The output distinguishes three logically different experiments:

* exact internal-residual isomorphs for R1158, R1378, and the representable
  unresolved terminal rows;
* adjacent reduced-entry brackets where an exact x87 inverse does not exist;
* independent large-argument reduction challenges, including operands on
  which the paired reciprocal quotient and standalone M66 quotient differ.

The manifests are immutable capture inputs.  Re-running without ``--verify``
refuses to overwrite them.  Hardware must not be consulted until the freeze
report and an external/private capture-ledger audit have both been accepted.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


M66 = (3 << 64) | 0x243F6A8885A308D3
TWO_OVER_PI_128 = (
    (0xA2F9836E4E441529 << 64) | 0xFC2757D1F534DDC0
)
MODES = ("rn", "rd", "ru", "rz")
INSTRUCTIONS = ("fsin", "fcos", "fsincos")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def op_text(se: int, sig: int) -> str:
    return f"{se:04x} {sig:016x}"


def split_op(op: str) -> tuple[int, int]:
    fields = op.replace(":", " ").split()
    if len(fields) != 2:
        raise ValueError(f"bad x87 operand: {op!r}")
    return int(fields[0], 16), int(fields[1], 16)


def x80_exact_integer(value: int, scale: int) -> str | None:
    """Encode ``value * 2**scale`` exactly as a normal x87 value."""

    if value <= 0:
        return None
    width = value.bit_length()
    shift = max(0, width - 64)
    if value & ((1 << shift) - 1):
        return None
    sig = value >> shift
    if not ((1 << 63) <= sig < (1 << 64)):
        return None
    # sig * 2**(unbiased-63) == value * 2**scale.
    unbiased = scale + shift + 63
    se = 0x3FFF + unbiased
    if not (0 < se < 0x7FFF):
        return None
    return op_text(se, sig)


def inverse_reduction(
    residual_sig: int, residual_scale: int, quotient: int, residual_side: int
) -> str | None:
    """Encode q*M66 + side*residual exactly, if 64 bits permit it."""

    if residual_scale > -65:
        raise ValueError("residual scale cannot be coarser than M66")
    m66_at_scale = M66 << (-65 - residual_scale)
    exact = quotient * m66_at_scale + residual_side * residual_sig
    return x80_exact_integer(exact, residual_scale)


def inverse_bracket(
    residual_sig: int,
    residual_scale: int,
    quotient: int,
    residual_side: int,
) -> list[tuple[str, str, int]]:
    """Return the two adjacent x87 encodings around an unencodable inverse.

    The integer error and resulting residual are expressed at residual_scale.
    """

    m66_at_scale = M66 << (-65 - residual_scale)
    exact = quotient * m66_at_scale + residual_side * residual_sig
    width = exact.bit_length()
    shift = max(0, width - 64)
    unit = 1 << shift
    low = exact & -unit
    if low == exact:
        raise ValueError("exact inverse unexpectedly exists")
    result = []
    for name, represented in (("lower", low), ("upper", low + unit)):
        operand = x80_exact_integer(represented, residual_scale)
        if operand is None:
            raise ValueError("failed to encode adjacent inverse")
        error = represented - exact
        actual_residual = residual_side * residual_sig + error
        result.append((name, operand, actual_residual))
    return result


def sky_quotient(sig: int, exponent: int) -> int:
    product = sig * TWO_OVER_PI_128
    shift = 191 - exponent
    quotient, remainder = divmod(product, 1 << shift)
    half = 1 << (shift - 1)
    if remainder > half or (remainder == half and quotient & 1):
        quotient += 1
    return quotient


def m66_quotient(sig: int, exponent: int) -> int:
    dividend = sig << (exponent + 2)
    quotient, remainder = divmod(dividend, M66)
    if 2 * remainder > M66:
        quotient += 1
    return quotient


def normalize_output(line: str, lane: str) -> str:
    fields = line.split()
    if not fields:
        raise RuntimeError("empty software-model output")
    if fields[0] == "C2":
        return "C2"
    if fields[0] != "OK":
        raise RuntimeError(f"bad software-model output: {line!r}")
    if len(fields) == 3:
        return f"{fields[1].lower()}:{fields[2].lower()}"
    if len(fields) == 5 and lane in ("sin", "cos"):
        offset = 1 if lane == "sin" else 3
        return f"{fields[offset].lower()}:{fields[offset + 1].lower()}"
    raise RuntimeError(f"wrong output arity for lane {lane}: {line!r}")


def model_outputs(
    binary: Path,
    instruction: str,
    mode: str,
    lane: str,
    operands: list[str],
) -> list[str]:
    command = [str(binary), "--batch"]
    if instruction == "fsin":
        command.append("--fsin-standalone")
    elif instruction == "fcos":
        command.append("--fcos-standalone")
    elif instruction != "fsincos":
        raise ValueError(instruction)
    if mode != "rn":
        command.append(f"--rc={mode}")
    completed = subprocess.run(
        command,
        input="".join(f"{op}\n" for op in operands),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    lines = completed.stdout.splitlines()
    if len(lines) != len(operands):
        raise RuntimeError(
            f"{binary} returned {len(lines)} lines for {len(operands)} inputs"
        )
    return [normalize_output(line, lane) for line in lines]


def repository_collisions(
    repo: Path, output_dir: Path, operands: set[str]
) -> set[str]:
    """Find candidate operands already printed in repository-visible text."""

    if not operands:
        return set()
    patterns = []
    for op in sorted(operands):
        patterns.extend((op, op.replace(" ", ":")))
    relative_output = output_dir.relative_to(repo)
    command = [
        "rg",
        "-I",
        "-i",
        "-o",
        "--no-filename",
        "-F",
        "-f",
        "-",
        "--glob",
        f"!**/{relative_output}/**",
        str(repo),
    ]
    completed = subprocess.run(
        command,
        input="\n".join(patterns) + "\n",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode not in (0, 1):
        raise RuntimeError(f"repository duplicate scan failed: {completed.stderr}")
    return {
        hit.strip().lower().replace(":", " ")
        for hit in completed.stdout.splitlines()
        if hit.strip()
    }


@dataclass(frozen=True)
class TransferPoint:
    family: str
    law: str
    transfer_kind: str
    mode: str
    operand: str
    residual_anchor: str
    residual_scale: int
    actual_residual: str
    quotient: int
    external_sign: int
    residual_side: int
    source_evidence: str
    anchor_hw: str
    anchor_features: str


def read_r1158(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    return [
        row
        for row in rows
        if row["verdict"] == "EXACT" and row["counterfactual_verdict"] == "MISS"
    ]


def select_r1158(
    path: Path, incumbent: Path, ablated: Path
) -> list[TransferPoint]:
    # The boundary blind also records the pre-R1158 base verdict.  Requiring
    # a base miss makes every standalone transfer point an actual recurrence
    # ablation separator, rather than merely an exact state representative.
    rows = [row for row in read_r1158(path) if row["base_verdict"] == "MISS"]
    targets = (1, 2, 3, 4, 5, 6, 7, 8, 9, 16, 17, 32, 35)
    selected: list[TransferPoint] = []
    used_anchors: set[str] = set()
    feature_counts: Counter[str] = Counter()
    mode_counts: Counter[str] = Counter()
    for index, quotient in enumerate(targets):
        preferred_side = 1 if index % 2 == 0 else -1
        external_sign = -1 if quotient in (3, 6, 9, 35) else 1
        candidates = []
        for row in rows:
            for residual_side in (preferred_side, -preferred_side):
                operand = inverse_reduction(
                    int(row["sig"], 16), -67, quotient, residual_side
                )
                if operand is None:
                    continue
                if external_sign < 0:
                    se, sig = split_op(operand)
                    operand = op_text(se | 0x8000, sig)
                features = (
                    f"mode={row['mode']}",
                    f"theta={row['theta']}",
                    f"ce={row['ce']}",
                    f"s4={row['s4']}",
                    f"side={row['side']}",
                    f"boundary={row['boundary_side']}",
                    f"fire={row['candidate_fire']}",
                    f"choice={row['physical_choice']}",
                )
                novelty = sum(feature_counts[feature] == 0 for feature in features)
                score = (
                    row["op"] in used_anchors,
                    residual_side != preferred_side,
                    mode_counts[row["mode"]],
                    -novelty,
                    row["op"],
                )
                candidates.append((score, row, residual_side, operand, features))
        # A transfer challenge is useful only if the law changes the selected
        # architectural lane.  Directed rounding and the output sign can hide
        # a one-unit internal difference, so test visibility on the exact
        # transformed operand before freezing the representative.
        instruction, lane, _ = target_instruction(quotient)
        visible: set[tuple[str, str]] = set()
        for mode in MODES:
            mode_candidates = [item for item in candidates if item[1]["mode"] == mode]
            if not mode_candidates:
                continue
            operands = [item[3] for item in mode_candidates]
            incumbent_outputs = model_outputs(
                incumbent, instruction, mode, lane, operands
            )
            ablated_outputs = model_outputs(
                ablated, instruction, mode, lane, operands
            )
            for item, on, off in zip(mode_candidates, incumbent_outputs, ablated_outputs):
                if on != off:
                    visible.add((item[1]["op"], item[3]))
        candidates = [
            item for item in candidates if (item[1]["op"], item[3]) in visible
        ]
        if not candidates:
            raise RuntimeError(
                f"no architecturally visible exact R1158 inverse for quotient {quotient}"
            )
        _, row, residual_side, operand, features = min(candidates, key=lambda item: item[0])
        used_anchors.add(row["op"])
        mode_counts[row["mode"]] += 1
        feature_counts.update(features)
        selected.append(
            TransferPoint(
                family="r1158_exact",
                law="R1158_lower_radix_recurrence",
                transfer_kind="exact_internal_residual",
                mode=row["mode"],
                operand=operand,
                residual_anchor=row["op"],
                residual_scale=-67,
                actual_residual=f"{residual_side * int(row['sig'], 16):+d}",
                quotient=quotient,
                external_sign=external_sign,
                residual_side=residual_side,
                source_evidence="h1161_3ffb_boundary_score.tsv",
                anchor_hw=row["hw"],
                anchor_features=";".join(features),
            )
        )
    return selected


def select_r1378(path: Path) -> list[TransferPoint]:
    with path.open(newline="") as source:
        rows = {row["op"]: row for row in csv.DictReader(source, delimiter="\t")}
    requests = (
        ("3ffc d9c0000002f12b2e", 1, -1, ("rn",)),
        ("3ffc d9c0000002f12b2e", 3, 1, ("rn",)),
        ("3ffc d0c0000007d541d8", 4, -1, ("rd", "ru")),
        ("3ffc dfdffffffef39810", 8, 1, ("rn",)),
    )
    result = []
    for anchor, quotient, residual_side, modes in requests:
        row = rows[anchor]
        sig = split_op(anchor)[1]
        operand = inverse_reduction(sig, -66, quotient, residual_side)
        if operand is None:
            raise RuntimeError(f"declared R1378 inverse is not exact: {anchor}")
        for mode in modes:
            if mode not in row["changed_modes"].split(","):
                raise RuntimeError(f"{anchor} does not separate R1378 under {mode}")
            result.append(
                TransferPoint(
                    family="r1378_exact",
                    law="R1378_attached_X67_Y64_fourth_power",
                    transfer_kind="exact_internal_residual",
                    mode=mode,
                    operand=operand,
                    residual_anchor=anchor,
                    residual_scale=-66,
                    actual_residual=f"{residual_side * sig:+d}",
                    quotient=quotient,
                    external_sign=1,
                    residual_side=residual_side,
                    source_evidence="h1362_x67_y64_replacement_manifest.tsv",
                    anchor_hw="",
                    anchor_features=(
                        f"q={row['q']};cut={row['cut']};"
                        f"square_low3={row['square_low3']};"
                        f"factor_delta={row['factor_delta']}"
                    ),
                )
            )
    return result


def read_unresolved(path: Path) -> list[dict[str, str]]:
    rows = []
    for line in path.read_text().splitlines():
        fields = line.split("\t")
        if len(fields) != 7:
            raise RuntimeError(f"unexpected unresolved row: {line!r}")
        rows.append(
            {
                "corpus": fields[0],
                "instruction": fields[1],
                "mode": fields[2],
                "index": fields[3],
                "op": fields[4],
                "current": fields[5],
                "hw": fields[6],
            }
        )
    return rows


def select_unresolved(path: Path) -> list[TransferPoint]:
    rows = read_unresolved(path)
    exact_requests = {
        "3ffc d920000000749eaa": (1, 1),
        "3ffc d0d000000cc0b3f8": (4, -1),
    }
    result = []
    seen_exact: set[tuple[str, str]] = set()
    for row in rows:
        anchor = row["op"]
        if anchor not in exact_requests:
            continue
        quotient, residual_side = exact_requests[anchor]
        operand = inverse_reduction(
            split_op(anchor)[1], -66, quotient, residual_side
        )
        if operand is None:
            raise RuntimeError(f"declared unresolved inverse is not exact: {anchor}")
        key = (row["mode"], anchor)
        if key in seen_exact:
            continue
        seen_exact.add(key)
        result.append(
            TransferPoint(
                family="unresolved_exact",
                law="open_R59_or_R1382_selector",
                transfer_kind="exact_internal_residual",
                mode=row["mode"],
                operand=operand,
                residual_anchor=anchor,
                residual_scale=-66,
                actual_residual=f"{residual_side * split_op(anchor)[1]:+d}",
                quotient=quotient,
                external_sign=1,
                residual_side=residual_side,
                source_evidence="h1378_x67y64_attached_noledger_misses.tsv",
                anchor_hw=row["hw"],
                anchor_features=f"corpus={row['corpus']};index={row['index']}",
            )
        )

    # Exact inverse reduction is impossible for these odd-low-bit residuals.
    # Freeze the two adjacent representable inputs and label them as brackets.
    quotient_cycle = iter((1, 4, 5, 8, 9, 16, 17, 32, 33))
    by_anchor: dict[str, dict[str, str]] = {}
    for row in rows:
        by_anchor.setdefault(row["op"], row)
    for anchor, row in sorted(by_anchor.items()):
        if anchor in exact_requests:
            continue
        quotient = next(quotient_cycle)
        sig = split_op(anchor)[1]
        if inverse_reduction(sig, -66, quotient, 1) is not None:
            raise RuntimeError(f"expected nonrepresentable anchor is exact: {anchor}")
        for bracket, operand, actual_residual in inverse_bracket(sig, -66, quotient, 1):
            result.append(
                TransferPoint(
                    family="unresolved_bracket",
                    law="open_R59_selector",
                    transfer_kind=f"adjacent_{bracket}_not_isomorphic",
                    mode=row["mode"],
                    operand=operand,
                    residual_anchor=anchor,
                    residual_scale=-66,
                    actual_residual=f"{actual_residual:+d}",
                    quotient=quotient,
                    external_sign=1,
                    residual_side=1,
                    source_evidence="h1378_x67y64_attached_noledger_misses.tsv",
                    anchor_hw=row["hw"],
                    anchor_features=(
                        f"corpus={row['corpus']};index={row['index']};"
                        "exact_inverse=impossible_due_discarded_low_bits"
                    ),
                )
            )
    return result


def cancellation_points(existing: set[str]) -> list[TransferPoint]:
    """Construct fresh M66-grid cancellation cases in distant binades."""

    result = []
    modes = iter(("rn", "rd", "ru", "rz", "rn", "rd", "ru", "rz"))
    for exponent in (8, 16, 24, 32, 40, 48, 56, 62):
        modulus = 1 << (exponent + 2)
        inverse = pow(M66, -1, modulus)
        chosen = None
        for distance in range(1, 1_000_000):
            for residual in (distance, -distance):
                quotient = (-residual * inverse) % modulus
                numerator = quotient * M66 + residual
                if numerator <= 0 or numerator % modulus:
                    continue
                sig = numerator // modulus
                if not ((1 << 63) <= sig < (1 << 64)):
                    continue
                operand = op_text(0x3FFF + exponent, sig)
                if operand in existing:
                    continue
                if m66_quotient(sig, exponent) != quotient:
                    continue
                chosen = (operand, quotient, residual)
                break
            if chosen:
                break
        if chosen is None:
            raise RuntimeError(f"no fresh cancellation point for exponent {exponent}")
        operand, quotient, residual = chosen
        existing.add(operand)
        result.append(
            TransferPoint(
                family="large_cancellation",
                law="M66_exact_reduction",
                transfer_kind="exact_large_argument_cancellation",
                mode=next(modes),
                operand=operand,
                residual_anchor="",
                residual_scale=-65,
                actual_residual=f"{residual:+d}",
                quotient=quotient,
                external_sign=1,
                residual_side=1 if residual > 0 else -1,
                source_evidence="software_constructed_M66_modular_inverse",
                anchor_hw="",
                anchor_features=(
                    f"external_binade={exponent};"
                    f"paired_quotient={sky_quotient(split_op(operand)[1], exponent)}"
                ),
            )
        )
    return result


def quotient_disagreement_points(existing: set[str]) -> list[TransferPoint]:
    """Find operands where the two currently coded quotient entries differ."""

    result = []
    starts = {
        48: 14456075972404953093,
        56: 13428074158442782893,
        60: 12914073251461697793,
        61: 15091416033930120470,
        62: 17268758816398543147,
    }
    for index, exponent in enumerate((48, 56, 60, 61, 62)):
        chosen = None
        for offset in range(2_000_000):
            sig = starts[exponent] + offset
            if sig >= 1 << 64:
                break
            operand = op_text(0x3FFF + exponent, sig)
            if operand in existing:
                continue
            q_sky = sky_quotient(sig, exponent)
            q_m66 = m66_quotient(sig, exponent)
            if q_sky != q_m66:
                chosen = (operand, q_sky, q_m66)
                break
        if chosen is None:
            raise RuntimeError(f"no fresh quotient disagreement in binade {exponent}")
        operand, q_sky, q_m66 = chosen
        existing.add(operand)
        result.append(
            TransferPoint(
                family="quotient_disagreement_guard",
                law="shared_table_guard_over_quotient_disagreement",
                transfer_kind="paired_table_short_circuit_at_quotient_disagreement",
                mode=MODES[index % len(MODES)],
                operand=operand,
                residual_anchor="",
                residual_scale=-65,
                actual_residual="",
                quotient=q_m66,
                external_sign=1,
                residual_side=0,
                source_evidence="software_selected_quotient_disagreement",
                anchor_hw="",
                anchor_features=(
                    f"external_binade={exponent};sky_N={q_sky};m66_N={q_m66}"
                ),
            )
        )
    return result


def architecture_rows() -> list[dict[str, str]]:
    """Create distinct-operand, masked-exception architectural probes."""

    specs = [
        # Basic state transitions and sticky-flag preservation.
        ("A001", "STATE.REPLACE.FSIN", "fsin", "rn", "pc64", "3f", 3, "clear", "normal"),
        ("A002", "STATE.REPLACE.FCOS", "fcos", "rd", "pc64", "3f", 5, "pe", "normal"),
        ("A003", "STATE.PUSH.FSINCOS", "fsincos", "ru", "pc64", "3f", 4, "ie", "normal"),
        ("A004", "STATE.FULL.FSIN", "fsin", "rz", "pc64", "3f", 8, "clear", "normal"),
        ("A005", "STATE.FULL.FCOS", "fcos", "rn", "pc64", "3f", 8, "pe", "normal"),
        ("A006", "STATE.DEPTH7.FSINCOS", "fsincos", "rd", "pc64", "3f", 7, "clear", "normal"),
        ("A007", "STATE.OVERFLOW.FSINCOS", "fsincos", "ru", "pc64", "3f", 8, "clear", "normal"),
        # Paired special/encoding coverage with full status and stack capture.
        ("A008", "ENC.QNAN.PAIRED", "fsincos", "rn", "pc64", "3f", 1, "clear", "qnan"),
        ("A009", "ENC.SNAN.PAIRED", "fsincos", "rd", "pc64", "3f", 1, "clear", "snan"),
        ("A010", "ENC.INFINITY.PAIRED", "fsincos", "ru", "pc64", "3f", 1, "clear", "infinity"),
        ("A011", "ENC.UNNORMAL.PAIRED", "fsincos", "rz", "pc64", "3f", 1, "clear", "unnormal"),
        ("A012", "ENC.SUBNORMAL.PAIRED", "fsincos", "rn", "pc64", "3f", 1, "clear", "subnormal"),
        ("A013", "ENC.PSEUDODENORM.PAIRED", "fsincos", "rd", "pc64", "3f", 1, "clear", "pseudo_denormal"),
        ("A014", "DOMAIN.C2.BELOW.PAIRED", "fsincos", "ru", "pc64", "3f", 2, "clear", "c2_below"),
        ("A015", "DOMAIN.C2.AT.PAIRED", "fsincos", "rz", "pc64", "3f", 2, "clear", "c2_at"),
        # Precision-control transfer beyond h172's standalone-FSIN evidence.
        ("A016", "CW.PC24.FCOS", "fcos", "rn", "pc24", "3f", 1, "clear", "normal"),
        ("A017", "CW.PC53.FCOS", "fcos", "rn", "pc53", "3f", 1, "clear", "normal"),
        ("A018", "CW.PC64.FCOS", "fcos", "rn", "pc64", "3f", 1, "clear", "normal"),
        ("A019", "CW.PC24.FSINCOS", "fsincos", "rd", "pc24", "3f", 1, "clear", "normal"),
        ("A020", "CW.PC53.FSINCOS", "fsincos", "rd", "pc53", "3f", 1, "clear", "normal"),
        ("A021", "CW.PC64.FSINCOS", "fsincos", "rd", "pc64", "3f", 1, "clear", "normal"),
        # Full-status behavior on fresh finite inexact operations.
        ("A022", "FLAGS.FINITE.FSIN", "fsin", "ru", "pc64", "3f", 1, "clear", "normal"),
        ("A023", "FLAGS.FINITE.FCOS", "fcos", "rz", "pc64", "3f", 1, "ie", "normal"),
        ("A024", "FLAGS.FINITE.FSINCOS", "fsincos", "rn", "pc64", "3f", 1, "pe", "normal"),
    ]
    rows = []
    for index, (case_id, requirement, insn, mode, pc, masks, depth, prior, kind) in enumerate(specs):
        salt = 0x2D91A7C35E680B4D + index * 0x01010101010101
        if kind == "normal":
            se, sig = 0x3FFD + (index % 2), 0x8000000000000000 | salt
        elif kind == "qnan":
            se, sig = 0x7FFF, 0xC000000000000000 | salt
        elif kind == "snan":
            se, sig = 0x7FFF, 0x8000000000000001 | (salt & 0x3FFFFFFFFFFFFFFF)
        elif kind == "infinity":
            se, sig = 0xFFFF, 0x8000000000000000
        elif kind == "unnormal":
            se, sig = 0x4123, 0x2000000000000000 | salt
        elif kind == "subnormal":
            se, sig = 0x0000, 0x0010000000000001 | (salt & 0x000FFFFFFFFFFFFF)
        elif kind == "pseudo_denormal":
            se, sig = 0x0000, 0x8000000000000000 | salt
        elif kind == "c2_below":
            se, sig = 0x403D, 0xFFFFFFFFFFF00000 | (salt & 0xFFFFF)
        elif kind == "c2_at":
            se, sig = 0x403E, 0x8000000000000000 | (salt & 0xFFFFF)
        else:
            raise ValueError(kind)
        if kind == "c2_at":
            expected_stack = "TOP and all registers unchanged; C2=1; no push"
        elif insn == "fsincos" and depth == 8:
            expected_stack = (
                "measure masked stack-overflow result, TOP, C1 and tags; "
                "no predeclared value assumption"
            )
        elif insn == "fsincos":
            expected_stack = "TOP decremented; ST0=cos; ST1=sin; deeper values preserved"
        else:
            expected_stack = "TOP unchanged; ST0 replaced; deeper tags/values preserved"
        rows.append(
            {
                "case_id": case_id,
                "requirement": requirement,
                "instruction": insn,
                "mode": mode,
                "precision_control": pc,
                "exception_masks_hex": masks,
                "pre_stack_depth": str(depth),
                "prior_flags": prior,
                "operand": op_text(se, sig),
                "encoding_class": kind,
                "expected_stack_relation": expected_stack,
                "required_observation": (
                    "before/after CW,SW,TOP,abridged-tag and all eight raw x87 registers"
                ),
                "capture_tool": "x87_state_capture.c",
                "capture_state": "FROZEN_UNOPENED",
            }
        )
    return rows


def target_instruction(quotient: int) -> tuple[str, str, int]:
    if quotient & 1:
        instruction, lane = "fsin", "sin"
    else:
        instruction, lane = "fcos", "cos"
    # Sign of the selected cosine projection for a positive external input.
    sign = -1 if quotient % 4 in (2, 3) else 1
    return instruction, lane, sign


def expand_points(points: list[TransferPoint]) -> list[dict[str, str]]:
    rows = []
    case_number = 1
    for point in points:
        standalone, lane, projection_sign = target_instruction(point.quotient)
        if point.external_sign < 0 and standalone == "fsin":
            projection_sign *= -1
        instructions = (standalone, "fsincos")
        for instruction in instructions:
            rows.append(
                {
                    "case_id": f"T{case_number:04d}",
                    "family": point.family,
                    "law": point.law,
                    "transfer_kind": point.transfer_kind,
                    "instruction": instruction,
                    "target_lane": lane,
                    "mode": point.mode,
                    "precision_control": "pc64",
                    "operand": point.operand,
                    "external_sign": str(point.external_sign),
                    "reduction_n_magnitude": str(point.quotient),
                    "quadrant": str(point.quotient & 3),
                    "cosine_projection_sign": str(projection_sign),
                    "residual_side_before_external_sign": str(point.residual_side),
                    "residual_anchor": point.residual_anchor,
                    "residual_scale": str(point.residual_scale),
                    "actual_residual_integer": point.actual_residual,
                    "source_evidence": point.source_evidence,
                    "anchor_hardware": point.anchor_hw,
                    "anchor_features": point.anchor_features,
                    "model_incumbent": "",
                    "model_ablation": "",
                    "ablation_visible": "",
                    "capture_state": "FROZEN_UNOPENED",
                }
            )
            case_number += 1
    return rows


def add_predictions(
    rows: list[dict[str, str]], incumbent: Path, ablations: dict[str, Path]
) -> None:
    groups: dict[tuple[str, str, str], list[int]] = {}
    for index, row in enumerate(rows):
        groups.setdefault(
            (row["instruction"], row["mode"], row["target_lane"]), []
        ).append(index)
    for (instruction, mode, lane), indexes in groups.items():
        operands = [rows[index]["operand"] for index in indexes]
        outputs = model_outputs(incumbent, instruction, mode, lane, operands)
        for index, output in zip(indexes, outputs):
            rows[index]["model_incumbent"] = output
    law_binary = {
        "R1158_lower_radix_recurrence": ablations["r1158"],
        "R1378_attached_X67_Y64_fourth_power": ablations["r1378"],
    }
    for law, binary in law_binary.items():
        law_indexes = [index for index, row in enumerate(rows) if row["law"] == law]
        regrouped: dict[tuple[str, str, str], list[int]] = {}
        for index in law_indexes:
            row = rows[index]
            regrouped.setdefault(
                (row["instruction"], row["mode"], row["target_lane"]), []
            ).append(index)
        for (instruction, mode, lane), indexes in regrouped.items():
            operands = [rows[index]["operand"] for index in indexes]
            outputs = model_outputs(binary, instruction, mode, lane, operands)
            for index, output in zip(indexes, outputs):
                rows[index]["model_ablation"] = output
                rows[index]["ablation_visible"] = str(
                    output != rows[index]["model_incumbent"]
                ).lower()


def write_tsv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        raise RuntimeError(f"refusing to write empty manifest {path}")
    with path.open("x", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=tuple(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def write_capture_inputs(output_dir: Path, rows: list[dict[str, str]]) -> list[Path]:
    paths = []
    grouped: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault((row["instruction"], row["mode"]), []).append(row)
    capture_dir = output_dir / "core-inputs"
    capture_dir.mkdir()
    for (instruction, mode), group in sorted(grouped.items()):
        path = capture_dir / f"{instruction}_{mode}.txt"
        with path.open("x") as target:
            for row in group:
                target.write(row["operand"] + "\n")
        paths.append(path)
    return paths


def write_arch_input(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("x") as target:
        target.write(
            "# case instruction mode pc exception_masks_hex "
            "pre_stack_depth prior_flags se sig\n"
        )
        for row in rows:
            se, sig = row["operand"].split()
            target.write(
                f"{row['case_id']} {row['instruction']} {row['mode']} "
                f"{row['precision_control']} {row['exception_masks_hex']} "
                f"{row['pre_stack_depth']} {row['prior_flags']} {se} {sig}\n"
            )


def verify_frozen(output_dir: Path) -> None:
    report = output_dir / "FREEZE.json"
    if not report.exists():
        raise SystemExit(f"missing freeze report: {report}")
    metadata = json.loads(report.read_text())
    failures = []
    for relative, expected in metadata["sha256"].items():
        path = output_dir / relative
        if not path.exists():
            failures.append(f"missing {relative}")
        elif sha256(path) != expected:
            failures.append(f"hash mismatch {relative}")
    if failures:
        raise SystemExit("frozen manifest verification failed:\n" + "\n".join(failures))
    print(
        f"verified {len(metadata['sha256'])} frozen files; "
        f"hardware_execution={metadata['hardware_execution']}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--incumbent", type=Path)
    parser.add_argument("--no-r1158", type=Path)
    parser.add_argument("--no-r1378", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    output_dir = args.output or repo / "transfer-tests" / "h1400"
    if args.verify:
        verify_frozen(output_dir)
        return
    binaries = (args.incumbent, args.no_r1158, args.no_r1378)
    if any(binary is None for binary in binaries):
        parser.error("freeze requires --incumbent, --no-r1158, and --no-r1378")
    assert args.incumbent and args.no_r1158 and args.no_r1378
    for binary in binaries:
        if not binary.is_file():
            parser.error(f"model binary does not exist: {binary}")
    if output_dir.exists():
        raise SystemExit(f"refusing to overwrite frozen directory {output_dir}")

    source_paths = {
        "r1158": repo / "tmp/ledger33/current/h1161_3ffb_boundary_score.tsv",
        "r1378": repo / "tmp/ledger33/current/h1362_x67_y64_replacement_manifest.tsv",
        "unresolved": repo / "tmp/ledger33/current/h1378_x67y64_attached_noledger_misses.tsv",
    }
    points = [
        *select_r1158(source_paths["r1158"], args.incumbent, args.no_r1158),
        *select_r1378(source_paths["r1378"]),
        *select_unresolved(source_paths["unresolved"]),
    ]

    # Reject any exact/bracket point already visible before using those values
    # as exclusions for the large-range constructive searches.
    point_operands = {point.operand for point in points}
    collisions = repository_collisions(repo, output_dir, point_operands)
    if collisions:
        raise RuntimeError(
            "candidate transfer operands already occur in the repository:\n"
            + "\n".join(sorted(collisions))
        )
    points.extend(cancellation_points(set(point_operands)))
    points.extend(quotient_disagreement_points({point.operand for point in points}))
    architecture = architecture_rows()
    all_operands = {point.operand for point in points} | {
        row["operand"] for row in architecture
    }
    architecture_operands = [row["operand"] for row in architecture]
    if len(architecture_operands) != len(set(architecture_operands)):
        raise RuntimeError("architecture manifest reuses an operand")
    collisions = repository_collisions(repo, output_dir, all_operands)
    if collisions:
        raise RuntimeError(
            "freshness audit found repository-visible operands:\n"
            + "\n".join(sorted(collisions))
        )

    core = expand_points(points)
    keys = [(row["instruction"], row["mode"], row["operand"]) for row in core]
    arch_keys = [
        (row["instruction"], row["mode"], row["operand"])
        for row in architecture
    ]
    if len(keys + arch_keys) != len(set(keys + arch_keys)):
        raise RuntimeError("duplicate (instruction, mode, operand) capture key")
    add_predictions(
        core,
        args.incumbent,
        {"r1158": args.no_r1158, "r1378": args.no_r1378},
    )

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir()
    core_path = output_dir / "core-transfer.tsv"
    arch_path = output_dir / "architecture-semantics.tsv"
    arch_input_path = output_dir / "architecture-state-inputs.txt"
    write_tsv(core_path, core)
    write_tsv(arch_path, architecture)
    write_arch_input(arch_input_path, architecture)
    input_paths = write_capture_inputs(output_dir, core)

    counts = Counter(row["family"] for row in core)
    counts.update(f"arch.{row['encoding_class']}" for row in architecture)
    metadata = {
        "schema": "fsincos-h1400-freeze-v1",
        "capture_state": "FROZEN_UNOPENED",
        "hardware_execution": "none",
        "selection_inputs": {
            name: {"path": str(path.relative_to(repo)), "sha256": sha256(path)}
            for name, path in source_paths.items()
        },
        "software_models": {
            "incumbent_sha256": sha256(args.incumbent),
            "no_r1158_sha256": sha256(args.no_r1158),
            "no_r1378_sha256": sha256(args.no_r1378),
        },
        "architecture_harness": {
            "path": "capture-kit/x87_state_capture.c",
            "sha256": sha256(repo / "capture-kit/x87_state_capture.c"),
            "scope": "masked exceptions only; one target instruction per input row",
        },
        "freshness_scope": (
            "candidate operand absent in both 'se sig' and 'se:sig' spelling "
            "from repository-visible text outside transfer-tests/h1400"
        ),
        "external_ledger_gate": (
            "REQUIRED before capture: merge private/supplemental tuple ledger "
            "locally and reject any repeated (instruction,mode,operand); do not "
            "publish that ledger"
        ),
        "one_observation_policy": (
            "exactly one hardware observation per fresh "
            "(instruction,mode,operand); timing repetition forbidden"
        ),
        "core_rows": len(core),
        "architecture_rows": len(architecture),
        "unique_capture_keys": len(set(keys + arch_keys)),
        "counts": dict(sorted(counts.items())),
        "sha256": {},
    }
    frozen_paths = [core_path, arch_path, arch_input_path, *input_paths]
    metadata["sha256"] = {
        str(path.relative_to(output_dir)): sha256(path) for path in frozen_paths
    }
    report_path = output_dir / "FREEZE.json"
    with report_path.open("x") as target:
        json.dump(metadata, target, indent=2, sort_keys=True)
        target.write("\n")
    print(
        f"froze {len(core)} core legs and {len(architecture)} architecture legs "
        f"({metadata['unique_capture_keys']} unique capture keys); hardware=none"
    )


if __name__ == "__main__":
    main()
