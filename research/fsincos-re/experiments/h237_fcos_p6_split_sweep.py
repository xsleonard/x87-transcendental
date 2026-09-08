#!/usr/bin/env python3
"""Cross-validate C Round 38 on the independent FCOS master sweep."""

from __future__ import annotations

import argparse
import collections
import pathlib
import subprocess

import h58_constraint_search as h58
import h234_fcos_residual_map as h234


ROOT = pathlib.Path(__file__).resolve().parents[1]
INPUTS = ROOT / "capture-kit" / "inputs" / "sweep_inputs.txt"
CAPTURE = ROOT / "capture-kit-captures" / "skylake-fsin-h110"


BASE_FLAGS = (
    "--batch",
    "--fcos-standalone",
    "--round18-poly",
    "--round21-table-bias",
    "--round23-narrow-coefficient",
    "--round24-table-delta-rn67",
    "--round29-p5-fmul-route",
    "--round30-fsin-cosine-square",
    "--round31-fsin-cosine-tail",
    "--round32-fsin-cosine-horner",
    "--round33-fsin-cosine-product",
    "--round34-table-lookup-firc",
    "--round35-table-p-terminal",
    "--round36-table-fadd-microcontrol",
    "--round37-p6-four-term",
)


def parse_value(line: str) -> tuple[str, ...]:
    fields = line.split()
    if fields[0] == "C2":
        return ("C2",)
    if fields[0] != "OK":
        raise ValueError(line)
    return "OK", fields[1], fields[2]


def run_model(
    model: pathlib.Path,
    input_text: str,
    rc: str,
    round38: bool,
    replay_dir: pathlib.Path | None = None,
) -> list[tuple[str, ...]]:
    if round38 and replay_dir is not None:
        return [
            parse_value(line)
            for line in (
                replay_dir / f"sweep_{rc}.txt"
            ).read_text().splitlines()
        ]
    command = [str(model.resolve()), *BASE_FLAGS]
    if round38:
        command.append("--round38-p6-cosine-split")
    if rc != "rn":
        command.append(f"--rc={rc}")
    return [
        parse_value(line)
        for line in subprocess.run(
            command,
            input=input_text,
            text=True,
            stdout=subprocess.PIPE,
            check=True,
        ).stdout.splitlines()
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=pathlib.Path)
    parser.add_argument(
        "--round38-replay-dir",
        type=pathlib.Path,
        help="score precomputed sweep_{rn,rd,ru}.txt Round-38 output",
    )
    args = parser.parse_args()

    input_text = INPUTS.read_text()
    inputs = [
        tuple(int(field, 16) for field in line.split())
        for line in input_text.splitlines()
    ]
    baseline_misses = 0
    round38_misses = 0
    fixed = 0
    regressed = 0
    baseline_inputs = set()
    round38_inputs = set()
    residuals = collections.Counter()
    transitions = collections.Counter()
    for rc in h58.RCS:
        baseline = run_model(args.model, input_text, rc, False)
        round38 = run_model(
            args.model,
            input_text,
            rc,
            True,
            args.round38_replay_dir,
        )
        hardware = [
            parse_value(line)
            for line in (
                CAPTURE / f"sweep_fcos_{rc}_status.txt"
            ).read_text().splitlines()
        ]
        rc_baseline = 0
        rc_round38 = 0
        for index, (old, new, expected) in enumerate(
            zip(baseline, round38, hardware)
        ):
            old_miss = old != expected
            new_miss = new != expected
            rc_baseline += old_miss
            rc_round38 += new_miss
            baseline_inputs.add(index) if old_miss else None
            round38_inputs.add(index) if new_miss else None
            fixed += old_miss and not new_miss
            regressed += new_miss and not old_miss
            path = h234.classify(*inputs[index])
            if old_miss and not new_miss:
                transitions[path + ("fixed",)] += 1
            elif new_miss and not old_miss:
                transitions[path + ("regressed",)] += 1
            if new_miss:
                residuals[path] += 1
        baseline_misses += rc_baseline
        round38_misses += rc_round38
        print(f"{rc}: {rc_baseline} -> {rc_round38} mode misses")

    print(
        f"combined: {baseline_misses} -> {round38_misses} mode misses; "
        f"{len(baseline_inputs)} -> {len(round38_inputs)} inputs; "
        f"fixed={fixed} regressed={regressed}"
    )
    print("Round-38 residual paths:")
    for path, count in sorted(residuals.items()):
        cell = "-" if path[3] is None else str(path[3])
        print(
            f"  {path[0]:7s} {path[1]:12s} {path[2]:9s} "
            f"cell={cell}: {count}"
        )
    print("Round-38 changed-result transitions:")
    for key, count in sorted(transitions.items()):
        path, disposition = key[:4], key[4]
        cell = "-" if path[3] is None else str(path[3])
        print(
            f"  {path[0]:7s} {path[1]:12s} {path[2]:9s} "
            f"cell={cell} {disposition}: {count}"
        )


if __name__ == "__main__":
    main()
