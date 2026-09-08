#!/usr/bin/env python3
"""Reframe the cached stage-A FCOS residual as an all-mode endpoint test.

The complete h1208 stage-A score identifies every RN/RD/RU disagreement for
the promoted model on the eight cached comb corpora.  For each distinct
operand in that miss set, this script reconstructs the other mode results from
the same verified wall, evaluates the five absolute R59 retained corrections,
and intersects their allowed sets across RN/RD/RU/RZ.  Positive FCOS outputs
make RZ identical to RD; no hardware is executed here.

It also emits one internal-feature row per operand.  The feature mode is a
mode in which the incumbent model fails, but the desired correction is the
all-mode intersection and therefore cannot be selected by a one-mode fit.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import subprocess
from pathlib import Path


MODES = ("rn", "rd", "ru", "rz")


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


def run(model: Path, mode: str, operands: list[str], dump: bool = False
        ) -> tuple[list[str], str]:
    command = [str(model), "--batch", f"--rc={mode}", "--fcos-standalone"]
    if dump:
        command.append("--dump-internals")
    process = subprocess.run(
        command, input="\n".join(operands) + "\n", text=True,
        capture_output=True, check=True,
    )
    values = [parse_output(line) for line in process.stdout.splitlines()]
    if len(values) != len(operands):
        raise RuntimeError(
            f"output count {len(values)} != {len(operands)} for {model}/{mode}"
        )
    return values, process.stderr


def parse_tokens(line: str) -> dict[str, str]:
    return {
        match.group(1): match.group(2)
        for match in re.finditer(r"(\w+)=([0-9a-fA-F,-]+)", line)
    }


def parse_wide_values(line: str) -> dict[str, str]:
    values = {}
    for match in re.finditer(
        r"(mul|lf|rf|f4|mag|left|right)=([01]):(-?\d+):([0-9a-fA-F]+)",
        line,
    ):
        name, sign, exponent, significand = match.groups()
        values["tc_" + name + "_sign"] = sign
        values["tc_" + name + "_exp"] = exponent
        values["tc_" + name + "_sig"] = significand.lower()
    return values


def parse_dump(stderr: str, operands: list[str]) -> list[dict[str, str]]:
    records = []
    current = None
    for line in stderr.splitlines():
        if line.startswith("DI_IN "):
            if current is not None:
                records.append(current)
            current = {"op": " ".join(line.split()[1:3]).lower()}
        elif current is not None and line.startswith("DI_R59 "):
            current.update(parse_tokens(line))
        elif current is not None and line.startswith("DI_TC "):
            current.update({
                "tc_" + key: value for key, value in parse_tokens(line).items()
            })
            current.update(parse_wide_values(line))
        elif current is not None and line.startswith("DI_CRIT "):
            current.update({
                "crit_" + key: value for key, value in parse_tokens(line).items()
            })
        elif current is not None and line.startswith("DI_BS "):
            current.update({
                "bs_" + key: value for key, value in parse_tokens(line).items()
            })
        elif current is not None and line.startswith("DI_BR "):
            current["branch"] = line.split()[1].split("=", 1)[1]
            current.update({
                "br_" + key: value
                for key, value in parse_tokens(line).items() if key != "br"
            })
    if current is not None:
        records.append(current)
    if len(records) != len(operands):
        raise RuntimeError(
            f"dump count {len(records)} != {len(operands)}"
        )
    for expected, record in zip(operands, records):
        if record["op"] != expected:
            raise RuntimeError(
                f"dump desynchronization {record['op']} != {expected}"
            )
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("misses", type=Path)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("score", type=Path)
    parser.add_argument("features", type=Path)
    parser.add_argument("forces", nargs=5, type=Path)
    args = parser.parse_args()
    for path in (args.report, args.score, args.features):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")

    replacements: dict[tuple[str, str], str] = {}
    miss_modes: dict[str, list[str]] = {}
    with args.misses.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            mode = row["mode"].lower()
            operand = row["op"].lower()
            key = (mode, operand)
            hardware = row["hardware"].lower()
            if key in replacements and replacements[key] != hardware:
                raise RuntimeError(f"conflicting cached truth for {key}")
            replacements[key] = hardware
            miss_modes.setdefault(operand, []).append(mode)
    operands = sorted(miss_modes)

    outputs: dict[tuple[str, str, int], str] = {}
    for mode in MODES:
        baseline_values, _ = run(args.baseline, mode, operands)
        for operand, value in zip(operands, baseline_values):
            outputs[mode, operand, 0] = value
        for number, model in enumerate(args.forces, 1):
            values, _ = run(model, mode, operands)
            for operand, value in zip(operands, values):
                outputs[mode, operand, number] = value

    truth: dict[tuple[str, str], str] = {}
    for operand in operands:
        for mode in ("rn", "rd", "ru"):
            truth[mode, operand] = replacements.get(
                (mode, operand), outputs[mode, operand, 0]
            )
        truth["rz", operand] = truth["rd", operand]
    for key, hardware in replacements.items():
        if outputs[key[0], key[1], 0] == hardware:
            raise RuntimeError(f"listed miss is now exact: {key}")

    allowed: dict[str, set[int]] = {}
    per_mode_allowed: dict[tuple[str, str], set[int]] = {}
    for operand in operands:
        mode_sets = []
        for mode in MODES:
            values = {
                number - 3 for number in range(1, 6)
                if outputs[mode, operand, number] == truth[mode, operand]
            }
            per_mode_allowed[mode, operand] = values
            mode_sets.append(values)
        allowed[operand] = set.intersection(*mode_sets)

    args.score.parent.mkdir(parents=True, exist_ok=True)
    with args.score.open("x", newline="") as target:
        columns = ("insn", "mode", "op", "hw", "f0", "f1", "f2",
                   "f3", "f4", "f5", "matches")
        writer = csv.DictWriter(target, columns, delimiter="\t")
        writer.writeheader()
        for operand in operands:
            for mode in MODES:
                row = {
                    "insn": "cos", "mode": mode, "op": operand,
                    "hw": truth[mode, operand],
                    "f0": outputs[mode, operand, 0],
                    "matches": ",".join(str(delta + 3) for delta in sorted(
                        per_mode_allowed[mode, operand]
                    )) or "-",
                }
                for number in range(1, 6):
                    row[f"f{number}"] = outputs[mode, operand, number]
                writer.writerow(row)

    feature_rows = []
    for mode in MODES:
        mode_operands = sorted(
            operand for operand in operands
            if sorted(set(miss_modes[operand]), key=MODES.index)[0] == mode
        )
        if not mode_operands:
            continue
        _, stderr = run(args.baseline, mode, mode_operands, dump=True)
        for record in parse_dump(stderr, mode_operands):
            operand = record["op"]
            record.update({
                "label": "POS",
                "mode": mode,
                "hw": truth[mode, operand],
                "miss_modes": ",".join(sorted(set(miss_modes[operand]),
                                               key=MODES.index)),
                "allowed_delta": ",".join(map(str, sorted(allowed[operand])))
                    or "-",
            })
            feature_rows.append(record)
    metadata = ("label", "mode", "op", "hw", "miss_modes", "allowed_delta")
    feature_columns = metadata + tuple(sorted(
        {key for row in feature_rows for key in row} - set(metadata)
    ))
    with args.features.open("x", newline="") as target:
        writer = csv.DictWriter(
            target, feature_columns, delimiter="\t", extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(sorted(feature_rows, key=lambda row: row["op"]))

    impossible = [operand for operand in operands if not allowed[operand]]
    with args.report.open("x") as target:
        target.write(f"misses_sha256\t{digest(args.misses)}\n")
        target.write(f"baseline_sha256\t{digest(args.baseline)}\n")
        for number, model in enumerate(args.forces, 1):
            target.write(f"force{number}_sha256\t{digest(model)}\n")
        target.write("hardware_policy\tcached_stageA_only_no_x87_execution\n")
        target.write("rz_truth\tpositive_fcos_equals_rd\n")
        target.write(f"source_miss_rows\t{sum(1 for _ in args.misses.open()) - 1}\n")
        target.write(f"distinct_miss_legs\t{len(replacements)}\n")
        target.write(f"operands\t{len(operands)}\n")
        target.write(f"carry_impossible_operands\t{len(impossible)}\n")
        target.write(f"score_sha256\t{digest(args.score)}\n")
        target.write(f"features_sha256\t{digest(args.features)}\n")
        target.write("\n[all-mode endpoint intersection]\n")
        target.write("op\tmiss_modes\tallowed_delta\tper_mode\n")
        for operand in operands:
            modes = ",".join(sorted(set(miss_modes[operand]), key=MODES.index))
            common = ",".join(map(str, sorted(allowed[operand]))) or "-"
            rendered = ";".join(
                f"{mode}=" + (",".join(map(str, sorted(
                    per_mode_allowed[mode, operand]
                ))) or "-") for mode in MODES
            )
            target.write(f"{operand}\t{modes}\t{common}\t{rendered}\n")

    print(
        f"wrote {args.report} operands={len(operands)} "
        f"miss_legs={len(replacements)} carry_impossible={len(impossible)}"
    )


if __name__ == "__main__":
    main()
