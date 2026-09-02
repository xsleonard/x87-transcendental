#!/usr/bin/env python3
"""h1068: adversarial R96 bank that can expose common-mode misses.

The h1055 banks selected only operands on which frozen R95 and R96 differed.
That is a strong collateral test, but it cannot expose a row where both models
make the same wrong prediction.  This bank deliberately includes frozen
candidate no-fire controls.  Absolute one-quantum force builds identify
terminal states where an alternative selector endpoint is architecturally
visible; deterministic bounded reservoirs then sample those controls by
generation family, force direction, instruction, and RC mode.

Generation is independent of hardware labels and attacks six structures:

* power-of-two input-column straddles with +/-1, 17, and 257 halos;
* individual bit, adjacent-column, and carry-run mask flips;
* low-tail replacement patterns at 7/8/11/16-bit boundaries;
* same-exponent cross-center splices at byte and selector-window cuts;
* exponent siblings of known selector-visible centers;
* fresh wide offsets and randomized low tails.

Every selected operand is captured on Skylake under RN/RD/RU/RZ.  In
particular, COMMON_MISS means R95 == R96 != hardware and is evidence the old
difference-only blind design was unable to observe.

Expected models (built by h1068_build_models.sh):
  ./h1068_base
  ./h1068_candidate
  ./h1068_force1 ... ./h1068_force10

Run from /root/r84 on the authorized Skylake host.  Set H1068_CAPTURE=0 for a
selection-only dry run.  Output files are append-safe: the script refuses to
replace an existing bank.
"""

import csv
import glob
import hashlib
import heapq
import os
import random
import subprocess
from collections import Counter, defaultdict


MODES = ("rn", "rd", "ru", "rz")
BASE = os.environ.get("H1068_BASE", "./h1068_base")
CANDIDATE = os.environ.get("H1068_CANDIDATE", "./h1068_candidate")
FORCES = tuple(
    os.environ.get("H1068_FORCE%d" % index, "./h1068_force%d" % index)
    for index in range(1, 11)
)
CAPTURE_BINARY = os.environ.get(
    "H1068_CAPTURE_BINARY", "/root/x87_capture_x86_64")
DO_CAPTURE = os.environ.get("H1068_CAPTURE", "1") != "0"
OUTPUT = os.environ.get("H1068_OUTPUT", "h1068_commonmode_adversarial.tsv")
OPERAND_OUTPUT = os.environ.get(
    "H1068_OPERANDS", "h1068_commonmode_adversarial_operands.tsv")
SEED = int(os.environ.get("H1068_SEED", "0x1068C0DE5E1EC7"), 0)
CHUNK = int(os.environ.get("H1068_CHUNK", "50000"))
PER_FORCE_BUCKET = int(os.environ.get("H1068_PER_FORCE_BUCKET", "12"))
PER_GENERIC_BUCKET = int(os.environ.get("H1068_PER_GENERIC_BUCKET", "48"))
WIDE_PER_CENTER = int(os.environ.get("H1068_WIDE_PER_CENTER", "24"))
PAIR_PER_CENTER = int(os.environ.get("H1068_PAIR_PER_CENTER", "24"))


def run(args, operands):
    if not operands:
        return []
    process = subprocess.run(
        args, input="\n".join(operands) + "\n",
        capture_output=True, text=True, check=True)
    output = []
    for line in process.stdout.splitlines():
        fields = line.split()
        # Out-of-range exponent siblings legitimately return a non-OK status
        # while still carrying the two architectural result fields.  Keep
        # those rows: dropping them would desynchronize the deterministic
        # operand/result map and would also hide C2-boundary controls.
        if len(fields) >= 3:
            output.append("%s:%s" % (fields[1].lower(), fields[2].lower()))
    if len(output) != len(operands):
        raise RuntimeError(
            "output length mismatch: %d != %d for %r" %
            (len(output), len(operands), args))
    return output


def model(binary, insn, mode, operands):
    args = [binary, "--batch", "--f%s-standalone" % insn]
    if mode != "rn":
        args.insert(2, "--rc=" + mode)
    return run(args, operands)


def capture(insn, mode, operands):
    return run([CAPTURE_BINARY, mode, insn], operands)


def stable_score(bucket, operand):
    text = "%x|%s|%s" % (SEED, bucket, operand)
    return int.from_bytes(
        hashlib.blake2b(text.encode("ascii"), digest_size=8).digest(), "big")


def reservoir_add(reservoirs, bucket, operand, limit):
    """Keep the deterministically lowest-hash operands in each bucket."""
    score = stable_score(bucket, operand)
    heap = reservoirs[bucket]
    item = (-score, operand)
    if len(heap) < limit:
        heapq.heappush(heap, item)
    elif score < -heap[0][0]:
        heapq.heapreplace(heap, item)


def load_known():
    known = set()
    for path in ["h989_union_legs.tsv"] + sorted(
            glob.glob("h1055_allclosed_*.tsv")):
        if not os.path.exists(path):
            continue
        with open(path) as source:
            for row in csv.DictReader(source, delimiter="\t"):
                if row.get("insn") and row.get("op"):
                    known.add((row["insn"], row["op"]))
    return known


