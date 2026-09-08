#!/usr/bin/env python3
"""h1069: silicon-map the fresh inactive-upper complementary endpoint cell.

h1068 found a common-mode R96 miss at

    FCOS RN bffc 94332f6145084ae1

whose exact terminal state has retained=0xff, theta=-1, s4=66, side=0,
P[cut]=1, pdown=6, distance=9, low3=6, and qpost11=2008.  Absolute force4
selects the hardware endpoint there.  This experiment maps that cell and its
neighbors without adding the observed tuple to the model.

Selection is hardware-label blind:

* generate fresh dense and multi-scale neighborhoods around the miss;
* add perturbations around prior force4-visible controls;
* retain only operands where the frozen absolute endpoint is RN-visible;
* dump exact terminal features and take bounded reservoirs by structural
  state and R60-coordinate bin;
* capture each previously unseen selected operand once under every RC mode.

The h1068 hardware file is a cache, not training input.  A row already in that
file (including the anchor miss) is never recaptured.  Output paths are unique
and the script refuses to overwrite them.

Expected files in /root/r84:
  ./h1068_candidate
  ./h1068_force4
  ./h1068_commonmode_adversarial.tsv
  ./h1068_commonmode_adversarial_operands.tsv
"""

import csv
import hashlib
import heapq
import os
import random
import re
import subprocess
from collections import Counter, defaultdict


MODES = ("rn", "rd", "ru", "rz")
CANDIDATE = os.environ.get("H1069_CANDIDATE", "./h1068_candidate")
FORCE4 = os.environ.get("H1069_FORCE4", "./h1068_force4")
CAPTURE_BINARY = os.environ.get(
    "H1069_CAPTURE_BINARY", "/root/x87_capture_x86_64")
CACHE_PATH = os.environ.get(
    "H1069_CACHE", "h1068_commonmode_adversarial.tsv")
CONTROL_PATH = os.environ.get(
    "H1069_CONTROLS", "h1068_commonmode_adversarial_operands.tsv")
OUTPUT = os.environ.get("H1069_OUTPUT", "h1069_inactive_upper_cell_map.tsv")
OPERAND_OUTPUT = os.environ.get(
    "H1069_OPERANDS", "h1069_inactive_upper_cell_operands.tsv")
FEATURE_OUTPUT = os.environ.get(
    "H1069_FEATURES", "h1069_inactive_upper_cell_features.tsv")
SEED = int(os.environ.get("H1069_SEED", "0x1069CE11A9"), 0)
CHUNK = int(os.environ.get("H1069_CHUNK", "40000"))
GENERATION_RESERVOIR = int(os.environ.get("H1069_GEN_RESERVOIR", "256"))
STATE_RESERVOIR = int(os.environ.get("H1069_STATE_RESERVOIR", "3"))
TARGET_LIMIT = int(os.environ.get("H1069_TARGET_LIMIT", "12000"))
ADJACENT_LIMIT = int(os.environ.get("H1069_ADJACENT_LIMIT", "12000"))
DO_CAPTURE = os.environ.get("H1069_CAPTURE", "1") != "0"

ANCHOR_SE = 0xBFFC
ANCHOR_SIG = 0x94332F6145084AE1
ANCHOR = "%04x %016x" % (ANCHOR_SE, ANCHOR_SIG)
ONE = 1 << 66
WVRE = re.compile(
    r"(mul|lf|rf|f4|mag|left|right)=(\d+):(-?\d+):([0-9a-f]{32})")


def run(args, operands, dump=False):
    """Run a batch model/capture and retain one architectural result/row."""
    if not operands:
        return [], ""
    process = subprocess.run(
        args, input="\n".join(operands) + "\n",
        capture_output=True, text=True, check=True)
    output = []
    for line in process.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 3:
            output.append("%s:%s" % (fields[1].lower(), fields[2].lower()))
    if len(output) != len(operands):
        raise RuntimeError(
            "output length mismatch: %d != %d for %r" %
            (len(output), len(operands), args))
    return output, process.stderr if dump else ""


def model(binary, mode, operands, dump=False):
    args = [binary, "--batch", "--fcos-standalone"]
    if mode != "rn":
        args.insert(2, "--rc=" + mode)
    if dump:
        args.append("--dump-internals")
    return run(args, operands, dump=dump)


