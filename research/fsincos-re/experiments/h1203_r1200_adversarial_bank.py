#!/usr/bin/env python3
"""Freeze fresh adversarial FCOS inputs for the R1200 recurrence.

This is a software-only pass: it never executes an x87 instruction and never
uses a hardware label for a generated operand.  It attacks two independent
failure modes:

* both edges of the closed R1200 FADD interval (half through half+4) at all
  four Horner additions, including the two earlier additions that a genuinely
  operation-level rule also reaches; and
* exact terminal-coordinate cells containing the eight post-R1186 residuals,
  with brackets in input and signed-M coordinates plus deliberately distant
  multiplier/CSA and rounding-history states.

Only mode legs for which the competing software hypotheses are
architecturally distinguishable are emitted.  RN/RD/RU are retained; RZ is
omitted because FCOS is positive in this domain and therefore duplicates RD.
Every generated operand is checked against all supplied local input,
manifest, operation-list, and tie inventories before selection.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import os
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

from h1126_r59_adversarial_bank_v2 import (
    append_product_signature,
    generated_operands,
    parse_dump,
    popcount,
    run_model,
)
from h1178_round_history_state_audit import (
    CELL,
    CONSTANTS,
    STAGES,
    add_same_sign,
    compare_scaled,
    feature_value,
    multiply,
)


MODES = ("rn", "rd", "ru")
ADD_STAGES = ("odd_a1", "odd_a2", "even_a1", "even_a2")
FULL_OPERAND = re.compile(
    r"(?<![0-9a-fA-F])([0-9a-fA-F]{4})[ \t]+"
    r"([0-9a-fA-F]{16})(?![0-9a-fA-F])"
)
SINGLE_SIGNIFICAND = re.compile(r"^([0-9a-fA-F]{16})(?:\s|$)")
REQUIRED = {
    "tc_mul_sig", "tc_lf_sig", "tc_rf_sig", "tc_f4_sig",
    "tc_mag_sig", "tc_left_sig", "tc_right_sig",
    "tc_mul_exp", "tc_lf_exp", "tc_rf_exp", "tc_f4_exp",
    "tc_mag_exp", "tc_left_exp", "tc_right_exp",
    "tc_mul_sign", "tc_lf_sign", "tc_rf_sign", "tc_f4_sign",
    "tc_mag_sign", "tc_left_sign", "tc_right_sign",
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def signed128(text: str) -> int:
    value = int(text, 16)
    return value - (1 << 128) if value >> 127 else value


def product_signature(row: dict[str, str]) -> tuple[int, int]:
    """Return a fixed-width signature available even outside R59 scope."""
    bits = []
    multiplier = int(row["tc_mul_sig"], 16)
    append_product_signature(
        bits, multiplier, int(row["tc_lf_sig"], 16))
    append_product_signature(
        bits, int(row["tc_f4_sig"], 16), int(row["tc_rf_sig"], 16))
    append_product_signature(bits, multiplier, multiplier >> 3, square=True)
    packed = 0
    for index, value in enumerate(bits):
        packed |= int(value) << index
    return packed, len(bits)


def candidate_inventory_paths(
        roots: list[Path], explicit: list[Path]) -> list[Path]:
    paths = {path.resolve() for path in explicit}
    for root in roots:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            name = path.name.lower()
            if not name.endswith((".txt", ".tsv", ".txt.gz", ".tsv.gz")):
                continue
            if ("input" in name or "_ops" in name or "manifest" in name
                    or name.startswith("ties_")):
                paths.add(path.resolve())
    return sorted(paths)


def exclude_inventory_hits(paths: list[Path], candidates: set[str]
                           ) -> tuple[set[str], list[tuple[Path, int]]]:
    """Return only inventory operands that intersect the generated set."""
    hits = set()
    counts = []
    for ordinal, path in enumerate(paths, 1):
        matched = set()
        opener = gzip.open if path.name.endswith(".gz") else open
        with opener(path, "rt", errors="replace") as source:
            tie_style = path.name.lower().startswith("ties_")
            for line in source:
                for match in FULL_OPERAND.finditer(line):
                    operand = (match.group(1) + " " + match.group(2)).lower()
                    if operand in candidates:
                        matched.add(operand)
                if tie_style:
                    match = SINGLE_SIGNIFICAND.match(line)
                    if match:
                        # Every generated challenge is in the direct 3ffc
                        # binade.  Conservatively interpret any bare tie word
                        # as a 3ffc operand for exclusion purposes.
                        operand = "3ffc " + match.group(1).lower()
                        if operand in candidates:
                            matched.add(operand)
        hits.update(matched)
        counts.append((path, len(matched)))
        if ordinal % 100 == 0:
            print(
                f"inventory {ordinal}/{len(paths)} candidate_hits={len(hits)}",
                flush=True,
            )
    return hits, counts


def r1200_add(
        left: tuple[int, int, int], left_history: dict[str, object] | None,
        right: tuple[int, int, int], right_history: dict[str, object] | None,
        ) -> tuple[tuple[int, int, int], dict[str, object]]:
    """Transcribe the operation-level R1200 same-sign RN64 recurrence."""
    rounded, history = add_same_sign(left, right)
    scale = min(left[1], right[1])
    magnitude = ((left[2] << (left[1] - scale))
                 + (right[2] << (right[1] - scale)))
    shift = max(0, magnitude.bit_length() - 64)
    remainder = magnitude & ((1 << shift) - 1) if shift else 0
    half = 1 << (shift - 1) if shift else 0
    lower = magnitude >> shift if shift else magnitude
    toward_zero = 1 if left[0] else -1
    directions = (
        int(left_history["direction"]) if left_history else 0,
        int(right_history["direction"]) if right_history else 0,
    )
    fires = (
        shift > 0
        and toward_zero in directions
        and -toward_zero not in directions
        and half <= remainder <= half + 4
        and rounded[2] > lower
    )
    if fires:
        rounded = (rounded[0], rounded[1], lower)
        history = dict(history)
        history["direction"] = toward_zero
    history = dict(history)
    history["r1200"] = fires
    history["half_delta"] = remainder - half if shift else -1
    return rounded, history


def row_histories(row: dict[str, str]
                  ) -> tuple[dict[str, dict[str, object]], dict[str, object]]:
    """Reconstruct every materialization under the generic R1200 rule."""
    magnitude = feature_value(row, "mag")
    square, square_history = multiply(magnitude, magnitude)
    fourth, fourth_history = multiply(square, square)
    if square != feature_value(row, "mul"):
        raise AssertionError("square reconstruction mismatch")
    if fourth != feature_value(row, "f4"):
        raise AssertionError("fourth reconstruction mismatch")

    odd_p1, odd_p1_history = multiply(fourth, CONSTANTS[5])
    odd_a1, odd_a1_history = r1200_add(
        CONSTANTS[3], None, odd_p1, odd_p1_history)
    odd_p2, odd_p2_history = multiply(fourth, odd_a1)
    odd_a2, odd_a2_history = r1200_add(
        CONSTANTS[1], None, odd_p2, odd_p2_history)
    even_p1, even_p1_history = multiply(fourth, CONSTANTS[6])
    even_a1, even_a1_history = r1200_add(
        CONSTANTS[4], None, even_p1, even_p1_history)
    even_p2, even_p2_history = multiply(fourth, even_a1)
    even_a2, even_a2_history = r1200_add(
        CONSTANTS[2], None, even_p2, even_p2_history)
    if odd_a2 != feature_value(row, "lf"):
        raise AssertionError("odd factor reconstruction mismatch")
    if even_a2 != feature_value(row, "rf"):
        raise AssertionError("even factor reconstruction mismatch")

    left, left_history = multiply(square, odd_a2)
    right, right_history = multiply(fourth, even_a2)
    if left != feature_value(row, "left"):
        raise AssertionError("left product reconstruction mismatch")
    if right != feature_value(row, "right"):
        raise AssertionError("right product reconstruction mismatch")

    histories = {
        "square": square_history,
        "fourth": fourth_history,
        "odd_p1": odd_p1_history,
        "odd_a1": odd_a1_history,
        "odd_p2": odd_p2_history,
        "odd_a2": odd_a2_history,
        "even_p1": even_p1_history,
        "even_a1": even_a1_history,
        "even_p2": even_p2_history,
        "even_a2": even_a2_history,
        "left": left_history,
        "right": right_history,
    }
    lrem = int(left_history["remainder"])
    lshift = int(left_history["shift"])
    rrem = int(right_history["remainder"])
    rshift = int(right_history["shift"])
    terminal = {
        "fraction_order": compare_scaled(lrem, -lshift, rrem, -rshift),
        "physical_error_order": compare_scaled(
            lrem, square[1] + odd_a2[1],
            rrem, fourth[1] + even_a2[1],
        ),
        "class_pair": (left_history["class"], right_history["class"]),
        "direction_pair": (
            left_history["direction"], right_history["direction"]),
    }
    return histories, terminal


def decorate(row: dict[str, str], anchor: dict[str, str]) -> dict[str, object]:
    histories, terminal = row_histories(row)
    signature, signature_bits = product_signature(row)
    anchor_signature = int(anchor["_structural_signature"])
    result: dict[str, object] = dict(row)
    result["anchor"] = anchor["op"]
    result["anchor_status"] = anchor["_status"]
    result["offset"] = (
        int(row["op"].split()[1], 16)
        - int(anchor["op"].split()[1], 16)
    )
    result["mreg_signed"] = (
        signed128(row["Mreg"]) if row.get("Mreg") else "")
    result["anchor_mreg_signed"] = (
        signed128(anchor["Mreg"]) if anchor.get("Mreg") else "")
    result["mreg_delta"] = (
        int(result["mreg_signed"]) - int(result["anchor_mreg_signed"])
        if result["mreg_signed"] != ""
        and result["anchor_mreg_signed"] != ""
        else ""
    )
    result["structural_signature"] = "%0*x" % (
        (signature_bits + 3) // 4, signature)
    result["structural_hamming"] = popcount(signature ^ anchor_signature)
    fired = []
    for stage in ADD_STAGES:
        result[f"{stage}_half_delta"] = histories[stage]["half_delta"]
        result[f"{stage}_r1200"] = int(bool(histories[stage]["r1200"]))
        if histories[stage]["r1200"]:
            fired.append(stage)
    result["r1200_stages"] = ",".join(fired) or "-"
    result["terminal_fraction_order"] = terminal["fraction_order"]
    result["terminal_physical_error_order"] = terminal[
        "physical_error_order"]
    result["terminal_class_pair"] = "/".join(terminal["class_pair"])
    result["terminal_direction_pair"] = "/".join(
        map(str, terminal["direction_pair"]))
    result["history_signature"] = "/".join(
        f"{histories[stage]['class']}:{histories[stage]['direction']}"
        for stage in STAGES
    )
    result["_histories"] = histories
    return result


def add_rows(
        selected: dict[str, tuple[dict[str, object], set[str]]],
        category: str, rows: list[dict[str, object]], count: int,
        ) -> None:
    added = 0
    for row in rows:
        entry = selected.setdefault(str(row["op"]), (row, set()))
        before = len(entry[1])
        entry[1].add(category)
        if before == 0:
            added += 1
        if added >= count:
            break


def choose_fadd(
        anchor: dict[str, str], rows: list[dict[str, object]],
        selected: dict[str, tuple[dict[str, object], set[str]]],
        per_side: int,
        ) -> None:
    for stage in ADD_STAGES:
        delta_name = f"{stage}_half_delta"
        fire_name = f"{stage}_r1200"
        for boundary in (0, 5):
            below = sorted(
                (row for row in rows if int(row[delta_name]) < boundary),
                key=lambda row: (
                    boundary - int(row[delta_name]),
                    abs(int(row["offset"])), row["op"],
                ),
            )
            above = sorted(
                (row for row in rows if int(row[delta_name]) >= boundary),
                key=lambda row: (
                    int(row[delta_name]) - boundary,
                    abs(int(row["offset"])), row["op"],
                ),
            )
            add_rows(
                selected, f"fadd.{stage}.edge{boundary}.below",
                below, per_side)
            add_rows(
                selected, f"fadd.{stage}.edge{boundary}.at_or_above",
                above, per_side)

        anchor_fire = int(anchor[f"_{fire_name}"])
        opposite = sorted(
            (row for row in rows if int(row[fire_name]) != anchor_fire),
            key=lambda row: (abs(int(row["offset"])), row["op"]),
        )
        add_rows(selected, f"fadd.{stage}.trigger_flip", opposite, per_side)
        for state in (0, 1):
            same_state = sorted(
                (row for row in rows if int(row[fire_name]) == state),
                key=lambda row: (
                    -int(row["structural_hamming"]),
                    abs(int(row["offset"])), row["op"],
                ),
            )
            add_rows(
                selected, f"fadd.{stage}.state{state}.far_netlist",
                same_state, per_side)


def choose_terminal(
        anchor: dict[str, str], rows: list[dict[str, object]],
        selected: dict[str, tuple[dict[str, object], set[str]]],
        per_side: int,
        ) -> None:
    if (not anchor.get("Mreg")
            or any(not anchor.get(name) for name in CELL)):
        raise AssertionError("residual anchor lacks terminal coordinates")
    anchor_cell = tuple(int(anchor[name]) for name in CELL)
    same_cell = [row for row in rows
                 if row.get("Mreg")
                 and all(row.get(name) for name in CELL)
                 and tuple(int(row[name]) for name in CELL) == anchor_cell]
    if not same_cell:
        return
    for name, target in (
            ("input", 0),
            ("M", signed128(anchor["Mreg"])),
            ):
        value_name = "offset" if name == "input" else "mreg_signed"
        below = sorted(
            (row for row in same_cell if int(row[value_name]) < target),
            key=lambda row: (target - int(row[value_name]), row["op"]),
        )
        above = sorted(
            (row for row in same_cell if int(row[value_name]) > target),
            key=lambda row: (int(row[value_name]) - target, row["op"]),
        )
        add_rows(selected, f"terminal.{name}.below", below, per_side)
        add_rows(selected, f"terminal.{name}.above", above, per_side)

    far = sorted(
        same_cell,
        key=lambda row: (
            -int(row["structural_hamming"]),
            abs(int(row["offset"])), row["op"],
        ),
    )
    add_rows(selected, "terminal.same_cell_far_netlist", far, 2 * per_side)

    state_best: dict[tuple[object, ...], dict[str, object]] = {}
    for row in same_cell:
        state = (
            row["terminal_class_pair"], row["terminal_direction_pair"],
            row["terminal_fraction_order"],
            row["terminal_physical_error_order"], row["r1200_stages"],
        )
        candidate = (abs(int(row["offset"])), row["op"])
        incumbent = state_best.get(state)
        if incumbent is None or candidate < (
                abs(int(incumbent["offset"])), incumbent["op"]):
            state_best[state] = row
    diverse = sorted(
        state_best.values(),
        key=lambda row: (
            -int(row["structural_hamming"]),
            abs(int(row["offset"])), row["op"],
        ),
    )
    add_rows(
        selected, "terminal.same_cell_history_diverse",
        diverse, 4 * per_side)


def run_many(model: Path, mode: str, operands: list[str], chunk: int
             ) -> list[str]:
    values = []
    for start in range(0, len(operands), chunk):
        part, _ = run_model(
            str(model), mode, operands[start:start + chunk], dump=False)
        values.extend(part)
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("anchors", type=Path)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("carry0", type=Path)
    parser.add_argument("carry1", type=Path)
    parser.add_argument("output_prefix", type=Path)
    parser.add_argument("--exclude-root", action="append", default=[], type=Path)
    parser.add_argument("--exclude", action="append", default=[], type=Path)
    parser.add_argument("--samples-per-anchor", type=int, default=12000)
    parser.add_argument("--per-side", type=int, default=3)
    parser.add_argument("--seed", type=lambda value: int(value, 0),
                        default=0x1203A6B3)
    parser.add_argument("--chunk", type=int, default=4000)
    args = parser.parse_args()

    outputs = {
        "features": args.output_prefix.with_name(
            args.output_prefix.name + "_features.tsv"),
        "manifest": args.output_prefix.with_name(
            args.output_prefix.name + "_manifest.tsv"),
        "report": args.output_prefix.with_name(
            args.output_prefix.name + "_report.txt"),
        **{
            mode: args.output_prefix.with_name(
                args.output_prefix.name + f"_{mode}_ops.txt")
            for mode in MODES
        },
    }
    for path in outputs.values():
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")

    with args.anchors.open(newline="") as source:
        anchor_rows = [dict(row) for row in
                       csv.DictReader(source, delimiter="\t")
                       if row.get("old_label", row["label"]) == "POS"]
    if len(anchor_rows) != 29:
        raise RuntimeError(f"expected 29 pre-R1186 anchors, got {len(anchor_rows)}")
    for anchor in anchor_rows:
        anchor["_status"] = (
            "post_r1200_residual" if anchor["current"] != anchor["hw"]
            else "r1200_fixed"
        )
        signature, _ = product_signature(anchor)
        anchor["_structural_signature"] = str(signature)
        histories, _ = row_histories(anchor)
        for stage in ADD_STAGES:
            anchor[f"_{stage}_r1200"] = str(
                int(bool(histories[stage]["r1200"])))
    residuals = [row for row in anchor_rows
                 if row["_status"] == "post_r1200_residual"]
    if len(residuals) != 8:
        raise RuntimeError(f"expected eight post-R1200 residuals, got {len(residuals)}")

    generator = random.Random(args.seed)
    generated_by_anchor = {}
    generated_union = set()
    for anchor in anchor_rows:
        operands = generated_operands(
            anchor["op"], args.samples_per_anchor, generator)
        generated_by_anchor[anchor["op"]] = operands
        generated_union.update(operands)
    inventory_paths = candidate_inventory_paths(
        args.exclude_root, args.exclude + [args.anchors])
    excluded, inventory_counts = exclude_inventory_hits(
        inventory_paths, generated_union)
    print(
        f"generated={sum(map(len, generated_by_anchor.values()))} "
        f"unique={len(generated_union)} inventory_files={len(inventory_paths)} "
        f"excluded_hits={len(excluded)}",
        flush=True,
    )

    selected: dict[str, tuple[dict[str, object], set[str]]] = {}
    reconstruction_failures = Counter()
    eligible_counts = Counter()
    for index, anchor in enumerate(anchor_rows, 1):
        operands = [operand for operand in generated_by_anchor[anchor["op"]]
                    if operand not in excluded]
        decorated = []
        for start in range(0, len(operands), args.chunk):
            chunk = operands[start:start + args.chunk]
            _, stderr = run_model(
                str(args.candidate), "rn", chunk, dump=True)
            records = parse_dump(stderr)
            if len(records) != len(chunk):
                raise RuntimeError("dump count mismatch")
            for operand, record in zip(chunk, records):
                if record.get("op") != operand:
                    raise RuntimeError("dump desynchronization")
                if not REQUIRED.issubset(record):
                    reconstruction_failures["missing_fields"] += 1
                    continue
                try:
                    decorated.append(decorate(record, anchor))
                except AssertionError as error:
                    reconstruction_failures[str(error)] += 1
        eligible_counts["fresh"] += len(operands)
        eligible_counts["decorated"] += len(decorated)
        before = len(selected)
        choose_fadd(anchor, decorated, selected, args.per_side)
        if anchor["_status"] == "post_r1200_residual":
            choose_terminal(anchor, decorated, selected, args.per_side)
        print(
            f"anchor {index}/29 {anchor['op']} {anchor['_status']} "
            f"fresh={len(operands)} decorated={len(decorated)} "
            f"selected_delta={len(selected) - before} total={len(selected)}",
            flush=True,
        )

    if not selected:
        raise RuntimeError("no adversarial operands selected")
    selected_operands = sorted(selected)
    predictions = {
        mode: {
            "baseline": run_many(args.baseline, mode, selected_operands, args.chunk),
            "candidate": run_many(args.candidate, mode, selected_operands, args.chunk),
            "carry0": run_many(args.carry0, mode, selected_operands, args.chunk),
            "carry1": run_many(args.carry1, mode, selected_operands, args.chunk),
        }
        for mode in MODES
    }

    output_rows = []
    rejected = Counter()
    for mode in MODES:
        for ordinal, operand in enumerate(selected_operands):
            row, categories = selected[operand]
            values = {name: predictions[mode][name][ordinal]
                      for name in predictions[mode]}
            has_fadd = any(category.startswith("fadd.")
                            for category in categories)
            has_terminal = any(category.startswith("terminal.")
                               for category in categories)
            fadd_visible = values["baseline"] != values["candidate"]
            terminal_visible = values["carry0"] != values["carry1"]
            keep_fadd = has_fadd and fadd_visible
            keep_terminal = has_terminal and terminal_visible
            if not (keep_fadd or keep_terminal):
                rejected[f"{mode}.not_visible"] += 1
                continue
            challenge = "+".join(
                name for name, active in (
                    ("fadd_boundary", keep_fadd),
                    ("terminal_collision", keep_terminal),
                ) if active
            )
            clean = {key: value for key, value in row.items()
                     if key != "_histories"}
            output_rows.append({
                "insn": "cos",
                "mode": mode,
                **clean,
                "challenge": challenge,
                "selection": ",".join(sorted(categories)),
                **values,
            })

    if not output_rows:
        raise RuntimeError("no architecturally visible adversarial legs")
    keys = [(row["mode"], row["op"]) for row in output_rows]
    if len(keys) != len(set(keys)):
        raise AssertionError("duplicate mode/operand legs")
    if any(str(row["op"]) in excluded for row in output_rows):
        raise AssertionError("excluded operand reached output")

    preferred = (
        "insn", "mode", "op", "anchor", "anchor_status", "challenge",
        "selection", "baseline", "candidate", "carry0", "carry1",
        "offset", "mreg_signed", "anchor_mreg_signed", "mreg_delta",
        "r1200_stages",
        *(f"{stage}_half_delta" for stage in ADD_STAGES),
        *(f"{stage}_r1200" for stage in ADD_STAGES),
        "terminal_fraction_order", "terminal_physical_error_order",
        "terminal_class_pair", "terminal_direction_pair",
        "structural_hamming", "structural_signature", "history_signature",
    )
    columns = preferred + tuple(sorted(
        {key for row in output_rows for key in row} - set(preferred)))
    outputs["features"].parent.mkdir(parents=True, exist_ok=True)
    with outputs["features"].open("x", newline="") as target:
        writer = csv.DictWriter(
            target, columns, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(output_rows)

    manifest_columns = (
        "insn", "mode", "op", "anchor", "anchor_status", "challenge",
        "selection", "baseline", "candidate", "carry0", "carry1",
    )
    with outputs["manifest"].open("x", newline="") as target:
        writer = csv.DictWriter(target, manifest_columns, delimiter="\t")
        writer.writeheader()
        writer.writerows({key: row[key] for key in manifest_columns}
                         for row in output_rows)
    for mode in MODES:
        with outputs[mode].open("x") as target:
            for row in output_rows:
                if row["mode"] == mode:
                    target.write(str(row["op"]) + "\n")

    inventory_spec = hashlib.sha256()
    for path in inventory_paths:
        stat = path.stat()
        inventory_spec.update(
            f"{path}\t{stat.st_size}\n".encode("utf-8", "surrogateescape"))
    counts = Counter()
    for row in output_rows:
        counts[f"mode.{row['mode']}"] += 1
        counts[f"challenge.{row['challenge']}"] += 1
        counts[f"anchor_status.{row['anchor_status']}"] += 1
    with outputs["report"].open("x") as target:
        target.write(f"anchors_sha256\t{digest(args.anchors)}\n")
        for name, model in (
                ("baseline", args.baseline), ("candidate", args.candidate),
                ("carry0", args.carry0), ("carry1", args.carry1)):
            target.write(f"{name}_sha256\t{digest(model)}\n")
        target.write(f"seed\t0x{args.seed:x}\n")
        target.write(f"samples_per_anchor\t{args.samples_per_anchor}\n")
        target.write(f"anchors\t{len(anchor_rows)}\n")
        target.write(f"post_r1200_residual_anchors\t{len(residuals)}\n")
        target.write(
            f"generated_rows\t{sum(map(len, generated_by_anchor.values()))}\n")
        target.write(f"generated_unique_operands\t{len(generated_union)}\n")
        target.write(f"inventory_files\t{len(inventory_paths)}\n")
        target.write(f"inventory_spec_sha256\t{inventory_spec.hexdigest()}\n")
        target.write(f"generated_inventory_hits\t{len(excluded)}\n")
        target.write(f"fresh_decorated_rows\t{eligible_counts['decorated']}\n")
        target.write(f"selected_software_operands\t{len(selected_operands)}\n")
        target.write(f"manifest_legs\t{len(output_rows)}\n")
        target.write(
            "rz_policy\tomitted_positive_fcos_duplicate_of_rd\n")
        target.write(
            "hardware_policy\tsoftware_only_no_x87_execution\n")
        target.write(
            "dense_archive_gap\t1463888-row extracted operand archive is "
            "not present locally; surviving source inventories and h1194 "
            "rows were checked\n")
        target.write(f"manifest_sha256\t{digest(outputs['manifest'])}\n")
        target.write("\n[counts]\n")
        for name, value in sorted(counts.items()):
            target.write(f"{name}\t{value}\n")
        target.write("\n[reconstruction failures]\n")
        if reconstruction_failures:
            for name, value in sorted(reconstruction_failures.items()):
                target.write(f"{name}\t{value}\n")
        else:
            target.write("none\t0\n")
        target.write("\n[inventory candidate hits]\n")
        for path, count in inventory_counts:
            if count:
                target.write(f"{count}\t{path}\n")
        target.write("\n[visibility rejects]\n")
        for name, value in sorted(rejected.items()):
            target.write(f"{name}\t{value}\n")

    print(
        f"wrote {outputs['manifest']} operands={len(set(row['op'] for row in output_rows))} "
        f"legs={len(output_rows)} counts={dict(counts)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
