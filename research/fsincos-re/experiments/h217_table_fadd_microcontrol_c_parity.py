#!/usr/bin/env python3
"""Prove the Round-36 C port and measure its complete-corpus effect.

h216 freshly selects one lane-local first-FADD rule.  The rule's two base
conditions are rare, so this pass emits every dense/sweep input on which
either lane reaches that state, including both values of the discriminating
raw carrier bit.  C output captured on Debian is then checked against the
literal Python program for RN/RD/RU, while the complete hardware-backed
datasets are scored directly in Python.

The parity input is not a new hardware discriminator.  It is a compact,
exhaustive exercise of every complete-corpus state at which the new C branch
can become active or is rejected solely by carrier bit 3.
"""

from __future__ import annotations

import argparse
import collections
import pathlib

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h131_fsin_table_c1_search as h131
import h135_fsin_table_terminal_discriminator as h135
import h171_fsin_table_correction_discriminator as h171
import h182_table_joint_terminal_edges as h182
import h188_table_stage_local_pairs as h188
import h207_tang_literal_fadd as h207
import h213_fadd_causal_selector as h213
import h214_fadd_node0_selector as h214
import h216_fadd_microcontrol_discriminator as h216


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_INPUT = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_table_fadd_microcontrol_h217_parity.txt"
)
DEFAULT_METADATA = DEFAULT_INPUT.with_suffix(".meta.txt")
RULE = h216.RULES["b_bit3"]
BASE_TERMS = RULE.terms[:2]
BASE_FLAGS = (
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
)


def blank(observed) -> h182.Point:
    return h182.Point(
        observed,
        ((0, 0),) * len(h58.RCS),
        (False,) * len(h58.RCS),
    )


def matches(features, terms) -> bool:
    return all(features.get(name) == value for name, value in terms)


def source_lines(name: str) -> list[str]:
    path = h131.INPUTS / (
        "dense_qn.txt" if name == "dense" else "sweep_inputs.txt"
    )
    return path.read_text().splitlines()


def complete_points(name: str) -> list[h207.Point]:
    return [
        point
        for _, partition in h207.joint_partitions(name)
        for point in partition
    ]


def generate(output: pathlib.Path, metadata: pathlib.Path) -> None:
    rows = []
    meta = []
    census = collections.Counter()
    seen = set()
    for dataset in ("sweep", "dense"):
        lines = source_lines(dataset)
        for point in complete_points(dataset):
            observed = point.prepared.joint.observed
            lanes = []
            for cosine in (False, True):
                features = h214.lane_features(point, RULE.candidate, cosine)
                if not matches(features, BASE_TERMS):
                    continue
                bit = features["node0.raw.bit3"]
                lanes.append(f"{'c' if cosine else 's'}{bit}")
                census[dataset, "cosine" if cosine else "sine", bit] += 1
            if not lanes:
                continue
            key = (dataset, observed.index)
            if key in seen:
                raise AssertionError(key)
            seen.add(key)
            line = lines[observed.index]
            rows.append(line)
            meta.append(
                f"{dataset} {observed.index} {observed.source} "
                f"{observed.signed_n} {observed.point.cell} "
                f"{','.join(lanes)}"
            )
    output.write_text("\n".join(rows) + "\n")
    metadata.write_text("\n".join(meta) + "\n")
    print(
        f"h217 generated inputs={len(rows)} base-lanes={sum(census.values())} "
        f"census={dict(sorted(census.items()))}"
    )


def parse_single(line: str):
    fields = line.split()
    if len(fields) != 3 or fields[0] != "OK":
        raise ValueError(line)
    return int(fields[1], 16), int(fields[2], 16)


def parse_pair(line: str):
    fields = line.split()
    if len(fields) != 5 or fields[0] != "OK":
        raise ValueError(line)
    return (
        (int(fields[1], 16), int(fields[2], 16)),
        (int(fields[3], 16), int(fields[4], 16)),
    )


def output_path(directory, candidate: bool, standalone: bool, rc: str):
    version = "candidate" if candidate else "baseline"
    instruction = "fsin" if standalone else "fsincos"
    return directory / f"h217_{version}_{instruction}_{rc}.txt"