def capture(mode, operands):
    return run([CAPTURE_BINARY, mode, "cos"], operands)[0]


def stable_score(bucket, operand):
    payload = "%x|%s|%s" % (SEED, bucket, operand)
    return int.from_bytes(
        hashlib.blake2b(payload.encode("ascii"), digest_size=8).digest(),
        "big")


def reservoir_add(reservoirs, bucket, operand, limit):
    score = stable_score(bucket, operand)
    item = (-score, operand)
    heap = reservoirs[bucket]
    if len(heap) < limit:
        heapq.heappush(heap, item)
    elif score < -heap[0][0]:
        heapq.heapreplace(heap, item)


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
    records = []
    current = None
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
        elif line.startswith("DI_TC2 "):
            current.update(parse_tokens(line))
        elif line.startswith("DI_R96TOPCLOSED "):
            current.update({
                "top_" + name: value
                for name, value in parse_tokens(line).items()
            })
    if current is not None:
        records.append(current)
    return records


def qdiscard(first, second):
    product = first * second
    shift = product.bit_length() - 67
    if shift <= 0:
        return 0
    return ((product & ((1 << shift) - 1)) << 66) >> shift


def signed_hex(value):
    return ("-" if value < 0 else "") + format(abs(value), "x")


def feature_vector(record):
    required = (
        "low3", "dist", "rsh", "active", "mul", "rf", "f4",
        "left", "right", "rdisc", "top_sum", "top_retained",
        "top_theta", "top_s4", "top_side", "top_b1", "top_b2",
        "top_pdown", "top_qpost11", "top_edge", "top_use", "top_fire",
        "top_down")
    if any(name not in record for name in required):
        return None

    low3 = int(record["low3"])
    square = record["mul"][2]
    fourth_full = square * square
    s4 = fourth_full.bit_length() - 67
    t4 = fourth_full & ((1 << s4) - 1)
    mreg = low3 * (square - ONE) - t4
    right_factor = record["rf"][2]
    fourth = record["f4"][2]
    qright = qdiscard(fourth, right_factor)
    x5 = mreg - 5 * qright

    left = record["left"]
    right = record["right"]
    dl = left[1] - right[1]
    if dl <= 0:
        return None
    minuend = left[2] << dl
    subtrahend = right[2]
    magnitude = minuend - subtrahend
    if magnitude <= 0:
        return None
    cut = magnitude.bit_length() - 67
    if cut <= 0:
        return None
    residue = magnitude & ((1 << cut) - 1)
    qterminal = (residue << 66) >> cut
    prop = ~(minuend ^ subtrahend)
    pcut = (prop >> cut) & 1
    pbelow = 0
    while cut - 1 - pbelow >= 0 \
            and ((prop >> (cut - 1 - pbelow)) & 1):
        pbelow += 1

    def scaled(value, factor):
        return (factor * value) // ONE

    return {
        "active": int(record["active"]),
        "low3": low3,
        "distance": int(record["dist"]),
        "rsh": int(record["rsh"]),
        "sum": int(record["top_sum"]),
        "retained": int(record["top_retained"]),
        "theta": int(record["top_theta"]),
        "s4": int(record["top_s4"]),
        "side": int(record["top_side"]),
        "b1": int(record["top_b1"]),
        "b2": int(record["top_b2"]),
        "pcut": pcut,
        "pdown": int(record["top_pdown"]),
        "pbelow": pbelow,
        "qpost11": int(record["top_qpost11"]),
        "edge": int(record["top_edge"]),
        "old_use": int(record["top_use"]),
        "old_fire": int(record["top_fire"]),
        "old_down": int(record["top_down"]),
        "m_floor": mreg // ONE,
        "m32": scaled(mreg, 32),
        "m64": scaled(mreg, 64),
        "m128": scaled(mreg, 128),
        "m256": scaled(mreg, 256),
        "m512": scaled(mreg, 512),
        "mreg": signed_hex(mreg),
        "qright": format(qright, "x"),
        "x5_floor": x5 // ONE,
        "x5_128": scaled(x5, 128),
        "x5": signed_hex(x5),
        "qterminal": format(qterminal, "x"),
        "cut": cut,
        "rf43": (right_factor >> 43) & 1,
        "rdisc": str(record["rdisc"]),
    }


