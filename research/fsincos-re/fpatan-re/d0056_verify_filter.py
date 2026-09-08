"""Check the frozen boundary exclusion against independent full-scan carries."""
import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys

from compressed_guard import digest
import d0031_internal_rounding_coverage as audit
from d0049_algebraic_tie_preimages import domains, graph, fraction, ROM, COEFFICIENTS, invert_target
from d0056_outer_boundary_lattice import parameters
from prepare import save

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'tmp/fpatan-re'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists()
    counts, pins = Counter(), {}
    for node in (0, 1):
        directory = BASE / f'd0055-node{node}-wide'
        report = json.loads((directory / 'REPORT.json').read_text())
        source = directory / 'targets.tsv'
        assert digest(source) == report['target_sha256']
        for name, sha in report['source_sha256'].items():
            assert digest(HERE / name) == sha
        # The full scan was generated independently, without using D0056's
        # filter. Retrieve every reported changed-outer occurrence from it.
        found = subprocess.run(['rg', r' 1$', str(source)], text=True, capture_output=True)
        assert found.returncode == 0 and not found.stderr
        choices = domains(node, report['exponent'])
        bounded = [parameters(node, d) for d in choices]
        for line in found.stdout.splitlines():
            fields = line.split()
            assert fields[0] == 'T' and fields[7] == '1'
            um = int(fields[4], 16)
            target, h, outer = graph(node, (um, report['exponent'] - 63))
            _, alternate_h, alternate_outer = graph(node, (um, report['exponent'] - 63), True)
            assert outer != alternate_outer and (h != alternate_h) == bool(int(fields[6]))
            covered = False
            base = abs(fraction(ROM[COEFFICIENTS[node][0]]))
            for d, p in zip(choices, bounded):
                term = (abs(fraction(target)) - base) / audit.two(d['unit'])
                assert term.denominator == 1
                index, remainder = divmod(int(term) - d['first'], d['modulus'])
                if remainder or not 0 <= index < d['count'] or um not in invert_target(d, int(term)):
                    continue
                start = index // (1 << 20) * (1 << 20)
                length = min(1 << 20, d['count'] - start)
                offset = index - start
                slope = 2 * p['alpha'] * start + p['beta']
                intercept = p['alpha'] * start * start + p['beta'] * start + p['gamma']
                residue = (slope * offset + intercept) % p['modulus']
                upper = p['error_high'] + p['alpha'] * (length - 1) ** 2
                covered |= residue <= p['error_low'] or residue >= p['modulus'] - upper
            assert covered, (node, fields[4])
            counts[f'node{node}:outer_carry_occurrences_included'] += 1
        assert counts[f'node{node}:outer_carry_occurrences_included'] == report['native_counts']['first_outer_changed']
        pins[str(source)] = digest(source)
        pins[str(directory / 'REPORT.json')] = digest(directory / 'REPORT.json')
        print('PASS independent full-scan carries included, node', node,
              counts[f'node{node}:outer_carry_occurrences_included'], flush=True)
    run = subprocess.run([sys.executable, str(HERE / 'test_d0056_boundary_lattice.py')],
                         text=True, capture_output=True)
    assert run.returncode == 0, run.stderr
    for name in ('d0056_verify_filter.py', 'd0056_outer_boundary_lattice.py', 'test_d0056_boundary_lattice.py'):
        pins[str(HERE / name)] = digest(HERE / name)
    save(args.out, dict(status='PASS_INDEPENDENT_CARRY_FILTER_AUDIT', counts=counts,
        tests=dict(returncode=run.returncode, stdout=run.stdout, stderr=run.stderr), evidence_sha256=pins,
        hardware_executed=False, numerical_model_changed=False, goal_complete=False,
        limits='No false exclusions among all carried ties from the independently generated saved scans, plus direct arithmetic/enumeration tests. The exclusion itself follows the stated interval derivation; this finite check is not an all-input hardware proof.'))


if __name__ == '__main__':
    main()
