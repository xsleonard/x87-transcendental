#!/usr/bin/env python3
"""h1071: blind search and single-capture test of the distance-9 phase edge.

h1069 observed force4 at normalized phase offsets 12, 16, and 20, followed
by base-endpoint rows at 24 and 32, in the inactive-upper distance-9,
retained-ff, s4=66, side=0 state.  This experiment seeks independent rows in
that state without using those labels during generation or selection.

Millions of deterministic random FSIN/FCOS operands are streamed through the
frozen R96 candidate and its absolute force4 endpoint.  Only RN-visible
operands are dumped, and only the structural distance-9 band is sent to
hardware.  Prior h1068/h1069 captures are a cache; every unseen operand is
captured exactly once per RC mode.
"""

import csv
import os
import random
import re
import subprocess
from collections import Counter


MODES = ("rn", "rd", "ru", "rz")
INSN = os.environ.get("H1071_INSN", "cos")
if INSN not in ("cos", "sin"):
    raise SystemExit("H1071_INSN must be cos or sin")
CANDIDATE = os.environ.get("H1071_CANDIDATE", "./h1068_candidate")
FORCE4 = os.environ.get("H1071_FORCE4", "./h1068_force4")
CAPTURE_BINARY = os.environ.get(
    "H1071_CAPTURE_BINARY", "/root/x87_capture_x86_64")
SAMPLES = int(os.environ.get("H1071_SAMPLES", "8000000"))
CHUNK = int(os.environ.get("H1071_CHUNK", "50000"))
SEED = int(os.environ.get("H1071_SEED", "0x1071D9B11D"), 0)
LIMIT = int(os.environ.get("H1071_LIMIT", "5000"))
DO_CAPTURE = os.environ.get("H1071_CAPTURE", "1") != "0"
PREFIX_ONLY = os.environ.get("H1071_PREFIX_ONLY", "0") != "0"
BAND_ONLY = os.environ.get("H1071_BAND_ONLY", "0") != "0"
CONTROL_ONLY = os.environ.get("H1071_CONTROL_ONLY", "0") != "0"
CONTROL_PATH = os.environ.get(
    "H1071_CONTROLS", "h1068_commonmode_adversarial_operands.tsv")
FIXED_CONTROL = os.environ.get("H1071_FIXED_CONTROL", "")
OUTPUT = os.environ.get("H1071_OUTPUT", "h1071_distance9_phase_blind.tsv")
FEATURE_OUTPUT = os.environ.get(
    "H1071_FEATURES", "h1071_distance9_phase_features.tsv")
CACHE_PATHS = tuple(filter(None, os.environ.get(
    "H1071_CACHES",
    "h1068_commonmode_adversarial.tsv,"
    "h1069_inactive_upper_cell_map_run1.tsv,"
    "h1071_distance9_phase_blind.tsv").split(",")))
ONE = 1 << 66
ANCHOR = 0x94332F6145084AE1
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
        if len(fields) >= 3:
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
    required = (
        "active", "low3", "dist", "mul", "f4", "rf", "left", "right",
        "top_sum", "top_retained", "top_theta", "top_s4", "top_side",
        "top_b1", "top_b2", "top_pdown", "top_qpost11", "top_edge",
        "top_use", "top_fire", "top_down")
    if any(name not in record for name in required):
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
        "phase": phase, "edge_offset": phase - edge_base,
        "edge": int(record["top_edge"]),
        "old_use": int(record["top_use"]),
        "old_fire": int(record["top_fire"]),
        "old_down": int(record["top_down"]),
        "m128": (128 * mreg) // ONE, "m256": (256 * mreg) // ONE,
        "x5_128": (128 * x5) // ONE, "qright11": qright >> 55,
        "rf43": (record["rf"][2] >> 43) & 1,
    }


def load_cache():
    cache = {}
    for path in CACHE_PATHS:
        if not os.path.exists(path):
            raise SystemExit("missing cache " + path)
        with open(path) as source:
            for row in csv.DictReader(source, delimiter="\t"):
                row_insn = row.get("insn")
                if row_insn and row_insn != INSN:
                    continue
                if not row_insn and INSN != "cos":
                    continue
                if not row.get("mode") or not row.get("op") or not row.get("hw"):
                    continue
                key = row["mode"], row["op"]
                value = ":".join(row["hw"].lower().split())
                if key in cache and cache[key] != value:
                    raise RuntimeError("cache disagreement for %r" % (key,))
                cache[key] = value
    return cache


def load_force4_controls():
    controls = []
    if not os.path.exists(CONTROL_PATH):
        return controls
    with open(CONTROL_PATH) as source:
        for row in csv.DictReader(source, delimiter="\t"):
            if row.get("insn") != INSN or "force4" not in row.get(
                    "selection", ""):
                continue
            se_text, sig_text = row["op"].split()
            controls.append((int(se_text, 16), int(sig_text, 16)))
    return controls


force4_controls = load_force4_controls()
if FIXED_CONTROL:
    fixed_se, fixed_sig = FIXED_CONTROL.split()
    force4_controls = [(int(fixed_se, 16), int(fixed_sig, 16))]


