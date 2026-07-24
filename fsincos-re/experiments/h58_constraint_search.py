#!/usr/bin/env python3
"""Constraint search for the remaining Pentium-lineage FSINCOS table tail.

The three directed-rounding captures constrain the hidden pre-final value:
a candidate micro-operation schedule must round to the captured RN, RD, and
RU results from one RC-independent internal value.  This script searches
plausible 64..69-bit round/chop placements in the sine-of-a and cosine-tail
chains, first on every baseline-disagreement point plus a deterministic
control sample, then verifies the best schedules on the full direct table
region.

The first stage varies the table-tail graph.  A coordinate beam then varies
the upstream a^2, coefficient-storage, and Horner rounding independently,
and the finalists are crossed and verified against the full capture.
"""

from __future__ import annotations

import argparse
import dataclasses
import itertools
import pathlib
from collections import Counter


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_CAPTURE = ROOT / "capture-kit-captures" / "pentiumII"
INPUTS = ROOT / "capture-kit" / "inputs" / "dense_qn.txt"
ROM_TSV = ROOT / "data" / "pentium-rom" / "rom-constants.tsv"

FP = tuple[int, int, int]  # sign, positive integer significand, binary scale
ZERO: FP = (0, 0, 0)
ONE: FP = (0, 1, 0)

SIN_ROW = {18: 181, 22: 182, 26: 183, 30: 184,
           36: 177, 44: 178, 52: 179, 60: 180}
COS_ROW = {18: 189, 22: 190, 26: 191, 30: 192,
           36: 185, 44: 186, 52: 187, 60: 188}
S4 = (172, 171, 170, 169)
C4 = (176, 175, 174, 173)
S6 = (162, 161, 160, 159, 158, 157)
C6 = (168, 167, 166, 165, 164, 163)
RCS = ("rn", "rd", "ru")


def load_rom() -> dict[int, FP]:
    rom: dict[int, FP] = {}
    with ROM_TSV.open() as f:
        for line in f:
            fields = line.rstrip("\n").split("\t")
            if fields[0] == "row":
                continue
            row = int(fields[0])
            exponent_field = int(fields[1], 16)
            sign = int(fields[2])
            significand = int(fields[4], 16)
            rom[row] = (sign, significand, (exponent_field - 0xFFFD) - 68)
    # Published-table transcription errors; see notes/rom-errata.md.
    sign, significand, scale = rom[186]
    rom[186] = (sign, significand - (1 << 43), scale)
    sign, significand, scale = rom[189]
    rom[189] = (sign, significand - (1 << 12), scale)
    return rom


ROM = load_rom()


def neg(v: FP) -> FP:
    return (v[0] ^ 1, v[1], v[2]) if v[1] else v


def mul_exact(a: FP, b: FP) -> FP:
    if not a[1] or not b[1]:
        return ZERO
    return a[0] ^ b[0], a[1] * b[1], a[2] + b[2]


def add_exact(a: FP, b: FP) -> FP:
    if not a[1]:
        return b
    if not b[1]:
        return a
    scale = min(a[2], b[2])
    av = (-1 if a[0] else 1) * (a[1] << (a[2] - scale))
    bv = (-1 if b[0] else 1) * (b[1] << (b[2] - scale))
    value = av + bv
    if not value:
        return ZERO
    return int(value < 0), abs(value), scale


def round_fp(v: FP, bits: int, mode: str) -> FP:
    """Round to significant bits; mode is rn, chop, or away from zero."""
    sign, significand, scale = v
    if not significand:
        return v
    shift = significand.bit_length() - bits
    if shift <= 0:
        return v
    top = significand >> shift
    remainder = significand & ((1 << shift) - 1)
    increment = False
    if mode == "rn":
        half = 1 << (shift - 1)
        increment = remainder > half or (remainder == half and bool(top & 1))
    elif mode == "away":
        increment = bool(remainder)
    elif mode != "chop":
        raise ValueError(mode)
    if increment:
        top += 1
        if top.bit_length() > bits:
            top >>= 1
            shift += 1
    return sign, top, scale + shift


def fmul(a: FP, b: FP, bits: int, mode: str) -> FP:
    return round_fp(mul_exact(a, b), bits, mode)


