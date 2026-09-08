#!/usr/bin/env python3
"""Freshly test standalone-FSIN terminal table coefficients.

h134's exhaustive per-edge search leaves three provisional changes:

* narrow P terminal coefficient: chop64;
* wide P terminal coefficient: away64;
* wide Q terminal coefficient: away64.

The C model applies the validated path-aware rule by default and exposes the
old carrier through ``--fsin-table-shared`` for A/B reproduction.  This
script first proves exact C/Python parity, then uses the fast C model—not
hardware—to select fresh direct and M66-reduced operands whose RN/RD/RU
results separate baseline from the candidate.  Returned standalone-FSIN
status captures are scored against baseline, individual wide components,
and the combined rule.
"""

from __future__ import annotations

import argparse
import dataclasses
import pathlib
import random
import subprocess
import sys

import h58_constraint_search as h58
import h80_round21_parity as h80
import h110_fsin_standalone as h110
import h131_fsin_table_c1_search as h131
import h134_fsin_table_per_edge_search as h134


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_fsin_table_terminal_h135.txt"
)
DEFAULT_METADATA = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_fsin_table_terminal_h135.meta.txt"
)
SEED = 0xF135C5
PI_BY_4_SIG = 0xC90FDAA22168C234
BASE_FLAGS = (
    "--fsin-standalone",
    "--round18-poly",
    "--round21-table-bias",
    "--round23-narrow-coefficient",
    "--round24-table-delta-rn67",
)


def set_quant(
    schedule: h134.Schedule,
    field: str,
    index: int,
    quant: h110.Quant,
) -> h134.Schedule:
    values = list(getattr(schedule, field))
    values[index] = quant
    return dataclasses.replace(schedule, **{field: tuple(values)})


NARROW = set_quant(
    h134.CURRENT, "p_coefficients", 3, h110.Quant(64, "chop")
)
WIDE_P = set_quant(
    h134.CURRENT, "p_coefficients", 5, h110.Quant(64, "away")
)
WIDE_Q = set_quant(
    h134.CURRENT, "q_coefficients", 5, h110.Quant(64, "away")
)
WIDE_BOTH = set_quant(
    WIDE_P, "q_coefficients", 5, h110.Quant(64, "away")
)


def path_candidate(point: h131.Observed) -> h134.Schedule:
    if point.family == "narrow":
        return NARROW if point.source == "direct" else h134.CURRENT
    return WIDE_BOTH if point.source == "direct" else WIDE_Q


def score_path_candidate(
    points: list[h131.Observed],
) -> tuple[int, int, int]:
    mode_misses = 0
    input_misses = 0
    c1_misses = 0
    for point in points:
        result = h134.score([point], path_candidate(point))
        mode_misses += result[0]
        input_misses += result[1]
        c1_misses += result[2]
    return mode_misses, input_misses, c1_misses


def parse_single(line: str) -> tuple[int, int] | str:
    fields = line.split()
    if fields[0] == "C2":
        return "C2"
    if len(fields) < 3 or fields[0] != "OK":
        raise ValueError(line)
    return int(fields[1], 16), int(fields[2], 16)


def run_model(
    model: pathlib.Path,
    lines: list[str],
    rc: str,
    candidate: bool,
) -> list[tuple[int, int] | str]:
    command = [str(model), "--batch", *BASE_FLAGS]
    if rc != "rn":
        command.append(f"--rc={rc}")
    if not candidate:
        command.append("--fsin-table-shared")
    completed = subprocess.run(
        command,
        input="\n".join(lines) + "\n",
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    )
    return [
        parse_single(line) for line in completed.stdout.splitlines()
    ]


def parity(model: pathlib.Path) -> None:
    checks = 0
    inactive = 0
    for name, input_path in (
        ("dense", h131.INPUTS / "dense_qn.txt"),
        ("sweep", h131.INPUTS / "sweep_inputs.txt"),
    ):
        lines = input_path.read_text().splitlines()
        observed = h131.load_dataset(name, input_path)
        by_index = {point.index: point for point in observed}
        modes = {
            (rc, candidate): run_model(
                model, lines, rc, candidate
            )
            for rc in h58.RCS
            for candidate in (False, True)
        }
        for index in range(len(lines)):
            point = by_index.get(index)
            if point is None:
                for rc in h58.RCS:
                    if modes[(rc, False)][index] != modes[(rc, True)][index]:
                        raise SystemExit(
                            f"h135 inactive C path changed: {name} "
                            f"line {index + 1} {rc}"
                        )
                    inactive += 1
                continue
            schedules = (
                (False, h134.CURRENT),
                (True, path_candidate(point)),
            )
            for candidate, schedule in schedules:
                hidden = h134.hidden_value(point, schedule)
                for rc in h58.RCS:
                    expected = h58.x87_round(hidden, rc)
                    actual = modes[(rc, candidate)][index]
                    if actual != expected:
                        raise SystemExit(
                            f"h135 C/Python mismatch: {name} "
                            f"line {index + 1} {point.family} {rc} "
                            f"candidate={candidate}: "
                            f"C={actual} Python={expected}"
                        )
                    checks += 1
    print(
        f"PASS: {checks} baseline/candidate table results match Python; "
        f"{inactive} inactive candidate results match baseline"
    )


