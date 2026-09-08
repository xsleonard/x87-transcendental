#!/usr/bin/env python3
"""Prove the Round-34 C port matches h184's selected FIRC route.

The candidate is scoped to the wide table family in C because that is the
only family where the complete h184 corpus observes an architectural change.
This pass checks every RN/RD/RU result in the dense and sweep inputs, proves
non-table/non-wide outputs unchanged, and replays the fresh h185 inputs.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import h58_constraint_search as h58
import h131_fsin_table_c1_search as h131
import h135_fsin_table_terminal_discriminator as h135
import h184_table_lookup_firc_routes as h184
import h185_table_lookup_firc_discriminator as h185


BASE_FLAGS = (
    *h135.BASE_FLAGS,
    "--round29-p5-fmul-route",
    "--round30-fsin-cosine-square",
    "--round31-fsin-cosine-tail",
    "--round32-fsin-cosine-horner",
    "--round33-fsin-cosine-product",
)
CANDIDATE = h184.Candidate(p_product="rn64")


def run_model(
    model: pathlib.Path,
    lines: list[str],
    rc: str,
    candidate: bool,
) -> list[tuple[int, int] | str]:
    command = [
        str(model),
        "--batch",
        *BASE_FLAGS,
    ]
    if candidate:
        command.append("--round34-table-lookup-firc")
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
    model: pathlib.Path, name: str
) -> tuple[int, int, int, int, int]:
    input_path = h131.INPUTS / (
        "dense_qn.txt" if name == "dense" else "sweep_inputs.txt"
    )
    lines = input_path.read_text().splitlines()
    prepared = [
        h184.prepare(point) for point in h184.dataset(name)
    ]
    by_index = {
        point.joint.observed.index: point for point in prepared
    }
    baseline = {
        rc: run_model(model, lines, rc, False) for rc in h58.RCS
    }
    candidate = {
        rc: run_model(model, lines, rc, True) for rc in h58.RCS
    }
    checked = 0
    changed = 0
    unchanged_other = 0
    old_hardware_misses = 0
    new_hardware_misses = 0
    for index in range(len(lines)):
        point = by_index.get(index)
        if point is None or point.joint.observed.family != "wide":
            for rc in h58.RCS:
                if candidate[rc][index] != baseline[rc][index]:
                    raise SystemExit(
                        f"h186 changed non-wide input: {name} "
                        f"line {index + 1} {rc}"
                    )
                unchanged_other += 1
            continue
        hidden = h184.values(point, CANDIDATE)[0]
        for rc_index, rc in enumerate(h58.RCS):
            expected = h58.x87_round(hidden, rc)
            actual = candidate[rc][index]
            if actual != expected:
                raise SystemExit(
                    f"h186 C/Python mismatch: {name} line {index + 1} "
                    f"{rc}: C={actual} Python={expected}"
                )
            observed = point.joint.observed.outputs[rc_index]
            changed += actual != baseline[rc][index]
            old_hardware_misses += baseline[rc][index] != observed
            new_hardware_misses += actual != observed
            checked += 1
    return (
        checked,
        changed,
        unchanged_other,
        old_hardware_misses,
        new_hardware_misses,
    )


def parity_h185(model: pathlib.Path) -> tuple[int, int]:
    lines = h185.DEFAULT_OUTPUT.read_text().splitlines()
    points = h185.load_capture(
        h185.DEFAULT_OUTPUT,
        h185.ROOT / "capture-kit-captures" / "skylake-fsin-h185",
    )
    outputs = {
        rc: run_model(model, lines, rc, True) for rc in h58.RCS
    }
    checked = 0
    hardware_misses = 0
    for index, point in enumerate(points):
        hidden = h184.values(point, CANDIDATE)[0]
        for rc_index, rc in enumerate(h58.RCS):
            expected = h58.x87_round(hidden, rc)
            actual = outputs[rc][index]
            if actual != expected:
                raise SystemExit(
                    f"h186 h185 C/Python mismatch: line {index + 1} "
                    f"{rc}: C={actual} Python={expected}"
                )
            hardware_misses += (
                actual != point.joint.observed.outputs[rc_index]
            )
            checked += 1
    return checked, hardware_misses


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} MODEL")
    model = pathlib.Path(sys.argv[1]).resolve()
    total = [0, 0, 0, 0, 0]
    for name in ("dense", "sweep"):
        result = parity_dataset(model, name)
        total = [old + new for old, new in zip(total, result)]
        print(
            f"{name}: checked={result[0]} changed={result[1]} "
            f"unchanged-other={result[2]} "
            f"hardware={result[3]}->{result[4]}"
        )
    fresh = parity_h185(model)
    print(
        f"h185: checked={fresh[0]} sine-mode-misses={fresh[1]}"
    )
    print(
        f"PASS: {total[0]} complete wide-table results match Python; "
        f"{total[1]} outputs change; {total[2]} other results remain "
        f"unchanged; complete hardware misses "
        f"{total[3]}->{total[4]}"
    )


if __name__ == "__main__":
    main()
