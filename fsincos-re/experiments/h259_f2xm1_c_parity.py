#!/usr/bin/env python3
"""Verify the C F2XM1 port against all existing and fresh captures."""

from __future__ import annotations

import argparse
import pathlib
import subprocess


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_MODEL = ROOT / "src" / "fsincos_skylake"
SETS = (
    (
        "dense",
        ROOT / "capture-kit" / "inputs" / "dense_qn.txt",
        ROOT / "capture-kit-captures" / "skylake-sibling-h245",
        "dense_f2xm1_{}_status.txt",
    ),
    (
        "sweep",
        ROOT / "capture-kit" / "inputs" / "sweep_inputs.txt",
        ROOT / "capture-kit-captures" / "skylake-sibling-h245",
        "sweep_f2xm1_{}_status.txt",
    ),
    (
        "target",
        ROOT / "capture-kit" / "inputs" / "sibling_fptan_f2xm1_h245.txt",
        ROOT / "capture-kit-captures" / "skylake-sibling-h245",
        "target_f2xm1_{}_status.txt",
    ),
    (
        "h257",
        ROOT / "capture-kit" / "inputs" / "f2xm1_validation_h257.txt",
        ROOT / "capture-kit-captures" / "skylake-f2xm1-h257",
        "f2xm1_validation_h257_{}_status.txt",
    ),
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", nargs="?", type=pathlib.Path, default=DEFAULT_MODEL)
    args = parser.parse_args()
    model = args.model.resolve()
    total = 0
    misses = 0
    for name, inputs, capture, pattern in SETS:
        for rc in ("rn", "rd", "ru"):
            result = subprocess.run(
                [str(model), "--batch", "--f2xm1", f"--rc={rc}"],
                input=inputs.read_bytes(),
                stdout=subprocess.PIPE,
                check=True,
            ).stdout.decode().splitlines()
            hardware = capture.joinpath(pattern.format(rc)).read_text().splitlines()
            if len(result) != len(hardware):
                raise SystemExit(f"{name}/{rc}: row-count mismatch")
            row_misses = sum(
                predicted.split()[:3] != observed.split()[:3]
                for predicted, observed in zip(result, hardware)
            )
            total += len(result)
            misses += row_misses
            print(f"{name}/{rc}: {row_misses}/{len(result)} misses")
    print(f"complete C parity: {misses}/{total} misses")


if __name__ == "__main__":
    main()
