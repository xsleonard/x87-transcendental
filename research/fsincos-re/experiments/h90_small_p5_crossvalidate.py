#!/usr/bin/env python3
"""Cross-validate the Pentium six-term path over all small discriminators.

h83 is the original master residue.  h85 and h87 were generated to separate
incorrect internal-width hypotheses.  h89 was independently generated from
P5-versus-Itanium disagreements at exponents -7 through -32.  The Round-18
P5 schedule must match every RN/RD/RU output in all four sets.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess

import h58_constraint_search as h58
import h60_round16_parity as h60
import h84_small_operation_search as h84
import h89_small_deep_discriminator as h89


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODEL = ROOT / "src" / "fsincos_skylake"
DATASETS = (
    (
        "h83",
        "constraint_small_h83.txt",
        "skylake-h83-small-boundary",
        "constraint_small",
    ),
    (
        "h85",
        "constraint_small_width_h85.txt",
        "skylake-h85-small-width",
        "constraint_small_width",
    ),
    (
        "h87",
        "constraint_small_chop_h87.txt",
        "skylake-h87-small-chop",
        "constraint_small_chop",
    ),
    (
        "h89",
        "constraint_small_deep_h89.txt",
        "skylake-h89-small-deep",
        "constraint_small_deep",
    ),
)


def parse_capture(path: pathlib.Path) -> list[
    tuple[tuple[int, int], tuple[int, int]]
]:
    outputs = []
    for line in path.read_text().splitlines():
        parsed = h60.parse_output(line)
        if parsed == "C2":
            raise AssertionError("small input returned C2")
        assert not isinstance(parsed, str)
        outputs.append(parsed)
    return outputs


def run_c(
    binary: pathlib.Path,
    input_text: str,
    rc: str,
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    completed = subprocess.run(
        [
            str(binary),
            "--batch",
            "--round18-poly",
            f"--rc={rc}",
        ],
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    )
    outputs = []
    for line in completed.stdout.splitlines():
        parsed = h60.parse_output(line)
        if parsed == "C2":
            raise AssertionError("C model returned C2")
        assert not isinstance(parsed, str)
        outputs.append(parsed)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", nargs="?", type=pathlib.Path, default=MODEL)
    args = parser.parse_args()
    binary = args.binary.resolve()

    all_itanium = [0, 0, 0]
    all_p5 = [0, 0, 0]
    all_c = [0, 0, 0]
    total_inputs = 0
    for name, input_name, capture_dir, prefix in DATASETS:
        input_path = ROOT / "capture-kit" / "inputs" / input_name
        input_text = input_path.read_text()
        inputs = [
            tuple(int(field, 16) for field in line.split())
            for line in input_text.splitlines()
        ]
        hardware = [
            parse_capture(
                ROOT
                / "capture-kit-captures"
                / capture_dir
                / f"{prefix}_{rc}.txt"
            )
            for rc in h58.RCS
        ]
        c_outputs = [
            run_c(binary, input_text, rc) for rc in h58.RCS
        ]
        misses = {
            "itanium": [0, 0, 0],
            "p5": [0, 0, 0],
            "c": [0, 0, 0],
        }
        for index, (se, sig) in enumerate(inputs):
            itanium = tuple(
                h84.outputs(se, sig, rc, h84.Variant())
                for rc in h58.RCS
            )
            pentium = h89.p5_predictions(se, sig)
            for rc_index in range(3):
                for lane in (0, 1):
                    wanted = hardware[rc_index][index][lane]
                    misses["itanium"][rc_index] += (
                        itanium[rc_index][lane] != wanted
                    )
                    misses["p5"][rc_index] += (
                        pentium[rc_index][lane] != wanted
                    )
                    misses["c"][rc_index] += (
                        c_outputs[rc_index][index][lane] != wanted
                    )
        total_inputs += len(inputs)
        for index in range(3):
            all_itanium[index] += misses["itanium"][index]
            all_p5[index] += misses["p5"][index]
            all_c[index] += misses["c"][index]
        print(
            f"{name}: inputs={len(inputs)} "
            f"Itanium-misses={misses['itanium']} "
            f"P5-misses={misses['p5']} C-misses={misses['c']}"
        )

    checks = total_inputs * 2 * 3
    print(
        f"total: {total_inputs} inputs, {checks} output-mode checks; "
        f"Itanium-misses={all_itanium} "
        f"P5-misses={all_p5} C-misses={all_c}"
    )
    if any(all_p5) or any(all_c):
        raise SystemExit("P5 small-path cross-validation failed")
    print(f"PASS: Python and C Round-18 P5 paths match {checks}/{checks}")


if __name__ == "__main__":
    main()
