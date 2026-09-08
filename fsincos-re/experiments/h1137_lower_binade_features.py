#!/usr/bin/env python3
"""Recover per-operand retained-delta sets and R59 state for h1135."""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path


DELTAS = (-2, -1, 0, 1)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def parse_values(text: str, expected: int) -> list[str]:
    values = []
    for number, line in enumerate(text.splitlines(), 1):
        fields = line.split()
        if len(fields) != 3 or fields[0] != "OK":
            raise RuntimeError(f"bad model row {number}: {line}")
        values.append(fields[1].lower() + ":" + fields[2].lower())
    if len(values) != expected:
        raise RuntimeError(f"model rows {len(values)} != {expected}")
    return values


def run_values(binary: Path, mode: str, rows: list[dict[str, str]]) -> list[str]:
    result = subprocess.run(
        [str(binary), "--batch", f"--rc={mode}", "--fcos-standalone"],
        input="".join(row["op"] + "\n" for row in rows),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return parse_values(result.stdout, len(rows))


def parse_tokens(line: str) -> dict[str, str]:
    return {
        match.group(1): match.group(2)
        for match in re.finditer(r"(\w+)=([0-9a-fA-F,-]+)", line)
    }


def dump_records(binary: Path, operands: list[str]) -> dict[str, dict[str, str]]:
    records = {}
    for start in range(0, len(operands), 2000):
        chunk = operands[start : start + 2000]
        result = subprocess.run(
            [str(binary), "--batch", "--rc=rn", "--fcos-standalone",
             "--dump-internals"],
            input="".join(op + "\n" for op in chunk),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        current = None
        parsed = []
        for line in result.stderr.splitlines():
            if line.startswith("DI_IN "):
                if current is not None:
                    parsed.append(current)
                fields = line.split()
                current = {"op": (fields[1] + " " + fields[2]).lower()}
            elif current is not None and line.startswith("DI_R59 "):
                current.update(parse_tokens(line))
            elif current is not None and line.startswith("DI_TC "):
                current.update({"tc_" + key: value
                                for key, value in parse_tokens(line).items()})
            elif current is not None and line.startswith("DI_CRIT "):
                current.update({"crit_" + key: value
                                for key, value in parse_tokens(line).items()})
            elif current is not None and line.startswith("DI_BS "):
                current.update({"bs_" + key: value
                                for key, value in parse_tokens(line).items()})
            elif current is not None and line.startswith("DI_BR "):
                current["branch"] = line.split()[1].split("=", 1)[1]
                current.update({"br_" + key: value
                                for key, value in parse_tokens(line).items()
                                if key != "br"})
        if current is not None:
            parsed.append(current)
        if len(parsed) != len(chunk):
            raise RuntimeError(f"dump rows {len(parsed)} != {len(chunk)}")
        for expected, record in zip(chunk, parsed):
            if record["op"] != expected:
                raise RuntimeError("dump desynchronization")
            records[expected] = record
    return records


def signed128(text: str) -> int:
    value = int(text, 16)
    return value - (1 << 128) if value >> 127 else value


def add_derived(record: dict[str, str]) -> None:
    k = int(record["k"])
    s_value = int(record["S"], 16)
    b_value = int(record["B"], 16)
    propagate = ~(s_value ^ b_value)
    above = 0
    while above < 48 and ((propagate >> (k + above)) & 1):
        above += 1
    below = 0
    while k - 1 - below >= 0 and ((propagate >> (k - 1 - below)) & 1):
        below += 1
    umag = int(record["umag"], 16)
    record["pabove"] = str(above)
    record["pbelow"] = str(below)
    record["retained_low16"] = f"{(umag >> k) & 0xffff:04x}"
    record["retained_low8"] = f"{(umag >> k) & 0xff:02x}"
    record["mreg_signed"] = str(signed128(record["Mreg"]))
    record["mreg_128"] = str(signed128(record["Mreg"]) // (1 << 59))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("score", type=Path)
    parser.add_argument("wide_rule", type=Path)
    parser.add_argument("force_minus2", type=Path)
    parser.add_argument("force_minus1", type=Path)
    parser.add_argument("force_zero", type=Path)
    parser.add_argument("force_plus1", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--candidate", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    with args.score.open(newline="") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    by_mode = defaultdict(list)
    for row in rows:
        by_mode[row["mode"]].append(row)
    force_paths = {
        -2: args.force_minus2,
        -1: args.force_minus1,
        0: args.force_zero,
        1: args.force_plus1,
    }
    predictions: dict[tuple[str, str], dict[int, str]] = {}
    candidate_predictions: dict[tuple[str, str], str] = {}
    for mode, mode_rows in sorted(by_mode.items()):
        values = {
            delta: run_values(path, mode, mode_rows)
            for delta, path in force_paths.items()
        }
        for index, row in enumerate(mode_rows):
            entry = {delta: result[index] for delta, result in values.items()}
            if entry[-2] != row["force_minus2"] or entry[1] != row["force_plus1"]:
                raise RuntimeError("frozen endpoint prediction changed")
            predictions[(mode, row["op"])] = entry
        if args.candidate is not None:
            candidate_values = run_values(args.candidate, mode, mode_rows)
            for row, value in zip(mode_rows, candidate_values):
                candidate_predictions[(mode, row["op"])] = value

    grouped = defaultdict(list)
    for row in rows:
        grouped[row["op"]].append(row)
    operands = sorted(grouped)
    internals = dump_records(args.wide_rule, operands)
    output_rows = []
    allowed_counts = Counter()
    for op in operands:
        legs = grouped[op]
        target = set(DELTAS)
        base = set(DELTAS)
        wide = set(DELTAS)
        candidate = set(DELTAS)
        for leg in legs:
            values = predictions[(leg["mode"], op)]
            target &= {delta for delta, value in values.items() if value == leg["hw"]}
            base &= {delta for delta, value in values.items() if value == leg["base"]}
            wide &= {delta for delta, value in values.items()
                     if value == leg["wide_rule"]}
            if args.candidate is not None:
                candidate &= {
                    delta for delta, value in values.items()
                    if value == candidate_predictions[(leg["mode"], op)]
                }
        if not target:
            raise RuntimeError(f"no retained delta matches all captured modes for {op}")
        record = dict(internals[op])
        add_derived(record)
        first = legs[0]
        record.update({
            "modes": ",".join(sorted(leg["mode"] for leg in legs)),
            "target_allowed": ",".join(str(value) for value in sorted(target)),
            "base_allowed": ",".join(str(value) for value in sorted(base)),
            "wide_allowed": ",".join(str(value) for value in sorted(wide)),
            "candidate_allowed": (
                ",".join(str(value) for value in sorted(candidate))
                if args.candidate is not None else ""
            ),
            "target_unique": str(int(len(target) == 1)),
            "target_delta": str(next(iter(target))) if len(target) == 1 else "",
            "base_exact": str(int(all(leg["verdict"] == "EXACT" for leg in legs))),
            "wide_exact": str(int(all(leg["wide_verdict"] == "EXACT" for leg in legs))),
            "candidate_exact": str(int(
                args.candidate is not None
                and all(candidate_predictions[(leg["mode"], op)] == leg["hw"]
                        for leg in legs)
            )),
            "scan_corr_e": first["corr_e"],
            "scan_dist": first["dist"],
            "scan_theta": first["theta"],
            "scan_t4hi12": first["t4hi12"],
            "scan_rdhi12": first["rdhi12"],
        })
        output_rows.append(record)
        allowed_counts[record["target_allowed"]] += 1

    metadata = (
        "op", "modes", "target_allowed", "target_unique", "target_delta",
        "base_allowed", "wide_allowed", "candidate_allowed", "base_exact",
        "wide_exact", "candidate_exact",
        "scan_corr_e", "scan_dist", "scan_theta", "scan_t4hi12",
        "scan_rdhi12", "branch", "theta", "k", "ce", "s4", "side",
        "b1", "b2", "low3", "dist", "rsh", "payload", "rscale", "dl",
        "dr", "dp", "umag", "S", "B", "Mreg", "t4", "sqlow", "rd3",
        "disc", "pabove", "pbelow", "retained_low16", "retained_low8",
        "mreg_signed", "mreg_128",
    )
    extras = sorted({name for row in output_rows for name in row} - set(metadata))
    columns = metadata + tuple(extras)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as target_file:
        writer = csv.DictWriter(target_file, columns, delimiter="\t",
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"score_sha256={digest(args.score)} legs={len(rows)}")
    for delta, path in force_paths.items():
        print(f"force_delta_{delta}_sha256={digest(path)}")
    print(f"output_sha256={digest(args.output)} operands={len(output_rows)}")
    print(f"target_allowed={dict(allowed_counts)}")
    print(f"base_exact={sum(row['base_exact'] == '1' for row in output_rows)}")
    print(f"wide_exact={sum(row['wide_exact'] == '1' for row in output_rows)}")
    if args.candidate is not None:
        print(f"candidate_sha256={digest(args.candidate)}")
        print(f"candidate_exact={sum(row['candidate_exact'] == '1' for row in output_rows)}")


if __name__ == "__main__":
    main()
