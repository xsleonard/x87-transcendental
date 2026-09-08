#!/usr/bin/env python3
"""Score every h1278 gate realizable in one default square-tree schedule.

The local h1278 search reports many exact two-wire gates after conditioning
on one default-orientation threshold predicate.  This pass removes that
conditioning: it evaluates each gate directly as a one-cell R60 threshold
extension on all 174,718 constraining rows in the dense cell.  Only signals
from the patent-default Q/QX tree, its single CSA3 low-digit merge, and the
corresponding redundant comparator are admitted.  Hardware is never run.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import re
from collections import Counter
from pathlib import Path

from h1100_p5_multiplier_tree import TREE_MASK, csa3, multiplier_tree
from h1101_p5_tree_mine import carry_between as tree_carry_between
from h1129_r60_redundant_comparator_mine import (
    MASK, carry_between, merge_low_digit, negate_rows, reduce_balanced,
)
from h1172_p5_cpa_predictor_mine import group_state
from h1257_terminal_two_wire_gates import banked
from h1275_dcc_dense_structural_audit import SCOPE, TARGET


ALLOWED = (
    "known.tree.Q.", "known.tree.QX.",
    "known.cpa.Q.", "known.cpa.QX.",
    "redundant.inner0.mergecsa3.", "redundant.exact.",
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def bit(value: int, position: int) -> int:
    return (value >> position) & 1 if position >= 0 else 0


def literal_name(value: str) -> str:
    return value[1:] if value.startswith("!") else value


def read_gates(path: Path) -> list[tuple[str, str, str]]:
    text = path.read_text()
    section = text.split("[exact two-wire gates]\n", 1)[1]
    rows = csv.DictReader(section.splitlines(), delimiter="\t")
    gates = []
    for row in rows:
        left = row["left"]
        right = row["right"]
        if not (literal_name(left).startswith(ALLOWED)
                and literal_name(right).startswith(ALLOWED)):
            continue
        gates.append((row["gate"], left, right))
    return gates


class Signals:
    def __init__(self, row: dict[str, str]):
        self.row = row
        self.multiplier = int(row["tc_mul_sig"], 16)
        self.low3 = int(row["low3"])
        self.s4 = int(row["s4"])
        self.q = multiplier_tree(self.multiplier, self.multiplier >> 3)
        self.q_cut = (self.multiplier * (self.multiplier >> 3)).bit_length() - 67
        self.qx_sum, self.qx_carry = csa3(
            (self.q["sum"] << 3) & TREE_MASK,
            (self.q["carry"] << 3) & TREE_MASK,
            self.multiplier * self.low3,
        )
        self.qx_cut = (self.multiplier * self.multiplier).bit_length() - 67

        residue_mask = (1 << self.s4) - 1
        square_sum, square_carry = merge_low_digit(
            self.q, self.multiplier, "csa3")
        self.square_vectors = {
            "square_sum": square_sum,
            "square_carry": square_carry,
            "sum_residue": square_sum & residue_mask,
            "carry_residue": square_carry & residue_mask,
        }
        residue_total = (self.square_vectors["sum_residue"]
                         + self.square_vectors["carry_residue"])
        self.overflow = residue_total >> self.s4
        sqlow = self.multiplier - (1 << 66)
        low_product = self.low3 * sqlow
        raw_rows = [low_product]
        raw_rows.extend(negate_rows([
            self.square_vectors["sum_residue"],
            self.square_vectors["carry_residue"],
        ]))
        mod_rows = list(raw_rows)
        if self.overflow:
            mod_rows.append(self.overflow << self.s4)
        self.comparators = {
            "inner0.mergecsa3.raw": reduce_balanced(raw_rows),
            "inner0.mergecsa3.mod": reduce_balanced(mod_rows),
            "exact": reduce_balanced([
                low_product, (-int(row["t4"], 16)) & MASK,
            ]),
        }
        self.cache: dict[str, int] = {}

    def final_signal(self, prefix: str, signal: str, offset: int) -> int:
        if prefix == "Q":
            sum_vector, carry_vector, cut = (
                self.q["sum"], self.q["carry"], self.q_cut)
        else:
            sum_vector, carry_vector, cut = (
                self.qx_sum, self.qx_carry, self.qx_cut)
        position = cut + offset
        a = bit(sum_vector, position)
        b = bit(carry_vector, position)
        if signal == "sum":
            return a
        if signal == "carry":
            return b
        if signal == "propagate":
            return a ^ b
        if signal == "generate":
            return a & b
        if signal == "kill":
            return 1 ^ (a | b)
        if signal == "cin":
            return tree_carry_between(
                sum_vector, carry_vector, 0, position, 0)
        raise KeyError(signal)

    def tree(self, name: str) -> int:
        fields = name.split(".")
        prefix = fields[0]
        if fields[1] == "final":
            if fields[2] == "run_below":
                threshold = int(fields[4])
                if prefix == "Q":
                    vector = self.q["sum"] ^ self.q["carry"]
                    cut = self.q_cut
                else:
                    vector = self.qx_sum ^ self.qx_carry
                    cut = self.qx_cut
                run = 0
                for position in range(cut - 1, -1, -1):
                    if not bit(vector, position):
                        break
                    run += 1
                return int(run >= threshold)
            return self.final_signal(prefix, fields[2], int(fields[3]))
        if fields[1] == "booth":
            digit = self.q["digits"][int(fields[3])]
            return int(
                digit < 0 if fields[2] == "neg"
                else digit == 0 if fields[2] == "zero"
                else abs(digit) == 3)
        node = self.q["nodes"][fields[1]]
        return bit(node[fields[2]], self.q_cut + int(fields[3]))

    def cpa(self, name: str) -> int:
        match = re.fullmatch(
            r"(QX|Q)\.(p5|abs|cut)\.w(04|08|16)\.rel([+-]\d+)\."
            r"(g|p|c0|c1|cin|cout|sum[01]\.b[0-3])", name)
        if match:
            prefix, alignment, width_text, relative_text, signal = match.groups()
            width = int(width_text)
            relative = int(relative_text)
            if prefix == "Q":
                sum_vector, carry_vector, cut = (
                    self.q["sum"], self.q["carry"], self.q_cut)
            else:
                sum_vector, carry_vector, cut = (
                    self.qx_sum, self.qx_carry, self.qx_cut)
            origin = 2 if alignment == "p5" else 0 if alignment == "abs" else cut
            base = origin + ((cut - origin) // width) * width
            start = base + relative * width
            end = start + width
            state = group_state(sum_vector, carry_vector, start, end)
            if signal in ("g", "p", "c0", "c1", "cin", "cout"):
                return state[("g", "p", "c0", "c1", "cin", "cout").index(signal)]
            assumed = int(signal[3])
            wanted = int(signal[-1])
            local = assumed
            for offset, position in enumerate(range(start, end)):
                a = bit(sum_vector, position)
                b = bit(carry_vector, position)
                value = a ^ b ^ local
                if offset == wanted:
                    return value
                local = (a & b) | ((a ^ b) & local)
            raise AssertionError("conditional sum bit outside block")
        match = re.fullmatch(r"(QX|Q)\.p5prefix\.rel([+-]\d+)\.(g|p|c0|c1)", name)
        if match:
            prefix, offset_text, signal = match.groups()
            if prefix == "Q":
                sum_vector, carry_vector, cut = (
                    self.q["sum"], self.q["carry"], self.q_cut)
            else:
                sum_vector, carry_vector, cut = (
                    self.qx_sum, self.qx_carry, self.qx_cut)
            end = cut + int(offset_text) + 1
            state = group_state(sum_vector, carry_vector, 2, end)
            return state[("g", "p", "c0", "c1").index(signal)]
        raise KeyError(name)

    def redundant(self, name: str) -> int:
        if name.startswith("inner0.mergecsa3."):
            prefix, rest = name.rsplit(".", 1) if False else (None, None)
            fields = name.split(".")
            if fields[2] in self.square_vectors:
                return bit(self.square_vectors[fields[2]], int(fields[3][3:]))
            if fields[2] == "overflow":
                return self.overflow & 1
            tag = ".".join(fields[:3])
            suffix = ".".join(fields[3:])
        elif name.startswith("exact."):
            tag = "exact"
            suffix = name[6:]
        else:
            raise KeyError(name)
        sum_vector, carry_vector = self.comparators[tag]
        exact_total = (sum_vector + carry_vector) & MASK
        match = re.fullmatch(
            r"(cpa\.in|sum|carry|prop|gen|value)\.abs(\d+)", suffix)
        if match:
            signal, position_text = match.groups()
            position = int(position_text)
            if signal == "cpa.in":
                return carry_between(sum_vector, carry_vector, 0, position, 0)
            if signal == "sum":
                return bit(sum_vector, position)
            if signal == "carry":
                return bit(carry_vector, position)
            if signal == "prop":
                return bit(sum_vector ^ carry_vector, position)
            if signal == "gen":
                return bit(sum_vector & carry_vector, position)
            return bit(exact_total, position)
        match = re.fullmatch(
            r"(rel(\d+)|abs(\d+))\.end(\d+)\.c([01])\."
            r"(carry|mismatch)", suffix)
        if match:
            _, relative_width, absolute_width, end_text, assumed_text, signal = match.groups()
            end = int(end_text)
            if relative_width is not None:
                start = end - int(relative_width)
            else:
                width = int(absolute_width)
                start = end - (end % width)
            local = carry_between(
                sum_vector, carry_vector, start, end, int(assumed_text))
            if signal == "carry":
                return local
            exact = carry_between(sum_vector, carry_vector, 0, end, 0)
            return local ^ exact
        raise KeyError(name)

    def value(self, full_name: str) -> int:
        if full_name in self.cache:
            return self.cache[full_name]
        if full_name.startswith("known.tree."):
            value = self.tree(full_name[len("known.tree."):])
        elif full_name.startswith("known.cpa."):
            value = self.cpa(full_name[len("known.cpa."):])
        elif full_name.startswith("redundant."):
            value = self.redundant(full_name[len("redundant."):])
        else:
            raise KeyError(full_name)
        self.cache[full_name] = value
        return value

    def literal(self, name: str) -> int:
        value = self.value(literal_name(name))
        return value ^ int(name.startswith("!"))


def gate_value(signals: Signals, gate: str, left: str, right: str) -> int:
    a = signals.literal(left)
    b = signals.literal(right)
    if gate == "and":
        return a & b
    if gate == "or":
        return a | b
    if gate == "xor":
        return a ^ b
    raise KeyError(gate)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("labels", type=Path)
    parser.add_argument("gates", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")
    gates = read_gates(args.gates)
    required = {literal_name(name) for gate in gates for name in gate[1:]}

    if args.verify is not None:
        with args.verify.open(newline="") as source:
            for ordinal, row in enumerate(csv.DictReader(source, delimiter="\t")):
                expected = banked(row)
                actual = Signals(row)
                for name in required:
                    if actual.value(name) != expected[name]:
                        raise RuntimeError(
                            f"feature mismatch row={ordinal} {name}: "
                            f"{actual.value(name)} != {expected[name]}")
                if ordinal == 7:
                    break
        print("verified compact feature evaluator on 8 rows", flush=True)

    with args.labels.open(newline="") as source:
        labels = {(row["corpus"], row["index"]): row
                  for row in csv.DictReader(source, delimiter="\t")}
    counts = [Counter() for _ in gates]
    rows = 0
    with gzip.open(args.features, "rt", newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            if not all(row[name] == value for name, value in SCOPE.items()):
                continue
            label = labels[(row["corpus"], row["index"])]
            if label["selector_status"] != "constraining":
                continue
            rows += 1
            desired = int(label["allowed_carry"])
            current = int(label["current_carry"])
            target = int(row["op"] == TARGET)
            low3 = int(row["low3"])
            base0 = (2 * low3 + 2 * int(row["b1"])
                     + 3 * int(row["b2"]) - 3 * (low3 & 1) - 6)
            u0 = 2 * (base0 // 8) + (low3 & 1)
            mreg = int(row["Mreg"], 16)
            signals = Signals(row)
            for index, (gate, left, right) in enumerate(gates):
                predicate = gate_value(signals, gate, left, right)
                predicted = int(not (
                    mreg < (u0 + predicate) * (1 << 66)))
                changed = predicted != current
                counts[index]["errors"] += predicted != desired
                counts[index]["target_miss"] += target and not changed
                counts[index]["control_fire"] += changed and not target
                counts[index]["fires"] += changed
            if rows % 10000 == 0:
                print(f"features {rows}", flush=True)

    ranking = sorted(
        (counter["errors"], counter["target_miss"],
         counter["control_fire"], counter["fires"], gate, left, right)
        for counter, (gate, left, right) in zip(counts, gates))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"features_sha256\t{digest(args.features)}\n")
        target.write(f"labels_sha256\t{digest(args.labels)}\n")
        target.write(f"gates_sha256\t{digest(args.gates)}\n")
        target.write(f"rows\t{rows}\n")
        target.write(f"consistent_gates\t{len(gates)}\n")
        target.write(f"required_features\t{len(required)}\n")
        target.write("hardware_policy\tcached_labels_only_no_x87_execution\n")
        target.write("\n[ranking]\n")
        target.write(
            "errors\ttarget_miss\tcontrol_fire\tfires\t"
            "gate\tleft\tright\n")
        for score in ranking:
            target.write("\t".join(map(str, score)) + "\n")
    print(
        f"wrote {args.report} rows={rows} gates={len(gates)} "
        f"best={ranking[0]}", flush=True)


if __name__ == "__main__":
    main()