def fadd(a: FP, b: FP, bits: int, mode: str) -> FP:
    return round_fp(add_exact(a, b), bits, mode)


def ffma(a: FP, b: FP, c: FP, bits: int, mode: str) -> FP:
    return round_fp(add_exact(mul_exact(a, b), c), bits, mode)


def x87_round(v: FP, rc: str) -> tuple[int, int]:
    if not v[1]:
        return (v[0] << 15), 0
    if rc == "rn":
        mode = "rn"
    elif rc == "rd":
        mode = "away" if v[0] else "chop"
    elif rc == "ru":
        mode = "chop" if v[0] else "away"
    else:
        raise ValueError(rc)
    sign, significand, scale = round_fp(v, 64, mode)
    width = significand.bit_length()
    exponent = scale + width - 1
    significand <<= 64 - width
    return (sign << 15) | (exponent + 16383), significand


def cell_for(xsig: int, exponent: int) -> int:
    # Exact comparisons on x = xsig * 2^(exponent-63).
    if exponent == -2:
        # Four 4/64-wide cells over [1/4, 1/2).
        lane = ((xsig - (1 << 63)) * 4) >> 63
        return 18 + 4 * lane
    # Three 8/64-wide cells over [1/2, pi/4).
    lane = ((xsig - (1 << 63)) * 8) >> 64
    return 36 + 8 * min(2, lane)


def is_direct_table(se: int, sig: int) -> bool:
    exponent = (se & 0x7FFF) - 16383
    if exponent == -2:
        return True
    return exponent == -1 and sig < 0xC90FDAA22168C234


def parse_sincos(line: str) -> tuple[tuple[int, int], tuple[int, int]]:
    fields = line.split()
    if fields[0] != "OK" or len(fields) != 5:
        raise ValueError(line)
    return ((int(fields[1], 16), int(fields[2], 16)),
            (int(fields[3], 16), int(fields[4], 16)))


@dataclasses.dataclass(frozen=True)
class RawPoint:
    index: int
    sign: int
    exponent: int
    sig: int
    hw: tuple[
        tuple[tuple[int, int], tuple[int, int]],
        tuple[tuple[int, int], tuple[int, int]],
        tuple[tuple[int, int], tuple[int, int]],
    ]


@dataclasses.dataclass(frozen=True)
class PreparedPoint:
    raw: RawPoint
    cell: int
    wide: bool
    a: FP
    asq: FP
    p: FP
    q: FP
    sin_t: FP
    cos_t: FP


def load_points(capture: pathlib.Path) -> list[RawPoint]:
    paths = [capture / f"dense_{rc}.txt" for rc in RCS]
    for path in (INPUTS, *paths):
        if not path.exists():
            raise SystemExit(f"missing required input: {path}")
    input_lines = INPUTS.read_text().splitlines()
    outputs = [path.read_text().splitlines() for path in paths]
    if any(len(lines) != len(input_lines) for lines in outputs):
        raise SystemExit("input/capture line counts differ")
    points: list[RawPoint] = []
    for index, input_line in enumerate(input_lines):
        se_text, sig_text = input_line.split()
        se, sig = int(se_text, 16), int(sig_text, 16)
        if not is_direct_table(se, sig):
            continue
        points.append(
            RawPoint(
                index=index,
                sign=se >> 15,
                exponent=(se & 0x7FFF) - 16383,
                sig=sig,
                hw=tuple(parse_sincos(lines[index]) for lines in outputs),
            )
        )
    return points


@dataclasses.dataclass(frozen=True)
class ProducerConfig:
    asq_bits: int = 64
    asq_mode: str = "rn"
    coeff_bits: int = 67
    coeff_mode: str = "rn"
    horner_form: str = "separate"
    horner_bits: int = 64
    horner_mode: str = "rn"

    def short(self) -> str:
        return (
            f"sq{self.asq_bits}{self.asq_mode[0]}"
            f"/c{self.coeff_bits}{self.coeff_mode[0]}"
            f"/h{self.horner_form[0]}{self.horner_bits}{self.horner_mode[0]}"
        )


BASE_PRODUCER = ProducerConfig()
CANDIDATE_PRODUCER = ProducerConfig(
    asq_bits=65,
    asq_mode="chop",
    coeff_bits=66,
    coeff_mode="chop",
    horner_form="separate",
    horner_bits=66,
    horner_mode="chop",
)