def load_cache():
    cache = {}
    if not os.path.exists(CACHE_PATH):
        return cache
    with open(CACHE_PATH) as source:
        for row in csv.DictReader(source, delimiter="\t"):
            if row.get("insn") == "cos":
                cache[row["mode"], row["op"]] = row["hw"].lower()
    return cache


def load_force4_controls():
    controls = []
    if not os.path.exists(CONTROL_PATH):
        return controls
    with open(CONTROL_PATH) as source:
        for row in csv.DictReader(source, delimiter="\t"):
            if row.get("insn") == "cos" and "force4" in row.get(
                    "selection", ""):
                se_text, sig_text = row["op"].split()
                controls.append((int(se_text, 16), int(sig_text, 16)))
    return controls


cache = load_cache()
prior_controls = load_force4_controls()
points = defaultdict(set)


def add_point(se, sig, kind):
    if not (0 <= se <= 0xFFFF and (1 << 63) <= sig < (1 << 64)):
        return
    points[se, sig].add(kind)


# Preserve all immediate neighbors, then stratify the rest of a contiguous
# +/-2^17 scan by distance scale.  This makes local boundary purity testable
# without letting the densest family consume every downstream reservoir.
for delta in range(-(1 << 17), (1 << 17) + 1):
    distance = abs(delta)
    if distance <= 2048:
        kind = "close"
    else:
        kind = "dense_%s_%02d" % (
            "n" if delta < 0 else "p", distance.bit_length())
    add_point(ANCHOR_SE, ANCHOR_SIG + delta, kind)

# Cross a power-of-two input column at every scale that can affect the
# significand, retaining a contiguous +/-2048 halo about each straddle.
for bit in range(18, 53):
    quantum = 1 << bit
    for direction in (-1, 1):
        kind = "scale_%02d_%s" % (bit, "n" if direction < 0 else "p")
        center = ANCHOR_SIG + direction * quantum
        for halo in range(-2048, 2049):
            add_point(ANCHOR_SE, center + halo, kind)

# Prior force4-visible controls provide structural transfer centers.  No old
# operand is privileged: only deterministic column and short-halo transforms
# are generated, and any cached point is excluded from a new hardware call.
for control_index, (se, sig) in enumerate(prior_controls):
    for delta in range(-64, 65):
        if delta:
            add_point(se, sig + delta, "control_halo")
    for bit in range(0, 49):
        add_point(se, sig ^ (1 << bit), "control_xor")
        if bit >= 8:
            add_point(se, (sig ^ (1 << bit)) - 1, "control_xor_halo")
            add_point(se, (sig ^ (1 << bit)) + 1, "control_xor_halo")

# Independent randomized tails break simple proximity to the anchor while
# preserving its high input columns.  These are deterministic and unlabeled.
generator = random.Random(SEED)
for width in (16, 24, 32, 40, 48):
    mask = (1 << width) - 1
    for _ in range(6000):
        add_point(
            ANCHOR_SE,
            (ANCHOR_SIG & ~mask) | generator.getrandbits(width),
            "randomtail_%02d" % width)

# Keep the prior miss as a diagnostic anchor.  Its four hardware values are
# read from the h1068 cache below and are never captured again.
add_point(ANCHOR_SE, ANCHOR_SIG, "anchor_cached")

print("generated", len(points), "prior force4 controls", len(prior_controls),
      "cached hardware legs", len(cache), flush=True)


# Phase 1: absolute endpoint visibility, using only frozen software models.
generation_reservoirs = defaultdict(list)
force_visible = 0
ordered_points = sorted(points)
for start in range(0, len(ordered_points), CHUNK):
    chunk_keys = ordered_points[start:start + CHUNK]
    operands = ["%04x %016x" % key for key in chunk_keys]
    candidate = model(CANDIDATE, "rn", operands)[0]
    forced = model(FORCE4, "rn", operands)[0]
    for key, operand, normal, endpoint in zip(
            chunk_keys, operands, candidate, forced):
        if normal == endpoint:
            continue
        force_visible += 1
        for kind in sorted(points[key]):
            limit = 4097 if kind == "close" else GENERATION_RESERVOIR
            reservoir_add(generation_reservoirs, kind, operand, limit)
    print("visibility", start + len(chunk_keys), "of", len(ordered_points),
          "force-visible", force_visible, flush=True)

