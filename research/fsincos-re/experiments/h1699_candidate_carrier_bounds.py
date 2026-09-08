#!/usr/bin/env python3
"""Exact interval/representation bounds for candidate polynomial/table carriers.

Universal over the stated entry domains, not sampled operands. Intervals may
overapproximate infeasible endpoint combinations. The graph is an explicit
source-backed transcription, not an automatically verified C translation.
No silicon claim, new hardware, behavior change or paper/default promotion.
"""
from __future__ import annotations
import argparse
import json
import re
from dataclasses import dataclass
from fractions import Fraction as F
from pathlib import Path
from h1640_remaining_scope_freshness import save
from h1665_small_denormal_provenance import digest
from h1634_independent_table_certificate import p2, rnd, top

LOCKS = {
    'src/fsincos_skylake.c': '0339a7d6161c29164232fadd46053a538b7163d5d4449889e3600e9245026f2b',
    'src/p5_rom_constants.h': '2189e0063c913ee4004e09c8b80cb17afb16c95715ea579854e152088bbfce97',
    'experiments/h1630_shared_polynomial.h': '5c279565bf3ab5b1a02d92a24fb2e40dc3b12ab23498522768118890cf5c5310',
    'experiments/h1633_shared_table.h': '238ee52346049bbb292cb43958c01f8f1ddae20e4d3fad004bf74423f6dae66b',
    'experiments/h1634_independent_table_certificate.py': '41393ef2dd4fc42ff4d047b8fae87af529f9cb51e2ef784a78bf7ddc1a20cefa',
}


@dataclass(frozen=True)
class Carrier:
    lo: F
    hi: F
    e_lo: int
    e_hi: int
    width: int

    def __post_init__(self):
        assert self.lo <= self.hi and self.e_lo <= self.e_hi
        assert 0 <= self.width <= 128
        assert (self.lo == self.hi == 0) == (self.width == 0)

    def negative(self): return Carrier(-self.hi, -self.lo, self.e_lo, self.e_hi, self.width)


ONE = Carrier(F(1), F(1), 0, 0, 1)


def literal(sign, e, hi, lo):
    sig = (int(hi, 16) << 64) | int(lo, 16)
    value = (-1 if int(sign) else 1) * sig * p2(int(e))
    return Carrier(value, value, int(e), int(e), sig.bit_length())


def quantized(lo, hi, bits, policy):
    lo, hi = rnd(lo, bits, policy)[0], rnd(hi, bits, policy)[0]
    if lo == hi == 0: return Carrier(lo, hi, 0, 0, 0)
    # A nonzero continuum straddling zero lacks a finite exponent lower bound.
    # Do not silently invent one. Domain splits must establish a fixed sign.
    assert not lo <= 0 <= hi, (str(lo), str(hi), bits, policy)
    a, b = sorted((abs(lo), abs(hi)))
    return Carrier(lo, hi, top(a) - bits + 1, top(b) - bits + 1, bits)


