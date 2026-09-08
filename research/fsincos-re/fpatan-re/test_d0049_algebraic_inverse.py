"""Replay all prior GMP halfway targets through the algebraic inverse."""
from collections import Counter
import json
from pathlib import Path
import unittest

from compressed_guard import digest
from d0045_tie_observability import target_and_correction
from d0049_algebraic_tie_preimages import domains, invert_target, graph, fraction, ROM, COEFFICIENTS
import d0031_internal_rounding_coverage as audit

BASE = Path(__file__).resolve().parent.parent / 'tmp/fpatan-re'


class AlgebraicInverseTests(unittest.TestCase):
    def test_all_previous_gmp_targets(self):
        counts = Counter()
        for node in range(3):
            directory = BASE / f'd0045-node{node}-upper'
            report = json.loads((directory / 'REPORT.json').read_text())
            self.assertEqual(digest(directory / 'miner.tsv'), report['target_sha256'])
            exponent = report['square_exponent']
            choices = domains(node, exponent)
            with (directory / 'miner.tsv').open() as source:
                for line in source:
                    fields = line.split()
                    if fields[0] != 'T':
                        continue
                    um, parity, changed = int(fields[4], 16), int(fields[5]), int(fields[6])
                    target, h, _ = graph(node, (um, exponent - 63))
                    _, other, _ = graph(node, (um, exponent - 63), True)
                    t, fh = target_and_correction(node, um * audit.two(exponent - 63))
                    _, fo = target_and_correction(node, um * audit.two(exponent - 63), True)
                    self.assertEqual((fraction(target), fraction(h), fraction(other)), (t, fh, fo))
                    self.assertEqual(audit.event(t, 64)['parity'], parity)
                    self.assertEqual(h != other, bool(changed))
                    base = abs(fraction(ROM[COEFFICIENTS[node][0]]))
                    recovered = False
                    for domain in choices:
                        term = (abs(t) - base) / audit.two(domain['unit'])
                        self.assertEqual(term.denominator, 1)
                        recovered |= um in invert_target(domain, int(term))
                    self.assertTrue(recovered)
                    counts[node] += 1
            self.assertEqual(counts[node], report['counts']['ties'])
        self.assertEqual(counts, {0: 12727, 1: 10515, 2: 70436})


if __name__ == '__main__':
    unittest.main()
