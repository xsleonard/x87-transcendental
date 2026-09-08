#!/usr/bin/env python3
"""Construct software-only FSIN siblings for the unresolved FCOS high-q rows.

For a direct FCOS operand x in binade 3ffc, FSIN(pi/2-x) reaches the same
odd-quadrant cosine polynomial.  Extended inputs near pi/2 lie on a residual
lattice eight times coarser than the direct operand, so an exact duplicate is
impossible for the two targets below: every sibling is at least four direct
input units away.  That makes the construction a disjoint structural test,
not a repeat capture.

The discovery pass scans that lattice with the predecessor and q<=7 factor
models in RN and RD.  Only architectural separators are then evaluated under
all four rounding modes and both forced terminal-carry endpoints.  Hardware is
never executed by this script; its output is a frozen bank for a later blind
one-shot capture.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from h1184_upstream_halfway_audit import schedule
from h1210_stagea_residual_reframe import parse_dump
from h1222_r1200_enable_state import cut_fields


M66 = (3 << 64) | 0x243F6A8885A308D3
MODES = ("rn", "rd", "ru", "rz")
DISCOVERY_MODES = ("rn", "rd")
TARGETS = {
    "d9": int("d9c000000a94151a", 16),
    "dcc": int("dcc000000d24fdf2", 16),
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def parse_output(line: str) -> str:
    fields = line.split()
    if len(fields) < 3 or fields[0] != "OK":
        raise RuntimeError("bad model output: " + line.rstrip())
    return fields[1].lower() + ":" + fields[2].lower()


def run(
        model: Path, mode: str, operands: list[str], dump: bool = False
        ) -> tuple[list[str], str]:
    command = [str(model), "--batch", f"--rc={mode}", "--fsin-standalone"]
    if dump:
        command.append("--dump-internals")
    process = subprocess.run(
        command,
        input="\n".join(operands) + "\n",
        text=True,
        capture_output=True,
        check=True,
    )
    values = [parse_output(line) for line in process.stdout.splitlines()]
    if len(values) != len(operands):
        raise RuntimeError(
            f"output count {len(values)} != {len(operands)} "
            f"for {model}/{mode}"
        )
    return values, process.stderr


def sibling_center(target: int) -> int:
    numerator = 2 * M66 - target
    quotient, remainder = divmod(numerator, 8)
    if remainder > 4 or (remainder == 4 and (quotient & 1)):
        quotient += 1
    return quotient


def residual66(input_significand: int) -> int:
    """Magnitude of M66-input in direct-binade 3ffc integer units."""
    value = 2 * M66 - 8 * input_significand
    if value <= 0:
        raise RuntimeError("scan crossed pi/2")
    return value


def operand(input_significand: int) -> str:
    return f"3fff {input_significand:016x}"


def scan_separators(
        predecessor: Path, wide: Path, radius: int, chunk_size: int
        ) -> tuple[dict[str, dict[str, object]], int]:
    separators: dict[str, dict[str, object]] = {}
    evaluated = 0
    for target_name, target in TARGETS.items():
        center = sibling_center(target)
        first = center - radius
        stop = center + radius + 1
        for chunk_first in range(first, stop, chunk_size):
            chunk_stop = min(chunk_first + chunk_size, stop)
            operands = [operand(value) for value in range(chunk_first, chunk_stop)]
            evaluated += len(operands)
            jobs = {}
            with ThreadPoolExecutor(max_workers=4) as executor:
                for mode in DISCOVERY_MODES:
                    jobs[mode, "predecessor"] = executor.submit(
                        run, predecessor, mode, operands)
                    jobs[mode, "wide"] = executor.submit(
                        run, wide, mode, operands)
            for mode in DISCOVERY_MODES:
                predecessor_values, _ = jobs[mode, "predecessor"].result()
                wide_values, _ = jobs[mode, "wide"].result()
                for input_value, pred, q7 in zip(
                        range(chunk_first, chunk_stop),
                        predecessor_values, wide_values):
                    if pred == q7:
                        continue
                    op = operand(input_value)
                    row = separators.setdefault(op, {
                        "op": op,
                        "input_sig": input_value,
                        "residual66": residual66(input_value),
                        "origins": set(),
                        "discovery_modes": set(),
                    })
                    row["origins"].add(target_name)
                    row["discovery_modes"].add(mode)
    return separators, evaluated


def add_model_outputs(
        rows: list[dict[str, object]], model_paths: dict[str, Path]) -> None:
    operands = [str(row["op"]) for row in rows]
    for mode in MODES:
        for name, model in model_paths.items():
            values, _ = run(model, mode, operands)
            for row, value in zip(rows, values):
                row[f"{mode}_{name}"] = value


def add_horner_state(rows: list[dict[str, object]], predecessor: Path) -> None:
    operands = [str(row["op"]) for row in rows]
    _, stderr = run(predecessor, "rn", operands, dump=True)
    dumps = parse_dump(stderr, operands)
    for row, dump in zip(rows, dumps):
        operations = schedule(dump)
        negative_source = cut_fields(operations["negative.mul2"], 67)
        negative_add = cut_fields(operations["negative.add2"], 64)
        row.update({
            "tc_mag_sig": dump["tc_mag_sig"],
            "tc_square_sig": dump["tc_mul_sig"],
            "tc_fourth_sig": dump["tc_f4_sig"],
            "tc_negative_sig": dump["tc_lf_sig"],
            "negative_product_shift": negative_source["shift"],
            "negative_product_remainder": int(negative_source["remainder"]),
            "negative_add_q": int(negative_add["half_delta"]),
            "negative_add_class": negative_add["class"],
            "negative_add_retained_lsb": int(negative_add["retained"]) & 1,
        })


def endpoint_class(row: dict[str, object]) -> str:
    pred_distinct = any(
        row[f"{mode}_predecessor_carry0"]
        != row[f"{mode}_predecessor_carry1"]
        for mode in MODES
    )
    wide_distinct = any(
        row[f"{mode}_wide_carry0"] != row[f"{mode}_wide_carry1"]
        for mode in MODES
    )
    factor_distinct = any(
        row[f"{mode}_predecessor"] != row[f"{mode}_wide"]
        for mode in MODES
    )
    if factor_distinct and pred_distinct:
        return "factor_and_terminal_visible"
    if factor_distinct and wide_distinct:
        return "factor_and_wide_terminal_visible"
    if factor_distinct:
        return "factor_only_visible"
    return "unexpected_no_factor_difference"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predecessor", type=Path, required=True)
    parser.add_argument("--predecessor-carry0", type=Path, required=True)
    parser.add_argument("--predecessor-carry1", type=Path, required=True)
    parser.add_argument("--wide", type=Path, required=True)
    parser.add_argument("--wide-carry0", type=Path, required=True)
    parser.add_argument("--wide-carry1", type=Path, required=True)
    parser.add_argument("--radius", type=int, default=16_000_000)
    parser.add_argument("--chunk-size", type=int, default=100_000)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--bank", type=Path, required=True)
    args = parser.parse_args()
    for output_path in (args.report, args.manifest, args.bank):
        if output_path.exists():
            raise SystemExit(f"refusing to overwrite {output_path}")
    if args.radius < 0 or args.chunk_size <= 0:
        raise SystemExit("radius must be nonnegative and chunk-size positive")

    model_paths = {
        "predecessor": args.predecessor,
        "predecessor_carry0": args.predecessor_carry0,
        "predecessor_carry1": args.predecessor_carry1,
        "wide": args.wide,
        "wide_carry0": args.wide_carry0,
        "wide_carry1": args.wide_carry1,
    }
    separators, evaluated = scan_separators(
        args.predecessor, args.wide, args.radius, args.chunk_size)
    if not separators:
        raise RuntimeError("no architectural separators in scan")

    rows = list(separators.values())
    for row in rows:
        row["origins"] = ",".join(sorted(row["origins"]))
        row["discovery_modes"] = ",".join(
            mode for mode in MODES if mode in row["discovery_modes"])
        row["distance_d9"] = abs(int(row["residual66"]) - TARGETS["d9"])
        row["distance_dcc"] = abs(int(row["residual66"]) - TARGETS["dcc"])
    rows.sort(key=lambda row: (
        min(int(row["distance_d9"]), int(row["distance_dcc"])),
        str(row["op"]),
    ))
    add_model_outputs(rows, model_paths)
    add_horner_state(rows, args.predecessor)
    for row in rows:
        row["endpoint_class"] = endpoint_class(row)

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    columns = tuple(rows[0])
    with args.manifest.open("x", newline="") as target_file:
        writer = csv.DictWriter(target_file, columns, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

    # Freeze a compact blind bank.  Prefer the nearest rows for each target,
    # q, and endpoint-response class; the key contains no hardware outcome.
    selected: dict[str, dict[str, object]] = {}
    for target_name in TARGETS:
        ranked = sorted(rows, key=lambda row: (
            int(row[f"distance_{target_name}"]), str(row["op"])))
        seen = set()
        for row in ranked:
            key = (row["negative_add_q"], row["endpoint_class"])
            if key in seen:
                continue
            seen.add(key)
            selected[str(row["op"])] = row
            if len(seen) >= 8:
                break
    bank_rows = sorted(selected.values(), key=lambda row: str(row["op"]))
    with args.bank.open("x") as target_file:
        for row in bank_rows:
            target_file.write(str(row["op"]) + "\n")

    counts = Counter(str(row["endpoint_class"]) for row in rows)
    q_counts = Counter(int(row["negative_add_q"]) for row in rows)
    with args.report.open("x") as target_file:
        for name, model_path in model_paths.items():
            target_file.write(f"model_sha256.{name}\t{digest(model_path)}\n")
        target_file.write("hardware_policy\tsoftware_only_no_x87_execution\n")
        target_file.write("instruction\tfsin\n")
        target_file.write(f"radius_per_target\t{args.radius}\n")
        target_file.write(f"lattice_points_evaluated\t{evaluated}\n")
        target_file.write(f"unique_separators\t{len(rows)}\n")
        target_file.write(f"blind_bank_operands\t{len(bank_rows)}\n")
        target_file.write(f"manifest_sha256\t{digest(args.manifest)}\n")
        target_file.write(f"bank_sha256\t{digest(args.bank)}\n")
        target_file.write("\n[target geometry]\n")
        target_file.write(
            "name\ttarget_residual66\tsibling_center\t"
            "center_residual66\tcenter_delta\n")
        for name, target_value in TARGETS.items():
            center = sibling_center(target_value)
            center_residual = residual66(center)
            target_file.write(
                f"{name}\t{target_value:016x}\t{center:016x}\t"
                f"{center_residual:016x}\t{center_residual-target_value}\n")
        target_file.write("\n[endpoint classes]\n")
        for name, count in sorted(counts.items()):
            target_file.write(f"{name}\t{count}\n")
        target_file.write("\n[negative.add2 q]\n")
        for q, count in sorted(q_counts.items()):
            target_file.write(f"{q}\t{count}\n")
        target_file.write("\n[blind bank]\n")
        target_file.write(
            "op\tresidual66\tdistance_d9\tdistance_dcc\tq\t"
            "endpoint_class\tdiscovery_modes\n")
        for row in bank_rows:
            target_file.write("\t".join(map(str, (
                row["op"], f"{int(row['residual66']):016x}",
                row["distance_d9"], row["distance_dcc"],
                row["negative_add_q"], row["endpoint_class"],
                row["discovery_modes"],
            ))) + "\n")

    print(
        f"wrote {args.report}: evaluated={evaluated} "
        f"separators={len(rows)} bank={len(bank_rows)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