def coefficient(row: int, cfg: ProducerConfig) -> FP:
    return round_fp(ROM[row], cfg.coeff_bits, cfg.coeff_mode)


def horner(rows: tuple[int, ...], asq: FP, cfg: ProducerConfig) -> FP:
    value = coefficient(rows[0], cfg)
    for row in rows[1:]:
        constant = coefficient(row, cfg)
        if cfg.horner_form == "fused":
            value = ffma(
                value, asq, constant, cfg.horner_bits, cfg.horner_mode
            )
        else:
            value = fadd(
                fmul(value, asq, cfg.horner_bits, cfg.horner_mode),
                constant,
                cfg.horner_bits,
                cfg.horner_mode,
            )
    return value


def prepare(
    point: RawPoint, cfg: ProducerConfig = BASE_PRODUCER
) -> PreparedPoint:
    cell = cell_for(point.sig, point.exponent)
    wide = cell >= 36
    magnitude: FP = (0, point.sig, point.exponent - 63)
    center: FP = (1, cell, -6)
    a = add_exact(magnitude, center)
    asq = fmul(a, a, cfg.asq_bits, cfg.asq_mode)
    p = horner(S6 if wide else S4, asq, cfg)
    q = horner(C6 if wide else C4, asq, cfg)
    return PreparedPoint(
        raw=point,
        cell=cell,
        wide=wide,
        a=a,
        asq=asq,
        p=p,
        q=q,
        sin_t=ROM[SIN_ROW[cell]],
        cos_t=ROM[COS_ROW[cell]],
    )


@dataclasses.dataclass(frozen=True)
class TailConfig:
    topology: str = "direct"
    m_bits: int = 64
    m_mode: str = "rn"
    mid_bits: int = 64
    mid_mode: str = "rn"
    s_bits: int = 64
    s_mode: str = "rn"
    t_bits: int = 64
    t_mode: str = "rn"

    def short(self) -> str:
        return (
            f"{self.topology}:m{self.m_bits}{self.m_mode[0]}"
            f"/i{self.mid_bits}{self.mid_mode[0]}"
            f"/S{self.s_bits}{self.s_mode[0]}"
            f"/t{self.t_bits}{self.t_mode[0]}"
        )


BASE = TailConfig()
NEAR_TAIL = TailConfig(
    topology="factored",
    m_bits=67,
    m_mode="rn",
    mid_bits=69,
    mid_mode="chop",
    s_bits=64,
    s_mode="rn",
    t_bits=65,
    t_mode="chop",
)
NARROW_TAIL = TailConfig(
    topology="factored",
    m_bits=69,
    m_mode="rn",
    mid_bits=68,
    mid_mode="chop",
    s_bits=64,
    s_mode="rn",
    t_bits=66,
    t_mode="chop",
)
WIDE_TAIL = TailConfig(t_bits=64, t_mode="chop")


def table_tail(point: PreparedPoint, cfg: TailConfig) -> tuple[FP, FP]:
    m = fmul(point.p, point.asq, cfg.m_bits, cfg.m_mode)
    if cfg.topology == "direct":
        correction = fmul(m, point.a, cfg.mid_bits, cfg.mid_mode)
        sine_a = fadd(point.a, correction, cfg.s_bits, cfg.s_mode)
    elif cfg.topology == "factored":
        one_plus_m = fadd(ONE, m, cfg.mid_bits, cfg.mid_mode)
        sine_a = fmul(point.a, one_plus_m, cfg.s_bits, cfg.s_mode)
    elif cfg.topology == "fma":
        sine_a = ffma(m, point.a, point.a, cfg.s_bits, cfg.s_mode)
    elif cfg.topology == "full-fma":
        product = mul_exact(mul_exact(point.p, point.asq), point.a)
        sine_a = round_fp(add_exact(point.a, product), cfg.s_bits, cfg.s_mode)
    else:
        raise ValueError(cfg.topology)
    cosine_tail = fmul(point.q, point.asq, cfg.t_bits, cfg.t_mode)
    one_plus_t = add_exact(ONE, cosine_tail)
    sine = add_exact(
        mul_exact(point.sin_t, one_plus_t),
        mul_exact(point.cos_t, sine_a),
    )
    cosine = add_exact(
        mul_exact(point.cos_t, one_plus_t),
        neg(mul_exact(point.sin_t, sine_a)),
    )
    if point.raw.sign:
        sine = neg(sine)
    return sine, cosine


