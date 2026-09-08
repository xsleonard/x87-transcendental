#!/usr/bin/env python3
"""Audit whether h1442 feedback histories can drive a closed microcontrol state.

Intel's Pentium 4 verification account establishes a two-pass extended-
precision multiplier: low product bits are produced first and fed back into
the adder network for the high partial products.  It deliberately abstracts
the feedback and control equations.  The numerical model uses a fixed arithmetic-stage order.
A fixed stage index is not itself a data-dependent observable.

h1442 reconstructs exact source-defined feedback signals from a public AMD
iterative-multiplier design.  This audit asks the information-theoretic
question that precedes fitting a state machine: does a complete history of
one such signal, all isomorphic versions of one signal, or a fixed physical
signal family distinguish the required R59 carry?  If opposite labels share
the same complete history, no deterministic finite-state machine driven only
by that history can distinguish them, even if every modeled stage
selects an arbitrary transition function.

The deliberately broad groupings are fixed before labels are inspected.  A
collision-free high-dimensional grouping is reported only as lookup capacity,
never as a selector.  No operand identity, threshold, decision tree, learned
gate, x87 execution, or paper/emulator change is involved.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import defaultdict
from pathlib import Path

import h1442_corrected_iterative_feedback as h1442


INTEL_SOURCE = "Kaivola_Narasimhan_DATE_2002"
INTEL_DOI = "10.1109/DATE.2002.998245"
INTEL_URL = (
    "https://past.date-conference.com/proceedings-archive/2002/DATE02/"
    "PDFFILES/01B_1.PDF"
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def summary_columns(names: tuple[str, ...]) -> dict[tuple[str, str], int]:
    columns: dict[tuple[str, str], int] = {}
    for index, name in enumerate(names):
        for stage in h1442.FMUL_STAGES:
            prefix = stage + "."
            if not name.startswith(prefix):
                continue
            stream = name[len(prefix):]
            if any(stream.endswith("." + suffix)
                   for suffix in h1442.SUMMARY_SUFFIXES):
                columns[(stage, stream)] = index
            break
    return columns


def stream_suffix(stream: str) -> str:
    for suffix in h1442.SUMMARY_SUFFIXES:
        if stream.endswith("." + suffix):
            return suffix
    raise ValueError(stream)


def assess_group(
    prepared: list[h1442.PreparedRow],
    columns: tuple[int, ...],
) -> tuple[int, int, int, tuple[tuple[object, ...], ...]]:
    groups: dict[tuple[str, int, bytes], list[list[h1442.PreparedRow]]]
    groups = defaultdict(lambda: [[], []])
    for item in prepared:
        history = bytes(item.signals[index] for index in columns)
        groups[(item.row["branch"], item.current, history)][
            item.required
        ].append(item)

    mixed_groups = 0
    targets_in_mixed = 0
    rows_in_mixed = 0
    witnesses = []
    for (branch, current, _), sides in groups.items():
        if not sides[0] or not sides[1]:
            continue
        mixed_groups += 1
        members = sides[0] + sides[1]
        targets = [item for item in members if item.target]
        targets_in_mixed += len(targets)
        rows_in_mixed += len(members)
        if len(witnesses) < 4:
            witnesses.append((
                branch,
                current,
                len(sides[0]),
                len(sides[1]),
                tuple((item.row["mode"], item.row["op"])
                      for item in targets[:8]),
                (sides[0][0].row["mode"], sides[0][0].row["op"]),
                (sides[1][0].row["mode"], sides[1][0].row["op"]),
            ))
    return mixed_groups, targets_in_mixed, rows_in_mixed, tuple(witnesses)


def ordered_columns(
    columns: dict[tuple[str, str], int], streams: tuple[str, ...],
) -> tuple[int, ...]:
    return tuple(
        columns[(stage, stream)]
        for stage in h1442.FMUL_STAGES
        for stream in streams
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("positive_allmode", type=Path)
    parser.add_argument("control_allmode", type=Path)
    parser.add_argument("model", type=Path)
    parser.add_argument("misses", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--extra-op", default=h1442.h1425.EXTRA_OP)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    prepared, source_rows, names = h1442.prepare(args)
    columns = summary_columns(names)
    streams = tuple(sorted({stream for _, stream in columns}))
    expected_streams = (
        len(h1442.REPRESENTATIONS)
        * len(h1442.PROJECTIONS)
        * len(h1442.ROLES)
        * len(h1442.SUMMARY_SUFFIXES)
    )
    if len(streams) != expected_streams:
        raise RuntimeError(
            f"expected {expected_streams} summary streams, got {len(streams)}"
        )
    if len(columns) != len(streams) * len(h1442.FMUL_STAGES):
        raise RuntimeError("summary stream missing an FMUL stage")

    single_results = []
    for stream in streams:
        result = assess_group(
            prepared, ordered_columns(columns, (stream,)))
        single_results.append((stream, *result[:3], result[3]))

    suffix_results = []
    for suffix in h1442.SUMMARY_SUFFIXES:
        members = tuple(
            stream for stream in streams if stream_suffix(stream) == suffix
        )
        result = assess_group(prepared, ordered_columns(columns, members))
        suffix_results.append((suffix, len(members), *result[:3], result[3]))

    suffix_sets = {
        "tree_wrap": tuple(
            suffix for suffix in h1442.SUMMARY_SUFFIXES
            if suffix.endswith(".tree_wrap")
        ),
        "carry_endpoints": tuple(
            suffix for suffix in h1442.SUMMARY_SUFFIXES
            if suffix.endswith(".carry0") or suffix.endswith(".carry1")
        ),
        "selected_carry_chain": tuple(
            suffix for suffix in h1442.SUMMARY_SUFFIXES
            if "selected_carry" in suffix
            or suffix.endswith(".incoming_carry")
        ),
        "sticky_chain": tuple(
            suffix for suffix in h1442.SUMMARY_SUFFIXES
            if "sticky" in suffix and not suffix.startswith("final.")
        ),
        "final_rounding": tuple(
            suffix for suffix in h1442.SUMMARY_SUFFIXES
            if suffix.startswith("final.")
        ),
        "all_feedback": tuple(
            suffix for suffix in h1442.SUMMARY_SUFFIXES
            if not suffix.startswith("final.")
        ),
        "all_summary": h1442.SUMMARY_SUFFIXES,
    }
    family_results = []
    for family, suffixes in suffix_sets.items():
        members = tuple(
            stream for stream in streams if stream_suffix(stream) in suffixes
        )
        result = assess_group(prepared, ordered_columns(columns, members))
        family_results.append((
            family, len(suffixes), len(members), *result[:3], result[3]
        ))

    target_count = sum(item.target for item in prepared)
    control_count = len(prepared) - target_count
    exact_single = sum(item[1] == 0 for item in single_results)
    exact_suffix = sum(item[2] == 0 for item in suffix_results)
    exact_family = sum(item[3] == 0 for item in family_results)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        for label, path in (
            ("features", args.features),
            ("positive_allmode", args.positive_allmode),
            ("control_allmode", args.control_allmode),
            ("model", args.model),
            ("misses", args.misses),
            ("feedback_reconstruction", Path(h1442.__file__)),
        ):
            output.write(f"{label}_sha256\t{digest(path)}\n")
        output.write("hardware_policy\timmutable_cached_labels_no_x87_execution\n")
        output.write(
            f"intel_primary_source\t{INTEL_SOURCE}\tdoi:{INTEL_DOI}\t"
            f"{INTEL_URL}\n"
        )
        output.write(
            "intel_source_scope\ttwo_pass_low_first_feedback_into_adder_"
            "network_no_published_feedback_or_control_equation\n"
        )
        output.write(
            "feedback_signal_scope\texact_AMD_source_defined_isomorphism_"
            "not_Intel_or_Skylake_provenance\n"
        )
        output.write(
            "candidate_policy\tcomplete_history_collision_test_no_learned_"
            "transition_or_decoder\n"
        )
        output.write(
            "address_policy\tfixed_stage_indices_add_no_data_"
            "discrimination\n"
        )
        output.write(f"source_rows\t{len(source_rows)}\n")
        output.write(f"constraining_mode_rows\t{len(prepared)}\n")
        output.write(f"target_mode_rows\t{target_count}\n")
        output.write(f"control_mode_rows\t{control_count}\n")
        output.write(f"fmul_stages\t{len(h1442.FMUL_STAGES)}\n")
        output.write(f"summary_streams\t{len(streams)}\n")
        output.write(f"single_stream_exact_histories\t{exact_single}\n")
        output.write(f"isomorphic_suffix_exact_histories\t{exact_suffix}\n")
        output.write(f"physical_family_exact_histories\t{exact_family}\n")

        output.write("\n[single-stream complete-history collisions]\n")
        output.write(
            "stream\tmixed_groups\ttargets_in_mixed\trows_in_mixed\t"
            "witnesses\n"
        )
        for item in sorted(single_results, key=lambda value: (
                value[2], value[1], value[0])):
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[isomorphic-suffix complete-history collisions]\n")
        output.write(
            "suffix\tstreams\tmixed_groups\ttargets_in_mixed\t"
            "rows_in_mixed\twitnesses\n"
        )
        for item in suffix_results:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[fixed-physical-family complete-history collisions]\n")
        output.write(
            "family\tsuffixes\tstreams\tmixed_groups\ttargets_in_mixed\t"
            "rows_in_mixed\twitnesses\n"
        )
        for item in family_results:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[result]\n")
        if exact_single:
            output.write(
                "single_feedback_stream_fsm\tlookup_capacity_only\n"
            )
        else:
            output.write(
                "single_feedback_stream_fsm\timpossible_by_complete_"
                "history_collision\n"
            )
        output.write(
            "collision_free_group_status\tlookup_capacity_not_closed_"
            "selector\n"
        )


if __name__ == "__main__":
    main()
