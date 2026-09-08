"""Independent MPFR and integer-rounding checks of the D0019 diagnostic."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from fractions import Fraction as F
from d0010_causal_intervals import BASE
from verify_d0017_d0020 import quantize
from verify_d0014_certificate import two
from prepare import save


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--binary', type=Path, required=True)
    args = ap.parse_args()
    binary = args.binary.resolve(strict=True)
    source = Path(__file__).with_name('d0019_check_atan_bounds.c')
    path = BASE / 'd0019-certified-atan-diagnostic.json'
    report = json.loads(path.read_text())
    frontier_path = BASE / 'd0009-kernel-frontier.json'
    assert hashlib.sha256(frontier_path.read_bytes()).hexdigest() == report['frontier_sha256']
    originals = {r['input']: r for p in json.loads(frontier_path.read_text())['pairs'] for r in p['rows']}
    records = []
    checked = 0
    for point in report['results']:
        for name, key in (('atan_c67', 'z'), ('atan_ratio', 'exact_ratio')):
            lower, upper = point['variants'][name]['bounds']
            records.append(f'{point[key]} {lower} {upper}\n')
        for variant in point['variants'].values():
            a, b = (F(v) for v in variant['bounds'])
            for row in variant['observations']:
                tokens = row['input'].split()
                original = originals[row['input']]
                assert row['observed'] == [original[k] for k in ('se', 'sig', 'C1')]
                negative = bool(int(tokens[3], 16) & 32768)
                lo, hi = (-b, -a) if negative else (a, b)
                fmt = ('chop' if tokens[1] == 'rz' else tokens[1]) + '64'
                q = quantize(lo, fmt)
                assert q == quantize(hi, fmt)
                c1 = int(abs(q) > abs(lo))
                assert c1 == int(abs(q) > abs(hi))
                se, sig, expected_c1 = row['predicted']
                predicted = (-1 if se & 32768 else 1) * sig * two((se & 32767) - 16383 - 63)
                assert q == predicted and c1 == expected_c1
                checked += 1
    result = subprocess.run([str(binary)], input=''.join(records), capture_output=True, text=True, check=True)
    assert result.stdout == f'PASS {len(records)} rational atan enclosures at 768 bits\n'
    # Confirm the separate checker rejects false enclosures and malformed data.
    mutation_results = {}
    for name, inp, expected in (('too_high', '1/4 1/2 3/4\n', 3),
                                ('too_low', '1/4 0 1/8\n', 3),
                                ('malformed', 'not-a-rational\n', 4)):
        mutation = subprocess.run([str(binary)], input=inp, capture_output=True, text=True)
        assert mutation.returncode == expected
        mutation_results[name] = mutation.returncode
    save(BASE / 'd0019-independent-diagnostic-verification.json', dict(status='PASS',
         rational_enclosures=len(records), independently_rounded_observations=checked,
         source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
         binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
         diagnostic_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
         frontier_sha256=report['frontier_sha256'], mutations=mutation_results,
         stdout=result.stdout, hardware_executed=False, numerical_model_promoted=False))
    print(result.stdout.strip(), ';', checked, 'independent RC/C1 checks; mutations PASS', flush=True)


if __name__ == '__main__':
    main()
