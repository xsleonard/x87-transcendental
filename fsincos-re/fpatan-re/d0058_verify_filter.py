"""Audit the short-odd exclusion against independent, unfiltered H carries."""
import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys

from compressed_guard import digest
import d0031_internal_rounding_coverage as audit
from d0045_tie_observability import target_and_correction
from d0049_algebraic_tie_preimages import domains, graph, fraction, invert_target
from d0058_short_odd_boundary import parameters, block_enclosure
from prepare import save

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'tmp/fpatan-re'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists()
    counts, pins = Counter(), {}
    for name in ('d0049-node2-wide', 'd0049-node2-expanded', 'd0049-node2-next'):
        directory = BASE / name
        report = json.loads((directory / 'REPORT.json').read_text())
        source = directory / 'targets.tsv'
        assert digest(source) == report['target_sha256']
        for filename, sha in report['source_sha256'].items():
            assert digest(HERE / filename) == sha
        found = subprocess.run(['rg', r'^T 2 .* 1 1$', str(source)], text=True, capture_output=True)
        assert found.returncode == 0 and not found.stderr
        exponent = report['square_exponent']
        choices = domains(2, exponent)
        bounds = [parameters(d, exponent) for d in choices]
        for line in found.stdout.splitlines():
            fields = line.split()
            assert fields[0] == 'T' and fields[6:] == ['1', '1']
            word = int(fields[4], 16)
            target, h, _ = graph(2, (word, exponent - 63))
            _, alternate, _ = graph(2, (word, exponent - 63), True)
            ft, fh = target_and_correction(2, word * audit.two(exponent - 63))
            _, fa = target_and_correction(2, word * audit.two(exponent - 63), True)
            assert (fraction(target), fraction(h), fraction(alternate)) == (ft, fh, fa)
            assert h != alternate
            covered = set()
            for d, p in zip(choices, bounds):
                term = (fraction(target) - audit.ROM[115]) / audit.two(d['unit'])
                assert term.denominator == 1
                index, remainder = divmod(int(term) - d['first'], d['modulus'])
                if remainder or not 0 <= index < d['count'] or word not in invert_target(d, int(term)):
                    continue
                for bits in (7, 8, 10, 12):
                    width = 1 << bits
                    start = index // width * width
                    length = min(width, d['count'] - start)
                    envelope = block_enclosure(p, start, length)
                    residue = (envelope['slope'] * (index - start) + envelope['intercept']) % envelope['modulus']
                    assert (residue <= envelope['lower']
                            or residue >= envelope['modulus'] - envelope['upper']), (name, fields[4], bits)
                    covered.add(bits)
            assert covered == {7, 8, 10, 12}
            counts[f'{name}:H_carries_included_all_four_block_sizes'] += 1
        assert counts[f'{name}:H_carries_included_all_four_block_sizes'] == report['counts']['H_changed']
        pins[str(source)] = report['target_sha256']
        pins[str(directory / 'REPORT.json')] = digest(directory / 'REPORT.json')
        print('PASS independent H carries included:', name, report['counts']['H_changed'], flush=True)
    tests = subprocess.run([sys.executable, str(HERE / 'test_d0058_short_boundary.py')],
                           text=True, capture_output=True)
    assert tests.returncode == 0, tests.stderr
    for name in ('d0058_verify_filter.py', 'd0058_short_odd_boundary.py', 'test_d0058_short_boundary.py',
                 'd0056_outer_boundary_lattice.py'):
        pins[str(HERE / name)] = digest(HERE / name)
    save(args.out, dict(status='PASS_INDEPENDENT_SHORT_ODD_FILTER_AUDIT', counts=counts,
        tests=dict(returncode=tests.returncode, stdout=tests.stdout, stderr=tests.stderr),
        evidence_sha256=pins, hardware_executed=False, numerical_model_changed=False, goal_complete=False,
        limits='Every saved H carry in three independently generated unfiltered scans survives four block-size versions of the filter and full Fraction replay. This checks the analytic exclusion; it is not an all-input hardware proof.'))


if __name__ == '__main__':
    main()
