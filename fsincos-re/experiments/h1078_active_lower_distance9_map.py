#!/usr/bin/env python3
"""Map the active-lower distance-9 selector cell containing c037.

The current ledger key

    FSIN RU c037 fb109f8a9d6453dd

falls through the scoped q67 branch into the ordinary terminal.  Its
G_R96ACTCLOSED state is active/lower, distance 9, low3 4, qpost11 8,
P[cut] 1, but the current support enumeration excludes that digit cell.
Both absolute lower-endpoint probes (force 3 and force 9) reproduce the
banked hardware result.  This program searches new operands around that
reduction seed, selects endpoint-visible neighboring states without reading
hardware labels, and optionally captures each previously unseen operand once
per architectural rounding mode.
"""

import csv
import os
import random
import re
import subprocess
from collections import Counter


MODES = ("rn", "rd", "ru", "rz")
INSN = os.environ.get("H1078_INSN", "sin")
if INSN not in ("sin", "cos"):
    raise SystemExit("H1078_INSN must be sin or cos")
CANDIDATE = os.environ.get("H1078_CANDIDATE", "./model_h1076_noled")
DUMP_CANDIDATE = os.environ.get("H1078_DUMP_CANDIDATE", CANDIDATE)
FORCE3 = os.environ.get("H1078_FORCE3", "./model_force3")
FORCE9 = os.environ.get("H1078_FORCE9", "./model_force9")
CAPTURE_BINARY = os.environ.get(
    "H1078_CAPTURE_BINARY", "/root/x87_capture_x86_64")
SAMPLES = int(os.environ.get("H1078_SAMPLES", "8000000"))
CHUNK = int(os.environ.get("H1078_CHUNK", "50000"))
SEED = int(os.environ.get("H1078_SEED", "0x1078C037D9"), 0)
LIMIT = int(os.environ.get("H1078_LIMIT", "1000"))
DO_CAPTURE = os.environ.get("H1078_CAPTURE", "0") != "0"
BROAD = os.environ.get("H1078_BROAD", "0") != "0"
GENERATION = os.environ.get("H1078_GENERATION", "random")
EXACT_LOW3 = int(os.environ.get("H1078_EXACT_LOW3", "-1"))
EXACT_QPOST11 = int(os.environ.get("H1078_EXACT_QPOST11", "-1"))
OUTPUT = os.environ.get("H1078_OUTPUT", "h1078_active_lower_distance9.tsv")
FEATURE_OUTPUT = os.environ.get(
    "H1078_FEATURES", "h1078_active_lower_distance9_features.tsv")
CACHE_PATHS = tuple(filter(None, os.environ.get(
    "H1078_CACHES", "probe_keys.tsv").split(",")))
ANCHOR_SE = int(os.environ.get("H1078_ANCHOR_SE", "c037"), 16)
ANCHOR_SIG = int(os.environ.get(
    "H1078_ANCHOR_SIG", "fb109f8a9d6453dd"), 16)
ONE = 1 << 66
WVRE = re.compile(
    r"(mul|lf|rf|f4|mag|left|right)=(\d+):(-?\d+):([0-9a-f]{32})")


def run(args, operands, dump=False):
    if not operands:
        return [], ""
    process = subprocess.run(
        args, input="\n".join(operands) + "\n", capture_output=True,
        text=True, check=True)
    outputs = []
    for line in process.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[0] == "OK":
            outputs.append("%s:%s" % (fields[1].lower(), fields[2].lower()))
    if len(outputs) != len(operands):
        raise RuntimeError("output count mismatch for %r" % (args,))
    return outputs, process.stderr if dump else ""


def model(binary, mode, operands, dump=False):
    args = [binary, "--batch", "--f%s-standalone" % INSN]
    if mode != "rn":
        args.insert(2, "--rc=" + mode)
    if dump:
        args.append("--dump-internals")
    return run(args, operands, dump=dump)


def capture(mode, operands):
    return run([CAPTURE_BINARY, mode, INSN], operands)[0]


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
        elif line.startswith("DI_R96ACTCLOSED "):
            current.update({"act_" + name: value
                            for name, value in parse_tokens(line).items()})
    if current is not None:
        records.append(current)
    return records