def direct_operand(
    rng: random.Random, family: str
) -> tuple[int, int]:
    sign = rng.getrandbits(1)
    if family == "narrow":
        exponent = -2
        sig = rng.randrange(1 << 63, 1 << 64)
    else:
        exponent = -1
        sig = rng.randrange(1 << 63, PI_BY_4_SIG)
    return (sign << 15) | (exponent + 16383), sig


def reduced_operands(
    rng: random.Random,
    family: str,
    count: int,
) -> tuple[list[tuple[int, int]], int]:
    result = []
    scanned = 0
    while len(result) < count:
        exponent = rng.randrange(0, 63)
        sig = rng.randrange(1 << 63, 1 << 64)
        sign = rng.getrandbits(1)
        se = (sign << 15) | (exponent + 16383)
        scanned += 1
        active = h80.active_table_input(se, sig)
        if (
            active is not None
            and active[2]
            and ("wide" if active[1].wide else "narrow") == family
        ):
            result.append((se, sig))
    return result, scanned


def generate(
    model: pathlib.Path,
    output: pathlib.Path,
    metadata: pathlib.Path,
    direct_count: int,
    reduced_count: int,
    scan_limit: int,
    chunk_size: int,
) -> None:
    rng = random.Random(SEED)
    rows = []
    meta = []
    for family in ("narrow", "wide"):
        for source in ("direct", "reduced"):
            count = (
                direct_count if source == "direct" else reduced_count
            )
            selected = 0
            scanned = 0
            signatures: dict[
                tuple[
                    tuple[tuple[int, int] | str, ...],
                    tuple[tuple[int, int] | str, ...],
                ],
                int,
            ] = {}
            while selected < count and scanned < scan_limit:
                wanted = min(chunk_size, scan_limit - scanned)
                if source == "direct":
                    operands = [
                        direct_operand(rng, family)
                        for _ in range(wanted)
                    ]
                    scanned += wanted
                else:
                    operands, attempts = reduced_operands(
                        rng, family, wanted
                    )
                    scanned += attempts
                lines = [
                    f"{se:04x} {sig:016x}" for se, sig in operands
                ]
                old_modes = [
                    run_model(model, lines, rc, False)
                    for rc in h58.RCS
                ]
                new_modes = [
                    run_model(model, lines, rc, True)
                    for rc in h58.RCS
                ]
                for index, line in enumerate(lines):
                    old = tuple(mode[index] for mode in old_modes)
                    new = tuple(mode[index] for mode in new_modes)
                    if old == new:
                        continue
                    signature = old, new
                    signature_count = signatures.get(signature, 0)
                    if signature_count >= 16:
                        continue
                    signatures[signature] = signature_count + 1
                    rows.append(line)
                    meta.append(
                        f"{family} {source} {selected} "
                        f"{signature_count}"
                    )
                    selected += 1
                    if selected >= count:
                        break
                if scanned // 1_000_000 != (
                    max(0, scanned - wanted) // 1_000_000
                ):
                    print(
                        f"h135 {family}/{source}: selected {selected}/"
                        f"{count} after {scanned} scans",
                        file=sys.stderr,
                    )
            if selected < count:
                raise SystemExit(
                    f"h135 {family}/{source}: selected {selected} "
                    f"after {scanned} scans; wanted {count}"
                )
            print(
                f"h135 {family}/{source}: selected {selected} from "
                f"{scanned} scans, {len(signatures)} signatures",
                file=sys.stderr,
            )
    output.write_text("\n".join(rows) + "\n")
    metadata.write_text("\n".join(meta) + "\n")
    print(
        f"h135 wrote {len(rows)} separators; seed={SEED:#x}",
        file=sys.stderr,
    )