@dataclasses.dataclass
class Score:
    mode_misses: float = 0
    constrained_output_misses: float = 0
    rn_misses: float = 0
    total_outputs: float = 0
    by_region: Counter[tuple[str, str]] = dataclasses.field(default_factory=Counter)

    def rank(self) -> tuple[float, float, float]:
        return self.mode_misses, self.constrained_output_misses, self.rn_misses

    def describe(self) -> str:
        return (
            f"mode-miss={self.mode_misses:.0f}/{3 * self.total_outputs:.0f} "
            f"output-miss={self.constrained_output_misses:.0f}/{self.total_outputs:.0f} "
            f"RN-miss={self.rn_misses:.0f}/{self.total_outputs:.0f}"
        )


def score_config(
    points: list[PreparedPoint],
    cfg: TailConfig,
    weights: dict[int, float] | None = None,
) -> Score:
    score = Score()
    for point in points:
        weight = weights.get(point.raw.index, 1.0) if weights else 1.0
        score.total_outputs += 2 * weight
        results = table_tail(point, cfg)
        region = "wide" if point.wide else "narrow"
        for side, value in enumerate(results):
            misses = 0
            for rc_index, rc in enumerate(RCS):
                mismatch = x87_round(value, rc) != point.raw.hw[rc_index][side]
                misses += mismatch
                score.mode_misses += mismatch * weight
                score.by_region[(region, f"{'sc'[side]}-{rc}")] += mismatch * weight
                if rc == "rn":
                    score.rn_misses += mismatch * weight
            if misses:
                score.constrained_output_misses += weight
    return score


