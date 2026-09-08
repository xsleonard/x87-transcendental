#!/usr/bin/env python3
"""Score h1438's apparent singleton wire on an earlier hardware holdout.

h1438 found that ``positive.add2.lzd.ls36.code.bit3`` is asserted on the
single b000 frontier row and on no row in its 34,464-row control bank.  That
is not validation: it is one bit of a high-dimensional normalization-code
fingerprint.  The already-opened h1127b support-boundary holdout predates this
hypothesis and contains cached hardware results near b000.

This audit re-dumps those operands from the current executable, reconstructs
the source-defined wire, and evaluates the two h1438 zero-training-collateral
gates (carry OR wire and carry XOR wire).  Separately compiled analysis-only
binaries force final R59 carry zero and one, allowing the candidate's result
to be scored without modifying the emulator.  The cached hardware files are
never executed or changed, and no new x87 observation is made.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import subprocess
from collections import Counter
from pathlib import Path

import h1386_current_r59_feature_bank as h1386
import h1438_multiformat_postadd_normalizer as h1438
from h1110_carry_gate_mine import extract_carry_state


SIGNAL = "positive.add2.lzd.ls36.code.bit3"
GATES = (("c_xor_f", 6), ("c_or_f", 14))


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
    details = []
    gate_scores = {name: Counter() for name, _ in GATES}
    for row in refreshed:
        if row["baseline"] != row["hw"]:
            counts["baseline_misses"] += 1
        current = extract_carry_state(row, set())[2]
        endpoints = (row["carry0"], row["carry1"])
        if endpoints[current] != row["baseline"]:
            raise RuntimeError(
                f"forced endpoint/current mismatch for {row['mode']} {row['op']}"
            )
        allowed = {carry for carry, value in enumerate(endpoints) if value == row["hw"]}
        signal = h1438.source_signals(row)[0][SIGNAL]
        counts["signal_ones"] += signal
        counts["signal_endpoint_visible"] += signal and len(set(endpoints)) == 2
        local = []
        for name, gate in GATES:
            prediction = (gate >> (2 * current + signal)) & 1
            changed = prediction != current
            wrong = prediction not in allowed
            gate_scores[name]["changes"] += changed
            gate_scores[name]["errors"] += wrong
            gate_scores[name]["signal_changes"] += signal and changed
            gate_scores[name]["signal_errors"] += signal and wrong
            local.append((name, prediction, int(changed), int(wrong)))
        if signal:
            details.append((
                row["mode"], row["op"], row["hw"], current,
                row["carry0"], row["carry1"],
                ",".join(map(str, sorted(allowed))), *local,
            ))

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        for name, path in (
            ("holdout", args.holdout),
            ("model", args.model),
            ("carry0", args.carry0),
            ("carry1", args.carry1),
            ("signal_reconstruction", Path(h1438.__file__)),
        ):
            output.write(f"{name}_sha256\t{digest(path)}\n")
        output.write("hardware_policy\tpreexisting_cached_holdout_no_x87_execution\n")
        output.write(f"candidate_signal\t{SIGNAL}\n")
        output.write(f"holdout_rows\t{len(refreshed)}\n")
        output.write(f"baseline_misses\t{counts['baseline_misses']}\n")
        output.write(f"signal_ones\t{counts['signal_ones']}\n")
        output.write(
            f"signal_endpoint_visible\t{counts['signal_endpoint_visible']}\n"
        )
        for name, _ in GATES:
            score = gate_scores[name]
            output.write(f"{name}_changes\t{score['changes']}\n")
            output.write(f"{name}_errors\t{score['errors']}\n")
            output.write(f"{name}_signal_changes\t{score['signal_changes']}\n")
            output.write(f"{name}_signal_errors\t{score['signal_errors']}\n")

        output.write("\n[signal-one holdout rows]\n")
        output.write(
            "mode\top\thw\tcurrent\tcarry0\tcarry1\tallowed\t"
            "xor_name\txor_prediction\txor_changed\txor_wrong\t"
            "or_name\tor_prediction\tor_changed\tor_wrong\n"
        )
        for detail in details:
            flat = (*detail[:7], *detail[7], *detail[8])
            output.write("\t".join(map(str, flat)) + "\n")

        output.write("\n[result]\n")
        if any(score["errors"] for score in gate_scores.values()):
            output.write(
                "h1438_singleton_signal\trefuted_by_preexisting_hardware_holdout\n"
            )
        else:
            output.write("h1438_singleton_signal\tnot_refuted_on_this_holdout\n")

    print(
        f"wrote {args.report}: rows={len(refreshed)} "
        f"signal_ones={counts['signal_ones']} "
        + " ".join(
            f"{name}_errors={gate_scores[name]['errors']}" for name, _ in GATES
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
