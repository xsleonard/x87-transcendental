#!/usr/bin/env python3
"""h1070: put every cached force4-visible leg in one terminal coordinate.

This is a no-capture census.  It merges the h989 union bank, h1068
common-mode adversarial bank, and h1069 cell-map bank; compares the frozen
R95 baseline with the absolute inactive-upper opposite endpoint (force4);
and reconstructs exact R96 terminal features for every visible operand.

The purpose is to test whether the new distance-9 observations continue the
same normalized residue staircase as the earlier distance-7/8 response map.
No hardware command is invoked by this script.
"""

import csv
import os
import re
import subprocess
from collections import Counter, defaultdict


MODES = ("rn", "rd", "ru", "rz")
BASE = os.environ.get("H1070_BASE", "./h1068_base")
CANDIDATE = os.environ.get("H1070_CANDIDATE", "./h1068_candidate")
FORCE4 = os.environ.get("H1070_FORCE4", "./h1068_force4")
OUTPUT = os.environ.get("H1070_OUTPUT", "h1070_force4_cached_census.tsv")
CHUNK = int(os.environ.get("H1070_CHUNK", "40000"))
SOURCES = tuple(filter(None, os.environ.get(
    "H1070_SOURCES",
    "h989_union_legs.tsv,h1068_commonmode_adversarial.tsv,"
    "h1069_inactive_upper_cell_map_run1.tsv").split(",")))
ONE = 1 << 66
WVRE = re.compile(
    r"(mul|lf|rf|f4|mag|left|right)=(\d+):(-?\d+):([0-9a-f]{32})")


def normalize(value):
    return ":".join(value.lower().split())


def run(binary, insn, mode, operands, dump=False):
    if not operands:
        return [], ""
    args = [binary, "--batch", "--f%s-standalone" % insn]
    if mode != "rn":
        args.insert(2, "--rc=" + mode)
    if dump:
        args.append("--dump-internals")
    process = subprocess.run(
        args, input="\n".join(operands) + "\n", capture_output=True,
        text=True, check=True)
    outputs = []
    for line in process.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 3:
            outputs.append("%s:%s" % (fields[1].lower(), fields[2].lower()))
    if len(outputs) != len(operands):
        raise RuntimeError("model output count mismatch")
    return outputs, process.stderr if dump else ""


def parse_tokens(line):
    values = {}
    for token in line.split()[1:]:
        if "=" not in token:
            continue
        name, value = token.split("=", 1)
        try:
            values[name] = int(value, 0)
        except ValueError:
            values[name] = value
    return values


def parse_dumps(text):
    records, current = [], None
    for line in text.splitlines():
        if line.startswith("DI_IN "):
            if current is not None:
                records.append(current)
            fields = line.split()
            current = {"op": fields[1].lower() + " " + fields[2].lower()}
            continue
        if current is None:
            continue
        if line.startswith("DI_TC ") and "low3" not in current:
            current.update(parse_tokens(line))
            for match in WVRE.finditer(line):
                name, sign, exponent, significand = match.groups()
                current[name] = (
                    int(sign), int(exponent), int(significand, 16))
        elif line.startswith("DI_R96TOPCLOSED "):
            current.update({"top_" + name: value
                            for name, value in parse_tokens(line).items()})
    if current is not None:
        records.append(current)
    return records


def qdiscard(first, second):
    product = first * second
    shift = product.bit_length() - 67
    if shift <= 0:
        return 0
    return ((product & ((1 << shift) - 1)) << 66) >> shift


