"""Test the necessary outer-boundary filter independently of its search."""
import json
from pathlib import Path
import random
import unittest

import d0031_internal_rounding_coverage as audit
from d0049_algebraic_tie_preimages import domains, invert_target, graph, fraction, ROM, COEFFICIENTS
from d0056_outer_boundary_lattice import floor_sum, candidate_offsets, parameters, filtered_indices

BASE = Path(__file__).resolve().parent.parent / 'tmp/fpatan-re'


class BoundaryLatticeTests(unittest.TestCase):
    def test_floor_sum_and_residue_enumeration(self):
        rng = random.Random('d0056-floor-sum-tests')
        for _ in range(500):
            n, modulus = rng.randrange(200), rng.randrange(1, 1 << 30)
            slope, intercept = rng.randrange(1 << 34), rng.randrange(1 << 40)
            self.assertEqual(floor_sum(n, modulus, slope, intercept),
                             sum((slope * i + intercept) // modulus for i in range(n)))
            low, high = rng.randrange(modulus), rng.randrange(modulus)
            expected = [i for i in range(n)
                        if (slope * i + intercept) % modulus <= low
                        or (slope * i + intercept) % modulus >= modulus - high]
            self.assertEqual(list(candidate_offsets(n, modulus, slope, intercept, low, high)), expected)

    def fixtures(self):
        data = json.loads((BASE / 'd0052-wide-masking.json').read_text())
        for node in (0, 1):
            for row in data['results'][f'd0049-node{node}-wide']['selected_states']:
                yield node, row['square_exponent'], int(row['square_sig'], 16)

    def test_all_known_long_outer_carries_survive_filter(self):
        count = 0
        for node, exponent, um in self.fixtures():
            target, _, outer = graph(node, (um, exponent - 63))
            _, _, alternative = graph(node, (um, exponent - 63), True)
            self.assertNotEqual(outer, alternative)
            recovered = False
            base = abs(fraction(ROM[COEFFICIENTS[node][0]]))
            for d in domains(node, exponent):
                term = (abs(fraction(target)) - base) / audit.two(d['unit'])
                self.assertEqual(term.denominator, 1)
                index, rem = divmod(int(term) - d['first'], d['modulus'])
                if rem or not 0 <= index < d['count'] or um not in invert_target(d, int(term)):
                    continue
                p = parameters(node, d)
                start = index // (1 << 20) * (1 << 20)
                recovered |= index in filtered_indices(p, start, min(1 << 20, d['count'] - start))
                v = audit.T((um * audit.two(exponent - 63)) ** 2, 67)
                anchor = abs(fraction(ROM[119 if node == 0 else 118]))
                pre = abs(fraction(target))
                unit = audit.two(audit.exponent(pre) - 63)
                whole = int(pre / unit)
                center = audit.Q(p['alpha'] * index * index + p['beta'] * index + p['gamma'], p['modulus'])
                lower = center - audit.Q(p['error_low'], p['modulus'])
                upper = center + audit.Q(p['error_high'], p['modulus'])
                for inner in (whole * unit, (whole + 1) * unit):
                    actual = (anchor + audit.T(v * inner, 67)) / audit.Q(p['proof_errors']['outer_unit'])
                    self.assertLessEqual(lower, actual)
                    self.assertLessEqual(actual, upper)
            self.assertTrue(recovered)
            count += 1
        self.assertEqual(count, 30)

    def test_complete_small_blocks_against_exact_forward_graph(self):
        rng = random.Random('d0056-unfiltered-blocks')
        checked = 0
        for node in (0, 1):
            for d in domains(node, -9):
                p = parameters(node, d)
                for _ in range(8):
                    start = rng.randrange(d['count'] - 4096)
                    selected = set(filtered_indices(p, start, 4096))
                    for j in range(start, start + 4096):
                        term = d['first'] + j * d['modulus']
                        for um in invert_target(d, term):
                            _, _, first = graph(node, (um, -72))
                            _, _, other = graph(node, (um, -72), True)
                            if first != other:
                                self.assertIn(j, selected)
                            checked += 1
        self.assertGreater(checked, 1000)


if __name__ == '__main__':
    unittest.main()
