#!/usr/bin/env python3
"""Prove C/Python parity for h142's path-specific P5 FMUL route.

Round 29 replaces only Round 28's narrow-table Cj*p materialization.  This
script proves exact parity on every narrow result in the complete dense and
structured datasets, proves all other results unchanged, and separately
reports the old/new score on the independent h140 hardware capture.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import h58_constraint_search as h58
import h131_fsin_table_c1_search as h131
import h135_fsin_table_terminal_discriminator as h135
import h139_p5_fmul_route_search as h139
import h140_p5_fmul_discriminator as h140
import h142_p5_fmul_path_route as h142


DIRECT = h139.Route("y", "rn", "rn", "ru")
REDUCED = h139.Route("x", "rn", "rn", "rd")
SCHEDULE = h142.Schedule(DIRECT, REDUCED)


def run_model(
    model: pathlib.Path,
    lines: list[str],
    rc: str,
    candidate: bool,
) -> list[tuple[int, int] | str]:
    command = [str(model), "--batch", *h135.BASE_FLAGS]
    command.append(
        "--round29-p5-fmul-route"
        if candidate
        else "--round28-tang-narrow"
    )
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


def parity_points(
    model: pathlib.Path,
    name: str,
    lines: list[str],
    observed: list[h131.Observed],
) -> tuple[int, int, int, int, int]:
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
    old_hardware_misses = 0
    new_hardware_misses = 0
    for index in range(len(lines)):
        point = by_index.get(index)
        if point is None or point.family == "wide":
            for rc in h58.RCS:
                if candidate[rc][index] != baseline[rc][index]:
                    raise SystemExit(
                        f"h143 changed non-narrow input: {name} "
                        f"line {index + 1} {rc}"
                    )
                inactive += 1
            continue
        route = SCHEDULE.route(point.source == "reduced")
        hidden = h139.hidden_value(point, route)
        for rc_index, rc in enumerate(h58.RCS):
            expected = h58.x87_round(hidden, rc)
            actual = candidate[rc][index]
            if actual != expected:
                raise SystemExit(
                    f"h143 C/Python mismatch: {name} line {index + 1} "
                    f"{rc}: C={actual} Python={expected}"
                )
            changed += actual != baseline[rc][index]
            old_hardware_misses += (
                baseline[rc][index] != point.outputs[rc_index]
            )
            new_hardware_misses += (
                actual != point.outputs[rc_index]
            )
            checked += 1
    return (
        checked,
        changed,
        inactive,
        old_hardware_misses,
        new_hardware_misses,
    )


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} MODEL")
    model = pathlib.Path(sys.argv[1]).resolve()
    total = [0, 0, 0, 0, 0]
    for name, input_path in (
        ("dense", h131.INPUTS / "dense_qn.txt"),
        ("sweep", h131.INPUTS / "sweep_inputs.txt"),
    ):
        lines = input_path.read_text().splitlines()
        result = parity_points(
            model, name, lines, h131.load_dataset(name, input_path)
        )
        print(
            f"{name}: checked={result[0]} changed={result[1]} "
            f"unchanged-other={result[2]} "
            f"hardware={result[3]}->{result[4]}"
        )
        total = [a + b for a, b in zip(total, result)]

    h140_lines = h140.DEFAULT_OUTPUT.read_text().splitlines()
    captured = h140.load_capture(
        h140.DEFAULT_OUTPUT,
        h140.ROOT
        / "capture-kit-captures"
        / "skylake-fsin-h140",
    )
    focused = parity_points(
        model, "h140", h140_lines, captured
    )
    print(
        f"h140: checked={focused[0]} changed={focused[1]} "
        f"hardware={focused[3]}->{focused[4]}"
    )
    print(
        f"PASS: {total[0]} complete narrow results match Python; "
        f"{total[1]} results differ from Round 28; "
        f"{total[2]} other results remain unchanged; "
        f"complete hardware misses {total[3]}->{total[4]}"
    )


if __name__ == "__main__":
    main()