def union_operands():
    with open("h989_union_legs.tsv") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    return {
        insn: sorted({row["op"] for row in rows if row["insn"] == insn})
        for insn in ("cos", "sin")
    }


def changed_centers():
    union = union_operands()
    centers = []
    for insn in ("cos", "sin"):
        operands = union[insn]
        changed = [False] * len(operands)
        for mode in MODES:
            before = model(BASE, insn, mode, operands)
            after = model(CANDIDATE, insn, mode, operands)
            for index, (old, new) in enumerate(zip(before, after)):
                changed[index] |= old != new
        centers.extend(
            (insn, operand) for operand, differs in zip(operands, changed)
            if differs)
    return centers


known = load_known()
centers = changed_centers()
points = {"cos": defaultdict(set), "sin": defaultdict(set)}


def add_point(insn, se, sig, kind):
    if not (0 <= se <= 0xFFFF and (1 << 63) <= sig < (1 << 64)):
        return
    operand = "%04x %016x" % (se, sig)
    if (insn, operand) in known:
        return
    points[insn][operand].add(kind)


generator = random.Random(SEED)
parsed_centers = []
by_insn_se = defaultdict(list)
for center_index, (insn, operand) in enumerate(centers):
    se_text, sig_text = operand.split()
    se = int(se_text, 16)
    sig = int(sig_text, 16)
    parsed_centers.append((center_index, insn, se, sig))
    by_insn_se[insn, se].append(sig)

    # Carry-column straddles: the halo widths deliberately cross low bit,
    # radix-8 digit, byte, and 11-bit selector boundaries.
    for bit in range(15, 49):
        quantum = 1 << bit
        for sign in (-1, 1):
            for halo in (-257, -17, -1, 0, 1, 17, 257):
                add_point(insn, se, sig + sign * quantum + halo,
                          "powedge")

    # Direct column perturbations and their immediate arithmetic neighbors.
    for bit in range(0, 49):
        flipped = sig ^ (1 << bit)
        add_point(insn, se, flipped, "xor1")
        if bit >= 8:
            add_point(insn, se, flipped - 1, "xor1halo")
            add_point(insn, se, flipped + 1, "xor1halo")

    # Consecutive propagate/generate runs at structural widths used by R96.
    for width in (3, 5, 8, 11, 16):
        for shift in (0, 3, 5, 8, 11, 16, 24, 32, 40):
            if shift + width < 63:
                mask = ((1 << width) - 1) << shift
                add_point(insn, se, sig ^ mask, "runmask")

    # Canonical low-tail boundary patterns, preserving all higher columns.
    for width in (7, 8, 11, 16, 24, 32):
        mask = (1 << width) - 1
        patterns = (0, 1, (1 << (width - 1)) - 1,
                    1 << (width - 1), mask - 1, mask)
        for pattern in patterns:
            add_point(insn, se, (sig & ~mask) | pattern, "tailpattern")

    # Hamming-distance-two changes challenge branches that appear pure in
    # one column but may actually read a second discarded product column.
    for _ in range(PAIR_PER_CENTER):
        first = generator.randrange(0, 49)
        second = generator.randrange(0, 48)
        if second >= first:
            second += 1
        add_point(insn, se, sig ^ (1 << first) ^ (1 << second), "xor2")

    # Fresh nonlocal offsets and randomized tails are not centered annuli.
    for _ in range(WIDE_PER_CENTER):
        delta = generator.randrange(-(1 << 52), 1 << 52)
        if abs(delta) <= (1 << 20):
            delta += (1 << 20) if delta >= 0 else -(1 << 20)
        add_point(insn, se, sig + delta, "wide")
        width = generator.choice((24, 32, 40, 48))
        mask = (1 << width) - 1
        add_point(insn, se, (sig & ~mask) | generator.getrandbits(width),
                  "randomtail")

    # Same significand under nearby range-reduction exponents.
    exponent = se & 0x7FFF
    sign = se & 0x8000
    for delta in (-4, -2, -1, 1, 2, 4):
        sibling = exponent + delta
        # The standalone batch driver emits no ordinary output record once
        # the trigonometric instruction takes its |x| >= 2^63 C2 path.  Those
        # encodings do not reach this terminal selector, so keep the bank in
        # the computational range (largest normal exponent below 2^63).
        if 1 <= sibling <= 0x403D:
            add_point(insn, sign | sibling, sig, "expsibling")

# Cross-center splices challenge hidden-tail dependence while retaining large
# blocks from selector-visible states.  Pairing is deterministic and uses no
# hardware label.
for (insn, se), significands in sorted(by_insn_se.items()):
    ordered = sorted(set(significands))
    if len(ordered) < 2:
        continue
    offset = 1 + stable_score("splice", "%s:%04x" % (insn, se)) \
        % (len(ordered) - 1)
    for index, high_source in enumerate(ordered):
        low_source = ordered[(index + offset) % len(ordered)]
        for cut in (8, 11, 16, 24, 32, 40, 48):
            mask = (1 << cut) - 1
            add_point(insn, se,
                      (high_source & ~mask) | (low_source & mask), "splice")

