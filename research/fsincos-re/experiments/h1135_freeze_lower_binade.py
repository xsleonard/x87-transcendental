#!/usr/bin/env python3
"""Freeze a blind, endpoint-observable FCOS bank from a 3ffb tie scan.

The scanner and all three model variants are software-only.  Hardware labels
must not exist when this script is run.  Positive FCOS makes RD and RZ
architecturally redundant, so the frozen bank contains RN, RD, and RU only.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import subprocess
from collections import Counter
from pathlib import Path


MODES = ("rn", "rd", "ru")
TIE_FIELDS = (
    "sig",
    "dist",
    "low3",
    "k",
    "rud",
    "t4hi12",
    "rdhi12",
    "terminal_r",
    "corr_e",
    "theta",
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def read_ties(path: Path) -> list[dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    with path.open() as source:
        for number, line in enumerate(source, 1):
            fields = line.split()
            if len(fields) != len(TIE_FIELDS):
                raise SystemExit(f"bad tie row {path}:{number}")
            row = dict(zip(TIE_FIELDS, fields))
            op = "3ffb " + row["sig"].lower()
            if op in rows and rows[op] != row:
                raise SystemExit(f"conflicting duplicate tie row for {op}")
            rows[op] = row
    return [{"op": op, **rows[op]} for op in sorted(rows)]


def run_model(binary: Path, mode: str, rows: list[dict[str, str]]) -> list[str]:
    operands = "".join(row["op"] + "\n" for row in rows)
    result = subprocess.run(
        [str(binary), "--batch", f"--rc={mode}", "--fcos-standalone"],
        input=operands,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    values = []
    for number, line in enumerate(result.stdout.splitlines(), 1):
        fields = line.split()
        if len(fields) != 3 or fields[0] != "OK":
            raise SystemExit(f"bad model row {binary}:{mode}:{number}: {line}")
        values.append(fields[1].lower() + ":" + fields[2].lower())
    if len(values) != len(rows):
        raise SystemExit(
            f"model row mismatch {binary}:{mode}: {len(values)} != {len(rows)}"
        )
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("ties", type=Path)
    parser.add_argument("base", type=Path)
    parser.add_argument("wide_rule", type=Path)
    parser.add_argument("force_minus2", type=Path)
    parser.add_argument("force_plus1", type=Path)
    parser.add_argument("output_prefix", type=Path)
    args = parser.parse_args()

    outputs = [
        args.output_prefix.with_name(args.output_prefix.name + "_manifest.tsv"),
        *[
            args.output_prefix.with_name(
                args.output_prefix.name + f"_{mode}_ops.txt"
            )
            for mode in MODES
        ],
    ]
    for path in outputs:
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")

    ties = read_ties(args.ties)
    if not ties:
        raise SystemExit("empty tie scan")
    model_paths = {
        "base": args.base,
        "wide_rule": args.wide_rule,
        "force_minus2": args.force_minus2,
        "force_plus1": args.force_plus1,
    }
    manifest: list[dict[str, str]] = []
    visibility = Counter()
    for mode in MODES:
        predictions = {
            name: run_model(path, mode, ties) for name, path in model_paths.items()
        }
        for ordinal, tie in enumerate(ties):
            values = {name: result[ordinal] for name, result in predictions.items()}
            endpoint_count = len({
                values[name]
                for name in ("base", "force_minus2", "force_plus1")
            })
            if endpoint_count == 1:
                continue
            choices = [
                name for name in ("force_minus2", "force_plus1")
                if values["base"] == values[name]
            ]
            row = {
                "insn": "cos",
                "mode": mode,
                **tie,
                **values,
                "base_choice": ",".join(choices) or "neither",
                "endpoint_count": str(endpoint_count),
                "scan_ordinal": str(ordinal),
            }
            manifest.append(row)
            visibility[(mode, endpoint_count)] += 1

    columns = (
        "insn",
        "mode",
        "op",
        *TIE_FIELDS,
        "base",
        "wide_rule",
        "force_minus2",
        "force_plus1",
        "base_choice",
        "endpoint_count",
        "scan_ordinal",
    )
    outputs[0].parent.mkdir(parents=True, exist_ok=True)
    with outputs[0].open("w", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=columns, delimiter="\t")
        writer.writeheader()
        writer.writerows(manifest)
    for mode, path in zip(MODES, outputs[1:]):
        with path.open("w") as target:
            for row in manifest:
                if row["mode"] == mode:
                    target.write(row["op"] + "\n")

    print(f"ties_sha256={digest(args.ties)} ties={len(ties)}")
    for name, path in model_paths.items():
        print(f"{name}_sha256={digest(path)}")
    print(f"manifest_rows={len(manifest)} unique_operands={len({row['op'] for row in manifest})}")
    for key, count in sorted(visibility.items()):
        print(f"mode={key[0]} endpoint_count={key[1]} rows={count}")
    for path in outputs:
        print(f"{path.name}_sha256={digest(path)} rows={sum(1 for _ in path.open())}")


if __name__ == "__main__":
    main()