def feature_vector(record):
    needed = (
        "active", "low3", "dist", "rsh", "mul", "f4", "rf", "left",
        "right", "top_sum", "top_retained", "top_theta", "top_s4",
        "top_side", "top_b1", "top_b2", "top_pdown", "top_qpost11",
        "top_edge", "top_use", "top_fire", "top_down")
    if any(name not in record for name in needed):
        return None
    low3 = int(record["low3"])
    square = record["mul"][2]
    fourth_full = square * square
    s4 = fourth_full.bit_length() - 67
    tail4 = fourth_full & ((1 << s4) - 1)
    mreg = low3 * (square - ONE) - tail4
    qright = qdiscard(record["f4"][2], record["rf"][2])
    x5 = mreg - 5 * qright

    left, right = record["left"], record["right"]
    distance = left[1] - right[1]
    if distance <= 0:
        return None
    minuend = left[2] << distance
    subtrahend = right[2]
    magnitude = minuend - subtrahend
    if magnitude <= 0:
        return None
    cut = magnitude.bit_length() - 67
    if cut <= 0:
        return None
    propagate = ~(minuend ^ subtrahend)
    pcut = (propagate >> cut) & 1
    pbelow = 0
    while cut - 1 - pbelow >= 0 \
            and ((propagate >> (cut - 1 - pbelow)) & 1):
        pbelow += 1
    qpost11 = int(record["top_qpost11"])
    dist = int(record["dist"])
    phase = qpost11 + 8 * low3
    edge_base = 2024 + 8 * (dist - 7)
    return {
        "active": int(record["active"]), "low3": low3, "distance": dist,
        "sum": int(record["top_sum"]),
        "retained": int(record["top_retained"]),
        "theta": int(record["top_theta"]),
        "s4": int(record["top_s4"]), "side": int(record["top_side"]),
        "b1": int(record["top_b1"]), "b2": int(record["top_b2"]),
        "pcut": pcut, "pdown": int(record["top_pdown"]),
        "pbelow": pbelow, "qpost11": qpost11,
        "phase": phase, "edge_base": edge_base,
        "edge_offset": phase - edge_base,
        "edge": int(record["top_edge"]),
        "old_use": int(record["top_use"]),
        "old_fire": int(record["top_fire"]),
        "old_down": int(record["top_down"]),
        "m_floor": mreg // ONE, "m128": (128 * mreg) // ONE,
        "m256": (256 * mreg) // ONE, "x5_floor": x5 // ONE,
        "x5_128": (128 * x5) // ONE,
        "qright11": qright >> 55,
        "rf43": (record["rf"][2] >> 43) & 1,
    }


hardware = {}
origins = defaultdict(set)
for path in SOURCES:
    if not os.path.exists(path):
        raise SystemExit("missing source " + path)
    with open(path) as source:
        for row in csv.DictReader(source, delimiter="\t"):
            # h1069 is an FCOS-only map and therefore omits a constant insn
            # column.  Preserve that schema while still merging its fresh
            # controls into this cross-bank cache.
            insn = row.get("insn") or (
                "cos" if path.startswith("h1069_") else None)
            mode = row.get("mode")
            op = row.get("op")
            hw = row.get("hw")
            if not (insn and mode and op and hw):
                continue
            key = insn, mode, op
            value = normalize(hw)
            if key in hardware and hardware[key] != value:
                raise RuntimeError("hardware cache disagreement for %r" % (key,))
            hardware[key] = value
            origins[key].add(path)

print("cached legs", len(hardware), "sources", SOURCES, flush=True)


# Retain every leg where force4 is architecturally distinguishable from the
# frozen R95 baseline.  Hardware labels do not affect this selection.
visible = []
groups = defaultdict(list)
for key in hardware:
    groups[key[0], key[1]].append(key[2])
for (insn, mode), operands in sorted(groups.items()):
    operands = sorted(set(operands))
    for start in range(0, len(operands), CHUNK):
        chunk = operands[start:start + CHUNK]
        baseline = run(BASE, insn, mode, chunk)[0]
        endpoint = run(FORCE4, insn, mode, chunk)[0]
        for op, before, after in zip(chunk, baseline, endpoint):
            if before != after:
                visible.append((insn, mode, op, before, after))
    print("visible", insn, mode,
          sum(1 for row in visible if row[0] == insn and row[1] == mode),
          flush=True)


# Dump each operand once at RN.  Terminal structure is RC-independent.
feature_by_operand = {}
by_insn = defaultdict(set)
for insn, _, op, _, _ in visible:
    by_insn[insn].add(op)
for insn, operand_set in sorted(by_insn.items()):
    operands = sorted(operand_set)
    for start in range(0, len(operands), CHUNK):
        chunk = operands[start:start + CHUNK]
        _, dump = run(CANDIDATE, insn, "rn", chunk, dump=True)
        records = parse_dumps(dump)
        if len(records) != len(chunk):
            raise RuntimeError("dump count mismatch")
        for op, record in zip(chunk, records):
            if record["op"] != op:
                raise RuntimeError("dump operand desynchronization")
            feature = feature_vector(record)
            if feature is not None:
                feature_by_operand[insn, op] = feature
    print("featured", insn,
          sum(1 for key in feature_by_operand if key[0] == insn), flush=True)


