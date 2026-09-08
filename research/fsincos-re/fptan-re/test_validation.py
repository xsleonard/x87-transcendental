"""Independent arithmetic and synthetic capture/guard mutation tests."""
import gzip
from pathlib import Path
import random
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import guard
from independent_inputs import count_low, floor_sum, near_count, near_indices
from protocol import make_line, parse, validate_output
from score import compare_prediction
from support import HERE, copy, digest, read, save


class ArithmeticTests(unittest.TestCase):
    def test_exact_residue_enumeration(self):
        rng = random.Random(123)
        for _ in range(1000):
            n, m = rng.randrange(1, 80), rng.randrange(3, 300)
            a, b = rng.randrange(-1000, 1000), rng.randrange(-1000, 1000)
            limit = rng.randrange(m + 1)
            self.assertEqual(floor_sum(n, m, a, b), sum((a * i + b) // m for i in range(n)))
            self.assertEqual(count_low(n, m, a, b, limit), sum((a * i + b) % m < limit for i in range(n)))
            margin, start = rng.randrange(1, (m + 1) // 2), rng.randrange(100)
            hits = [i for i in range(start, start + n) if (a * i + b) % m < margin or (a * i + b) % m >= m - margin]
            self.assertEqual(near_count(start, n, m, a, b, margin), len(hits))
            self.assertEqual(near_indices(start, n, m, a, b, margin), hits[:4])

    def test_protocol_rejects_mapping_control_and_stack_mutations(self):
        line = make_line('rn', 64, 16382, (1 << 63) + 31)
        good = line + ' 037f 3800 3020 0020 3ffe 800000000000001f 3fff 8000000000000000'
        validate_output(good, line)
        for bad in (good + ' 0', good.replace('037f', '027f'), good.replace('3800', '3000'), good.replace('3020', '3820'), good.replace('0020', '3820')):
            with self.assertRaises(ValueError):
                validate_output(bad, line)
        with self.assertRaises(ValueError):
            parse(line.replace(' rn ', ' xx '))

    def test_scorer_detects_each_numerical_field(self):
        line = make_line('rn', 64, 16382, (1 << 63) + 31)
        actual = line + ' 037f 3800 3020 0020 3ffe 800000000000001f 3fff 8000000000000000'
        ident = line.split()[0]
        fields = ['3ffe', '800000000000001f', '3fff', '8000000000000000', '0', '0']
        self.assertFalse(compare_prediction(line, actual, ident + ' ' + ' '.join(fields))[3]['union_misses'])
        names = ('result_misses', 'result_misses', 'pushed_value_misses', 'pushed_value_misses', 'C2_misses', 'C1_misses')
        for index, name in enumerate(names):
            changed = list(fields)
            changed[index] = f'{int(changed[index], 16) ^ 1:x}'
            difference = compare_prediction(line, actual, ident + ' ' + ' '.join(changed))[3]
            self.assertTrue(difference[name])
            self.assertTrue(difference['union_misses'])
            self.assertEqual(sum(difference.values()), 2)
        # Exception-latch differences are captured, but intentionally not
        # passed off as a prediction made by this numerical-only adapter.
        flags_only = actual.replace('3020', '3000')
        self.assertFalse(compare_prediction(line, flags_only, ident + ' ' + ' '.join(fields))[3]['union_misses'])


class GuardTests(unittest.TestCase):
    def test_complete_failure_and_no_repeat(self):
        base = Path(tempfile.mkdtemp(prefix='fptan-guard-test-'))
        def make_job(name, offset):
            job = base / name
            job.mkdir()
            for filename in ('capture.c', 'protocol.py', 'support.py', 'guard.py'):
                copy(HERE / filename, job / filename)
            copy(HERE / 'synthetic_capture.py', job / 'capture')
            (job / 'capture').chmod(0o700)
            with gzip.open(job / 'inputs.txt.gz', 'xt') as stream:
                for pc in (24, 53, 64):
                    for rc in ('rn', 'rd', 'ru', 'rz'):
                        for field in (16382, 16446):
                            stream.write(make_line(rc, pc, field, (1 << 63) + offset) + '\n')
            save(job / 'CLEARANCE.json', dict(status='CLEARED_COMMON_TWO_HOST_INPUTS'))
            save(job / 'MANIFEST.json', dict(status='FROZEN_UNOPENED', rows=24, signature='00050654', microcode='0x1',
                files={'inputs.txt.gz': digest(job / 'inputs.txt.gz')}, clearance_sha256=digest(job / 'CLEARANCE.json'),
                public_sources={n: digest(job / n) for n in ('capture.c', 'protocol.py', 'support.py', 'guard.py')}))
            return job
        original_read = Path.read_text
        def cpu_read(path, *args, **kwargs):
            return 'microcode : 0x1\n' if str(path) == '/proc/cpuinfo' else original_read(path, *args, **kwargs)
        with patch.object(guard.os, 'sched_setaffinity', create=True), patch.object(guard.os, 'sched_getaffinity', return_value={0}, create=True), patch.object(Path, 'read_text', cpu_read):
            success = make_job('success', 17)
            guard.run(base, success)
            self.assertEqual(read(success / 'COMPLETE.json')['rows'], 24)
            with self.assertRaises(AssertionError):
                guard.run(base, success)
            repeated = make_job('repeated', 17)
            with self.assertRaises(sqlite3.IntegrityError):
                guard.run(base, repeated)
            self.assertFalse((repeated / 'STARTED.json').exists())
            failure = make_job('failure', 29)
            with patch.dict(guard.os.environ, {'FPTAN_SYNTHETIC_FAIL': '1'}):
                with self.assertRaises(AssertionError):
                    guard.run(base, failure)
            self.assertTrue((failure / 'STARTED.json').exists())
            self.assertFalse((failure / 'COMPLETE.json').exists())
            with self.assertRaises(AssertionError):
                guard.run(base, failure)
        print('Synthetic guard artifacts retained at', base)


if __name__ == '__main__':
    unittest.main()