print("centers", len(centers), "generated",
      {insn: len(points[insn]) for insn in ("cos", "sin")}, flush=True)

reservoirs = defaultdict(list)
candidate_changes = set()
generation_counts = Counter()
for insn in ("cos", "sin"):
    operands = sorted(points[insn])
    for start in range(0, len(operands), CHUNK):
        chunk = operands[start:start + CHUNK]
        baseline = {}
        candidate = {}
        for mode in MODES:
            baseline[mode] = model(BASE, insn, mode, chunk)
            candidate[mode] = model(CANDIDATE, insn, mode, chunk)
        differs = [
            any(baseline[mode][index] != candidate[mode][index]
                for mode in MODES)
            for index in range(len(chunk))
        ]

        for index, operand in enumerate(chunk):
            kinds = sorted(points[insn][operand])
            primary = kinds[0]
            generation_counts.update(kinds)
            if differs[index]:
                candidate_changes.add((insn, operand))
            else:
                reservoir_add(
                    reservoirs, "%s|%s|generic" % (insn, primary),
                    operand, PER_GENERIC_BUCKET)

        # Force-visible controls cover output-observable endpoint alternatives
        # even when both R95 and R96 predict the same architectural result.
        for force_index, force_binary in enumerate(FORCES, 1):
            for mode in MODES:
                forced = model(force_binary, insn, mode, chunk)
                for index, operand in enumerate(chunk):
                    if differs[index] or forced[index] == candidate[mode][index]:
                        continue
                    primary = sorted(points[insn][operand])[0]
                    bucket = "%s|%s|force%d|%s" % (
                        insn, primary, force_index, mode)
                    reservoir_add(
                        reservoirs, bucket, operand, PER_FORCE_BUCKET)

        print("filter", insn, start + len(chunk), "of", len(operands),
              "candidate-diff", len(candidate_changes),
              "reservoir buckets", len(reservoirs), flush=True)

selection_reasons = defaultdict(set)
for insn, operand in candidate_changes:
    selection_reasons[insn, operand].add("candidate_diff")
for bucket, heap in reservoirs.items():
    insn = bucket.split("|", 1)[0]
    for _, operand in heap:
        selection_reasons[insn, operand].add(bucket)

if os.path.exists(OPERAND_OUTPUT):
    raise SystemExit("refusing to overwrite %s" % OPERAND_OUTPUT)
with open(OPERAND_OUTPUT, "w") as out:
    out.write("insn\top\tkinds\tselection\n")
    for insn, operand in sorted(selection_reasons):
        out.write("%s\t%s\t%s\t%s\n" % (
            insn, operand, ",".join(sorted(points[insn][operand])),
            ",".join(sorted(selection_reasons[insn, operand]))))

print("selected operands", len(selection_reasons),
      "candidate-diff", len(candidate_changes),
      "generation counts", dict(generation_counts), flush=True)

if not DO_CAPTURE:
    print("H1068_SELECTION_ONLY", OPERAND_OUTPUT)
    raise SystemExit(0)

if os.path.exists(OUTPUT):
    raise SystemExit("refusing to overwrite %s" % OUTPUT)

rows = []
totals = Counter()
for insn in ("cos", "sin"):
    operands = sorted(
        operand for row_insn, operand in selection_reasons
        if row_insn == insn)
    for start in range(0, len(operands), CHUNK):
        chunk = operands[start:start + CHUNK]
        for mode in MODES:
            baseline = model(BASE, insn, mode, chunk)
            candidate = model(CANDIDATE, insn, mode, chunk)
            hardware = capture(insn, mode, chunk)
            for index, operand in enumerate(chunk):
                before = baseline[index]
                after = candidate[index]
                actual = hardware[index]
                if after == actual and before != actual:
                    outcome = "FIX"
                elif after == actual and before == actual:
                    outcome = "COMMON_OK"
                elif before == actual and after != actual:
                    outcome = "BREAK"
                elif before == after and after != actual:
                    outcome = "COMMON_MISS"
                else:
                    outcome = "OTHER"
                totals[outcome] += 1
                rows.append((
                    outcome, insn, mode, operand,
                    ",".join(sorted(points[insn][operand])),
                    ",".join(sorted(selection_reasons[insn, operand])),
                    actual, before, after))
        print("capture", insn, start + len(chunk), "of", len(operands),
              dict(totals), flush=True)

with open(OUTPUT, "w") as out:
    out.write("outcome\tinsn\tmode\top\tkinds\tselection\t"
              "hw\tbase\tcandidate\n")
    for row in rows:
        out.write("\t".join(row) + "\n")

print("H1068_DONE", "generated", sum(map(len, points.values())),
      "selected", len(selection_reasons), "legs", len(rows),
      dict(totals), "output", OUTPUT)
