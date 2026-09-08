#!/usr/bin/env python3
"""Characterize exact q=0/q>0 M66 reduction-history discriminators.

This is an analysis-only replay over the SAT witnesses preserved by h1404.
It does not search an operand corpus, execute x87 hardware, inspect capture
labels, or change the emulator.  For each exact external preimage it:

* verifies the integer reduction equation at scale 2^-66;
* constructs the signed q=0 representative of the same reduced residual;
* records every ripple carry or borrow entering every bit column;
* replays both instructions and all four rounding modes through the C model;
* compares the complete exposed cosine-producer trace for the projection that
  maps the external quadrant back to cosine; and
* ranks the resulting pairs by hardware-discriminator cleanliness.

For subtraction, both the natural borrow chain of ``A - R`` and the carry
chain of the equivalent fixed-width ``A + ~R + 1`` are retained.  Keeping
both conventions is essential: a physical carry wire has the opposite
polarity from a borrow wire, and the three exact preimages separate them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Iterable


M66 = (3 << 64) | 0x243F6A8885A308D3
MODES = ("rn", "rd", "ru", "rz")
INSTRUCTIONS = ("fsin", "fcos")
TARGET_ANCHORS = (
    "3ffc cca0000009242f0c",
    "3ffc d920000000749eaa",
    "3ffc d0d000000cc0b3f8",
)
TRACE_PREFIXES = (
    "DI_RED ",
    "DI_POLY ",
    "DI_TC ",
    "DI_R59 ",
    "DI_CRIT ",
    "DI_BS ",
    "DI_BR ",
)
REQUIRED_TRACE_STAGES = ("DI_RED", "DI_POLY", "DI_TC", "DI_R59", "DI_BR")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def parse_operand(text: str) -> tuple[int, int]:
    fields = text.lower().replace(":", " ").split()
    if len(fields) != 2:
        raise ValueError(f"bad x87 operand {text!r}")
    return int(fields[0], 16), int(fields[1], 16)


def operand_text(se: int, sig: int) -> str:
    return f"{se:04x} {sig:016x}"


def signed_direct_operand(anchor: str, residual_side: int) -> str:
    se, sig = parse_operand(anchor)
    if se != 0x3FFC:
        raise AssertionError(f"anchor is outside the direct 3ffc binade: {anchor}")
    if residual_side not in (-1, 1):
        raise AssertionError(f"bad residual side {residual_side}")
    return operand_text(se | (0x8000 if residual_side < 0 else 0), sig)


def set_columns(mask: int, width: int) -> list[int]:
    return [column for column in range(width + 1) if (mask >> column) & 1]


def runs(columns: Iterable[int]) -> list[list[int]]:
    result: list[list[int]] = []
    for column in columns:
        if result and column == result[-1][1] + 1:
            result[-1][1] = column
        else:
            result.append([column, column])
    return result


def history_summary(kind: str, mask: int, width: int) -> dict[str, Any]:
    columns = set_columns(mask, width)
    probes = (2, 3, 4, 11, 12, 54, 55, 60, 61, 63, 64, 65, 66, 67)
    return {
        "kind": kind,
        "width": width,
        "entering_column_mask_hex": f"0x{mask:0{(width + 4) // 4}x}",
        "set_count": len(columns),
        "set_runs_inclusive": runs(columns),
        "selected_columns": {str(column): int(column in columns)
                             for column in probes if column <= width},
    }


def add_carry_mask(left: int, right: int, width: int,
                   carry_in: int = 0) -> tuple[int, int]:
    """Return mask of carries entering columns 0..width and the exact sum."""

    carry = carry_in
    mask = 0
    result = 0
    for column in range(width):
        if carry:
            mask |= 1 << column
        total = ((left >> column) & 1) + ((right >> column) & 1) + carry
        result |= (total & 1) << column
        carry = total >> 1
    if carry:
        mask |= 1 << width
        result |= 1 << width
    return mask, result


def subtract_borrow_mask(minuend: int, subtrahend: int,
                         width: int) -> tuple[int, int]:
    """Return mask of borrows entering columns 0..width and A-B modulo 2^w."""

    borrow = 0
    mask = 0
    result = 0
    for column in range(width):
        if borrow:
            mask |= 1 << column
        digit = ((minuend >> column) & 1) - ((subtrahend >> column) & 1) - borrow
        if digit < 0:
            digit += 2
            borrow = 1
        else:
            borrow = 0
        result |= digit << column
    if borrow:
        mask |= 1 << width
    return mask, result


def exact_reduction_history(row: dict[str, Any]) -> dict[str, Any]:
    _, residual = parse_operand(row["anchor"])
    external_se, external_sig = parse_operand(row["operand"])
    quotient = int(row["quotient"])
    side = int(row["residual_side"])
    addend = 2 * quotient * M66
    external_integer = external_sig << (external_se - 0x3FFC)
    expected = addend + side * residual
    if external_integer != expected:
        raise AssertionError(f"h1404 SAT equation failed for {row['anchor']}")

    width = max(67, addend.bit_length(), residual.bit_length(),
                external_integer.bit_length())
    direct_zero = history_summary("q=0 reducer bypass", 0, width)
    if side > 0:
        carry_mask, replay = add_carry_mask(addend, residual, width)
        if replay != external_integer:
            raise AssertionError("ripple-add replay differs from exact equation")
        natural = history_summary("carry entering column for A + R",
                                  carry_mask, width)
        cpa = natural
        borrow = None
    else:
        borrow_mask, replay = subtract_borrow_mask(addend, residual, width)
        if replay != external_integer:
            raise AssertionError("ripple-subtract replay differs from exact equation")
        complement = ((1 << width) - 1) ^ residual
        cpa_mask, cpa_replay = add_carry_mask(addend, complement, width, 1)
        if (cpa_replay & ((1 << width) - 1)) != external_integer:
            raise AssertionError("two's-complement CPA replay differs from equation")
        # For each nonzero bit column, carry(A + ~R + 1) is exactly the
        # complement of borrow(A - R).  Check the convention explicitly.
        for column in range(1, width + 1):
            if ((cpa_mask >> column) & 1) == ((borrow_mask >> column) & 1):
                raise AssertionError("carry/borrow polarity invariant failed")
        borrow = history_summary("borrow entering column for A - R",
                                 borrow_mask, width)
        cpa = history_summary("carry entering column for A + ~R + 1",
                              cpa_mask, width)
        natural = borrow

    return {
        "equation": "X = 2*q*M66 + side*R at scale 2^-66",
        "equation_replay": "exact",
        "quotient": quotient,
        "quotient_bit_length": quotient.bit_length(),
        "quotient_mod_4": quotient & 3,
        "residual_side": side,
        "residual_integer": residual,
        "m66_addend": addend,
        "external_integer": external_integer,
        "external_width": width,
        "direct_history": direct_zero,
        "natural_external_history": natural,
        "subtraction_borrow_history": borrow,
        "physical_cpa_carry_history": cpa,
    }


def run_model(binary: Path, instruction: str, operand: str,
              mode: str, dump: bool) -> tuple[str, list[str]]:
    command = [str(binary.resolve()), "--batch", f"--rc={mode}",
               f"--{instruction}-standalone"]
    if dump:
        command.append("--dump-internals")
    completed = subprocess.run(
        command,
        input=operand + "\n",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    outputs = [line.strip() for line in completed.stdout.splitlines()
               if line.startswith(("OK ", "C2 ", "UNSUPPORTED "))]
    if len(outputs) != 1:
        raise AssertionError(f"C model emitted {len(outputs)} architectural outputs")
    trace = [line.strip() for line in completed.stderr.splitlines()
             if line.startswith(TRACE_PREFIXES)]
    return outputs[0], trace


def trace_fields(line: str) -> tuple[str, dict[str, str]]:
    fields = line.split()
    return fields[0], {
        token.split("=", 1)[0]: token.split("=", 1)[1]
        for token in fields[1:] if "=" in token
    }


def compare_traces(direct: list[str], external: list[str]) -> dict[str, Any]:
    direct_stages = [trace_fields(line) for line in direct]
    external_stages = [trace_fields(line) for line in external]
    if [stage for stage, _ in direct_stages] != [stage for stage, _ in external_stages]:
        raise AssertionError("paired C traces have different stage sequences")
    for stage in REQUIRED_TRACE_STAGES:
        if stage not in [name for name, _ in direct_stages]:
            raise AssertionError(f"paired C trace omitted {stage}")

    differences: list[dict[str, str]] = []
    payload_equal = True
    for (stage, direct_fields), (_, external_fields) in zip(
            direct_stages, external_stages, strict=True):
        if direct_fields.keys() != external_fields.keys():
            raise AssertionError(f"{stage} trace schema differs")
        for field in direct_fields:
            if direct_fields[field] != external_fields[field]:
                differences.append({
                    "field": f"{stage}.{field}",
                    "direct": direct_fields[field],
                    "external": external_fields[field],
                })
                if field not in ("i0", "i1"):
                    payload_equal = False
    direct_text = "\n".join(direct) + "\n"
    external_text = "\n".join(external) + "\n"
    return {
        "full_trace_equal": direct == external,
        "datapath_equal_excluding_quadrant_control_i0_i1": payload_equal,
        "differences": differences,
        "direct_trace_sha256": sha256_text(direct_text),
        "external_trace_sha256": sha256_text(external_text),
    }


def parse_ok_output(output: str) -> tuple[int, int] | None:
    if not output.startswith("OK "):
        return None
    return parse_operand(output[3:])


def compare_outputs(direct: str, external: str) -> dict[str, Any]:
    direct_value = parse_ok_output(direct)
    external_value = parse_ok_output(external)
    result: dict[str, Any] = {
        "direct": direct,
        "external": external,
        "exact_equal": direct == external,
    }
    if direct_value is None or external_value is None:
        result["absolute_equal"] = False
        return result
    direct_se, direct_sig = direct_value
    external_se, external_sig = external_value
    result.update({
        "absolute_equal": ((direct_se & 0x7FFF), direct_sig)
        == ((external_se & 0x7FFF), external_sig),
        "sign_relation": (
            "same" if (direct_se >> 15) == (external_se >> 15)
            else "opposite"
        ),
        "significand_delta_external_minus_direct": external_sig - direct_sig
        if (direct_se & 0x7FFF) == (external_se & 0x7FFF) else None,
    })
    return result


def external_cosine_instruction(quotient: int) -> str:
    # For even quadrants FCOS selects the cosine producer.  For odd
    # quadrants FSIN selects it.  The C trace's i1 bit validates this mapping.
    return "fsin" if quotient & 1 else "fcos"


def replay_pair(binary: Path, row: dict[str, Any],
                history: dict[str, Any]) -> dict[str, Any]:
    side = int(row["residual_side"])
    quotient = int(row["quotient"])
    direct = signed_direct_operand(row["anchor"], side)
    external = row["operand"]
    paired_external_instruction = external_cosine_instruction(quotient)

    output_matrix: dict[str, Any] = {}
    trace_comparisons: dict[str, Any] = {}
    paired_outputs: dict[str, Any] = {}
    for role, operand in (("direct_q0", direct), ("external_q_nonzero", external)):
        role_outputs: dict[str, Any] = {}
        for instruction in INSTRUCTIONS:
            role_outputs[instruction] = {}
            for mode in MODES:
                output, _ = run_model(binary, instruction, operand, mode, False)
                role_outputs[instruction][mode] = output
        output_matrix[role] = role_outputs

    for mode in MODES:
        direct_output, direct_trace = run_model(
            binary, "fcos", direct, mode, True)
        external_output, external_trace = run_model(
            binary, paired_external_instruction, external, mode, True)
        comparison = compare_traces(direct_trace, external_trace)
        trace_comparisons[mode] = comparison
        paired_outputs[mode] = compare_outputs(direct_output, external_output)

        red_direct = next(fields for stage, fields in map(trace_fields, direct_trace)
                          if stage == "DI_RED")
        red_external = next(fields for stage, fields in map(trace_fields, external_trace)
                            if stage == "DI_RED")
        _, residual = parse_operand(row["anchor"])
        for fields in (red_direct, red_external):
            sign, exponent, significand = fields["mag"].split(":")
            if int(fields["rsn"]) != int(side < 0) or int(sign) != 0 \
                    or int(exponent) != -66 or int(significand, 16) != residual:
                raise AssertionError("C reducer did not replay exact signed residual")

    all_full_equal = all(item["full_trace_equal"]
                         for item in trace_comparisons.values())
    all_payload_equal = all(
        item["datapath_equal_excluding_quadrant_control_i0_i1"]
        for item in trace_comparisons.values())
    differing_modes = [mode for mode, item in paired_outputs.items()
                       if not item["exact_equal"]]
    differing_abs_modes = [mode for mode, item in paired_outputs.items()
                           if not item["absolute_equal"]]

    cpa64 = history["physical_cpa_carry_history"]["selected_columns"]["64"]
    borrow = history["subtraction_borrow_history"]
    borrow64 = None if borrow is None else borrow["selected_columns"]["64"]
    return {
        "direct_operand": direct,
        "external_operand": external,
        "direct_instruction": "fcos",
        "external_instruction": paired_external_instruction,
        "quadrant_mod_4": quotient & 3,
        "full_exposed_trace_equal_all_modes": all_full_equal,
        "datapath_equal_excluding_quadrant_control_i0_i1_all_modes": all_payload_equal,
        "trace_comparisons": trace_comparisons,
        "paired_outputs": paired_outputs,
        "paired_output_difference_modes": differing_modes,
        "paired_absolute_output_difference_modes": differing_abs_modes,
        "all_instruction_mode_outputs": output_matrix,
        "candidate_hidden_bits": {
            "direct_q0_reducer_history": 0,
            "external_physical_cpa_carry_into_column_64": cpa64,
            "external_natural_borrow_into_column_64": borrow64,
            "external_nonzero_quotient": 1,
            "external_residual_negative": int(side < 0),
            "external_high_quotient": int(quotient.bit_length() > 8),
        },
    }


def classify(anchor: str, replay: dict[str, Any]) -> dict[str, Any]:
    if anchor.endswith("d0d000000cc0b3f8"):
        return {
            "rank": 1,
            "quality": "cleanest same-instruction endpoint-null pair",
            "why": (
                "Signed q=0 FCOS and q=4 FCOS collide on the full exposed "
                "trace and every model endpoint.  The reduced state is the "
                "known R1382-sensitive d0d0 state, so any hardware split is "
                "direct evidence for retained reduction/subtraction history."
            ),
            "separates": [
                "q=0 bypass versus nonzero-q reduction",
                "negative-side subtraction borrow history versus no reducer history",
                "post-reduction-only R1382 rule versus reducer-history-qualified rule",
            ],
            "confounds": "none in instruction, exposed trace, sign, or model endpoint",
        }
    if anchor.endswith("d920000000749eaa"):
        return {
            "rank": 2,
            "quality": "cleanest positive-side carry-64 pair",
            "why": (
                "The full exposed trace, including quadrant controls, collides "
                "and q=1 creates a carry into column 64.  The necessary "
                "FCOS-to-FSIN projection has an incumbent RN one-bit split, "
                "so captures must be scored against per-instruction baselines."
            ),
            "separates": [
                "M66 addition carry into column 64 versus q=0 bypass",
                "positive-side addition history versus post-reduction-only state",
                "minimal q=1 history versus quotient-agnostic terminal logic",
            ],
            "confounds": "cross-instruction projection; incumbent RN endpoints differ by one bit",
        }
    if anchor.endswith("cca0000009242f0c"):
        return {
            "rank": 3,
            "quality": "unique exact high-q carry-polarity control",
            "why": (
                "The huge even quotient has no natural subtraction borrows, "
                "but its two's-complement CPA carry is set at every column.  "
                "Datapath fields collide after excluding the expected i0 "
                "quadrant/sign control, and absolute endpoints can be compared."
            ),
            "separates": [
                "borrow-wire interpretation versus complemented CPA-carry interpretation",
                "high-q retained history versus small-q or quotient-agnostic history",
                "quotient-width dependence versus reduced-state-only logic",
            ],
            "confounds": "quadrant i0 and architectural output sign differ",
        }
    raise AssertionError(f"unexpected SAT anchor {anchor}")


def build_report(preimages: Path, binary: Path) -> dict[str, Any]:
    source = json.loads(preimages.read_text())
    sat_rows = {row["anchor"].lower(): row for row in source["rows"]
                if row["result"] == "SAT"}
    if set(sat_rows) != set(TARGET_ANCHORS):
        raise AssertionError("h1404 SAT set is not the expected three exact preimages")

    rows = []
    cpa_masks: dict[str, int] = {}
    for anchor in TARGET_ANCHORS:
        source_row = sat_rows[anchor]
        history = exact_reduction_history(source_row)
        replay = replay_pair(binary, source_row, history)
        mask_text = history["physical_cpa_carry_history"]["entering_column_mask_hex"]
        cpa_masks[anchor] = int(mask_text, 16)
        rows.append({
            "anchor": anchor,
            "source_preimage": {
                "operand": source_row["operand"],
                "quotient": source_row["quotient"],
                "residual_side": source_row["residual_side"],
                "solver_result": source_row["result"],
            },
            "exact_history": history,
            "c_replay": replay,
            "hardware_discriminator": classify(anchor, replay),
        })

    common_cpa_columns = [column for column in range(68)
                          if all((mask >> column) & 1
                                 for mask in cpa_masks.values())]
    if common_cpa_columns != [2, 3, 4, 11, 12, 54, 55, 60]:
        raise AssertionError("unexpected shared CPA carry columns")

    rows.sort(key=lambda row: row["hardware_discriminator"]["rank"])
    return {
        "query": "exact_M66_preimage_hardware_discriminator_characterization",
        "result": "3_REPLAYED_SAT_PAIRS",
        "source_preimage_report": str(preimages.resolve()),
        "source_preimage_report_sha256": sha256_file(preimages),
        "c_model": str(binary.resolve()),
        "c_model_sha256": sha256_file(binary),
        "scale": "2^-66",
        "column_numbering": "column 0 is the 2^-66 residual integer LSB",
        "shared_external_cpa_carry_columns_among_all_three": common_cpa_columns,
        "column_64_pattern_rank_order_d0d0_d920_cca0": {
            "physical_twos_complement_CPA_carry": [0, 1, 1],
            "natural_add_carry_or_subtract_borrow": [1, 1, 0],
        },
        "interpretation": (
            "No column-64 convention maps all three nonzero-q witnesses to "
            "one common bit.  Columns 54, 55, and 60 (also 2, 3, 4, 11, 12) "
            "do have CPA carry=1 in every external witness and reducer-history=0 "
            "in every q=0 control; this is a discriminator fact, not evidence "
            "that Skylake routes any such bit to R59."
        ),
        "recommended_capture_order": [
            "d0d0 signed-q0 FCOS versus q4 FCOS",
            "d920 q0 FCOS versus q1 FSIN",
            "cca0 signed-q0 FCOS versus huge-q FCOS",
        ],
        "rows": rows,
        "validation": {
            "python_integer_equations": "exact",
            "python_ripple_histories": "exact",
            "c_reduction_replay": "exact in all four modes",
            "c_instructions_replayed": list(INSTRUCTIONS),
            "c_rounding_modes_replayed": list(MODES),
        },
        "capture_status": "analysis_only_not_frozen",
        "private_ledger_access": "none",
        "hardware_execution": "none",
        "emulator_changes": "none",
    }


def write_json_new(path: Path, report: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True)
        target.write("\n")


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--preimages",
        type=Path,
        default=repo / "tmp/ledger33/current/h1404_exact_external_preimages.json",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=repo / "tmp/ledger33/current/h1400_integrated_model",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=repo / "tmp/ledger33/current/h1411_exact_preimage_discriminators.json",
    )
    args = parser.parse_args()
    report = build_report(args.preimages, args.model)
    write_json_new(args.output, report)
    print(json.dumps({
        "output": str(args.output),
        "result": report["result"],
        "recommended_capture_order": report["recommended_capture_order"],
        "hardware_execution": "none",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
