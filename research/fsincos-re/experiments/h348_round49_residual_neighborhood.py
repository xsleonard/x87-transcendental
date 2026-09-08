#!/usr/bin/env python3
"""Compare the focused h347 hardware capture with the Round-49 model.

The comparison streams all nine result files so the large neighborhood does
not become another in-memory dataset.  It reports the exact contiguous delta
runs around every original residual seed and checks whether standalone FSIN
and FCOS continue to agree with the corresponding FSINCOS lanes.
"""

from __future__ import annotations

import argparse
import collections
import contextlib
import pathlib

import h58_constraint_search as h58
import h171_fsin_table_correction_discriminator as h171
import h188_table_stage_local_pairs as h188
import h207_tang_literal_fadd as h207
import h216_fadd_microcontrol_discriminator as h216
import h286_ingest_trig_sine_bias_capture as h286
import h230_p6_microop_materialization_search as h230
import h333_p6_carrier_metadata_semantics as h333
import h334_p6_carrier_metadata_fresh_gate as h334
import h346_round49_residual_inventory as h346


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_CAPTURE = (
    ROOT / "capture-kit-captures" / "skylake-trig-h347"
)
CANDIDATE = h333.CANDIDATES["interval-low1-last-interior"]


def point_from_input(index: int, se: int, sig: int):
    observed = h171.observed_from_input(index, se, sig)
    if observed is None:
        return None
    return h207.Point(h188.prepare(h216.blank(observed)), True)


def seed_rows():
    _, records = h346.inventory("sweep")
    grouped = collections.defaultdict(list)
    for record in records:
        grouped[record.se, record.sig].append(record)
    return tuple(sorted(grouped))


def seed_delta(se: int, sig: int, seeds):
    choices = []
    for seed_index, (seed_se, seed_sig) in enumerate(seeds):
        if se not in (seed_se, seed_se ^ 0x8000):
            continue
        choices.append((abs(sig - seed_sig), seed_index, sig - seed_sig))
    if not choices:
        return None
    _, seed_index, delta = min(choices)
    return seed_index, delta


def runs(values):
    values = sorted(set(values))
    if not values:
        return []
    result = []
    start = previous = values[0]
    for value in values[1:]:
        if value != previous + 1:
            result.append((start, previous))
            start = value
        previous = value
    result.append((start, previous))
    return result


def format_runs(values) -> str:
    return ",".join(
        str(start) if start == end else f"{start}..{end}"
        for start, end in runs(values)
    ) or "none"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", type=pathlib.Path, default=DEFAULT_CAPTURE)
    parser.add_argument("--mismatch-inputs", type=pathlib.Path)
    args = parser.parse_args()

    seeds = seed_rows()
    counts = collections.Counter()
    paired_deltas = collections.defaultdict(list)
    mismatch_operands = set()
    files = {}
    with contextlib.ExitStack() as stack:
        inputs = stack.enter_context((args.capture / "inputs.txt").open())
        for instruction in ("fsin", "fcos", "fsincos"):
            parser_for = (
                h286.parse_pair if instruction == "fsincos" else h286.parse_single
            )
            for rc in h58.RCS:
                stream = stack.enter_context(
                    (args.capture / f"{instruction}_{rc}_status.txt").open()
                )
                files[instruction, rc] = (stream, parser_for)

        for index, input_line in enumerate(inputs):
            if index and index % 512 == 0:
                h230.state.cache_clear()
            se, sig = (int(field, 16) for field in input_line.split())
            point = point_from_input(index, se, sig)
            if point is None:
                raise SystemExit(f"h348 inactive input line {index + 1}")
            hidden = h333.hidden_values(point, CANDIDATE)
            actual = {}
            for (instruction, rc), (stream, parser_for) in files.items():
                line = stream.readline()
                if not line:
                    raise SystemExit(
                        f"h348 short {instruction}/{rc} at line {index + 1}"
                    )
                actual[instruction, rc] = parser_for(line)

            for rc in h58.RCS:
                fsin = actual["fsin", rc][0]
                fcos = actual["fcos", rc][0]
                pair = actual["fsincos", rc][:2]
                counts["standalone-pair-disagreement"] += pair != (fsin, fcos)

            location = seed_delta(se, sig, seeds)
            observed = point.prepared.joint.observed
            for instruction in ("fsin", "fcos", "fsincos"):
                for rc in h58.RCS:
                    predicted, predicted_c1 = h334.expected(
                        hidden, instruction, rc
                    )
                    hardware, hardware_c1 = h286.hardware_values(
                        actual[instruction, rc], instruction
                    )
                    for lane_index, (got, want) in enumerate(
                        zip(predicted, hardware)
                    ):
                        if got == want:
                            continue
                        lane = (
                            ("sin", "cos")[lane_index]
                            if instruction == "fsincos"
                            else instruction[1:]
                        )
                        counts["result"] += 1
                        counts["instruction", instruction] += 1
                        counts["lane", lane] += 1
                        counts["rc", rc] += 1
                        counts["path", observed.source, observed.family] += 1
                        counts["cell", observed.point.cell] += 1
                        mismatch_operands.add((se, sig))
                        if instruction == "fsincos" and location is not None:
                            seed_index, delta = location
                            paired_deltas[
                                seed_index,
                                int(se != seeds[seed_index][0]),
                                lane,
                                rc,
                            ].append(delta)
                    if predicted == hardware and predicted_c1 != hardware_c1:
                        counts["c1"] += 1
                        counts["c1-instruction", instruction] += 1

        for (instruction, rc), (stream, _) in files.items():
            if stream.readline():
                raise SystemExit(f"h348 long {instruction}/{rc} capture")

    if args.mismatch_inputs:
        args.mismatch_inputs.write_text(
            "".join(
                f"{se:04x} {sig:016x}\n"
                for se, sig in sorted(mismatch_operands)
            )
        )

    print(
        f"h348 focused neighborhood: inputs={index + 1} "
        f"result={counts['result']} C1={counts['c1']} "
        f"affected-inputs={len(mismatch_operands)} "
        f"standalone/pair={counts['standalone-pair-disagreement']}"
    )
    for prefix in ("instruction", "lane", "rc", "path", "cell"):
        selected = {
            key[1:] if len(key) > 2 else key[1]: value
            for key, value in counts.items()
            if isinstance(key, tuple) and key[0] == prefix
        }
        print(f"  {prefix}: {dict(sorted(selected.items(), key=lambda item: str(item[0])))}")
    for key in sorted(paired_deltas):
        seed_index, mirrored, lane, rc = key
        se, sig = seeds[seed_index]
        print(
            f"  seed={seed_index + 1:02d} {se:04x}:{sig:016x} "
            f"mirror={mirrored} lane={lane} rc={rc} "
            f"deltas={format_runs(paired_deltas[key])}"
        )


if __name__ == "__main__":
    main()