def random_operand(generator, index):
    if CONTROL_ONLY:
        if not force4_controls:
            raise RuntimeError("no force4 controls for " + INSN)
        se, sig = generator.choice(force4_controls)
        width = generator.choice((16, 24, 32, 40, 48))
        sig = (sig & ~((1 << width) - 1)) | generator.getrandbits(width)
        return "%04x %016x" % (se, sig)
    if BAND_ONLY:
        se = 0xBFFC if (index & 1) == 0 else 0x3FFC
        high16 = generator.randrange(0x9000, 0x9500)
        sig = (high16 << 48) | generator.getrandbits(48)
        return "%04x %016x" % (se, sig)
    if PREFIX_ONLY:
        family = index & 3
        se = 0xBFFC if family in (0, 2) else 0x3FFC
        width = 48 if family < 2 else 40
        sig = (ANCHOR & ~((1 << width) - 1)) | generator.getrandbits(width)
        return "%04x %016x" % (se, sig)
    family = index & 7
    if family <= 2:
        se = 0xBFFC
        sig = (1 << 63) | generator.getrandbits(63)
    elif family <= 4:
        se = 0x3FFC
        sig = (1 << 63) | generator.getrandbits(63)
    elif family == 5:
        se = 0xBFFC
        sig = (ANCHOR & ~((1 << 48) - 1)) | generator.getrandbits(48)
    elif family == 6:
        se = 0x3FFC
        sig = (ANCHOR & ~((1 << 40) - 1)) | generator.getrandbits(40)
    else:
        exponent = generator.choice((0x3FFA, 0x3FFB, 0x3FFC, 0x3FFD,
                                     0x3FFE, 0x3FFF, 0x4000, 0x4001))
        se = exponent | (0x8000 if generator.getrandbits(1) else 0)
        sig = (1 << 63) | generator.getrandbits(63)
    return "%04x %016x" % (se, sig)


generator = random.Random(SEED)
visible = set()
processed = 0
while processed < SAMPLES:
    count = min(CHUNK, SAMPLES - processed)
    chunk = [random_operand(generator, processed + offset)
             for offset in range(count)]
    candidate = model(CANDIDATE, "rn", chunk)[0]
    endpoint = model(FORCE4, "rn", chunk)[0]
    for operand, normal, forced in zip(chunk, candidate, endpoint):
        if normal != forced:
            visible.add(operand)
    processed += count
    print("scan", processed, "of", SAMPLES, "visible", len(visible),
          flush=True)

visible_operands = sorted(visible)
features = {}
for start in range(0, len(visible_operands), CHUNK):
    chunk = visible_operands[start:start + CHUNK]
    _, dump = model(CANDIDATE, "rn", chunk, dump=True)
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
    return (feature["active"] == 0
            and feature["retained"] == 255
            and feature["pcut"] == 1
            and feature["pdown"] >= 5
            and feature["distance"] == 9
            and feature["s4"] == 66
            and feature["side"] == 0
            and feature["edge"] == 1
            and -6 <= feature["theta"] <= 4
            and 2032 <= feature["phase"] <= 2088)


def frozen_prediction(feature):
    """Pre-capture h1073 digit-line/R60 hypothesis."""
    low3 = feature["low3"]
    b1 = feature["b1"]
    b2 = feature["b2"]
    m128 = feature["m128"]
    limit = 2044 + 4 * low3
    if low3 == 2 and b1:
        limit += 4
    if low3 == 3 and b2:
        limit += 4
    if low3 == 4 and b2 and m128 <= 132:
        limit += 4
    if low3 == 5 and m128 <= 132:
        limit += 4
    if low3 == 6 and b1:
        limit += 4
    if low3 == 7 and m128 <= 266:
        limit += 4
    return "FORCE4" if feature["phase"] <= limit else "BASE"


selected = sorted(
    (operand for operand, feature in features.items() if target(feature)),
    key=lambda operand: (
        features[operand]["phase"], features[operand]["theta"], operand))
if len(selected) > LIMIT:
    raise RuntimeError("target population %d exceeds limit %d" %
                       (len(selected), LIMIT))

feature_columns = (
    "active", "low3", "distance", "sum", "retained", "theta", "s4",
    "side", "b1", "b2", "pcut", "pdown", "pbelow", "qpost11",
    "phase", "edge_offset", "edge", "old_use", "old_fire", "old_down",
    "m128", "m256", "x5_128", "qright11", "rf43")

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
      "distance9 targets", len(selected), flush=True)
print("target phases", dict(Counter(
    (features[op]["phase"], features[op]["theta"],
     features[op]["low3"]) for op in selected)), flush=True)
if not DO_CAPTURE:
    print("H1071_SELECTION_ONLY", FEATURE_OUTPUT, flush=True)
    raise SystemExit(0)

cache = load_cache()
software = {}
for mode in MODES:
    software[mode, "candidate"] = model(CANDIDATE, mode, selected)[0]
    software[mode, "force4"] = model(FORCE4, mode, selected)[0]

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
prediction_totals = Counter()
for mode in MODES:
    for index, operand in enumerate(selected):
        candidate = software[mode, "candidate"][index]
        force4 = software[mode, "force4"][index]
        hardware = cache.get((mode, operand), fresh_hw.get((mode, operand)))
        if hardware == force4 and hardware != candidate:
            label = "FORCE4"
        elif hardware == candidate and hardware != force4:
            label = "BASE"
        elif hardware == candidate == force4:
            label = "INVISIBLE_OK"
        else:
            label = "OTHER"
        totals[label] += 1
        feature = features[operand]
        if mode == "rn":
            prediction_totals[
                "OK" if frozen_prediction(feature) == label else "MISS"] += 1
        rows.append((
            label, mode, operand,
            "cached" if (mode, operand) in cache else "fresh",
            hardware, candidate, force4,
            *(str(feature[name]) for name in feature_columns)))

with open(OUTPUT, "w") as out:
    out.write("label\tmode\top\thw_source\thw\tcandidate\tforce4\t"
              + "\t".join(feature_columns) + "\n")
    for row in rows:
        out.write("\t".join(row) + "\n")

print("H1071_DONE", "samples", SAMPLES, "visible", len(visible),
      "targets", len(selected), "legs", len(rows), dict(totals), OUTPUT,
      "frozen_prediction", dict(prediction_totals), flush=True)
