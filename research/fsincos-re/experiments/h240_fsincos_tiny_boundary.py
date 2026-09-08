#!/usr/bin/env python3
"""Validate paired FSINCOS's two captured tiny-input lane boundaries."""

from __future__ import annotations

import argparse
import collections
import pathlib
import subprocess

import h58_constraint_search as h58
import h239_round39_residual_census as h239


ROOT = pathlib.Path(__file__).resolve().parents[1]
INPUTS = ROOT / "capture-kit" / "inputs" / "sweep_inputs.txt"
CAPTURE = ROOT / "capture-kit-captures" / "skylake-fsin-h177"
ONE = ("OK", "3fff", "8000000000000000")
PREDECESSOR = ("OK", "3ffe", "ffffffffffffffff")


def run_model(
    model: pathlib.Path,
    input_text: str,
    rc: str,
    round40: bool,
    replay_dir: pathlib.Path | None = None,
) -> list[tuple[h239.Value, ...]]:
    if round40 and replay_dir is not None:
        return [
            h239.parse_model(line, True)
            for line in (
                replay_dir / f"sweep_{rc}.txt"
            ).read_text().splitlines()
        ]
    command = [str(model.resolve()), *h239.BASE_FLAGS]
    if round40:
        command.append("--round40-fsincos-tiny")
    if rc != "rn":
        command.append(f"--rc={rc}")
    return [
        h239.parse_model(line, True)
        for line in subprocess.run(
            command,
            input=input_text,
            text=True,
            stdout=subprocess.PIPE,
            check=True,
        ).stdout.splitlines()
    ]


def sine_expected(se: int, sig: int, rc: str) -> h239.Value:
    exponent = (se & 0x7FFF) - 16383
    sign = se >> 15
    if exponent < -68:
        return "OK", f"{se:04x}", f"{sig:016x}"
    decrement = rc == "rz" or (rc == "rd" and not sign) or (
        rc == "ru" and sign
    )
    if decrement:
        if sig > 0x8000000000000000:
            sig -= 1
        else:
            se = (se & 0x8000) | ((se & 0x7FFF) - 1)
            sig = 0xFFFFFFFFFFFFFFFF
    return "OK", f"{se:04x}", f"{sig:016x}"


def cosine_expected(exponent: int, rc: str) -> h239.Value:
    if exponent >= -68 and rc in ("rd", "rz"):
        return PREDECESSOR
    return ONE


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=pathlib.Path)
    parser.add_argument("--round40-replay-dir", type=pathlib.Path)
    args = parser.parse_args()

    input_text = INPUTS.read_text()
    inputs = [
        tuple(int(field, 16) for field in line.split())
        for line in input_text.splitlines()
    ]
    totals = collections.Counter()
    affected = {"old": set(), "new": set()}
    tiny_checks = 0
    residual_paths = collections.Counter()
    for rc in h58.RCS:
        old = run_model(args.model, input_text, rc, False)
        new = run_model(
            args.model,
            input_text,
            rc,
            True,
            args.round40_replay_dir,
        )
        hardware = [
            tuple(value for value, _ in h239.parse_hardware(line, True))
            for line in (
                CAPTURE / f"sweep_fsincos_{rc}_status.txt"
            ).read_text().splitlines()
        ]
        rc_old = 0
        rc_new = 0
        for index, ((se, sig), old_pair, new_pair, expected_pair) in enumerate(
            zip(inputs, old, new, hardware)
        ):
            exponent = (se & 0x7FFF) - 16383
            for lane_index, lane in enumerate(("sin", "cos")):
                path = h239.classify(se, sig, lane)
                if path[0] == "direct" and path[1] == "tiny":
                    predicted = (
                        sine_expected(se, sig, rc)
                        if lane == "sin"
                        else cosine_expected(exponent, rc)
                    )
                    if expected_pair[lane_index] != predicted:
                        raise SystemExit(
                            f"tiny rule differs at {lane} input {index} rc={rc}"
                        )
                    tiny_checks += 1
                old_miss = old_pair[lane_index] != expected_pair[lane_index]
                new_miss = new_pair[lane_index] != expected_pair[lane_index]
                rc_old += old_miss
                rc_new += new_miss
                if old_miss:
                    affected["old"].add(index)
                if new_miss:
                    affected["new"].add(index)
                    residual_paths[(lane, *path)] += 1
                totals["fixed"] += old_miss and not new_miss
                totals["regressed"] += new_miss and not old_miss
        totals["old"] += rc_old
        totals["new"] += rc_new
        print(f"{rc}: {rc_old} -> {rc_new} lane/mode misses")

    print(f"validated tiny capture checks: {tiny_checks}")
    print(
        f"combined: {totals['old']} -> {totals['new']} lane/mode misses; "
        f"{len(affected['old'])} -> {len(affected['new'])} affected inputs; "
        f"fixed={totals['fixed']} regressed={totals['regressed']}"
    )
    print("Round-40 residual paths:")
    for path, count in sorted(residual_paths.items()):
        lane, source, family, producer, cell = path
        cell_text = "-" if cell is None else str(cell)
        print(
            f"  {lane:3s} {source:7s} {family:12s} {producer:9s} "
            f"cell={cell_text}: {count}"
        )


if __name__ == "__main__":
    main()
