#!/usr/bin/env python3
"""Prove C/Python parity for h137's narrow Tang reconstruction.

The promoted rule changes only narrow table inputs.  This script compares
the C model with and without ``--round28-tang-narrow`` on the complete dense
and structured standalone-FSIN datasets, proves all inactive/wide results
are unchanged, and checks every narrow RN/RD/RU result against h137.
"""

from __future__ import annotations

import dataclasses
import pathlib
import subprocess
import sys

import h58_constraint_search as h58
import h131_fsin_table_c1_search as h131
import h135_fsin_table_terminal_discriminator as h135
import h137_tang_edge_schedule_search as h137


NARROW = dataclasses.replace(
    h137.CURRENT, p_product=h137.Quant(64, "away")
)


def run_model(
    model: pathlib.Path,
    lines: list[str],
    rc: str,
    tang: bool,
) -> list[tuple[int, int] | str]:
    command = [str(model), "--batch", *h135.BASE_FLAGS]
    if tang:
        command.append("--round28-tang-narrow")
    if rc != "rn":
        command.append(f"--rc={rc}")
    completed = subprocess.run(
        command,
        input="\n".join(lines) + "\n",
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    )
    return [
        h135.parse_single(line)
        for line in completed.stdout.splitlines()
    ]


def parity_dataset(
    model: pathlib.Path, name: str, input_path: pathlib.Path
) -> tuple[int, int, int]:
    lines = input_path.read_text().splitlines()
    observed = h131.load_dataset(name, input_path)
    by_index = {point.index: point for point in observed}
    baseline = {
        rc: run_model(model, lines, rc, False) for rc in h58.RCS
    }
    candidate = {
        rc: run_model(model, lines, rc, True) for rc in h58.RCS
    }
    checked = 0
    changed = 0
    inactive = 0
    for index in range(len(lines)):
        point = by_index.get(index)
        if point is None or point.family == "wide":
            for rc in h58.RCS:
                if candidate[rc][index] != baseline[rc][index]:
                    raise SystemExit(
                        f"h138 changed non-narrow input: {name} "
                        f"line {index + 1} {rc}"
                    )
                inactive += 1
            continue
        for rc in h58.RCS:
            expected = h58.x87_round(
                h137.hidden_value(point, NARROW), rc
            )
            actual = candidate[rc][index]
            if actual != expected:
                raise SystemExit(
                    f"h138 C/Python mismatch: {name} line {index + 1} "
                    f"{rc}: C={actual} Python={expected}"
                )
            changed += actual != baseline[rc][index]
            checked += 1
    return checked, changed, inactive


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} MODEL")
    model = pathlib.Path(sys.argv[1]).resolve()
    total = [0, 0, 0]
    for name, input_path in (
        ("dense", h131.INPUTS / "dense_qn.txt"),
        ("sweep", h131.INPUTS / "sweep_inputs.txt"),
    ):
        result = parity_dataset(model, name, input_path)
        print(
            f"{name}: checked={result[0]} changed={result[1]} "
            f"unchanged-other={result[2]}"
        )
        total = [a + b for a, b in zip(total, result)]
    print(
        f"PASS: {total[0]} narrow table results match Python; "
        f"{total[1]} candidate results differ; "
        f"{total[2]} other results remain unchanged"
    )


if __name__ == "__main__":
    main()
