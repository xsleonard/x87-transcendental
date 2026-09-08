#!/usr/bin/env python3
"""Emit the six-input RN/RD/RU/RZ P6 reference matrix as TSV.

RN/RD/RU are copied from the checked-in Skylake h384 captures.  RZ is
computed by the explicitly supplied fsincos_skylake model binary because the
public h384 capture predates the project's RZ campaign.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Dict, List


MODEL_SOURCE_SHA256 = "a844951c2c5193142e5520d709c3dc6b2f8d947c1cd266a7288c3ec3614058d2"
SOURCE_FIRST_ROW = 14
SOURCE_ROW_COUNT = 6
INSTRUCTION_OPTIONS: Dict[str, List[str]] = {
    "fsincos": [],
    "fsin": ["--fsin-standalone"],
    "fcos": ["--fcos-standalone"],
    "fptan": ["--fptan"],
}


def parse_args() -> argparse.Namespace:
    here = Path(__file__).resolve().parent
    fsincos_root = here.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument(
        "--inputs", type=Path, default=here / "validation-inputs.txt"
    )
    parser.add_argument(
        "--h384-captures",
        type=Path,
        default=fsincos_root / "capture-kit-captures" / "skylake-fcos-h384",
    )
    return parser.parse_args()


def rz_lines(model: Path, inputs: List[str], instruction: str) -> List[str]:
    command = [str(model), "--batch"]
    command.extend(INSTRUCTION_OPTIONS[instruction])
    command.append("--rc=rz")
    result = subprocess.run(
        command,
        input=("\n".join(inputs) + "\n").encode("ascii"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            f"model exited {result.returncode}: "
            f"{result.stderr.decode('utf-8', errors='replace')}"
        )
    return result.stdout.decode("ascii").splitlines()


def main() -> int:
    args = parse_args()
    inputs = args.inputs.read_text().splitlines()
    if len(inputs) != SOURCE_ROW_COUNT:
        raise ValueError(
            f"expected {SOURCE_ROW_COUNT} validation inputs, found {len(inputs)}"
        )

    print(
        "case_id\tinstruction\tmode\tinput_se\tinput_sig\t"
        "result0_se\tresult0_sig\tresult1_se\tresult1_sig\t"
        "skylake_sw\tprovenance"
    )
    for mode in ("rn", "rd", "ru", "rz"):
        for instruction in INSTRUCTION_OPTIONS:
            if mode == "rz":
                lines = rz_lines(args.model, inputs, instruction)
                provenance = f"model_{MODEL_SOURCE_SHA256[:8]}"
            else:
                capture = args.h384_captures / f"{instruction}_{mode}_status.txt"
                all_lines = capture.read_text().splitlines()
                lines = all_lines[
                    SOURCE_FIRST_ROW:SOURCE_FIRST_ROW + SOURCE_ROW_COUNT
                ]
                provenance = "skylake_h384"
            if len(lines) != len(inputs):
                raise ValueError(
                    f"{instruction}/{mode}: expected {len(inputs)} rows, "
                    f"found {len(lines)}"
                )

            for number, (input_line, output_line) in enumerate(zip(inputs, lines)):
                input_se, input_sig = input_line.split()
                fields = output_line.split()
                if not fields or fields[0] != "OK":
                    raise ValueError(
                        f"{instruction}/{mode}/GM{number:02d}: {output_line}"
                    )
                if mode == "rz":
                    status = "-"
                    values = fields[1:]
                else:
                    if len(fields) < 5 or fields[-2] != "SW":
                        raise ValueError(
                            f"missing status in {instruction}/{mode}: {output_line}"
                        )
                    status = fields[-1]
                    values = fields[1:-2]
                if len(values) == 2:
                    values.extend(["-", "-"])
                if len(values) != 4:
                    raise ValueError(
                        f"unexpected result arity in {instruction}/{mode}: {output_line}"
                    )
                print(
                    f"GM{number:02d}\t{instruction}\t{mode}\t"
                    f"{input_se}\t{input_sig}\t"
                    + "\t".join(values)
                    + f"\t{status}\t{provenance}"
                )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
