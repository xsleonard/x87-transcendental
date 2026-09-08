#!/usr/bin/env python3
"""Recover and validate standalone FCOS's tiny directed-rounding boundary."""

from __future__ import annotations

import argparse
import collections
import pathlib
import subprocess

import h58_constraint_search as h58
import h234_fcos_residual_map as h234
import h237_fcos_p6_split_sweep as h237


ROOT = pathlib.Path(__file__).resolve().parents[1]
INPUTS = ROOT / "capture-kit" / "inputs" / "sweep_inputs.txt"
CAPTURE = ROOT / "capture-kit-captures" / "skylake-fsin-h110"
ONE = ("OK", "3fff", "8000000000000000")
PREDECESSOR = ("OK", "3ffe", "ffffffffffffffff")


def run_model(
    model: pathlib.Path,
    input_text: str,
    rc: str,
    round39: bool,
    replay_dir: pathlib.Path | None = None,
) -> list[tuple[str, ...]]:
    if round39 and replay_dir is not None:
        return [
            h237.parse_value(line)
            for line in (
                replay_dir / f"sweep_{rc}.txt"
            ).read_text().splitlines()
        ]
    command = [
        str(model.resolve()),
        *h237.BASE_FLAGS,
        "--round38-p6-cosine-split",
    ]
    if round39:
        command.append("--round39-fcos-tiny")
    if rc != "rn":
        command.append(f"--rc={rc}")
    return [
        h237.parse_value(line)
        for line in subprocess.run(
            command,
            input=input_text,
            text=True,
            stdout=subprocess.PIPE,
            check=True,
        ).stdout.splitlines()
    ]


def tiny_expected(exponent: int, rc: str) -> tuple[str, ...]:
    if exponent >= -68 and rc in ("rd", "rz"):
        return PREDECESSOR
    return ONE


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=pathlib.Path)
    parser.add_argument("--round39-replay-dir", type=pathlib.Path)
    args = parser.parse_args()

    input_text = INPUTS.read_text()
    inputs = [
        tuple(int(field, 16) for field in line.split())
        for line in input_text.splitlines()
    ]
    total_old = 0
    total_new = 0
    old_inputs = set()
    new_inputs = set()
    fixed = 0
    regressed = 0
    residuals = collections.Counter()
    tiny_checks = 0
    for rc in h58.RCS:
        old = run_model(args.model, input_text, rc, False)
        new = run_model(
            args.model,
            input_text,
            rc,
            True,
            args.round39_replay_dir,
        )
        hardware = [
            h237.parse_value(line)
            for line in (
                CAPTURE / f"sweep_fcos_{rc}_status.txt"
            ).read_text().splitlines()
        ]
        rc_old = 0
        rc_new = 0
        for index, ((se, sig), old_value, new_value, expected) in enumerate(
            zip(inputs, old, new, hardware)
        ):
            path = h234.classify(se, sig)
            if path[0] == "direct" and path[1] == "tiny":
                exponent = (se & 0x7FFF) - 16383
                if expected != tiny_expected(exponent, rc):
                    raise SystemExit(
                        f"tiny rule differs at input {index} rc={rc}"
                    )
                tiny_checks += 1
            old_miss = old_value != expected
            new_miss = new_value != expected
            rc_old += old_miss
            rc_new += new_miss
            old_inputs.add(index) if old_miss else None
            new_inputs.add(index) if new_miss else None
            fixed += old_miss and not new_miss
            regressed += new_miss and not old_miss
            if new_miss:
                residuals[path] += 1
        total_old += rc_old
        total_new += rc_new
        print(f"{rc}: {rc_old} -> {rc_new} mode misses")

    print(f"validated tiny capture checks: {tiny_checks}")
    print(
        f"combined: {total_old} -> {total_new} mode misses; "
        f"{len(old_inputs)} -> {len(new_inputs)} inputs; "
        f"fixed={fixed} regressed={regressed}"
    )
    print("Round-39 residual paths:")
    for path, count in sorted(residuals.items()):
        cell = "-" if path[3] is None else str(path[3])
        print(
            f"  {path[0]:7s} {path[1]:12s} {path[2]:9s} "
            f"cell={cell}: {count}"
        )


if __name__ == "__main__":
    main()
