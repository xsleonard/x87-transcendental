"""Independent regression checks for newly constructed node-halfway inputs."""
import json
from pathlib import Path
import unittest

from compressed_guard import digest
import d0031_internal_rounding_coverage as audit
from d0037_polynomial_node_census import traced_kernel, restored
from d0041_inner_tie_preimages import NODES

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'tmp/fpatan-re'


class NewAdversaryTests(unittest.TestCase):
    def test_source_and_sanitizer_pins(self):
        mining = BASE / 'd0041-inner-ties'
        report = json.loads((mining / 'REPORT.json').read_text())
        for name, sha in report['source_sha256'].items():
            self.assertEqual(digest(HERE / name), sha)
        sanitizer = json.loads((mining / 'SANITIZED-MINER.json').read_text())
        self.assertEqual(sanitizer['target_sha256'], digest(mining / 'square-targets.tsv'))
        self.assertEqual(sanitizer['status'], 'PASS')

    def test_every_external_preimage_and_event(self):
        count = 0
        parities = set()
        with (BASE / 'd0041-inner-ties/candidate-pool.tsv').open() as source:
            for line in source:
                node, ident, cell, sign, ys, ym, xs, xm, parity, mask, zm, zs = line.split()
                node = int(node)
                y, x = audit.Raw80(int(ys, 16), int(ym, 16)), audit.Raw80(int(xs, 16), int(xm, 16))
                state = audit.reduction(audit.core_key(y, x))
                self.assertEqual(state['cell'], int(cell))
                self.assertEqual(state['z'], int(sign) * int(zm, 16) * audit.two(int(zs)))
                table = node >= 2
                kernel, trace = traced_kernel(state['z'], table)
                record = next(r for r in trace if r[0] == NODES[node])
                self.assertEqual(record[1:5], (64, 'RN', 'tie', int(parity)))
                other, altered = traced_kernel(state['z'], table,
                    (NODES[node], 'ties-away' if record[4] == 0 else 'ties-zero'))
                index = next(i for i, r in enumerate(trace) if r[0] == NODES[node])
                self.assertEqual(trace[:index], altered[:index])
                baseline = audit.endpoint_vector(restored(state, kernel))
                alternative = audit.endpoint_vector(restored(state, other))
                actual_mask = sum((a != b) << i for i, (a, b) in enumerate(zip(baseline, alternative)))
                self.assertEqual(actual_mask, int(mask, 16))
                self.assertEqual(restored(state, kernel)[0], audit.SPEC['finite_angle'](y, x))
                parities.add((node, int(parity)))
                count += 1
        self.assertEqual(count, 8562)
        self.assertEqual(parities, {(node, parity) for node in range(4) for parity in (0, 1)})

    def test_corpus_and_i7_reference_identity(self):
        job = BASE / 'd0043'
        reference = json.loads((job / 'SKYLAKE-REFERENCE.json').read_text())
        self.assertEqual(reference['counts']['rows'], 4612536)
        self.assertEqual(len(reference['source_packs']), 17)
        self.assertEqual(reference['catalog_sha256'], digest(HERE / 'corpus-v1/CATALOG-D0040.json'))
        manifest = json.loads((job / 'MANIFEST.json').read_text())
        self.assertEqual(manifest['reference_host'], '142.132.217.243')
        self.assertEqual(manifest['reference_receipt_sha256'], digest(job / 'SKYLAKE-REFERENCE.json'))
        self.assertEqual(manifest['expected_signature'], '000506e3')


if __name__ == '__main__':
    unittest.main()
