#!/usr/bin/env python3
"""Freeze the post-Round-39 FSIN/FCOS/FSINCOS residual census."""

from __future__ import annotations

import argparse
import collections
import dataclasses
import pathlib
import subprocess

import h58_constraint_search as h58
import h60_round16_parity as h60


ROOT = pathlib.Path(__file__).resolve().parents[1]
INPUTS = ROOT / "capture-kit" / "inputs" / "sweep_inputs.txt"
SINGLE_CAPTURE = ROOT / "capture-kit-captures" / "skylake-fsin-h110"
PAIRED_CAPTURE = ROOT / "capture-kit-captures" / "skylake-fsin-h177"
BASE_FLAGS = (
    "--batch",
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
    "--round38-p6-cosine-split",
    "--round39-fcos-tiny",
)
RC_INDEX = {rc: index for index, rc in enumerate(h58.RCS)}


Value = tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class Residual:
    instruction: str
    lane: str
    index: int
    rc: str
    source: str
    family: str
    producer: str
    cell: int | None
    direction: str
    c1: bool | None

    def path(self) -> tuple[str, str, str, str, str, int | None]:
        return (
            self.instruction,
            self.lane,
            self.source,
            self.family,
            self.producer,
            self.cell,
        )


def parse_model(line: str, paired: bool) -> tuple[Value, ...]:
    fields = line.split()
    if fields[0] == "C2":
        return (("C2",), ("C2",)) if paired else (("C2",),)
    if fields[0] != "OK":
        raise ValueError(line)
    if paired:
        return (
            ("OK", fields[1], fields[2]),
            ("OK", fields[3], fields[4]),
        )
    return (("OK", fields[1], fields[2]),)


def parse_hardware(
    line: str, paired: bool
) -> tuple[tuple[Value, bool | None], ...]:
    fields = line.split()
    if fields[0] == "C2":
        values = (("C2",), ("C2",)) if paired else (("C2",),)
        return tuple((value, None) for value in values)
    if fields[0] != "OK":
        raise ValueError(line)
    if paired:
        status = int(fields[6], 16)
        return (
            (("OK", fields[1], fields[2]), None),
            (("OK", fields[3], fields[4]), bool(status & 0x0200)),
        )
    status = int(fields[4], 16)
    return ((("OK", fields[1], fields[2]), bool(status & 0x0200)),)


def magnitude_rank(value: Value) -> tuple[int, int] | None:
    if value[0] != "OK":
        return None
    se, sig = int(value[1], 16), int(value[2], 16)
    return se >> 15, ((se & 0x7FFF) << 64) + sig


def direction(model: Value, hardware: Value) -> str:
    left = magnitude_rank(model)
    right = magnitude_rank(hardware)
    if left is None or right is None:
        return "class"
    if left[0] != right[0]:
        return "sign"
    delta = left[1] - right[1]
    if delta == 0:
        return "encoding"
    return "magnitude-high" if delta > 0 else "magnitude-low"


def classify(
    se: int, sig: int, lane: str
) -> tuple[str, str, str, int | None]:
    reduced = h60.reduced_kernel_input(se, sig)
    if reduced is None:
        source = "direct"
        signed_n = 0
        r_se, r_sig = se, sig
    else:
        source = "reduced"
        signed_n, r_se, r_sig, _ = reduced
    exponent = (r_se & 0x7FFF) - 16383
    if r_sig == 0 or exponent < -32:
        family = "tiny"
    elif exponent < -2:
        family = "polynomial"
    elif exponent == -2:
        family = "narrow-table"
    else:
        family = "wide-table"
    if lane == "sin":
        producer = "cos-state" if signed_n & 1 else "sin-state"
    else:
        producer = "sin-state" if signed_n & 1 else "cos-state"
    cell = (
        h58.cell_for(r_sig, exponent)
        if family.endswith("table")
        else None
    )
    return source, family, producer, cell


def run_model(
    model: pathlib.Path,
    input_text: str,
    instruction: str,
    rc: str,
) -> list[tuple[Value, ...]]:
    command = [str(model.resolve()), *BASE_FLAGS]
    if instruction == "fsin":
        command.append("--fsin-standalone")
    elif instruction == "fcos":
        command.append("--fcos-standalone")
    elif instruction != "fsincos":
        raise ValueError(instruction)
    if rc != "rn":
        command.append(f"--rc={rc}")
    paired = instruction == "fsincos"
    return [
        parse_model(line, paired)
        for line in subprocess.run(
            command,
            input=input_text,
            text=True,
            stdout=subprocess.PIPE,
            check=True,
        ).stdout.splitlines()
    ]