def load_capture(
    inputs: pathlib.Path,
    metadata: pathlib.Path,
    capture: pathlib.Path,
) -> dict[tuple[str, str], list[h131.Observed]]:
    operands = [
        tuple(int(field, 16) for field in line.split())
        for line in inputs.read_text().splitlines()
    ]
    labels = [line.split()[:2] for line in metadata.read_text().splitlines()]
    modes = [
        (
            capture / f"constraint_fsin_table_terminal_{rc}_status.txt"
        ).read_text().splitlines()
        for rc in h58.RCS
    ]
    if (
        len(labels) != len(operands)
        or any(len(lines) != len(operands) for lines in modes)
    ):
        raise SystemExit("h135 input/metadata/capture line counts differ")
    result: dict[tuple[str, str], list[h131.Observed]] = {}
    for index, ((se, sig), label) in enumerate(zip(operands, labels)):
        active = h80.active_table_input(se, sig)
        if active is None:
            raise SystemExit(f"h135 input {index + 1} is inactive")
        signed_n, point, reduced = active
        family = "wide" if point.wide else "narrow"
        source = "reduced" if reduced else "direct"
        if [family, source] != label:
            raise SystemExit(f"h135 metadata mismatch at input {index + 1}")
        outputs = []
        c1 = []
        for lines in modes:
            fields = lines[index].split()
            if (
                len(fields) != 5
                or fields[0] != "OK"
                or fields[3] != "SW"
            ):
                raise ValueError(lines[index])
            outputs.append((int(fields[1], 16), int(fields[2], 16)))
            c1.append(bool(int(fields[4], 16) & 0x0200))
        observed = h131.Observed(
            index,
            source,
            signed_n,
            point,
            tuple(outputs),
            tuple(c1),
        )
        result.setdefault((family, source), []).append(observed)
    return result


def score_capture(
    inputs: pathlib.Path,
    metadata: pathlib.Path,
    capture: pathlib.Path,
) -> None:
    datasets = load_capture(inputs, metadata, capture)
    for key in sorted(datasets):
        family, source = key
        points = datasets[key]
        schedules = [("baseline", h134.CURRENT)]
        if family == "narrow":
            schedules.append(("terminal P chop64", NARROW))
        else:
            schedules.extend(
                (
                    ("terminal P away64", WIDE_P),
                    ("terminal Q away64", WIDE_Q),
                    ("both terminal away64", WIDE_BOTH),
                )
            )
        print(f"{family}/{source}: {len(points)} fresh separators")
        for name, schedule in schedules:
            print(
                f"  {name:24s} "
                f"{h131.describe(h134.score(points, schedule), len(points))}"
            )
        print(
            f"  {'path-aware rule':24s} "
            f"{h131.describe(score_path_candidate(points), len(points))}"
        )


def score_existing() -> None:
    for name, input_path in (
        ("dense", h131.INPUTS / "dense_qn.txt"),
        ("sweep", h131.INPUTS / "sweep_inputs.txt"),
    ):
        points = h131.load_dataset(name, input_path)
        for family in ("narrow", "wide"):
            selected = [point for point in points if point.family == family]
            baseline = h134.score(selected, h134.CURRENT)
            candidate = score_path_candidate(selected)
            print(f"{name}/{family}: {len(selected)} inputs")
            print(
                f"  baseline        "
                f"{h131.describe(baseline, len(selected))}"
            )
            print(
                f"  path-aware rule "
                f"{h131.describe(candidate, len(selected))}"
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=pathlib.Path)
    parser.add_argument("--parity", action="store_true")
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--score", type=pathlib.Path)
    parser.add_argument("--score-existing", action="store_true")
    parser.add_argument("--direct-count", type=int, default=32)
    parser.add_argument("--reduced-count", type=int, default=8)
    parser.add_argument("--scan-limit", type=int, default=20_000_000)
    parser.add_argument("--chunk-size", type=int, default=20_000)
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--metadata", type=pathlib.Path, default=DEFAULT_METADATA
    )
    args = parser.parse_args()
    if args.parity or args.generate:
        if args.model is None:
            parser.error("--parity/--generate requires --model")
        model = args.model.resolve()
        if args.parity:
            parity(model)
        if args.generate:
            generate(
                model,
                args.output,
                args.metadata,
                args.direct_count,
                args.reduced_count,
                args.scan_limit,
                args.chunk_size,
            )
    if args.score is not None:
        score_capture(args.output, args.metadata, args.score)
    if args.score_existing:
        score_existing()
    if (
        not args.parity
        and not args.generate
        and args.score is None
        and not args.score_existing
    ):
        parser.error("select --parity, --generate, and/or --score")


if __name__ == "__main__":
    main()
