"""Independently verify source observations and necessary D0016 intervals.

No solver, graph, terminal inverse, or D0016 generator is imported. Exact
integer rounding verifies both allowed carrier endpoints and the immediately
adjacent disallowed carriers. Monotonicity of positive CHOP products makes
this a complete preimage check on the stated lattice. Rounding-error bounds
are reconstructed separately across each coefficient box.
"""
import argparse
import functools
import gzip
import hashlib
import itertools
import json
from pathlib import Path
from fractions import Fraction as F
from d0011_verify_role_certificate import rounded
from verify_d0014_certificate import angle_interval, rom_constants, two, binade
from protocol import validate_output
from prepare import save

BASE = Path(__file__).resolve().parents[1] / 'tmp/fpatan-re'


def positive_interval(rows):
    positive = []
    for row in rows:
        item = dict(row)
        tokens = item['input'].split()
        if item['se'] & 32768:
            tokens[1] = {'rd': 'ru', 'ru': 'rd'}.get(tokens[1], tokens[1])
        item['se'] &= 32767
        item['input'] = ' '.join(tokens)
        positive.append(item)
    return angle_interval(positive)


def terminal(z, h, recipe):
    u = rounded(z * z, 'chop67')
    zr = rounded(z, recipe['z_read'])
    first = 'chop' + str(recipe['first_bits'])
    last = 'chop' + str(recipe['last_bits'])
    order = recipe['order']
    if order == 'square-h-z':
        t = rounded(rounded(u * h, first) * zr, last)
    elif order == 'z-h-square':
        t = rounded(rounded(zr * h, first) * u, last)
    else:
        assert order == 'square-z-h'
        t = rounded(rounded(zr * u, first) * h, last)
    return z + t


@functools.lru_cache(maxsize=None)
def errors(z, hbits, read, bound):
    centers = rom_constants()
    units = {k: two(binade(v) - 68) for k, v in centers.items()}
    u = rounded(rounded(z * z, 'chop67'), read)
    lo, hi = centers[123] - bound * units[123], centers[123] + bound * units[123]
    elo = ehi = F(0)
    for k in range(122, 117, -1):
        lo, hi = lo * u, hi * u
        assert lo * hi > 0
        unit = two(max(binade(lo), binade(hi)) - 66)
        elo, ehi = elo * u, ehi * u
        if lo > 0:
            elo -= unit
        else:
            ehi += unit
        lo = rounded(lo, 'chop67') + centers[k] - bound * units[k]
        hi = rounded(hi, 'chop67') + centers[k] + bound * units[k]
        assert lo * hi > 0
        unit = two(max(binade(lo), binade(hi)) - hbits + 1)
        elo -= unit / 2
        ehi += unit / 2
        lo, hi = rounded(lo, 'rn' + str(hbits)), rounded(hi, 'rn' + str(hbits))
    return u, elo, ehi