dump_reasons = defaultdict(set)
for kind, heap in generation_reservoirs.items():
    for _, operand in heap:
        dump_reasons[operand].add(kind)
dump_reasons[ANCHOR].add("anchor_cached")
dump_operands = sorted(dump_reasons)
print("dump selection", len(dump_operands), "generation reservoirs",
      len(generation_reservoirs), flush=True)


# Phase 2: reconstruct exact terminal/R60 features.  No hardware is queried.
features = {}
candidate_rn = {}
force_rn = {}
for start in range(0, len(dump_operands), CHUNK):
    chunk = dump_operands[start:start + CHUNK]
    normal, dump_text = model(CANDIDATE, "rn", chunk, dump=True)
    endpoint = model(FORCE4, "rn", chunk)[0]
    records = parse_dumps(dump_text)
    if len(records) != len(chunk):
        raise RuntimeError(
            "dump count mismatch: %d != %d" % (len(records), len(chunk)))
    for operand, normal_value, endpoint_value, record in zip(
            chunk, normal, endpoint, records):
        if record["op"] != operand:
            raise RuntimeError("dump operand desynchronization")
        feature = feature_vector(record)
        if feature is not None:
            features[operand] = feature
            candidate_rn[operand] = normal_value
            force_rn[operand] = endpoint_value
    print("feature", start + len(chunk), "of", len(dump_operands),
          "usable", len(features), flush=True)


def is_target(feature):
    return (feature["active"] == 0
            and feature["retained"] == 255
            and feature["theta"] == -1
            and feature["s4"] == 66
            and feature["side"] == 0
            and feature["pcut"] == 1
            and feature["pdown"] >= 5
            and feature["distance"] == 9
            and feature["low3"] == 6
            and feature["qpost11"] == 2008)


def is_adjacent(feature):
    return (feature["active"] == 0
            and feature["retained"] in (254, 255)
            and -4 <= feature["theta"] <= 8
            and feature["s4"] in (66, 67)
            and feature["pcut"] == 1
            and feature["pdown"] >= 4
            and 7 <= feature["distance"] <= 11
            and 1 <= feature["low3"] <= 7
            and 1952 <= feature["qpost11"] <= 2040)