def point_from_line(index: int, line: str) -> h207.Point:
    se, sig = (int(field, 16) for field in line.split())
    observed = h171.observed_from_input(index, se, sig)
    if observed is None or observed.family != "wide":
        raise SystemExit(f"h217 line {index + 1} is not wide table")
    return h207.Point(h188.prepare(blank(observed)), True)


def expected(point: h207.Point, candidate: bool):
    values = (
        h216.hidden_values(point, RULE)
        if candidate
        else h207.current_values(point.prepared)
    )
    return {
        rc: tuple(h58.x87_round(value, rc) for value in values)
        for rc in h58.RCS
    }


def score_outputs(inputs: pathlib.Path, directory: pathlib.Path) -> None:
    lines = inputs.read_text().splitlines()
    runs = {}
    for candidate in (False, True):
        for standalone in (False, True):
            parser = parse_single if standalone else parse_pair
            for rc in h58.RCS:
                path = output_path(directory, candidate, standalone, rc)
                values = [parser(line) for line in path.read_text().splitlines()]
                if len(values) != len(lines):
                    raise SystemExit(
                        f"h217 output length {path}: {len(values)} != {len(lines)}"
                    )
                runs[candidate, standalone, rc] = values

    checks = 0
    changed = collections.Counter()
    active = collections.Counter()
    for index, line in enumerate(lines):
        point = point_from_line(index, line)
        features = {
            cosine: h214.lane_features(point, RULE.candidate, cosine)
            for cosine in (False, True)
        }
        for cosine in (False, True):
            if matches(features[cosine], BASE_TERMS):
                active["cosine" if cosine else "sine", features[cosine]["node0.raw.bit3"]] += 1
        for candidate in (False, True):
            profiles = expected(point, candidate)
            for rc in h58.RCS:
                actual = (
                    runs[candidate, True, rc][index],
                    runs[candidate, False, rc][index][1],
                )
                if actual != profiles[rc]:
                    raise SystemExit(
                        f"h217 C/Python mismatch line {index + 1} "
                        f"candidate={candidate} rc={rc}: "
                        f"C={actual} Python={profiles[rc]}"
                    )
                checks += 2
        for rc in h58.RCS:
            old = (
                runs[False, True, rc][index],
                runs[False, False, rc][index][1],
            )
            new = (
                runs[True, True, rc][index],
                runs[True, False, rc][index][1],
            )
            for lane, name in enumerate(("sine", "cosine")):
                changed[name] += old[lane] != new[lane]
    print(
        f"PASS: h217 C/Python checks={checks} inputs={len(lines)} "
        f"active={dict(sorted(active.items()))} changed={dict(changed)}"
    )


def add(left, right):
    return h207.add_metric(left, right)


def score_complete() -> None:
    for name in ("sweep", "dense"):
        datasets = h207.joint_partitions(name)
        for partition_name, points in datasets:
            baseline = h213.ZERO_JOINT
            candidate = h213.ZERO_JOINT
            activations = collections.Counter()
            for point in points:
                current_values = h207.current_values(point.prepared)
                current_metric = h213.metric_for_values(point, *current_values)
                literal_metric = h214.conditional_metric(point, RULE)
                baseline = add(baseline, current_metric)
                candidate = add(candidate, literal_metric)
                for cosine in (False, True):
                    features = h214.lane_features(
                        point, RULE.candidate, cosine
                    )
                    if matches(features, RULE.terms):
                        activations["cosine" if cosine else "sine"] += 1
            print(
                f"{partition_name}: n={len(points)} "
                f"hardware={baseline}->{candidate} "
                f"activations={dict(activations)}"
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--score-complete", action="store_true")
    parser.add_argument("--score-outputs", type=pathlib.Path)
    parser.add_argument("--input", type=pathlib.Path, default=DEFAULT_INPUT)
    parser.add_argument("--metadata", type=pathlib.Path, default=DEFAULT_METADATA)
    args = parser.parse_args()
    if args.generate:
        generate(args.input, args.metadata)
    if args.score_complete:
        score_complete()
    if args.score_outputs is not None:
        score_outputs(args.input, args.score_outputs)
    if not (args.generate or args.score_complete or args.score_outputs):
        parser.error("select --generate, --score-complete, or --score-outputs")


if __name__ == "__main__":
    main()
