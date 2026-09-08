"""Exact witness and synthetic scorer controls; no hardware execution."""
from collections import Counter
import contextlib
import gzip
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import json

from compressed_guard import digest
from prepare import save
from prepare_d0057 import witnesses
from protocol import make_line
import score_d0046_ties as scorer


class LongEvenTieDiscriminatorTests(unittest.TestCase):
    def test_all_external_witnesses_and_both_parities(self):
        rows = witnesses()
        self.assertEqual(len(rows), 9)
        self.assertEqual(Counter(r['parity'] for r in rows), {0: 1, 1: 8})

    def test_scorer_detects_both_possible_hardware_outcomes(self):
        base = Path(tempfile.mkdtemp(prefix='fpatan-d0057-synthetic-'))
        for mutate in (False, True):
            job = base / str(int(mutate))
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
                overrides.append(json.dumps(dict(id=ident, node=1, parity=parity,
                                                alternative=alternative)) + '\n')
            for name, rows in {'inputs.txt.gz': inputs, 'predictions.txt.gz': predictions,
                               'hardware.txt.gz': hardware, 'CONTROL-DIFFERENCES.jsonl.gz': overrides}.items():
                with gzip.open(job / name, 'xt') as stream:
                    stream.writelines(rows)
            save(job / 'MANIFEST.json', dict(status='SYNTHETIC_NOT_HARDWARE', rows=2))
            save(job / 'STRUCTURAL-HYPOTHESIS.json', dict(
                manifest_sha256=digest(job / 'MANIFEST.json'),
                sparse_predictions_sha256=digest(job / 'CONTROL-DIFFERENCES.jsonl.gz'),
                counts={'node1:separators:parity0': 1, 'node1:separators:parity1': 1}))
            save(job / 'DISPATCHED.json', dict(structural_hypothesis_sha256=digest(job / 'STRUCTURAL-HYPOTHESIS.json')))
            save(job / 'COMPLETE.json', dict(rows=2,
                hardware_sha256=hashlib.sha256(''.join(hardware).encode()).hexdigest(),
                hardware_gzip_sha256=digest(job / 'hardware.txt.gz'),
                manifest_sha256=digest(job / 'MANIFEST.json')))
            save(job / 'SCORE.json', dict(counts={'rows': 2}))
            with patch.object(scorer, 'JOB', job), contextlib.redirect_stdout(io.StringIO()):
                scorer.main()
            counts = json.loads((job / 'TIE-RULE-SCORE.json').read_text())['counts']
            self.assertEqual(counts['node1:nearest-even:union_misses'], 2 * int(mutate))
            self.assertEqual(counts['node1:nearest-odd:union_misses'], 2 * int(not mutate))
            self.assertEqual(counts['node1:ties-away:union_misses'], 1)
            self.assertEqual(counts['node1:ties-zero:union_misses'], 1)


if __name__ == '__main__':
    unittest.main()
