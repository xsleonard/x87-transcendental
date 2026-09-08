#!/usr/bin/env python3
"""Test the separate FAX1STK borrow-in interpretations of P5 FADD.

In US 5,257,215 FIG. 2 the shifted mantissa occupies bits 68:1 while
``FAX1STK`` is a separate signal entering the X2 path.  h200 initially
tested sticky ORed into the aligned word and sticky marked only after the
subtraction.  This pass tests the remaining two's-complement reading:

    diff = big - truncated_small - discarded_nonzero

The physically complete form retains sticky after that borrow because the
unrepresented remainder is ``1 - discarded_tail``.  ``borrow-clear`` is a
bounded falsifier that drops this complemented tail.

Both readings are evaluated in three already-defined grids:

* h200/h201 table P/Q carrier masks and direct/reduced gates;
* h202 scalar-proxy polynomial schedules through Rounds 31--33;
* h203 coherent native-ROM67/RN64 FMUL/FADD schedules.

Only exact sample profiles that are componentwise no worse proceed to the
complete old/fresh gates.
"""

from __future__ import annotations

import collections
import dataclasses

import h200_p5_fadd_bitvector as h200
import h201_p5_fadd_path_gate as h201
import h202_fsin_cosine_fadd_bitvector as h202
import h203_fsin_cosine_physical_datapath as h203


MODES = ("borrow-sticky", "borrow-clear")


def report_ranked(prefix: str, ranked, limit: int = 12) -> None:
    print(f"  leading {prefix} sample candidates:")
    for item in ranked[:limit]:
        print(
            f"    modes/c1/inputs={item[0]}/{item[1]}/{item[2]} "
            f"{item[4].short()}"
        )


def table_pass() -> None:
    sweep = h200.partitions("sweep")
    selected = h201.sample(sweep)
    baselines, baseline_signature = h201.score_signature(
        selected, h201.CURRENT
    )
    complete_baselines = h201.score_signature(sweep, h201.CURRENT)[0]
    profiles = collections.defaultdict(list)
    raw = []
    tested = 0
    for mode in MODES:
        p_profiles = h201.mask_profiles(mode, "p", selected)
        q_profiles = h201.mask_profiles(mode, "q", selected)
        print(
            f"  table {mode}: P mask profiles={p_profiles}; "
            f"Q mask profiles={q_profiles}"
        )
        for candidate in h201.candidate_set(mode, p_profiles, q_profiles):
            tested += 1
            values, signature = h201.score_signature(selected, candidate)
            item = (
                *h200.objective(values),
                candidate.short(),
                candidate,
                values,
            )
            raw.append(item)
            if (
                signature != baseline_signature
                and all(
                    h200.no_worse(value, baseline)
                    for value, baseline in zip(values, baselines)
                )
                and any(
                    value != baseline
                    for value, baseline in zip(values, baselines)
                )
            ):
                profiles[signature].append(item)
    raw.sort()
    representatives = sorted(min(items) for items in profiles.values())
    report_ranked("table", raw)
    print(
        f"h204 table sample: tested={tested} "
        f"survivors={sum(len(items) for items in profiles.values())} "
        f"profiles={len(representatives)}"
    )
    complete = []
    for item in representatives:
        candidate = item[4]
        values, _ = h201.score_signature(sweep, candidate)
        if all(
            h200.no_worse(value, baseline)
            for value, baseline in zip(values, complete_baselines)
        ) and any(
            value != baseline
            for value, baseline in zip(values, complete_baselines)
        ):
            complete.append(
                (*h200.objective(values), candidate.short(), candidate, values)
            )
    complete.sort()
    print(f"h204 table complete: {len(complete)} survivors")


def polynomial_pass() -> None:
    complete, selected = h203.selection_datasets()
    baselines, baseline_signature = h202.score_signature(
        selected, h202.CURRENT
    )
    complete_baselines = h202.score_signature(complete, h202.CURRENT)[0]
    candidates = tuple(
        h202.Candidate(mode, foundation, mask, False)
        for mode in MODES
        for foundation in h202.FOUNDATIONS
        for mask in range(32)
    )
    profiles = collections.defaultdict(list)
    raw = []
    for candidate in candidates:
        values, signature = h202.score_signature(selected, candidate)
        item = (
            *h202.objective(values),
            candidate.short(),
            candidate,
            values,
        )
        raw.append(item)
        if (
            signature != baseline_signature
            and all(
                h202.no_worse(value, baseline)
                for value, baseline in zip(values, baselines)
            )
            and any(
                value != baseline
                for value, baseline in zip(values, baselines)
            )
        ):
            profiles[signature].append(item)
    raw.sort()
    representatives = sorted(min(items) for items in profiles.values())
    report_ranked("polynomial proxy", raw)
    print(
        f"h204 polynomial sample: tested={len(candidates)} "
        f"survivors={sum(len(items) for items in profiles.values())} "
        f"profiles={len(representatives)}"
    )
    final = []
    for item in representatives:
        candidate = item[4]
        values, _ = h202.score_signature(complete, candidate)
        if all(
            h202.no_worse(value, baseline)
            for value, baseline in zip(values, complete_baselines)
        ) and any(
            value != baseline
            for value, baseline in zip(values, complete_baselines)
        ):
            final.append(
                (*h202.objective(values), candidate.short(), candidate, values)
            )
    final.sort()
    print(f"h204 polynomial complete: {len(final)} survivors")


def physical_pass() -> None:
    complete, selected = h203.selection_datasets()
    baselines, baseline_signature = h203.score_signature(selected, None)
    complete_baselines = h203.score_signature(complete, None)[0]
    candidates = tuple(
        dict.fromkeys(
            dataclasses.replace(candidate, mode=mode)
            for candidate in h203.candidates()
            for mode in MODES
        )
    )
    profiles = collections.defaultdict(list)
    raw = []
    for candidate in candidates:
        values, signature = h203.score_signature(selected, candidate)
        item = (
            *h203.objective(values),
            candidate.short(),
            candidate,
            values,
        )
        raw.append(item)
        if (
            signature != baseline_signature
            and all(
                h203.no_worse(value, baseline)
                for value, baseline in zip(values, baselines)
            )
            and any(
                value != baseline
                for value, baseline in zip(values, baselines)
            )
        ):
            profiles[signature].append(item)
    raw.sort()
    representatives = sorted(min(items) for items in profiles.values())
    report_ranked("physical", raw)
    print(
        f"h204 physical sample: tested={len(candidates)} "
        f"survivors={sum(len(items) for items in profiles.values())} "
        f"profiles={len(representatives)}"
    )
    final = []
    for item in representatives:
        candidate = item[4]
        values, _ = h203.score_signature(complete, candidate)
        if all(
            h203.no_worse(value, baseline)
            for value, baseline in zip(values, complete_baselines)
        ) and any(
            value != baseline
            for value, baseline in zip(values, complete_baselines)
        ):
            final.append(
                (*h203.objective(values), candidate.short(), candidate, values)
            )
    final.sort()
    print(f"h204 physical complete: {len(final)} survivors")


def main() -> None:
    print("h204 separate-sticky borrow calibration")
    table_pass()
    polynomial_pass()
    physical_pass()


if __name__ == "__main__":
    main()
