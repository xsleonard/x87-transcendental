"""Exact finite certificate: lower/odd ties are endpoint-equivalent in V7.

For an exact midpoint m/64 and table cell j, normalize the larger operand
as x=S*2**e, 2**63 <= S < 2**64. The numerator is exactly +/-x/64.
Writing K=2048+j*m, the 67-bit denominator is (K*S-t)*2**(e-11),
where 0 <= t <= 511 because K*S < 2**76. Thus the reduced magnitude is
CHOP67(32*S/(K*S-t)), enclosed by the two exact rational bounds below.

Only even lower cells 2..30 differ between the lower/odd rules. Enumerate
EVERY 67-bit value in these rigorous enclosures, including unreachable ones,
and show a single common RC/C1 endpoint vector for both neighboring cells.
This proves an identity of the candidate graph, not a silicon selector law.
No hardware labels, native floating-point or numerical fitting are used.
"""
import argparse
from fractions import Fraction as F
import json
from pathlib import Path
import re

from compressed_guard import digest
from d0010_causal_intervals import BASE
from d0024_index_residue_mining import endpoints as production_endpoints
from graph_v6 import kernel as production_kernel
from model import ROM as production_rom, cut
from prepare import save
from verify_d0017_d0020 import quantize


def two(e):
    return F(1 << e) if e >= 0 else F(1, 1 << -e)


def exponent(v):
    n, d = abs(v).numerator, abs(v).denominator
    result = n.bit_length()-d.bit_length()
    return result - (F(n, d) < two(result))


def c_constants():
    # Independent constant transport from the standalone C literals, not
    # the production Python ROM loader or its tab-separated data parser.
    source = Path(__file__).with_name('fpatan_candidate_v7.c').read_text()
    entries = re.findall(r'\{(\d+),\s*(\d+),\s*(-?\d+),\s*"([0-9a-f]+)"\}', source)
    result = {int(i): (-1 if int(s) else 1)*int(m, 16)*two(int(e)) for i, s, e, m in entries}
    assert len(result) == 44
    for i, v in result.items():
        assert v == production_rom[i]
    return result


def reference_angle(z, cell, constants):
    square = quantize(z*quantize(z, 'chop64'), 'rn64')
    fourth = quantize(square*square, 'chop67')
    ev = quantize(constants[114] + quantize(fourth*constants[116], 'chop67'), 'chop67')
    od = quantize(constants[115] + quantize(fourth*constants[117], 'chop67'), 'rn64')
    h = quantize(quantize(square*od, 'chop67') + ev, 'rn64')
    cubic = quantize(z*square, 'chop67')
    tail = quantize(cubic*h, 'chop67')
    return quantize(z+tail, 'chop67') + constants[124+cell]


def reference_endpoints(v, constants):
    truncated = quantize(v, 'chop67')
    restored = (v, constants[19]-truncated,
                constants[20]-truncated, constants[20]+truncated)
    result = []
    for angle in restored:
        assert angle > two(-10) and angle < 4
        for sign in (1, -1):
            for mode in ('rn64', 'rd64', 'ru64', 'chop64'):
                q = quantize(sign*angle, mode)
                e = exponent(q)
                significand = abs(q)/two(e-63)
                assert significand.denominator == 1 and (1 << 63) <= significand < (1 << 64)
                result.append(((int(q < 0) << 15) | (e+16383), int(significand),
                               int(abs(q) > angle)))
    return tuple(result)


def build():
    constants = c_constants()
    cells = []
    states = 0
    for n in range(2, 32, 2):
        common = None
        ranges = []
        for j in (n, n+1):
            m = 2*n+1
            k = 2048+j*m
            assert 2048 < k < 4096
            lower = F(32, k)
            upper = F(32*(1 << 63), k*(1 << 63)-511)
            assert lower <= upper and exponent(lower) == exponent(upper)
            unit = two(exponent(lower)-66)
            first = int(lower/unit)
            last = int(upper/unit)
            # Check the floor bounds independently of the production rounder.
            assert first*unit <= lower < (first+1)*unit
            assert last*unit <= upper < (last+1)*unit
            angles = []
            for integer in range(first, last+1):
                z = integer*unit*(1 if j == n else -1)
                angle = reference_angle(z, j, constants)
                assert angle == cut(production_kernel(z, True), 'chop67')+production_rom[124+j]
                vector = reference_endpoints(angle, constants)
                assert vector == production_endpoints(angle)
                if common is None:
                    common = vector
                assert vector == common, 'Enclosure contains an endpoint separator; no proof'
                angles.append(str(angle))
                states += 1
            ranges.append(dict(cell=j, K=k, lower=str(lower), upper=str(upper),
                               step=str(unit), first=first, last=last,
                               states=last-first+1, angles=angles))
        cells.append(dict(lower_cell=n, ratio=f'{2*n+1}/64', ranges=ranges,
                          common_endpoints=common))
    return dict(status='PROVED_LOWER_ODD_ENDPOINT_EQUIVALENCE_WITHIN_V7',
        scope='All valid finite nonzero raw80 pairs in this fixed graph; other input classes share the same architecture handler.',
        limits='Not a recovered hardware index rule or a proof that V7 matches silicon on every input.',
        arithmetic_premises=dict(normalized_S_min=1 << 63, normalized_S_max_exclusive=1 << 64,
            denominator_product_bits_max=76, denominator_retained_bits=67,
            discarded_integer_max=511,
            predivision_magnitude='32*S/(K*S-t)', K='2048+j*(2*n+1)'),
        equivalent_even_midpoints=len(cells), enumerated_reduced_states=states,
        endpoint_checks=states*32, cells=cells,
        odd_lower_cells='Both rules choose the same index; at 1/64 both indices use the direct path.',
        flags='All enumerated angles are normal and nonzero, so candidate PE is set and UE is clear; DE depends only on identical original operand classes.',
        hardware_executed=False, hardware_labels_opened=False, numerical_model_promoted=False,
        source_sha256={p.name: digest(p) for p in (Path(__file__),
            Path(__file__).with_name('fpatan_candidate_v7.c'),
            Path(__file__).with_name('graph_v6.py'),
            Path(__file__).with_name('graph_v7.py'),
            Path(__file__).with_name('verify_d0017_d0020.py'))})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    report = build()
    destination = BASE / 'd0025-midpoint-alias-certificate.json'
    if args.verify:
        assert json.loads(destination.read_text()) == json.loads(json.dumps(report))
    else:
        save(destination, report)
    print('PASS exact candidate-graph equivalence:', report['equivalent_even_midpoints'],
          'midpoints,', report['enumerated_reduced_states'], 'enclosed states,',
          report['endpoint_checks'], 'independent endpoint checks; no hardware', flush=True)
