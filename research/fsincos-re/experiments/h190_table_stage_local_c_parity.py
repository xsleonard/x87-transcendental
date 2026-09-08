#!/usr/bin/env python3
"""Prove the Round-35 C port matches h188's h189-selected schedule.

Round 35 changes only the terminal wide-table P producer: materialize the
last coefficient away64, retain the final sum as chop65, and consume that
65-bit value in the following RN64 product.  The path-aware terminal Q rule
remains the h135 away64/RN64 schedule.  This pass checks standalone-FSIN and
paired-FSINCOS cosine outputs over every dense/sweep wide-table observation,
proves all other inputs unchanged, and replays the fresh h189 capture.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import h58_constraint_search as h58
import h79_table_state_bias as h79
import h131_fsin_table_c1_search as h131
import h134_fsin_table_per_edge_search as h134
import h135_fsin_table_terminal_discriminator as h135
import h136_tang_reconstruction_search as h136
import h170_fsin_table_correction_search as h170
import h182_table_joint_terminal_edges as h182
import h184_table_lookup_firc_routes as h184
import h186_table_lookup_firc_c_parity as h186
import h188_table_stage_local_pairs as h188
import h189_table_stage_local_discriminator as h189


BASE_FLAGS = (
    *(flag for flag in h186.BASE_FLAGS if flag != "--fsin-standalone"),
    "--round34-table-lookup-firc",
)
CANDIDATE = h189.CANDIDATES[1]
CAPTURE = h189.ROOT / "capture-kit-captures" / "skylake-fsin-h189"


def hidden_values(
    point: h188.Point, candidate: bool
) -> tuple[h58.FP, h58.FP]:
    """Return the exact C standalone-sine and paired-cosine carriers.

    Standalone FSIN already uses h135's path-aware terminal Q schedule.
    Paired FSINCOS retains the shared RN67/RN64 Q schedule; Round 35 changes
    only P.  Keeping those instruction paths separate avoids attributing an
    older Q hypothesis to the fresh P discriminator.
    """
    override = CANDIDATE if candidate else h188.CURRENT_P
    sine = h188.values(point, override)[0]
    schedule = h134.CURRENT
    p = (
        h188.producer(point, CANDIDATE)
        if candidate
        else h134.horner(
            h58.S6,
            point.square,
            schedule.p_coefficients,
            schedule.p_products,
            schedule.p_sums,
        )
    )
    q = h134.horner(
        h58.C6,
        point.square,
        schedule.q_coefficients,
        schedule.q_products,
        schedule.q_sums,
    )
    observed = point.joint.observed
    m = h58.fmul(p, point.square, 64, "rn")
    correction = h58.fmul(m, observed.point.a, 64, "rn")
    sine_a = h58.fadd(observed.point.a, correction, 64, "rn")
    sine_a = h79.bias_toward_zero(sine_a, 5)
    state = h136.State(
        observed.point.a,
        h58.add_exact(sine_a, h58.neg(observed.point.a)),
        h58.fmul(q, point.square, 64, "rn"),
    )
    cosine = h184.values(
        h184.Point(point.joint, state, None), h188.ROUND34
    )[1]
    return sine, cosine


def metric(
    point: h188.Point, candidate: bool
) -> tuple[h188.Metric, h188.Metric]:
    sine, cosine = hidden_values(point, candidate)
    return (
        h170.point_metric(point.joint.observed, sine),
        h182.point_metric(
            point.joint.cosine_outputs,
            point.joint.cosine_c1,
            cosine,
        ),
    )


def add_metric(left, right):
    return tuple(
        h170.add(old, new) for old, new in zip(left, right)
    )


def parse_pair(line: str) -> tuple[tuple[int, int], tuple[int, int]] | str:
    fields = line.split()
    if fields[0] == "C2":
        return "C2"
    if len(fields) != 5 or fields[0] != "OK":
        raise ValueError(line)
    return (
        (int(fields[1], 16), int(fields[2], 16)),
        (int(fields[3], 16), int(fields[4], 16)),
    )


def run_model(
    model: pathlib.Path,
    lines: list[str],
    rc: str,
    candidate: bool,
    standalone: bool,
):
    command = [str(model), "--batch", *BASE_FLAGS]
    if candidate:
        command.append("--round35-table-p-terminal")
    if standalone:
        command.append("--fsin-standalone")
    if rc != "rn":
        command.append(f"--rc={rc}")
    completed = subprocess.run(
        command,
        input="\n".join(lines) + "\n",
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    )
    parser = h135.parse_single if standalone else parse_pair
    return [parser(line) for line in completed.stdout.splitlines()]


def parity_dataset(model: pathlib.Path, name: str):
    input_path = h131.INPUTS / (
        "dense_qn.txt" if name == "dense" else "sweep_inputs.txt"
    )
    lines = input_path.read_text().splitlines()
    prepared = [h188.prepare(point) for point in h184.dataset(name)]
    by_index = {
        point.joint.observed.index: point for point in prepared
    }
    runs = {
        (rc, candidate, standalone): run_model(
            model, lines, rc, candidate, standalone
        )
        for rc in h58.RCS
        for candidate in (False, True)
        for standalone in (False, True)
    }
    checked = 0
    changed = [0, 0]
    unchanged_other = 0
    hardware = [[0, 0], [0, 0]]
    metrics = [
        ((0, 0, 0), (0, 0, 0)),
        ((0, 0, 0), (0, 0, 0)),
    ]
    for index in range(len(lines)):
        point = by_index.get(index)
        if point is None or point.joint.observed.family != "wide":
            for rc in h58.RCS:
                for standalone in (False, True):
                    if (
                        runs[rc, False, standalone][index]
                        != runs[rc, True, standalone][index]
                    ):
                        raise SystemExit(
                            f"h190 changed non-wide input: {name} "
                            f"line {index + 1} {rc} standalone={standalone}"
                        )
                    unchanged_other += 1
            continue
        hidden = hidden_values(point, True)
        for candidate in (False, True):
            metrics[candidate] = add_metric(
                metrics[candidate], metric(point, candidate)
            )
        for rc_index, rc in enumerate(h58.RCS):
            expected = tuple(
                h58.x87_round(value, rc) for value in hidden
            )
            actual = (
                runs[rc, True, True][index],
                runs[rc, True, False][index][1],
            )
            if actual != expected:
                raise SystemExit(
                    f"h190 C/Python mismatch: {name} line {index + 1} "
                    f"{rc}: C={actual} Python={expected}"
                )
            baseline = (
                runs[rc, False, True][index],
                runs[rc, False, False][index][1],
            )
            observed = (
                point.joint.observed.outputs[rc_index],
                point.joint.cosine_outputs[rc_index],
            )
            for lane in (0, 1):
                changed[lane] += actual[lane] != baseline[lane]
                hardware[0][lane] += baseline[lane] != observed[lane]
                hardware[1][lane] += actual[lane] != observed[lane]
            checked += 2
    return checked, changed, unchanged_other, hardware, metrics


def parity_h189(model: pathlib.Path):
    lines = h189.DEFAULT_OUTPUT.read_text().splitlines()
    points = h189.load_capture(h189.DEFAULT_OUTPUT, CAPTURE)
    runs = {
        (rc, standalone): run_model(
            model, lines, rc, True, standalone
        )
        for rc in h58.RCS
        for standalone in (False, True)
    }
    checked = 0
    misses = [0, 0]
    metrics = [
        ((0, 0, 0), (0, 0, 0)),
        ((0, 0, 0), (0, 0, 0)),
    ]
    for index, point in enumerate(points):
        for candidate in (False, True):
            metrics[candidate] = add_metric(
                metrics[candidate], metric(point, candidate)
            )
        hidden = hidden_values(point, True)
        for rc_index, rc in enumerate(h58.RCS):
            expected = tuple(
                h58.x87_round(value, rc) for value in hidden
            )
            actual = (
                runs[rc, True][index],
                runs[rc, False][index][1],
            )
            if actual != expected:
                raise SystemExit(
                    f"h190 h189 C/Python mismatch: line {index + 1} "
                    f"{rc}: C={actual} Python={expected}"
                )
            observed = (
                point.joint.observed.outputs[rc_index],
                point.joint.cosine_outputs[rc_index],
            )
            for lane in (0, 1):
                misses[lane] += actual[lane] != observed[lane]
            checked += 2
    return checked, misses, metrics


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} MODEL")
    model = pathlib.Path(sys.argv[1]).resolve()
    totals = [
        0,
        [0, 0],
        0,
        [[0, 0], [0, 0]],
        [
            ((0, 0, 0), (0, 0, 0)),
            ((0, 0, 0), (0, 0, 0)),
        ],
    ]
    for name in ("dense", "sweep"):
        result = parity_dataset(model, name)
        totals[0] += result[0]
        totals[1] = [
            old + new for old, new in zip(totals[1], result[1])
        ]
        totals[2] += result[2]
        totals[3] = [
            [old + new for old, new in zip(old_row, new_row)]
            for old_row, new_row in zip(totals[3], result[3])
        ]
        totals[4] = [
            add_metric(old, new)
            for old, new in zip(totals[4], result[4])
        ]
        print(
            f"{name}: checked={result[0]} changed={result[1]} "
            f"unchanged-other={result[2]} hardware={result[3][0]}"
            f"->{result[3][1]} metrics={result[4][0]}->{result[4][1]}"
        )
    fresh = parity_h189(model)
    print(
        f"h189: checked={fresh[0]} output-misses={fresh[1]} "
        f"metrics={fresh[2][0]}->{fresh[2][1]}"
    )
    print(
        f"PASS: {totals[0]} complete joint-lane results match Python; "
        f"changed={totals[1]}; {totals[2]} other results unchanged; "
        f"complete hardware={totals[3][0]}->{totals[3][1]}; "
        f"metrics={totals[4][0]}->{totals[4][1]}"
    )


if __name__ == "__main__":
    main()
