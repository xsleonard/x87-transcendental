#!/usr/bin/env python3
"""Reconstruct every Horner producer/add boundary for one cached operand.

The last R1272 miss is causally non-identifying at the terminal accumulator:
several one-unit perturbations produce the same architectural answer.  This
audit therefore works upstream.  It reports the exact multiply remainder,
the chopped 67-bit source, the exact 64-bit add remainder, and the selected
four-bit word in the documented P5 product CPA for all four Horner adds.

Only a software model dump is used.  The operand is supplied explicitly so
the same audit can later be applied to generated adversarial preimages.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from h1172_p5_cpa_predictor_mine import add_cpa_features, product_state
from h1184_upstream_halfway_audit import (
    CONSTANTS,
    Value,
    add_same_sign,
    quantize,
    schedule,
)
from h1210_stagea_residual_reframe import parse_dump, run
from h1222_r1200_enable_state import cut_fields, scalar_schedule, value_delta
from h1192_precision_difference_recurrence import dyad_quantize, recurrence
from h1222_r1200_enable_state import bus_value, from_bus
import h206_p5_fadd_complete as h206


STAGES = (
    ("negative.add1", 3, "negative.mul1", 5),
    ("negative.add2", 1, "negative.mul2", None),
    ("positive.add1", 4, "positive.mul1", 6),
    ("positive.add2", 2, "positive.mul2", None),
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def cpa_word(multiplicand: int, multiplier: int) -> dict[str, int]:
    sum_vector, carry_vector, cut = product_state(multiplicand, multiplier)
    values: dict[str, int] = {}
    add_cpa_features(values, "P", sum_vector, carry_vector, cut)
    stem = "P.p5.w04.rel+0"
    sum0 = sum(values[f"{stem}.sum0.b{bit}"] << bit for bit in range(4))
    sum1 = sum(values[f"{stem}.sum1.b{bit}"] << bit for bit in range(4))
    carry_in = values[f"{stem}.cin"]
    selected = sum1 if carry_in else sum0
    product = multiplicand * multiplier
    return {
        "cut": cut,
        "sum0": sum0,
        "sum1": sum1,
        "cin": carry_in,
        "selected": selected,
        "bit65": (product >> 65) & 1,
    }


def rendered_cut(fields: dict[str, object]) -> str:
    return "\t".join(map(str, (
        fields["shift"],
        f"{int(fields['retained']):x}",
        f"{int(fields['remainder']):x}",
        f"{int(fields['denominator']):x}",
        fields["half_delta"],
        fields["class"],
        int(fields["retained"]) & 1,
    )))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("operand")
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    operand = args.operand.lower()
    _, stderr = run(args.model, "rn", [operand], dump=True)
    row = parse_dump(stderr, [operand])[0]
    operations = schedule(row)
    graph = recurrence(row)
    ordinary_values, ordinary_adds = scalar_schedule(row, False)
    history_values, history_adds = scalar_schedule(row, True)
    fourth = ordinary_values["fourth"].value

    records = []
    for stage, constant_index, producer_stage, first_multiplier_index in STAGES:
        chain = stage.split(".", 1)[0]
        source = quantize(operations[producer_stage], 67, False)
        if first_multiplier_index is not None:
            multiplier = Value(*CONSTANTS[first_multiplier_index])
        else:
            multiplier = ordinary_values[f"{chain}.add1"].value
        if operations[producer_stage].magnitude != (
                fourth.significand * multiplier.significand):
            raise AssertionError(f"producer multiplicands disagree at {stage}")
        # The recovered P5 129-bit CPA is the 67x64 second-multiply unit.
        # The first multiply has two 67-bit significands, so do not pretend
        # that its undocumented high-radix layout is the same circuit.
        cpa = (cpa_word(fourth.significand, multiplier.significand)
               if first_multiplier_index is None else None)
        producer_cut = cut_fields(operations[producer_stage], 67)
        add_operation = add_same_sign(Value(*CONSTANTS[constant_index]), source)
        add_cut = cut_fields(add_operation, 64)
        ordinary = quantize(add_operation, 64, True)
        if ordinary != ordinary_values[stage].value:
            raise AssertionError(f"ordinary add mismatch at {stage}")

        variants = []
        for delta in range(-4, 5):
            varied_source = Value(
                source.sign, source.exponent, source.significand + delta)
            varied = quantize(
                add_same_sign(Value(*CONSTANTS[constant_index]), varied_source),
                64,
                True,
            )
            variants.append((delta, value_delta(varied, ordinary)))

        lower = int(add_cut["retained"])
        increments = int(ordinary.significand > lower)
        q = int(add_cut["half_delta"])
        r1237 = int(
            cpa is not None
            and 0 <= q <= 4
            and increments
            and ((q >> 2) & 1) == cpa["bit65"]
        )
        records.append({
            "stage": stage,
            "producer": producer_stage,
            "producer_cut": producer_cut,
            "source": source,
            "source_history": ordinary_values[producer_stage].history,
            "add_cut": add_cut,
            "ordinary": ordinary,
            "ordinary_history": ordinary_values[stage].history,
            "history_value": history_values[stage].value,
            "history_fires": history_adds[stage]["fires"],
            "cpa": cpa,
            "r1237": r1237,
            "onehop_delta": (
                value_delta(
                    dyad_quantize(graph[f"onehop.{stage}"], 64, True),
                    ordinary,
                )
                if stage.endswith("add2") else None
            ),
            "recursive_delta": value_delta(
                dyad_quantize(graph[f"recursive.{stage}"], 64, True),
                ordinary,
            ),
            "literal_deltas": {
                mode: value_delta(
                    from_bus(h206.materialize(
                        h206.fadd(
                            bus_value(Value(*CONSTANTS[constant_index])),
                            bus_value(source),
                            mode,
                            normalize=True,
                        )[0],
                        "rn64",
                    )),
                    ordinary,
                )
                for mode in h206.MODES
            },
            "variants": variants,
        })

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"model_sha256\t{digest(args.model)}\n")
        target.write(f"operand\t{operand}\n")
        target.write("hardware_policy\tsoftware_model_dump_only\n")
        target.write(
            "cut_columns\tshift retained remainder denominator half_delta "
            "class retained_lsb\n"
        )
        target.write("\n[Horner boundaries]\n")
        target.write(
            "stage\tproducer\tproducer_shift\tproducer_retained\t"
            "producer_remainder\tproducer_denominator\t"
            "producer_half_delta\tproducer_class\tproducer_retained_lsb\t"
            "source_sign\tsource_exp\tsource_sig\tsource_history\t"
            "add_shift\tadd_retained\tadd_remainder\tadd_denominator\t"
            "add_half_delta\tadd_class\tadd_retained_lsb\t"
            "ordinary_sign\tordinary_exp\tordinary_sig\tordinary_history\t"
            "history_sig\thistory_fires\tproduct_cut\tcpa_sum0\tcpa_sum1\t"
            "cpa_cin\tcpa_selected\tproduct_bit65\tr1237_fires\t"
            "onehop_factor_delta\trecursive_factor_delta\n"
        )
        for record in records:
            source = record["source"]
            ordinary = record["ordinary"]
            cpa = record["cpa"]
            cpa_fields = (
                (str(cpa["cut"]), f"{cpa['sum0']:x}",
                 f"{cpa['sum1']:x}", str(cpa["cin"]),
                 f"{cpa['selected']:x}", str(cpa["bit65"]))
                if cpa is not None else ("-",) * 6
            )
            target.write("\t".join((
                record["stage"],
                record["producer"],
                rendered_cut(record["producer_cut"]),
                str(source.sign),
                str(source.exponent),
                f"{source.significand:x}",
                str(record["source_history"]),
                rendered_cut(record["add_cut"]),
                str(ordinary.sign),
                str(ordinary.exponent),
                f"{ordinary.significand:x}",
                str(record["ordinary_history"]),
                f"{record['history_value'].significand:x}",
                str(record["history_fires"]),
                *cpa_fields,
                str(record["r1237"]),
                str(record["onehop_delta"]),
                str(record["recursive_delta"]),
            )) + "\n")

        target.write("\n[source-ulp perturbation response]\n")
        target.write("stage\tsource_delta\tadd_result_delta\n")
        for record in records:
            for delta, result_delta in record["variants"]:
                target.write(f"{record['stage']}\t{delta}\t{result_delta}\n")

        target.write("\n[literal FAMUBUS response]\n")
        target.write("stage\tmode\tadd_result_delta\n")
        for record in records:
            for mode, result_delta in record["literal_deltas"].items():
                target.write(f"{record['stage']}\t{mode}\t{result_delta}\n")

    print(f"wrote {args.report} stages={len(records)}", flush=True)


if __name__ == "__main__":
    main()