def search_points(
    points: list[PreparedPoint], control_count: int
) -> tuple[list[PreparedPoint], dict[int, float]]:
    active: list[PreparedPoint] = []
    exact_groups: dict[tuple[int, int], list[PreparedPoint]] = {}
    for point in points:
        score = score_config([point], BASE)
        if score.constrained_output_misses:
            active.append(point)
        else:
            exact_groups.setdefault((point.cell, point.raw.sign), []).append(point)
    controls: list[PreparedPoint] = []
    weights: dict[int, float] = {point.raw.index: 1.0 for point in active}
    quota = max(1, control_count // len(exact_groups))
    for key in sorted(exact_groups):
        group = exact_groups[key]
        count = min(quota, len(group))
        chosen = [group[(i * len(group)) // count] for i in range(count)]
        weight = len(group) / count
        controls.extend(chosen)
        for point in chosen:
            weights[point.raw.index] = weight
    print(f"search set: {len(active)} baseline-constrained + "
          f"{len(controls)} stratified exact controls "
          f"(weighted to {sum(weights.values()):.0f} inputs)")
    return active + controls, weights


def precision_modes() -> list[tuple[int, str]]:
    return [(bits, mode) for bits in range(64, 70) for mode in ("rn", "chop")]


def search_tail(
    points: list[PreparedPoint],
    weights: dict[int, float],
    keep: int,
) -> list[TailConfig]:
    pm = precision_modes()
    candidates: list[TailConfig] = []
    for topology in ("direct", "factored"):
        for m, mid, s in itertools.product(pm, repeat=3):
            candidates.append(
                TailConfig(
                    topology=topology,
                    m_bits=m[0], m_mode=m[1],
                    mid_bits=mid[0], mid_mode=mid[1],
                    s_bits=s[0], s_mode=s[1],
                )
            )
    for topology in ("fma",):
        for m, s in itertools.product(pm, repeat=2):
            candidates.append(
                TailConfig(
                    topology=topology,
                    m_bits=m[0], m_mode=m[1],
                    s_bits=s[0], s_mode=s[1],
                )
            )
    for s in pm:
        candidates.append(
            TailConfig(topology="full-fma", s_bits=s[0], s_mode=s[1])
        )
    ranked: list[tuple[tuple[int, int, int], TailConfig, Score]] = []
    for index, cfg in enumerate(candidates, 1):
        score = score_config(points, cfg, weights)
        ranked.append((score.rank(), cfg, score))
        if index % 500 == 0:
            print(f"  searched {index}/{len(candidates)} S schedules")
    ranked.sort(key=lambda row: (row[0], row[1].short()))
    print("best S-chain schedules (t fixed at baseline):")
    for _, cfg, score in ranked[:keep]:
        print(f"  {cfg.short():46s} {score.describe()}")
    return [cfg for _, cfg, _ in ranked[:keep]]


def search_t(
    points: list[PreparedPoint],
    weights: dict[int, float],
    keep: int,
) -> list[TailConfig]:
    ranked = []
    for bits, mode in precision_modes():
        cfg = dataclasses.replace(BASE, t_bits=bits, t_mode=mode)
        score = score_config(points, cfg, weights)
        ranked.append((score.rank(), cfg, score))
    ranked.sort(key=lambda row: (row[0], row[1].short()))
    print("best t schedules (S fixed at baseline):")
    for _, cfg, score in ranked[:keep]:
        print(f"  {cfg.short():46s} {score.describe()}")
    return [cfg for _, cfg, _ in ranked[:keep]]


def cross_search(
    points: list[PreparedPoint],
    weights: dict[int, float],
    s_configs: list[TailConfig],
    t_configs: list[TailConfig],
    keep: int,
) -> list[TailConfig]:
    unique: dict[TailConfig, None] = {}
    for scfg, tcfg in itertools.product(s_configs, t_configs):
        unique[dataclasses.replace(
            scfg, t_bits=tcfg.t_bits, t_mode=tcfg.t_mode
        )] = None
    ranked = []
    for cfg in unique:
        score = score_config(points, cfg, weights)
        ranked.append((score.rank(), cfg, score))
    ranked.sort(key=lambda row: (row[0], row[1].short()))
    print("best crossed S/t schedules:")
    for _, cfg, score in ranked[:keep]:
        print(f"  {cfg.short():46s} {score.describe()}")
    return [cfg for _, cfg, _ in ranked[:keep]]


def producer_neighbors(cfg: ProducerConfig) -> list[ProducerConfig]:
    neighbors: dict[ProducerConfig, None] = {}
    for bits, mode in precision_modes():
        neighbors[dataclasses.replace(
            cfg, asq_bits=bits, asq_mode=mode
        )] = None
    for bits in range(64, 68):
        for mode in ("rn", "chop"):
            neighbors[dataclasses.replace(
                cfg, coeff_bits=bits, coeff_mode=mode
            )] = None
    for form in ("separate", "fused"):
        for bits, mode in precision_modes():
            neighbors[dataclasses.replace(
                cfg,
                horner_form=form,
                horner_bits=bits,
                horner_mode=mode,
            )] = None
    return list(neighbors)


def score_producer(
    base_points: list[PreparedPoint],
    producer: ProducerConfig,
    tail: TailConfig,
    weights: dict[int, float] | None = None,
) -> Score:
    points = [prepare(point.raw, producer) for point in base_points]
    return score_config(points, tail, weights)


def producer_beam_search(
    points: list[PreparedPoint],
    weights: dict[int, float],
    tail: TailConfig,
    keep: int,
    rounds: int,
) -> list[ProducerConfig]:
    beam = [BASE_PRODUCER]
    cache: dict[ProducerConfig, Score] = {}
    for round_index in range(rounds):
        candidates: dict[ProducerConfig, None] = {}
        for cfg in beam:
            candidates[cfg] = None
            for neighbor in producer_neighbors(cfg):
                candidates[neighbor] = None
        ranked = []
        for cfg in candidates:
            score = cache.get(cfg)
            if score is None:
                score = score_producer(points, cfg, tail, weights)
                cache[cfg] = score
            ranked.append((score.rank(), cfg, score))
        ranked.sort(key=lambda row: (row[0], row[1].short()))
        beam = [cfg for _, cfg, _ in ranked[:keep]]
        print(
            f"producer beam round {round_index + 1} "
            f"with tail {tail.short()}:"
        )
        for _, cfg, score in ranked[:min(8, keep)]:
            print(f"  {cfg.short():30s} {score.describe()}")
    return beam


def joint_producer_tail_search(
    points: list[PreparedPoint],
    weights: dict[int, float],
    producers: list[ProducerConfig],
    tails: list[TailConfig],
    keep: int,
) -> list[tuple[ProducerConfig, TailConfig]]:
    ranked = []
    for producer, tail in itertools.product(producers, tails):
        score = score_producer(points, producer, tail, weights)
        ranked.append((score.rank(), producer, tail, score))
    ranked.sort(key=lambda row: (row[0], row[1].short(), row[2].short()))
    print("best joint producer/tail schedules:")
    for _, producer, tail, score in ranked[:keep]:
        print(
            f"  {producer.short():30s} {tail.short():46s} "
            f"{score.describe()}"
        )
    return [(producer, tail) for _, producer, tail, _ in ranked[:keep]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", type=pathlib.Path, default=DEFAULT_CAPTURE)
    parser.add_argument("--controls", type=int, default=2000)
    parser.add_argument("--keep", type=int, default=12)
    parser.add_argument("--baseline-only", action="store_true")
    parser.add_argument(
        "--skip-tail",
        action="store_true",
        help="reuse the current near-best tail when searching producers",
    )
    parser.add_argument("--skip-producer", action="store_true")
    parser.add_argument("--producer-rounds", type=int, default=3)
    parser.add_argument(
        "--region",
        choices=("all", "narrow", "wide"),
        default="all",
        help="fit and verify only one table-kernel region",
    )
    args = parser.parse_args()

    raw = load_points(args.capture)
    points = [prepare(point) for point in raw]
    if args.region == "narrow":
        points = [point for point in points if not point.wide]
    elif args.region == "wide":
        points = [point for point in points if point.wide]
    narrow = sum(not point.wide for point in points)
    print(f"loaded {len(points)} {args.region} direct-table inputs "
          f"({narrow} narrow, {len(points) - narrow} wide)")
    base_score = score_config(points, BASE)
    print(f"baseline full: {base_score.describe()}")
    print("baseline full by region/side/mode:")
    for key in sorted(base_score.by_region):
        print(f"  {key[0]:6s} {key[1]}: {base_score.by_region[key]}")
    if args.baseline_only:
        return

    search, weights = search_points(points, args.controls)
    print(f"baseline search: {score_config(search, BASE, weights).describe()}")
    if args.skip_tail:
        carried_tail = NARROW_TAIL if args.region == "narrow" else NEAR_TAIL
        finalists = [carried_tail]
        print(f"tail search skipped; carrying {carried_tail.short()}")
    else:
        s_configs = search_tail(search, weights, args.keep)
        t_configs = search_t(search, weights, args.keep)
        finalists = cross_search(
            search, weights, s_configs, t_configs, args.keep
        )

    if args.skip_producer:
        print("full-region verification:")
        for tail in (BASE, *finalists):
            score = score_config(points, tail)
            print(
                f"  {BASE_PRODUCER.short():30s} {tail.short():46s} "
                f"{score.describe()}"
            )
        return

    producer_candidates: dict[ProducerConfig, None] = {}
    producer_tails = list(dict.fromkeys([BASE, *finalists[:2]]))
    for tail in producer_tails:
        for producer in producer_beam_search(
            search, weights, tail, args.keep, args.producer_rounds
        ):
            producer_candidates[producer] = None
    joint = joint_producer_tail_search(
        search,
        weights,
        list(producer_candidates),
        list(dict.fromkeys([BASE, *finalists])),
        args.keep,
    )

    print("full-region verification:")
    full_ranked = []
    pairs = list(dict.fromkeys([
        (BASE_PRODUCER, BASE),
        *((BASE_PRODUCER, cfg) for cfg in finalists),
        *joint,
    ]))
    for producer, tail in pairs:
        score = score_producer(points, producer, tail)
        full_ranked.append((score.rank(), producer, tail, score))
    full_ranked.sort(key=lambda row: (row[0], row[1].short(), row[2].short()))
    for _, producer, tail, score in full_ranked:
        print(
            f"  {producer.short():30s} {tail.short():46s} "
            f"{score.describe()}"
        )


if __name__ == "__main__":
    main()