def feature_vector(record):
    required = (
        "active", "low3", "dist", "mul", "left", "right",
        "act_sum", "act_force_sum", "act_retained", "act_cut",
        "act_qpost11", "act_pcut", "act_mi", "act_s4", "act_side",
        "act_b1", "act_b2", "act_d7", "act_support", "act_fire",
        "act_opposite")
    if any(name not in record for name in required):
        return None
    low3 = int(record["low3"])
    square = record["mul"][2]
    fourth_full = square * square
    s4 = fourth_full.bit_length() - 67
    tail4 = fourth_full & ((1 << s4) - 1)
    mreg = low3 * (square - ONE) - tail4

    left, right = record["left"], record["right"]
    distance = left[1] - right[1]
    payload = int(record.get("payload", 0))
    if distance <= 8:
        return None
    minuend = left[2] << distance
    if payload >= 0:
        minuend += payload << (distance - 8)
    else:
        minuend -= (-payload) << (distance - 8)
    subtrahend = right[2]
    magnitude = minuend - subtrahend
    if magnitude <= 0:
        return None
    cut = magnitude.bit_length() - 67
    propagate = ~(minuend ^ subtrahend)
    pbelow = 0
    while cut - 1 - pbelow >= 0 \
            and ((propagate >> (cut - 1 - pbelow)) & 1):
        pbelow += 1
    qpost11 = int(record["act_qpost11"])
    return {
        "active": int(record["active"]), "low3": low3,
        "distance": int(record["dist"]),
        "sum": int(record["act_sum"]),
        "force_sum": int(record["act_force_sum"]),
        "retained": int(record["act_retained"]),
        "cut": int(record["act_cut"]),
        "qpost11": qpost11, "phase4": qpost11 + 4 * low3,
        "phase8": qpost11 + 8 * low3,
        "pcut": int(record["act_pcut"]), "pbelow": pbelow,
        "mi": int(record["act_mi"]),
        "m16": (16 * mreg) // ONE,
        "m128": (128 * mreg) // ONE,
        "s4": int(record["act_s4"]),
        "side": int(record["act_side"]),
        "b1": int(record["act_b1"]), "b2": int(record["act_b2"]),
        "d7": int(record["act_d7"]),
        "support": int(record["act_support"]),
        "fire": int(record["act_fire"]),
        "opposite": int(record["act_opposite"]),
    }