class Graph:
    def __init__(self, domain): self.domain, self.events = domain, []

    def product(self, x, y, bits=67, policy='chop', name='product'):
        # acc_add_product is called at equal product/accumulator scale.
        width = x.width + y.width if x.width and y.width else 0
        emin, emax = x.e_lo + y.e_lo, x.e_hi + y.e_hi
        assert width < 256 and -(1 << 31) < emin <= emax < (1 << 31) - 256
        endpoints = [a * b for a in (x.lo, x.hi) for b in (y.lo, y.hi)]
        result = quantized(min(endpoints), max(endpoints), bits, policy)
        self.events.append(dict(name=name, kind='product', accumulator_bits=width,
            alignment_shift_max=0, scale_min=emin, scale_max=emax,
            output_e2_min=result.e_lo, output_e2_max=result.e_hi))
        return result

    def mul(self, x, y, bits=67, policy='chop', name='M'):
        x = self.product(x, ONE, 67, name=name + '.X67')
        y = self.product(y, ONE, 64, name=name + '.Y64')
        return self.product(x, y, bits, policy, name)

    def alignment(self, x, y, name):
        emin, emax = min(x.e_lo, y.e_lo), min(x.e_hi, y.e_hi)
        shifts = [v.e_hi - emin for v in (x, y) if v.width]
        widths = [v.width + v.e_hi - emin for v in (x, y) if v.width]
        maximum_shift = max(shifts, default=0)
        # Bound each first partial sum and the signed sum of both magnitudes.
        # If both are below2^w, their sum is below2^(w+1), never reaching signbit255.
        sum_width = max(widths, default=0) + int(len(widths) > 1)
        assert 0 <= maximum_shift <= 255 and sum_width <= 255, (self.domain, name, maximum_shift, sum_width)
        assert -(1 << 31) < emin <= emax < (1 << 31) - 256
        self.events.append(dict(name=name, kind='addition', accumulator_bits=sum_width,
            alignment_shift_max=maximum_shift, scale_min=emin, scale_max=emax))
        return emin, emax

    def add(self, x, y, bits=64, policy='rn', name='A'):
        self.alignment(x, y, name)
        return quantized(x.lo + y.lo, x.hi + y.hi, bits, policy)

    def final(self, leading, correction, name):
        emin, emax = self.alignment(leading, correction, name)
        lo, hi = leading.lo + correction.lo, leading.hi + correction.hi
        assert 0 < lo <= hi
        # One predecessor/successor can move the top binade by at most one.
        # This deliberately covers RN and either directed magnitude direction.
        stored_emin, stored_emax = top(lo) - 64, top(hi) - 62
        shmin, shmax = stored_emin - emax, stored_emax - emin
        assert 0 <= shmin <= shmax <= 255 and 64 + shmax <= 255, (self.domain, name, shmin, shmax)
        self.events.append(dict(name=name + '.C1_reencode', kind='C1', accumulator_bits=64 + shmax,
            alignment_shift_min=shmin, alignment_shift_max=shmax,
            scale_min=emin, scale_max=emax, stored_e2_min=stored_emin, stored_e2_max=stored_emax))
        return dict(prevalue_min=str(lo), prevalue_max=str(hi), final_normal=True)


def constants(root):
    rom = (root / 'src/p5_rom_constants.h').read_text(); c, tables = {}, {}
    for kind, size, index, sign, e, hi, lo in re.findall(r'P5([SC])([46])_(\d) = \{ ([01]), (-?\d+), .*?0x([0-9a-f]+)ull<<64\)\|0x([0-9a-f]+)ull', rom):
        value = literal(sign, e, hi, lo)
        if kind + size + index == 'S44':
            value = Carrier(value.lo - p2(-25), value.hi - p2(-25), value.e_lo, value.e_hi, value.width)
        c.setdefault(kind + size, {})[int(index)] = value
    pattern = r'\{ (\d+), \{ ([01]), (-?\d+), .*?0x([0-9a-f]+)ull<<64\)\|0x([0-9a-f]+)ull \}, \{ ([01]), (-?\d+), .*?0x([0-9a-f]+)ull<<64\)\|0x([0-9a-f]+)ull \} \}'
    for b, *fields in re.findall(pattern, rom): tables[int(b)] = literal(*fields[:4]), literal(*fields[4:])
    assert len(c) == 4 and len(tables) == 8
    return c, tables


def polynomial(binade, cosine, c):
    domain = dict(lane='polynomial', residual_binade=binade, cosine=cosine)
    g = Graph(domain); x = Carrier(p2(binade), p2(binade + 1), binade - 63, binade - 63, 64)
    s = g.mul(x, x, name='square'); f = g.mul(s, s, name='fourth')
    selected = c['C6' if cosine else 'S6']
    def chain(high, middle, low, name):
        p = g.mul(f, selected[high], name=name + '.high')
        p = g.add(selected[middle], p, name=name + '.middle')
        p = g.mul(f, p, name=name + '.product')
        return g.add(selected[low], p, name=name + '.low')
    n = chain(5, 3, 1, 'N'); p = chain(6, 4, 2, 'P')
    left, right = g.mul(s, n, name='left'), g.mul(f, p, name='right')
    combined = g.add(left, right, 67 if cosine else 64, 'chop' if cosine else 'rn', 'combined')
    correction = combined if cosine else g.mul(x, combined, name='correction')
    endpoint = g.final(ONE if cosine else x, correction, 'final')
    return domain, g.events, endpoint