feature_columns = (
    "active", "low3", "distance", "sum", "retained", "theta", "s4",
    "side", "b1", "b2", "pcut", "pdown", "pbelow", "qpost11",
    "phase", "edge_base", "edge_offset", "edge", "old_use", "old_fire",
    "old_down", "m_floor", "m128", "m256", "x5_floor", "x5_128",
    "qright11", "rf43")

rows = []
totals = Counter()
for insn, mode, op, before, after in visible:
    feature = feature_by_operand.get((insn, op))
    if feature is None:
        continue
    actual = hardware[insn, mode, op]
    if actual == after and actual != before:
        label = "FORCE4"
    elif actual == before and actual != after:
        label = "BASE"
    else:
        label = "OTHER"
    totals[label] += 1
    rows.append((
        label, insn, mode, op,
        ",".join(sorted(origins[insn, mode, op])), actual, before, after,
        *(str(feature[name]) for name in feature_columns)))

if os.path.exists(OUTPUT):
    raise SystemExit("refusing to overwrite " + OUTPUT)
with open(OUTPUT, "w") as target:
    target.write("label\tinsn\tmode\top\torigins\thw\tbase\tforce4\t"
                 + "\t".join(feature_columns) + "\n")
    for row in rows:
        target.write("\t".join(row) + "\n")

print("labeled legs", len(rows), dict(totals), flush=True)


# The complementary endpoint population relevant to the new miss.
response = []
for row in rows:
    datum = dict(zip(
        ("label", "insn", "mode", "op", "origins", "hw", "base",
         "force4") + feature_columns, row))
    for name in feature_columns:
        datum[name] = int(datum[name])
    if (datum["active"] == 0 and datum["retained"] == 255
            and datum["pcut"] == 1 and datum["pdown"] >= 5):
        response.append(datum)

print("complementary retained-ff response", len(response),
      dict(Counter(row["label"] for row in response)), flush=True)
print("by mode", dict(Counter(
    (row["mode"], row["label"]) for row in response)), flush=True)
print("by distance", dict(Counter(
    (row["distance"], row["label"]) for row in response)), flush=True)

for row in sorted(response, key=lambda item: (
        item["distance"], item["phase"], item["theta"], item["low3"],
        item["mode"], item["op"])):
    print("CELL", row["label"], row["insn"], row["mode"], row["op"],
          "d", row["distance"], "l", row["low3"],
          "q", row["qpost11"], "phase", row["phase"],
          "edgeoff", row["edge_offset"], "theta", row["theta"],
          "s4", row["s4"], "side", row["side"],
          "b", "%d%d" % (row["b1"], row["b2"]),
          "pd", row["pdown"], "m128", row["m128"],
          "x5_128", row["x5_128"])


# Report threshold purity for compact normalized coordinates inside modest
# structural cells.  This does not fit a classifier; it asks whether labels
# occupy disjoint intervals in each physically meaningful scalar.
coordinates = (
    "phase", "edge_offset", "m128", "m256", "x5_128", "qright11")
cell_specs = (
    ("distance",),
    ("distance", "mode"),
    ("distance", "mode", "s4", "side"),
    ("distance", "mode", "s4", "side", "b1", "b2"),
)
for fields in cell_specs:
    for coordinate in coordinates:
        cells = defaultdict(lambda: [[], []])
        for row in response:
            if row["label"] not in ("BASE", "FORCE4"):
                continue
            state = tuple(row[name] for name in fields)
            cells[state][row["label"] == "FORCE4"].append(row[coordinate])
        mixed = 0
        separated = 0
        conflicts = 0
        for negatives, positives in cells.values():
            if not negatives or not positives:
                continue
            mixed += 1
            if max(positives) < min(negatives) or min(positives) > max(negatives):
                separated += 1
            else:
                conflicts += 1
        print("PURITY", ",".join(fields), coordinate,
              "mixed", mixed, "separated", separated,
              "conflicts", conflicts)

print("H1070_DONE", OUTPUT)