def random_operand(generator, index):
    if GENERATION == "dense":
        step = index // 2 + 1
        sig = ANCHOR_SIG + (step if index & 1 else -step)
        if not (1 << 63) <= sig < (1 << 64):
            raise RuntimeError("dense operand left the normal range")
        return "%04x %016x" % (ANCHOR_SE, sig)
    if GENERATION == "bitflip":
        widths = (12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 56, 63)
        width = widths[index % len(widths)]
        count = 1 + ((index // len(widths)) % 6)
        bits = generator.sample(range(width), count)
        sig = ANCHOR_SIG
        for bit in bits:
            sig ^= 1 << bit
        return "%04x %016x" % (ANCHOR_SE, sig)
    if GENERATION != "random":
        raise ValueError("unknown H1078_GENERATION " + GENERATION)
    widths = (12, 16, 20, 24, 28, 32, 36, 40, 44, 48)
    width = widths[index % len(widths)]
    sig = ((ANCHOR_SIG & ~((1 << width) - 1))
           | generator.getrandbits(width))
    return "%04x %016x" % (ANCHOR_SE, sig)


def load_cache():
    cache = {}
    for path in CACHE_PATHS:
        if not os.path.exists(path):
            raise SystemExit("missing cache " + path)
        with open(path) as source:
            for fields in csv.reader(source, delimiter="\t"):
                if len(fields) == 6:
                    insn, mode, se, sig, hse, hsig = fields
                    if insn == INSN:
                        cache[mode, "%s %s" % (se, sig)] = \
                            "%s:%s" % (hse.lower(), hsig.lower())
                    continue
                # Also accept ordinary capture-bank TSVs with headers.
                break
        if fields and len(fields) != 6:
            with open(path) as source:
                for row in csv.DictReader(source, delimiter="\t"):
                    if row.get("insn") not in (None, "", INSN):
                        continue
                    if row.get("mode") and row.get("op") and row.get("hw"):
                        cache[row["mode"], row["op"]] = \
                            ":".join(row["hw"].lower().split())
    return cache


generator = random.Random(SEED)
visible = set()
processed = 0
while processed < SAMPLES:
    count = min(CHUNK, SAMPLES - processed)
    chunk = [random_operand(generator, processed + offset)
             for offset in range(count)]
    baseline = model(CANDIDATE, "ru", chunk)[0]
    force3 = model(FORCE3, "ru", chunk)[0]
    force9 = model(FORCE9, "ru", chunk)[0]
    for operand, normal, f3, f9 in zip(chunk, baseline, force3, force9):
        if normal != f3 or normal != f9:
            visible.add(operand)
    processed += count
    print("scan", processed, "of", SAMPLES, "visible", len(visible),
          flush=True)

visible_operands = sorted(visible)
features = {}
for start in range(0, len(visible_operands), CHUNK):
    chunk = visible_operands[start:start + CHUNK]
    _, dump = model(DUMP_CANDIDATE, "ru", chunk, dump=True)
    records = parse_dumps(dump)
    if len(records) != len(chunk):
        raise RuntimeError("dump count mismatch")
    for operand, record in zip(chunk, records):
        if operand != record["op"]:
            raise RuntimeError("dump operand desynchronization")
        feature = feature_vector(record)
        if feature is not None:
            features[operand] = feature


def target(feature):
    if EXACT_LOW3 >= 0 or EXACT_QPOST11 >= 0:
        return (feature["active"] == 1
                and feature["force_sum"] < 128
                and feature["distance"] == 9
                and (EXACT_LOW3 < 0
                     or feature["low3"] == EXACT_LOW3)
                and (EXACT_QPOST11 < 0
                     or feature["qpost11"] == EXACT_QPOST11))
    if BROAD:
        return (feature["active"] == 1
                and feature["force_sum"] < 128
                and feature["qpost11"] <= 64)
    return (feature["active"] == 1
            and feature["force_sum"] < 128
            and feature["distance"] == 9
            and 2 <= feature["low3"] <= 6
            and feature["s4"] == 67
            and feature["side"] == 1
            and feature["qpost11"] <= 32)


selected = sorted(
    (operand for operand, feature in features.items() if target(feature)),
    key=lambda operand: (
        features[operand]["low3"], features[operand]["qpost11"],
        features[operand]["m128"], operand))
anchor = "%04x %016x" % (ANCHOR_SE, ANCHOR_SIG)
if anchor not in selected:
    _, dump = model(DUMP_CANDIDATE, "ru", [anchor], dump=True)
    feature = feature_vector(parse_dumps(dump)[0])
    if feature is not None and target(feature):
        features[anchor] = feature
        selected.append(anchor)
if len(selected) > LIMIT:
    # Preserve coverage across structural state rather than taking the first
    # LIMIT operands from one dense residue run.
    cells = {}
    for operand in selected:
        feature = features[operand]
        key = (feature["low3"], feature["qpost11"], feature["pcut"],
               feature["pbelow"], feature["b1"], feature["b2"],
               feature["m16"])
        cells.setdefault(key, operand)
    selected = sorted(cells.values(), key=lambda operand: (
        features[operand]["low3"], features[operand]["qpost11"],
        features[operand]["m128"], operand))
if len(selected) > LIMIT:
    raise RuntimeError("target population %d exceeds limit %d" %
                       (len(selected), LIMIT))

feature_columns = (
    "active", "low3", "distance", "sum", "force_sum", "retained",
    "cut", "qpost11", "phase4", "phase8", "pcut", "pbelow", "mi",
    "m16", "m128", "s4", "side", "b1", "b2", "d7", "support",
    "fire", "opposite")
for path in (FEATURE_OUTPUT, OUTPUT):
    if os.path.exists(path):
        raise SystemExit("refusing to overwrite " + path)
with open(FEATURE_OUTPUT, "w") as out:
    out.write("op\t" + "\t".join(feature_columns) + "\n")
    for operand in selected:
        feature = features[operand]
        out.write(operand + "\t" + "\t".join(
            str(feature[name]) for name in feature_columns) + "\n")

print("scan done", "visible", len(visible), "featured", len(features),
      "targets", len(selected), flush=True)
print("target cells", dict(Counter(
    (features[op]["low3"], features[op]["qpost11"],
     features[op]["pcut"], features[op]["support"])
    for op in selected)), flush=True)
if not DO_CAPTURE:
    print("H1078_SELECTION_ONLY", FEATURE_OUTPUT, flush=True)
    raise SystemExit(0)

cache = load_cache()
software = {}
for mode in MODES:
    software[mode, "base"] = model(CANDIDATE, mode, selected)[0]
    software[mode, "force3"] = model(FORCE3, mode, selected)[0]
    software[mode, "force9"] = model(FORCE9, mode, selected)[0]

fresh_hw = {}
for mode in MODES:
    need = [operand for operand in selected if (mode, operand) not in cache]
    for start in range(0, len(need), CHUNK):
        chunk = need[start:start + CHUNK]
        values = capture(mode, chunk)
        for operand, value in zip(chunk, values):
            fresh_hw[mode, operand] = value
    print("capture", mode, len(need), "fresh operands", flush=True)

rows = []
totals = Counter()
for mode in MODES:
    for index, operand in enumerate(selected):
        base = software[mode, "base"][index]
        force3 = software[mode, "force3"][index]
        force9 = software[mode, "force9"][index]
        hardware = cache.get((mode, operand), fresh_hw.get((mode, operand)))
        matches = []
        if hardware == base:
            matches.append("BASE")
        if hardware == force3:
            matches.append("F3")
        if hardware == force9:
            matches.append("F9")
        label = ",".join(matches) if matches else "OTHER"
        totals[label] += 1
        feature = features[operand]
        rows.append((
            label, mode, operand,
            "cached" if (mode, operand) in cache else "fresh",
            hardware, base, force3, force9,
            *(str(feature[name]) for name in feature_columns)))

with open(OUTPUT, "w") as out:
    out.write("label\tmode\top\thw_source\thw\tbase\tforce3\tforce9\t"
              + "\t".join(feature_columns) + "\n")
    for row in rows:
        out.write("\t".join(row) + "\n")
print("RESULTS", dict(totals), OUTPUT, flush=True)