def table(binade, sign, b, c, tables):
    domain = dict(lane='table', offset_binade=binade, offset_sign=sign, center=b)
    g = Graph(domain)
    # Raw a uses the residual grid e2=-65 or-64. At exactly1/16, its integer
    # magnitude can need62 bits despite much smaller odd-part precision.
    if binade is None: a = Carrier(F(0), F(0), -65, -64, 0)
    else:
        a = Carrier(p2(binade), p2(binade + 1), -65, -64, 62)
        if sign: a = a.negative()
    a = g.mul(a, ONE, name='offset'); s = g.mul(a, a, name='square')
    def horner(values, name):
        value = values[4]
        for k in (3, 2, 1):
            value = g.mul(s, value, name=name + '.mul' + str(k))
            value = g.add(value, values[k], name=name + '.add' + str(k))
        return value
    p, q = horner(c['S4'], 'P'), horner(c['C4'], 'Q')
    psq = g.mul(s, p, name='p_square'); stail = g.mul(psq, a, name='sine_tail')
    ss = g.add(a, stail, name='sine_state')
    ct = g.mul(s, q, 64, 'rn', 'cosine_tail')
    ts, tc = tables[b]; endpoints = []
    for cosine in (0, 1):
        first = g.mul(ts if cosine else tc, ss, name=f'first{cosine}')
        second = g.mul(tc if cosine else ts, ct, name=f'second{cosine}')
        if cosine: first = first.negative()
        correction = g.add(first, second, 67, 'chop', f'correction{cosine}')
        endpoints.append(g.final(tc if cosine else ts, correction, f'final{cosine}'))
    return domain, g.events, endpoints


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path); parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args(); root, out = args.root.resolve(), args.output_dir.resolve(); assert not out.exists()
    for name, expected in LOCKS.items(): assert digest(root / name) == expected, name
    c, tables = constants(root); cases = []
    for binade in range(-32, -2):
        for cosine in (0, 1): cases.append(polynomial(binade, cosine, c))
    for b in (18, 22, 26, 30, 36, 44, 52):
        # Center52's zero offset is unreachable, but the helper case is safe
        # and included as an overapproximation, never new hardware coverage.
        cases.append(table(None, 0, b, c, tables))
        for binade in range(-65, -4):
            for sign in (0, 1): cases.append(table(binade, sign, b, c, tables))
    events = [event for _, sequence, _ in cases for event in sequence]
    maximum = max(events, key=lambda e: e['accumulator_bits'])
    shift = max(events, key=lambda e: e['alignment_shift_max'])
    out.mkdir(parents=True)
    save(out / 'cases.json', [dict(domain=d, events=e, endpoints=p) for d, e, p in cases])
    report = dict(experiment='h1699_candidate_carrier_bounds', status='PASS_EXACT_INTERVAL_AND_REPRESENTATION_BOUNDS',
        domain_cases=len(cases), polynomial_cases=60, table_cases=len(cases)-60, operation_bound_checks=len(events),
        maximum_accumulator_bits=maximum['accumulator_bits'], maximum_alignment_shift=shift['alignment_shift_max'],
        maximum_accumulator_event=maximum, maximum_shift_event=shift,
        scale_min=min(e['scale_min'] for e in events), scale_max=max(e['scale_max'] for e in events),
        argument='Monotone exact rational endpoint enclosures with fixed-sign splits; normalized carrier widths from the stated quantizers. Each signed partial sum and sum of two magnitudes stays below2^255. All candidate add alignments and final C1 reencodings use nonnegative shifts below256; products need at most128-bit host operands and fit signed256. No int32 scale/normalization increment overflow.',
        scope='All polynomial residuals with normalized64-bit representation,2^-32<=r<1/4, and table offsets on e2=-65/-64 grids with0<=|a|<=1/16, including overapproximated cell/sign combinations. Conditional on the existing reducer/dispatcher entry contract and the source-backed quantizer semantics; not automatic C verification, physical port recovery, tiny/special/state closure or universal silicon equality.',
        hardware_execution='none', labels_opened=False, private_ledger_access='none', production_default_or_paper_change=False,
        sha256=dict(script=digest(Path(__file__)), evidence=LOCKS, cases=digest(out / 'cases.json')))
    save(out / 'report.json', report)
    print(json.dumps({k: report[k] for k in ('status', 'domain_cases', 'operation_bound_checks', 'maximum_accumulator_bits', 'maximum_alignment_shift', 'scale_min', 'scale_max')}), flush=True)


if __name__ == '__main__': main()
