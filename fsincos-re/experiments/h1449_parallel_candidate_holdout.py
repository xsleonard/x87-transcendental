#!/usr/bin/env python3
"""Test h1448's partial CSA-wire repairs on a pre-existing holdout.

h1448 found two raw wires from Intel US6055555A's parallel plus-one
carry-save path that repair one operand each without collateral on the
34,475-row development wall.  The stronger bit-111 hit repairs both d0d0
rounding-mode legs; bit 103 repairs one frontier leg.  Neither wire is a
source-defined mux input, so these are provisional finite-wall aliases.

This audit re-dumps the already-opened h1127b support-boundary operands from
the current executable, reconstructs both wires, and scores exactly the gates
that had zero development-wall collateral.  Analysis-only binaries force the
two final R59 carry endpoints.  Hardware truth is read only from the older
cached holdout; no x87 instruction is executed and no observation is repeated.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import subprocess
from collections import Counter
from pathlib import Path

import h1386_current_r59_feature_bank as h1386
import h1448_parallel_round_candidate_csa as h1448
from h1110_carry_gate_mine import extract_carry_state


CANDIDATES = (
    (
        "carry111",
        "square.written.candidate_carry.bit111",
        (("c_xor_f", 6), ("c_or_f", 14)),
    ),
    (
        "carry103",
        "square.written.candidate_carry.bit103",
        (("c_xor_f", 6), ("c_and_not_f", 4)),
    ),
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    if not rows:
        raise RuntimeError(f"empty holdout: {path}")
    return rows


def run_model(model: Path, mode: str, operands: list[str]) -> list[str]:
    command = [str(model), "--batch", f"--rc={mode}", "--fcos-standalone"]
    process = subprocess.run(
        command,
        input="\n".join(operands) + "\n",
        text=True,
        capture_output=True,
        check=True,
    )
    values = []
    for line in process.stdout.splitlines():
        fields = line.lower().split()
        if len(fields) == 3 and fields[0] == "ok":
            values.append(f"{fields[1]}:{fields[2]}")
    if len(values) != len(operands):
        raise RuntimeError(
            f"{model}/{mode}: {len(values)} outputs for {len(operands)} inputs"
        )
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("holdout", type=Path)
    parser.add_argument("model", type=Path)
    parser.add_argument("carry0", type=Path)
    parser.add_argument("carry1", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    source_rows = read_rows(args.holdout)
    refreshed = []
    for mode in sorted({row["mode"] for row in source_rows}):
        selected = [row for row in source_rows if row["mode"] == mode]
        operands = [row["op"] for row in selected]
        baseline_rows = h1386.dump(str(args.model), mode, operands)
        carry0 = run_model(args.carry0, mode, operands)
        carry1 = run_model(args.carry1, mode, operands)
        for source, row, output0, output1 in zip(
            selected, baseline_rows, carry0, carry1
        ):
            if row["op"] != source["op"]:
                raise RuntimeError("current dump desynchronized from holdout")
            row.update({
                "mode": mode,
                "hw": source["hw"].lower(),
                "baseline": row["model"].lower(),
                "carry0": output0,
                "carry1": output1,
            })
            refreshed.append(row)

    counts = Counter()
    scores = {
        (tag, gate_name): Counter()
        for tag, _, gates in CANDIDATES
        for gate_name, _ in gates
    }
    signal_counts = {tag: Counter() for tag, _, _ in CANDIDATES}
    details = []
    for row in refreshed:
        if row["baseline"] != row["hw"]:
            counts["baseline_misses"] += 1
        current = extract_carry_state(row, set())[2]
        endpoints = (row["carry0"], row["carry1"])
        if endpoints[current] != row["baseline"]:
            raise RuntimeError(
                f"forced endpoint/current mismatch for {row['mode']} {row['op']}"
            )
        allowed = {
            carry for carry, value in enumerate(endpoints) if value == row["hw"]
        }
        source_signals = h1448.source_signals(row)[0]
        local_details = []
        any_signal = False
        for tag, signal_name, gates in CANDIDATES:
            signal = source_signals[signal_name]
            any_signal |= bool(signal)
            signal_counts[tag]["ones"] += signal
            signal_counts[tag]["endpoint_visible"] += (
                signal and len(set(endpoints)) == 2
            )
            for gate_name, gate in gates:
                prediction = (gate >> (2 * current + signal)) & 1
                changed = prediction != current
                wrong = prediction not in allowed
                score = scores[(tag, gate_name)]
                score["changes"] += changed
                score["errors"] += wrong
                score["signal_changes"] += signal and changed
                score["signal_errors"] += signal and wrong
                local_details.append((
                    tag, signal_name, signal, gate_name,
                    prediction, int(changed), int(wrong),
                ))
        if any_signal:
            details.append((
                row["mode"], row["op"], row["hw"], current,
                row["carry0"], row["carry1"],
                ",".join(map(str, sorted(allowed))),
                repr(tuple(local_details)),
            ))

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        for name, path in (
            ("holdout", args.holdout),
            ("model", args.model),
            ("carry0", args.carry0),
            ("carry1", args.carry1),
            ("signal_reconstruction", Path(h1448.__file__)),
        ):
            output.write(f"{name}_sha256\t{digest(path)}\n")
        output.write("hardware_policy\tpreexisting_cached_holdout_no_x87_execution\n")
        output.write(f"holdout_rows\t{len(refreshed)}\n")
        output.write(f"baseline_misses\t{counts['baseline_misses']}\n")
        for tag, signal_name, gates in CANDIDATES:
            output.write(f"{tag}_signal\t{signal_name}\n")
            output.write(f"{tag}_ones\t{signal_counts[tag]['ones']}\n")
            output.write(
                f"{tag}_endpoint_visible\t"
                f"{signal_counts[tag]['endpoint_visible']}\n"
            )
            for gate_name, _ in gates:
                score = scores[(tag, gate_name)]
                for field in (
                    "changes", "errors", "signal_changes", "signal_errors"
                ):
                    output.write(
                        f"{tag}_{gate_name}_{field}\t{score[field]}\n"
                    )

        output.write("\n[signal-one holdout rows]\n")
        output.write(
            "mode\top\thw\tcurrent\tcarry0\tcarry1\tallowed\tgate_details\n"
        )
        for detail in details:
            output.write("\t".join(map(str, detail)) + "\n")

        output.write("\n[result]\n")
        if any(score["errors"] for score in scores.values()):
            output.write(
                "h1448_partial_CSA_wire_repairs\t"
                "refuted_by_preexisting_hardware_holdout\n"
            )
        else:
            output.write(
                "h1448_partial_CSA_wire_repairs\tnot_refuted_on_this_holdout\n"
            )

    print(
        f"wrote {args.report}: rows={len(refreshed)} "
        + " ".join(
            f"{tag}_{gate_name}_errors={score['errors']}"
            for (tag, gate_name), score in scores.items()
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
