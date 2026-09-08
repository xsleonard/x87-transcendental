"""Exact witness and synthetic scoring tests; never execute hardware."""
from collections import Counter
import contextlib
import gzip
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from compressed_guard import digest
import d0031_internal_rounding_coverage as audit
from d0037_polynomial_node_census import restored, traced_kernel
from prepare import save
from protocol import make_line
import score_d0046_ties as scorer

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'tmp/fpatan-re'


class TieDiscriminatorTests(unittest.TestCase):
    def test_every_external_witness(self):
        report = json.loads((BASE / 'd0045-node3-upper/REPORT.json').read_text())
        parities = Counter()
        for row in report['witnesses']:
            self.assertEqual(row['status'], 'EXACT_EXTERNAL_ENDPOINT_SEPARATOR')
            y = audit.Raw80(int(row['raw'][0], 16), int(row['raw'][1], 16))
            x = audit.Raw80(int(row['raw'][2], 16), int(row['raw'][3], 16))
            state = audit.reduction(audit.core_key(y, x))
            self.assertEqual(state['cell'], row['cell'])
            self.assertEqual(state['z'], row['sign'] * int(row['z_sig'], 16) * audit.two(row['z_step']))
            kernel, trace = traced_kernel(state['z'], True)
            event = next(r for r in trace if r[0] == 'correction_sum')
            self.assertEqual(event[3:5], ('tie', row['parity']))
            other, changed_trace = traced_kernel(state['z'], True,
                ('correction_sum', 'ties-away' if row['parity'] == 0 else 'ties-zero'))
            index = next(i for i, r in enumerate(trace) if r[0] == 'correction_sum')
            self.assertEqual(trace[:index], changed_trace[:index])
            fixed_angles, other_angles = restored(state, kernel), restored(state, other)
            self.assertEqual(fixed_angles[0], audit.SPEC['finite_angle'](y, x))
            fixed, alternate = audit.endpoint_vector(fixed_angles), audit.endpoint_vector(other_angles)
            mask = sum((a != b) << i for i, (a, b) in enumerate(zip(fixed, alternate)))
            self.assertNotEqual(mask, 0)
            self.assertEqual(mask, int(row['endpoint_mask'], 16))
            parities[row['parity']] += 1
        self.assertEqual(parities, {0: 49, 1: 27})

    def test_sanitized_complete_target_stream(self):
        optimized = BASE / 'd0045-node3-upper'
        sanitized = BASE / 'd0045-node3-sanitized'
        for name in ('miner.tsv', 'miner.log'):
            self.assertEqual(digest(optimized / name), digest(sanitized / name))
        first = json.loads((optimized / 'REPORT.json').read_text())
        second = json.loads((sanitized / 'REPORT.json').read_text())
        self.assertEqual(first['counts'], second['counts'])
        self.assertEqual(first['witnesses'], second['witnesses'])

    def test_scorer_rejects_changed_hardware_for_both_parities(self):
        base = Path(tempfile.mkdtemp(prefix='fpatan-d0046-synthetic-'))
        for mutate in (False, True):
            job = base / ('odd-fixture' if mutate else 'even-fixture')
            job.mkdir()
            inputs, predictions, hardware, overrides = [], [], [], []
            for parity in (0, 1):
                line = make_line('rn', 64, 0x3fff, (1 << 63) + parity, 0x3fff, 1 << 63)
                ident = line.split()[0]
                baseline = (0x3ffe, 0xc90fdaa22168c235 + parity, 0, 32, 0)
                alternative = (baseline[0], baseline[1] + 1, 1, 32, 0)
                actual = alternative if mutate else baseline
                inputs.append(line + '\n')
                predictions.append(f'{ident} {baseline[0]:04x} {baseline[1]:016x} 0 20 00\n')
                hardware.append(f'{line} 037f 3000 {0x3820 | (actual[2] << 9):04x} '
                                f'{actual[0]:04x} {actual[1]:016x}\n')
                overrides.append(json.dumps(dict(id=ident, node=3, parity=parity,
                                                 alternative=alternative)) + '\n')
            streams = {'inputs.txt.gz': inputs, 'predictions.txt.gz': predictions,
                       'hardware.txt.gz': hardware, 'CONTROL-DIFFERENCES.jsonl.gz': overrides}
            for name, lines in streams.items():
                with gzip.open(job / name, 'xt') as target:
                    target.writelines(lines)
            save(job / 'MANIFEST.json', dict(status='SYNTHETIC_FIXTURE_NOT_HARDWARE', rows=2))
            save(job / 'STRUCTURAL-HYPOTHESIS.json', dict(
                manifest_sha256=digest(job / 'MANIFEST.json'),
                sparse_predictions_sha256=digest(job / 'CONTROL-DIFFERENCES.jsonl.gz'),
                counts={'node3:separators:parity0': 1, 'node3:separators:parity1': 1}))
            save(job / 'DISPATCHED.json', dict(structural_hypothesis_sha256=digest(job / 'STRUCTURAL-HYPOTHESIS.json')))
            save(job / 'COMPLETE.json', dict(rows=2,
                hardware_sha256=hashlib.sha256(''.join(hardware).encode()).hexdigest(),
                hardware_gzip_sha256=digest(job / 'hardware.txt.gz'),
                manifest_sha256=digest(job / 'MANIFEST.json')))
            save(job / 'SCORE.json', dict(counts={'rows': 2}))
            with patch.object(scorer, 'JOB', job), contextlib.redirect_stdout(io.StringIO()):
                scorer.main()
            counts = json.loads((job / 'TIE-RULE-SCORE.json').read_text())['counts']
            self.assertEqual(counts['node3:nearest-even:union_misses'], 2 * int(mutate))
            self.assertEqual(counts['node3:nearest-odd:union_misses'], 2 * int(not mutate))
            self.assertEqual(counts['node3:ties-away:union_misses'], 1)
            self.assertEqual(counts['node3:ties-zero:union_misses'], 1)


if __name__ == '__main__':
    unittest.main()