def authenticate(frontier):
    wanted = {row['input'].split()[0]: row for pair in frontier for row in pair['rows']}
    found = set()
    sources = []
    for name in ('d0008', 'd0009'):
        job = BASE / name
        receipt = json.loads((job / 'COMPLETE.json').read_text())
        manifest = json.loads((job / 'MANIFEST.json').read_text())
        digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
        assert digest(job / 'MANIFEST.json') == receipt['manifest_sha256']
        assert digest(job / 'inputs.txt.gz') == manifest['files']['inputs.txt.gz']
        assert digest(job / 'hardware.txt.gz') == receipt['hardware_gzip_sha256']
        sha = hashlib.sha256()
        count = 0
        with gzip.open(job / 'inputs.txt.gz', 'rt') as inputs, gzip.open(job / 'hardware.txt.gz', 'rt') as hardware:
            for inp, out in itertools.zip_longest(inputs, hardware):
                assert inp is not None and out is not None
                sha.update(out.encode())
                count += 1
                ident = inp.split()[0]
                if ident in wanted:
                    row = wanted[ident]
                    assert inp.strip() == row['input']
                    actual = validate_output(out, inp)
                    assert all(actual[k] == row[k] for k in ('se', 'sig', 'C1'))
                    found.add(ident)
        assert count == receipt['rows'] and sha.hexdigest() == receipt['hardware_sha256']
        sources.append(dict(job=name, rows=count, hardware_sha256=sha.hexdigest()))
        print('AUTHENTICATED', name, count, flush=True)
    assert found == wanted.keys()
    return sources, len(found)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('families', type=Path, nargs='+')
    args = ap.parse_args()
    assert not args.out.exists()
    frontier = json.loads((BASE / 'd0009-kernel-frontier.json').read_text())['pairs']
    points = {pair['rows'][0]['input']: pair for pair in frontier}
    sources, saved_rows = authenticate(frontier)
    # The interval helper is for unrotated direct angles below one. The
    # complete authenticated frontier also contains rotated/table cases;
    # construct intervals only when the selected D0016 point requires one.
    bands = {}
    preimages = set()
    families = []
    checked = 0
    for family in args.families:
        summary = json.loads((family / 'SUMMARY.json').read_text())
        read = summary.get('horner_square_read', 'exact')
        report_hashes = {}
        for record in summary['results']:
            path = family / f"t{record['index']:03d}.json"
            report = json.loads(path.read_text())
            assert hashlib.sha256(path.with_suffix('.smt2').read_bytes()).hexdigest() == report['query_sha256']
            assert report['result']['result'] == record['result']
            assert report['worker_returncode'] == 0 and not report['external_deadline']
            recipe = report['recipe']
            for point in report['constraints']:
                line = point['input']
                pair = points[line]
                ys, ym, xs, xm = pair['raw']
                assert not xs & 32768
                ratio = F(ym, xm) * two((ys & 32767) - xs)
                assert 0 < ratio < F(3, 64)
                z = rounded(ratio, 'chop67')
                u = rounded(z * z, 'chop67')
                assert str(z) == point['z'] and str(u) == point['u']
                h_lo, h_hi = F(point['h_lo']), F(point['h_hi'])
                bits = recipe['h_bits']
                key = (line, recipe['name'])
                if key not in preimages:
                    assert -F(1, 2) < h_lo <= h_hi < -F(1, 4)
                    step = two(-bits - 1)
                    assert (h_lo / step).denominator == 1 and (h_hi / step).denominator == 1
                    if line not in bands:
                        bands[line] = positive_interval(pair['rows'])
                    lo, hi, lc, hc = bands[line]
                    contains = lambda v: (v > lo or (lc and v == lo)) and (v < hi or (hc and v == hi))
                    assert contains(terminal(z, h_lo, recipe)) and contains(terminal(z, h_hi, recipe))
                    before, after = terminal(z, h_lo - step, recipe), terminal(z, h_hi + step, recipe)
                    assert before < lo or (before == lo and not lc)
                    assert after > hi or (after == hi and not hc)
                    preimages.add(key)
                uh, elo, ehi = errors(z, bits, read, report['coefficient_half_width_in_69bit_ULPs'])
                assert str(uh) == point.get('horner_u', point['u'])
                assert str(elo) == point['error_lo'] and str(ehi) == point['error_hi']
                checked += 1
            report_hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        families.append(dict(path=str(family), programs=summary['programs'], counts=summary['counts'],
                             horner_square_read=read, report_sha256=report_hashes))
        print('VERIFIED', family.name, summary['programs'], 'graphs', flush=True)
    save(args.out, dict(status='INDEPENDENT_D0016_INTERVAL_AND_SOURCE_VERIFICATION_PASS',
                       sources=sources, authenticated_frontier_rows=saved_rows,
                       unique_terminal_preimages=len(preimages), checked_point_envelopes=checked,
                       families=families, solver_imported=False, hardware_executed=False,
                       limits='Verifies the source data and necessary intervals; solver results are separately hash-pinned, with representative CVC5 crosschecks.'))
    print('PASS', len(preimages), 'terminal preimages;', checked, 'point envelopes', flush=True)


if __name__ == '__main__':
    main()
