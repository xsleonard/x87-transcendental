"""Software regressions for the polynomial census and inverse-tie campaign."""
import json
from pathlib import Path
import unittest

from compressed_guard import digest
import d0031_internal_rounding_coverage as audit
from d0037_polynomial_node_census import traced_kernel
import d0038_numerator_width_certificate as certificate
from prepare_d0040 import positive_values
from prepare_d0033 import neighbor

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'tmp/fpatan-re'


class AdversarialConstructionTests(unittest.TestCase):
    def test_width_certificate_replays_exactly(self):
        result = json.loads(json.dumps(certificate.build()))
        self.assertEqual(result, json.loads((BASE / 'd0038-numerator-width-certificate.json').read_text()))

    def test_mining_pins(self):
        report = json.loads((BASE / 'd0039-correction-ties/REPORT.json').read_text())
        self.assertEqual(report['verified_counts'], {'rows': 28799, 'visible': 32})
        self.assertEqual(digest(BASE / 'd0039-correction-ties/candidate-pool.tsv'), report['pool_sha256'])
        for name, expected in report['source_sha256'].items():
            self.assertEqual(digest(HERE / name), expected)

    def test_control_changes_only_the_selected_decision(self):
        report = json.loads((BASE / 'd0039-correction-ties/REPORT.json').read_text())
        parities = set()
        for witness in report['visible_witnesses']:
            ys, ym, xs, xm = (int(word, 16) for word in witness['raw'])
            key = audit.core_key(audit.Raw80(ys, ym), audit.Raw80(xs, xm))
            state = audit.reduction(key)
            fixed, records = traced_kernel(state['z'], False)
            index = next(i for i, r in enumerate(records) if r[0] == 'correction_sum')
            record = records[index]
            parities.add(record[4])
            changed, altered = traced_kernel(state['z'], False,
                ('correction_sum', 'ties-away' if record[4] == 0 else 'ties-zero'))
            self.assertEqual(records[:index], altered[:index])
            self.assertEqual(record[:-1], altered[index][:-1])
            self.assertEqual(abs(record[-1] - altered[index][-1]),
                             audit.two(audit.exponent(abs(record[-2])) - 63))
            self.assertEqual(records[index + 1], altered[index + 1])  # Cubic is unchanged.
            self.assertNotEqual(fixed, changed)
            base, other, tie, parity = positive_values(key)
            self.assertTrue(tie)
            mask = sum((a != b) << i for i, (a, b) in enumerate(zip(
                audit.endpoint_vector(base), audit.endpoint_vector(other))))
            self.assertEqual(mask, int(witness['endpoint_difference_mask'], 16))
        self.assertEqual(parities, {0, 1})

    def test_scale_extremes_and_neighbor_paths(self):
        report = json.loads((BASE / 'd0039-correction-ties/REPORT.json').read_text())
        for witness in report['visible_witnesses']:
            ys, ym, xs, xm = (int(word, 16) for word in witness['raw'])
            key = audit.core_key(audit.Raw80(ys, ym), audit.Raw80(xs, xm))
            for shift in (1 - ys, 32766 - xs, 97):
                a, b = audit.Raw80(ys + shift, ym), audit.Raw80(xs + shift, xm)
                self.assertEqual(audit.core_key(a, b), key)
                self.assertEqual(audit.SPEC['finite_angle'](a, b), positive_values(key)[0][0])
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    a = audit.Raw80(*neighbor(ys, ym, dy))
                    b = audit.Raw80(*neighbor(xs, xm, dx))
                    self.assertEqual(audit.reduction(audit.core_key(a, b))['path'], 'direct')


if __name__ == '__main__':
    unittest.main()
