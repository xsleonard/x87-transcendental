"""Algebra, signed rounding and independent coefficient-envelope tests."""
import json
import math
import random
import unittest
from d0010_causal_intervals import BASE, observation_interval, restore
from d0011_verify_role_certificate import rounded
from d0015_split_quotient_audit import correction, selftest as split_selftest, kernel as split_kernel
from d0015_sticky_datapath_audit import odd, kernel as sticky_kernel
from d0015_internal_rc_audit import formatted, kernel as rc_kernel
from d0016_wide_coefficient_family import envelope
from graph_v5 import prevalue
from model import F, ROM, cut, encode, value


class NewRepresentationTests(unittest.TestCase):
    def test_split_polynomial_and_derivative_identities(self):
        split_selftest()
        for b in (F(1, 1 << 69), -F(3, 1 << 70)):
            a = F(3, 128)
            full = correction(a, b, a * a, 'exact-polynomial-increment')
            first = correction(a, b, a * a, 'polynomial-derivative')
            higher = sum(ROM[k] * sum(math.comb(n, j) * a ** (n-j) * b ** j for j in range(2, n+1))
                         for k in range(118, 124) for n in (2 * (k-118) + 3,))
            self.assertEqual(full - first, higher)

    def test_round_to_odd_exactness_sign_and_idempotence(self):
        for sign in (-1, 1):
            for n in range(256, 512):
                x = sign * F(n, 256)
                got = odd(x, 4)
                lower = (n // 32) * F(1, 8)
                expected = lower if n % 32 == 0 else ((n // 32) | 1) * F(1, 8)
                self.assertEqual(got, sign * expected)
                self.assertEqual(odd(got, 4), got)

    def test_architectural_rounding_control_both_signs(self):
        tiny = F(1, 1 << 65)
        ulp = F(1, 1 << 63)
        for sign in (-1, 1):
            x = sign * (1 + tiny)
            for rc in ('rn', 'rd', 'ru', 'rz'):
                up = (rc == 'ru' and sign > 0) or (rc == 'rd' and sign < 0)
                self.assertEqual(formatted(x, 'rc64', rc), sign * (1 + (ulp if up else 0)))

    def test_saved_counterexamples_replay(self):
        frontier = json.loads((BASE / 'd0009-kernel-frontier.json').read_text())['pairs']
        pairs = {row['input']: (pair, row) for pair in frontier for row in pair['rows']}
        rng = random.Random('D0015 counterexample replay')
        for filename, kernel, keys in (
            ('d0015-split-quotient-audit.json', split_kernel,
             ('high', 'square', 'tail_first', 'tail_order', 'correction', 'correction_format', 'merge_format', 'layout')),
            ('d0015-sticky-datapath-audit.json', sticky_kernel,
             ('square_read', 'square', 'horner_multiply', 'horner_add', 'tail_first', 'tail_last', 'tail_z_read', 'tail_order')),
        ):
            records = json.loads((BASE / filename).read_text())['results']
            for item in rng.sample(records, 32):
                failure = item['counterexample']
                pair, _ = pairs[failure['input']]
                trace = {}
                prevalue(*pair['raw'], trace=trace)
                v = restore(kernel(trace['z'], *(item['recipe'][k] for k in keys)), trace, pair['raw'])
                self.assertEqual(str(v), failure['prevalue'])
                self.assertFalse(observation_interval(pair['rows']).contains(abs(v)))
        records = json.loads((BASE / 'd0015-internal-rc-audit.json').read_text())['results']
        keys = ('square_read', 'square', 'horner_product', 'horner_add', 'horner_scope', 'tail_first', 'tail_last', 'tail_z_read', 'tail_order')
        for item in rng.sample(records, 32):
            failure = item['counterexample']
            pair, row = pairs[failure['input']]
            trace = {}
            prevalue(*pair['raw'], trace=trace)
            v = restore(rc_kernel(trace['z'], failure['internal_rc'], *(item['recipe'][k] for k in keys)), trace, pair['raw'])
            se, sig = encode(v, row['rc'])
            got = [se, sig, int(abs(value(se, sig)) > abs(v))]
            self.assertEqual(got, failure['predicted'])
            self.assertNotEqual(got, failure['observed'])

    def test_wide_horner_envelopes_with_independent_rounder(self):
        sample = json.loads((BASE / 'd0016-wide-coefficient-family-b60/t000.json').read_text())['constraints'][::11]
        rng = random.Random('D0016 wide independent arithmetic')
        bound = 1 << 60
        for bits in (64, 67, 69):
            for read in ('exact', 'chop64', 'rn64'):
                for point in sample:
                    z = F(point['z'])
                    u, weights, lo, hi, units = envelope(z, bits, 60, read)
                    for trial in range(6):
                        coefficients = {k: ROM[k] + units[k] * (-bound if trial == 0 else bound if trial == 1
                                                              else rng.randrange(-bound, bound+1)) for k in range(118, 124)}
                        h = coefficients[123]
                        for k in range(122, 117, -1):
                            h = rounded(coefficients[k] + rounded(u * h, 'chop67'), 'rn' + str(bits))
                        exact = sum(weights[k] * coefficients[k] for k in weights)
                        self.assertLessEqual(lo, h-exact)
                        self.assertLessEqual(h-exact, hi)


if __name__ == '__main__':
    unittest.main()