target_heap = []
state_reservoirs = defaultdict(list)
for operand, feature in features.items():
    if candidate_rn[operand] == force_rn[operand]:
        continue
    if is_target(feature):
        reservoir_add({"target": target_heap}, "target", operand, TARGET_LIMIT)
    if not is_adjacent(feature):
        continue
    state = (
        feature["retained"], feature["theta"], feature["s4"],
        feature["side"], feature["distance"], feature["low3"],
        feature["qpost11"], min(feature["pdown"], 8),
        feature["b1"], feature["b2"], feature["m128"] // 16)
    reservoir_add(state_reservoirs, repr(state), operand, STATE_RESERVOIR)

selection = defaultdict(set)
for _, operand in target_heap:
    selection[operand].add("target")
for state, heap in state_reservoirs.items():
    for _, operand in heap:
        selection[operand].add("state:" + state)
selection[ANCHOR].add("anchor_cached")

# Bound the union of adjacent structural reservoirs without favoring labels.
if len(selection) > TARGET_LIMIT + ADJACENT_LIMIT + 1:
    target_operands = {operand for _, operand in target_heap}
    adjacent = [operand for operand in selection if operand not in target_operands
                and operand != ANCHOR]
    adjacent.sort(key=lambda operand: stable_score("adjacent_union", operand))
    keep = target_operands | set(adjacent[:ADJACENT_LIMIT]) | {ANCHOR}
    selection = defaultdict(
        set, {operand: reasons for operand, reasons in selection.items()
              if operand in keep})

selected_operands = sorted(selection)
print("target population", sum(is_target(feature) for feature in features.values()),
      "adjacent states", len(state_reservoirs), "hardware selection",
      len(selected_operands), flush=True)


feature_columns = (
    "active", "low3", "distance", "rsh", "sum", "retained", "theta",
    "s4", "side", "b1", "b2", "pcut", "pdown", "pbelow", "qpost11",
    "edge", "old_use", "old_fire", "old_down", "m_floor", "m32",
    "m64", "m128", "m256", "m512", "mreg", "qright", "x5_floor",
    "x5_128", "x5", "qterminal", "cut", "rf43", "rdisc")

for path in (OPERAND_OUTPUT, FEATURE_OUTPUT, OUTPUT):
    if os.path.exists(path):
        raise SystemExit("refusing to overwrite %s" % path)

with open(OPERAND_OUTPUT, "w") as out:
    out.write("op\tkinds\tdump_selection\thardware_selection\n")
    for operand in dump_operands:
        se_text, sig_text = operand.split()
        kinds = points[int(se_text, 16), int(sig_text, 16)]
        out.write("%s\t%s\t%s\t%s\n" % (
            operand, ",".join(sorted(kinds)),
            ",".join(sorted(dump_reasons[operand])),
            ",".join(sorted(selection.get(operand, ())))) )

with open(FEATURE_OUTPUT, "w") as out:
    out.write("op\t" + "\t".join(feature_columns) + "\n")
    for operand in sorted(features):
        feature = features[operand]
        out.write(operand + "\t" + "\t".join(
            str(feature[name]) for name in feature_columns) + "\n")

if not DO_CAPTURE:
    print("H1069_SELECTION_ONLY", OPERAND_OUTPUT, FEATURE_OUTPUT, flush=True)
    raise SystemExit(0)


# Phase 3: each uncached operand is captured exactly once per RC mode.
software = {}
for mode in MODES:
    for start in range(0, len(selected_operands), CHUNK):
        chunk = selected_operands[start:start + CHUNK]
        software[mode, "candidate", start] = model(
            CANDIDATE, mode, chunk)[0]
        software[mode, "force4", start] = model(FORCE4, mode, chunk)[0]

fresh = [operand for operand in selected_operands
         if any((mode, operand) not in cache for mode in MODES)]
fresh_hw = {}
for mode in MODES:
    need = [operand for operand in fresh if (mode, operand) not in cache]
    for start in range(0, len(need), CHUNK):
        chunk = need[start:start + CHUNK]
        values = capture(mode, chunk)
        for operand, value in zip(chunk, values):
            fresh_hw[mode, operand] = value
    print("capture", mode, len(need), "fresh operands", flush=True)

rows = []
totals = Counter()
for mode in MODES:
    for start in range(0, len(selected_operands), CHUNK):
        chunk = selected_operands[start:start + CHUNK]
        normal = software[mode, "candidate", start]
        endpoint = software[mode, "force4", start]
        for operand, candidate_value, force_value in zip(
                chunk, normal, endpoint):
            actual = cache.get((mode, operand), fresh_hw.get((mode, operand)))
            if actual is None:
                raise RuntimeError("missing hardware value for " + operand)
            if candidate_value == force_value == actual:
                label = "INVISIBLE_OK"
            elif actual == force_value and actual != candidate_value:
                label = "FORCE4"
            elif actual == candidate_value and actual != force_value:
                label = "BASE"
            else:
                label = "OTHER"
            totals[label] += 1
            feature = features[operand]
            rows.append((
                label, mode, operand,
                ",".join(sorted(selection[operand])),
                "cached" if (mode, operand) in cache else "fresh",
                actual, candidate_value, force_value,
                *(str(feature[name]) for name in feature_columns)))

with open(OUTPUT, "w") as out:
    out.write("label\tmode\top\tselection\thw_source\thw\tcandidate\tforce4\t"
              + "\t".join(feature_columns) + "\n")
    for row in rows:
        out.write("\t".join(row) + "\n")

print("H1069_DONE", "generated", len(points), "visible", force_visible,
      "dumped", len(dump_operands), "featured", len(features),
      "selected", len(selected_operands), "fresh", len(fresh),
      "legs", len(rows), dict(totals), "output", OUTPUT, flush=True)