def hardware_path(instruction: str, rc: str) -> pathlib.Path:
    if instruction == "fsincos":
        return PAIRED_CAPTURE / f"sweep_fsincos_{rc}_status.txt"
    return SINGLE_CAPTURE / f"sweep_{instruction}_{rc}_status.txt"


def collect(model: pathlib.Path) -> list[Residual]:
    input_text = INPUTS.read_text()
    inputs = [
        tuple(int(field, 16) for field in line.split())
        for line in input_text.splitlines()
    ]
    residuals = []
    for instruction in ("fsin", "fcos", "fsincos"):
        paired = instruction == "fsincos"
        lanes = ("sin", "cos") if paired else (instruction[1:],)
        for rc in h58.RCS:
            model_values = run_model(model, input_text, instruction, rc)
            hardware_values = [
                parse_hardware(line, paired)
                for line in hardware_path(instruction, rc).read_text().splitlines()
            ]
            if len(model_values) != len(inputs) or len(hardware_values) != len(inputs):
                raise SystemExit(f"length mismatch for {instruction}/{rc}")
            for index, (actual, expected) in enumerate(
                zip(model_values, hardware_values)
            ):
                path = None
                for lane, model_value, (hardware_value, c1) in zip(
                    lanes, actual, expected
                ):
                    if model_value == hardware_value:
                        continue
                    if path is None:
                        path = {
                            name: classify(*inputs[index], name)
                            for name in lanes
                        }
                    source, family, producer, cell = path[lane]
                    residuals.append(Residual(
                        instruction,
                        lane,
                        index,
                        rc,
                        source,
                        family,
                        producer,
                        cell,
                        direction(model_value, hardware_value),
                        c1,
                    ))
    return residuals


def partition(records: list[Residual]) -> dict[tuple, str]:
    """Assign all modes of one input/path to a balanced stable half."""
    by_path: dict[tuple, set[int]] = collections.defaultdict(set)
    for record in records:
        by_path[record.path()].add(record.index)
    result = {}
    for path, indices in by_path.items():
        for position, index in enumerate(sorted(indices)):
            result[path, index] = "train" if position % 2 == 0 else "held"
    return result


def report(records: list[Residual]) -> None:
    halves = partition(records)
    by_path: dict[tuple, list[Residual]] = collections.defaultdict(list)
    for record in records:
        by_path[record.path()].append(record)

    print(
        "instruction lane source family producer cell: "
        "modes inputs train/held [details]"
    )
    for path in sorted(
        by_path,
        key=lambda item: (*item[:5], -1 if item[5] is None else item[5]),
    ):
        group = by_path[path]
        indices = {record.index for record in group}
        half_counts = collections.Counter(
            halves[path, index] for index in indices
        )
        details = collections.Counter(
            (record.rc, record.direction, record.c1) for record in group
        )
        detail_text = " ".join(
            f"{rc}/{direction}"
            + ("" if c1 is None else f"/C1={int(c1)}")
            + f"={count}"
            for (rc, direction, c1), count in sorted(
                details.items(),
                key=lambda item: (
                    RC_INDEX[item[0][0]], item[0][1], str(item[0][2])
                ),
            )
        )
        cell = "-" if path[5] is None else str(path[5])
        print(
            f"{path[0]:8s} {path[1]:3s} {path[2]:7s} "
            f"{path[3]:12s} {path[4]:9s} {cell:>2s}: "
            f"{len(group):4d} {len(indices):4d} "
            f"{half_counts['train']:3d}/{half_counts['held']:3d} "
            f"{detail_text}"
        )

    print("summary:")
    for instruction in ("fsin", "fcos", "fsincos"):
        group = [
            record for record in records
            if record.instruction == instruction
        ]
        print(
            f"  {instruction:8s}: {len(group):4d} lane/mode misses; "
            f"{len({record.index for record in group}):4d} affected inputs"
        )
        if instruction == "fsincos":
            for lane in ("sin", "cos"):
                lane_group = [
                    record for record in group if record.lane == lane
                ]
                print(
                    f"    {lane}: {len(lane_group):4d} mode misses; "
                    f"{len({record.index for record in lane_group}):4d} inputs"
                )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=pathlib.Path)
    args = parser.parse_args()
    report(collect(args.model))


if __name__ == "__main__":
    main()
