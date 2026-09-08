#!/usr/bin/env python3
"""Validate and score the already-opened h1400 one-shot state capture.

The remote campaign captured the 100 core transfer rows and 24 architectural
rows with one FXSAVE-before/after record per frozen identity.  This scorer is
strictly read-only with respect to that immutable output.  It first proves
that the campaign identity is exactly the concatenation of the tracked frozen
manifests, then scores the core arithmetic transfers and checks the declared
architectural stack relations.

No absent status bit is silently accepted: the prior-flag seeding checks are
reported separately so a harness setup failure cannot be mistaken for an
instruction semantic result.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

from h1400_score_transfer_capture import anchor_value, point_key


RC_BITS = {"rn": 0x0000, "rd": 0x0400, "ru": 0x0800, "rz": 0x0C00}
PC_BITS = {"pc24": 0x0000, "pc53": 0x0200, "pc64": 0x0300}
REL_REPLACE = "TOP unchanged; ST0 replaced; deeper tags/values preserved"
REL_PUSH = "TOP decremented; ST0=cos; ST1=sin; deeper values preserved"
REL_C2 = "TOP and all registers unchanged; C2=1; no push"


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    if not rows:
        raise RuntimeError(f"empty input: {path}")
    return rows


def parse_state(path: Path) -> list[dict[str, str]]:
    rows = []
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        fields = {}
        for token in line.split():
            key, separator, value = token.partition("=")
            if not separator:
                raise RuntimeError(f"{path}:{line_number}: bad token {token!r}")
            fields[key] = value.lower()
        required = {
            "CASE", "INSN", "MODE", "PC", "MASKS", "DEPTH", "PRIOR",
            "B_CW", "B_SW", "B_TOP", "B_FTW", "B_R0",
            "A_CW", "A_SW", "A_TOP", "A_FTW", "A_R0",
        }
        missing = required - set(fields)
        if missing:
            raise RuntimeError(
                f"{path}:{line_number}: missing {sorted(missing)}"
            )
        rows.append(fields)
    return rows


def expected_identity(core: list[dict[str, str]],
                      architecture: list[dict[str, str]]
                      ) -> list[dict[str, str]]:
    rows = []
    for row in core:
        rows.append({
            "case_id": row["case_id"],
            "source": "core",
            "family_or_requirement": row["family"],
            "transfer_kind": row["transfer_kind"],
            "instruction": row["instruction"],
            "mode": row["mode"],
            "precision_control": "pc64",
            "exception_masks_hex": "3f",
            "pre_stack_depth": "1",
            "prior_flags": "clear",
            "operand": row["operand"],
        })
    for row in architecture:
        rows.append({
            "case_id": row["case_id"],
            "source": "architecture",
            "family_or_requirement": row["requirement"],
            "transfer_kind": row["encoding_class"],
            "instruction": row["instruction"],
            "mode": row["mode"],
            "precision_control": row["precision_control"],
            "exception_masks_hex": row["exception_masks_hex"],
            "pre_stack_depth": row["pre_stack_depth"],
            "prior_flags": row["prior_flags"],
            "operand": row["operand"],
        })
    return rows


def verify_identity(expected: list[dict[str, str]],
                    observed: list[dict[str, str]]) -> None:
    if len(expected) != len(observed):
        raise RuntimeError(
            f"identity row count differs: {len(expected)} != {len(observed)}"
        )
    columns = tuple(expected[0])
    if tuple(observed[0]) != columns:
        raise RuntimeError(
            f"identity columns differ: {tuple(observed[0])} != {columns}"
        )
    for index, (left, right) in enumerate(zip(expected, observed), 1):
        expected_normalized = {
            key: value.lower() for key, value in left.items()
        }
        normalized = {key: value.lower() for key, value in right.items()}
        if expected_normalized != normalized:
            differences = {
                key: (expected_normalized[key], normalized.get(key))
                for key in columns
                if expected_normalized[key] != normalized.get(key)
            }
            raise RuntimeError(f"identity row {index} differs: {differences}")


def raw_value(row: dict[str, str], name: str) -> str:
    return row[name].lower()


def target_value(core: dict[str, str], state: dict[str, str]) -> str:
    instruction = core["instruction"]
    if instruction != "fsincos":
        return raw_value(state, "A_R0")
    return raw_value(state, "A_R1" if core["target_lane"] == "sin" else "A_R0")


def check_before(identity: dict[str, str], state: dict[str, str]) -> list[str]:
    failures = []
    mappings = {
        "CASE": "case_id",
        "INSN": "instruction",
        "MODE": "mode",
        "PC": "precision_control",
        "MASKS": "exception_masks_hex",
        "DEPTH": "pre_stack_depth",
        "PRIOR": "prior_flags",
    }
    for raw_name, identity_name in mappings.items():
        if state[raw_name] != identity[identity_name].lower():
            failures.append(f"metadata.{raw_name}")

    masks = int(identity["exception_masks_hex"], 16)
    expected_cw = 0x0040 | masks | RC_BITS[identity["mode"]] | PC_BITS[
        identity["precision_control"]
    ]
    depth = int(identity["pre_stack_depth"])
    expected_top = (-depth) & 7
    expected_ftw = ((1 << depth) - 1) << (8 - depth)
    expected_operand = identity["operand"].replace(" ", ":").lower()
    if int(state["B_CW"], 16) != expected_cw:
        failures.append("before.control_word")
    if int(state["B_TOP"]) != expected_top:
        failures.append("before.top")
    if int(state["B_FTW"], 16) != expected_ftw:
        failures.append("before.abridged_tag")
    if state["B_R0"] != expected_operand:
        failures.append("before.operand")

    sw = int(state["B_SW"], 16)
    prior = identity["prior_flags"]
    expected_flag = {"clear": 0, "ie": 0x01, "pe": 0x20}[prior]
    if (sw & 0x21) != expected_flag:
        failures.append(f"before.prior_flags.{prior}")
    return failures


def check_relation(architecture: dict[str, str],
                   state: dict[str, str]) -> list[str]:
    relation = architecture["expected_stack_relation"]
    before_top = int(state["B_TOP"])
    after_top = int(state["A_TOP"])
    failures = []
    if relation == REL_REPLACE:
        if after_top != before_top:
            failures.append("relation.replace.top")
        if state["A_FTW"] != state["B_FTW"]:
            failures.append("relation.replace.tags")
        if any(state[f"A_R{index}"] != state[f"B_R{index}"]
               for index in range(1, 8)):
            failures.append("relation.replace.deeper_values")
    elif relation == REL_PUSH:
        if after_top != ((before_top - 1) & 7):
            failures.append("relation.push.top")
        if any(state[f"A_R{index}"] != state[f"B_R{index - 1}"]
               for index in range(2, 8)):
            failures.append("relation.push.deeper_values")
    elif relation == REL_C2:
        if after_top != before_top:
            failures.append("relation.c2.top")
        if state["A_FTW"] != state["B_FTW"]:
            failures.append("relation.c2.tags")
        if any(state[f"A_R{index}"] != state[f"B_R{index}"]
               for index in range(8)):
            failures.append("relation.c2.values")
        if not (int(state["A_SW"], 16) & 0x0400):
            failures.append("relation.c2.flag")
    elif relation.startswith("measure masked stack-overflow"):
        # This row intentionally had no predeclared outcome.
        pass
    else:
        failures.append("relation.unknown_specification")
    return failures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("core_manifest", type=Path)
    parser.add_argument("architecture_manifest", type=Path)
    parser.add_argument("identity_manifest", type=Path)
    parser.add_argument("raw_state", type=Path)
    parser.add_argument("output_prefix", type=Path)
    args = parser.parse_args()

    score_path = args.output_prefix.with_name(args.output_prefix.name + "_score.tsv")
    architecture_path = args.output_prefix.with_name(
        args.output_prefix.name + "_architecture.tsv"
    )
    report_path = args.output_prefix.with_name(args.output_prefix.name + "_report.txt")
    for path in (score_path, architecture_path, report_path):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")

    core = read_tsv(args.core_manifest)
    architecture = read_tsv(args.architecture_manifest)
    identity = read_tsv(args.identity_manifest)
    expected = expected_identity(core, architecture)
    verify_identity(expected, identity)
    raw = parse_state(args.raw_state)
    if len(raw) != len(expected):
        raise RuntimeError(
            f"state row count differs: {len(raw)} != {len(expected)}"
        )

    state_by_case = {}
    before_failures = {}
    for identity_row, state in zip(expected, raw):
        case_id = identity_row["case_id"]
        if case_id in state_by_case:
            raise RuntimeError(f"duplicate raw case {case_id}")
        state_by_case[case_id] = state
        failures = check_before(identity_row, state)
        if failures:
            before_failures[case_id] = failures

    core_counts = Counter()
    points = defaultdict(list)
    for row in core:
        state = state_by_case[row["case_id"]]
        hardware = target_value(row, state)
        row["hardware_target"] = hardware
        row["incumbent_verdict"] = (
            "EXACT" if hardware == row["model_incumbent"] else "MISS"
        )
        row["ablation_verdict"] = (
            "" if not row["model_ablation"]
            else "EXACT" if hardware == row["model_ablation"] else "MISS"
        )
        expected_anchor = anchor_value(row["anchor_hardware"])
        row["anchor_transfer_verdict"] = (
            "" if not expected_anchor
            or row["transfer_kind"] != "exact_internal_residual"
            or row["cosine_projection_sign"] != "1"
            else "EXACT" if hardware == expected_anchor else "MISS"
        )
        points[point_key(row)].append(row)
        core_counts[f"family.{row['family']}.incumbent.{row['incumbent_verdict']}"] += 1
        if row["ablation_verdict"]:
            core_counts[f"family.{row['family']}.ablation.{row['ablation_verdict']}"] += 1
        if row["anchor_transfer_verdict"]:
            core_counts[
                f"family.{row['family']}.anchor.{row['anchor_transfer_verdict']}"
            ] += 1

    point_counts = Counter()
    for key, members in points.items():
        if len(members) != 2:
            raise RuntimeError(f"bad transfer point {key}: {len(members)} rows")
        paired = next(row for row in members if row["instruction"] == "fsincos")
        standalone = next(row for row in members if row["instruction"] != "fsincos")
        verdict = (
            "EXACT" if paired["hardware_target"] == standalone["hardware_target"]
            else "DIFF"
        )
        point_counts[f"family.{key[0]}.paired_vs_standalone.{verdict}"] += 1
        for row in members:
            row["paired_standalone_verdict"] = verdict

    architecture_rows = []
    architecture_counts = Counter()
    for row in architecture:
        state = state_by_case[row["case_id"]]
        failures = before_failures.get(row["case_id"], []) + check_relation(row, state)
        rendered = dict(row)
        rendered["before_verdict"] = (
            "EXACT" if row["case_id"] not in before_failures else "FAIL"
        )
        rendered["relation_verdict"] = (
            "EXACT" if not check_relation(row, state) else "FAIL"
        )
        rendered["failures"] = ",".join(failures)
        rendered["before_sw"] = state["B_SW"]
        rendered["after_sw"] = state["A_SW"]
        rendered["before_top"] = state["B_TOP"]
        rendered["after_top"] = state["A_TOP"]
        rendered["before_ftw"] = state["B_FTW"]
        rendered["after_ftw"] = state["A_FTW"]
        architecture_rows.append(rendered)
        architecture_counts[f"before.{rendered['before_verdict']}"] += 1
        architecture_counts[f"relation.{rendered['relation_verdict']}"] += 1
        for failure in failures:
            architecture_counts[f"failure.{failure}"] += 1

    score_path.parent.mkdir(parents=True, exist_ok=True)
    with score_path.open("x", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=tuple(core[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(core)
    with architecture_path.open("x", newline="") as target:
        writer = csv.DictWriter(
            target, fieldnames=tuple(architecture_rows[0]), delimiter="\t"
        )
        writer.writeheader()
        writer.writerows(architecture_rows)

    with report_path.open("x") as target:
        target.write(f"core_manifest_sha256\t{sha256(args.core_manifest)}\n")
        target.write(
            f"architecture_manifest_sha256\t{sha256(args.architecture_manifest)}\n"
        )
        target.write(f"identity_manifest_sha256\t{sha256(args.identity_manifest)}\n")
        target.write(f"raw_state_sha256\t{sha256(args.raw_state)}\n")
        target.write(f"score_sha256\t{sha256(score_path)}\n")
        target.write(f"architecture_score_sha256\t{sha256(architecture_path)}\n")
        target.write("capture_policy\texisting_one_observation_per_frozen_identity\n")
        target.write(f"identity_rows\t{len(expected)}\n")
        target.write(f"core_rows\t{len(core)}\n")
        target.write(f"architecture_rows\t{len(architecture)}\n")
        target.write("identity_reconciliation\tEXACT\n")
        target.write("\n[core counts]\n")
        for name, count in sorted(core_counts.items()):
            target.write(f"{name}\t{count}\n")
        for name, count in sorted(point_counts.items()):
            target.write(f"{name}\t{count}\n")
        target.write("\n[architecture counts]\n")
        for name, count in sorted(architecture_counts.items()):
            target.write(f"{name}\t{count}\n")
        target.write("\n[architecture failures]\n")
        target.write("case_id\tfailures\n")
        for row in architecture_rows:
            if row["failures"]:
                target.write(f"{row['case_id']}\t{row['failures']}\n")

    print(
        f"wrote {score_path}, {architecture_path}, {report_path}: "
        f"core={len(core)} architecture={len(architecture)} "
        f"before_failures={len(before_failures)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
