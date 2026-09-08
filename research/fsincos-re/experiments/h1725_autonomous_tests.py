#!/usr/bin/env python3
"""Software-only codec/generator/scorer parity checks against sealed captures."""
import copy
import gzip
import json
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'tmp/ledger33/current/h1725_full_campaign'
sys.path.insert(0, str(ROOT / 'corpus-suite'))
import suite
import h1725_autonomous as auto


class Codec(unittest.TestCase):
    def setUp(self):
        self.case = suite.case_id('fsincos', 'rn', 64, '3ffe 8000000000000000')
        self.pred = {self.case: dict(value='OK 3ffd f57743a2582f7f44 3ffe e0a94032dbea7cee', known=1, c1=0)}
        self.raw = auto.canonical_line(self.case, self.pred[self.case], 0x3800, 0x3020)

    def encode(self, raw=None):
        return auto.encode_lines([self.raw if raw is None else raw], [self.case], self.pred)

    def decoded(self, payload):
        return b''.join(auto.decode_lines(payload, [self.case], self.pred))

    def test_exact(self):
        self.assertEqual(self.decoded(self.encode()), self.raw)

    def test_miss_is_lossless_raw_override(self):
        raw = self.raw.replace(b'f57743a2582f7f44', b'f57743a2582f7f45')
        payload = self.encode(raw); self.assertEqual(len(payload['raw_line_overrides']), 1)
        self.assertEqual(self.decoded(payload), raw)

    def test_c2_miss_is_lossless(self):
        p = dict(value='C2', known=0, c1=0)
        raw = auto.canonical_line(self.case, p, 0x3800, 0x3c00)
        self.assertEqual(self.decoded(self.encode(raw)), raw)

    def test_c1_and_undefined_status_retained(self):
        raw = auto.canonical_line(self.case, self.pred[self.case], 0x3920, 0x7220)
        self.assertEqual(self.decoded(self.encode(raw)), raw)

    def test_missing_native_never_passes(self):
        with self.assertRaises(StopIteration):
            auto.encode_lines([], [self.case], self.pred)

    def test_extra_native_rejected(self):
        with self.assertRaises(ValueError):
            auto.encode_lines([self.raw, self.raw], [self.case], self.pred)

    def test_status_corruption_rejected(self):
        p = self.encode(); p['statuses_b64'] = 'ADggMg=='
        with self.assertRaises(ValueError):
            self.decoded(p)

    def test_truncation_rejected(self):
        p = self.encode(); p['statuses_b64'] = ''
        with self.assertRaises(ValueError):
            self.decoded(p)

    def test_wrong_predictor_rejected(self):
        p = self.encode(); p['prediction_content_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            self.decoded(p)

    def test_extra_override_rejected(self):
        p = self.encode(); p['raw_line_overrides']['1'] = ''
        with self.assertRaises(ValueError):
            self.decoded(p)

    def test_wrong_case_rejected(self):
        with self.assertRaises(ValueError):
            self.encode(self.raw.replace(b'MODE=rn', b'MODE=rd'))

    def test_unobserved_has_no_archive(self):
        with tempfile.TemporaryDirectory(prefix='h1725-no-native-') as d:
            with self.assertRaises(FileNotFoundError):
                auto.seal(Path(d), Path(d) / 'observation.gz', [], {}, {})
            self.assertFalse((Path(d) / 'observation.gz').exists())


class Lifecycle(unittest.TestCase):
    """Synthetic observations only: exercise durability without native x87."""
    def test_checkpoint_resume_and_uncertain_job(self):
        with tempfile.TemporaryDirectory(prefix='h1725-autonomy-lifecycle-') as d:
            package = Path(d) / 'package'; package.mkdir()
            base = Path(d) / 'campaign'; base.mkdir()
            shutil_source = BASE / 'frozen-model/experiments/h1725_run_full.py'
            auto.durable(package / 'h1725_run_full.py', shutil_source.read_bytes())
            raw = auto.RECORD.pack(12, 0x3ffe, 0x8000000000000000, 4095)
            packed = gzip.compress(raw, mtime=0); auto.durable(package / 'plan.bin', packed)
            entry = dict(offset=0, bytes=len(packed), packed_sha256=auto.sha(packed),
                         records_sha256=auto.sha(raw), operands=1)
            auto.save(package / 'PLAN.json', dict(selection_sha256='selection', corpus_id=auto.CORPUS,
                                                  jobs={'0': entry}, end_job=1))
            cfg = dict(host='test', remote_base=str(base), predictor=str(BASE / 'predictor'),
                predictor_sha256=suite.digest(BASE / 'predictor'), capture_sha256='capture',
                capture_binary='/not-a-capture-binary', ledger='/not-a-ledger', cpu_context_id='context',
                selection_sha256='selection', algorithm_pins={}, start_job=0, prior_totals={'rows': 0},
                selected_cases=12, selection_counts={})
            auto.save(package / 'CUTOVER.json', cfg)
            manifest = dict(cutover_sha256=suite.digest(package / 'CUTOVER.json'))
            calls = []

            def fake_capture(unused_base, job, unused_binary, unused_ledger):
                calls.append(job.name)
                with gzip.open(job / 'predictions.json.gz', 'rt') as f:
                    predictions = json.load(f)
                with gzip.open(job / 'inputs.txt.gz', 'rt') as f:
                    ordered = [line.split()[0] for line in f]
                with gzip.open(job / 'outputs.txt.gz', 'xb') as f:
                    for case in ordered:
                        insn = suite.decode_case(case)[0]; expected = predictions[case]
                        sw = (0x3020 if insn == 'fsincos' else 0x3820) | (expected['c1'] << 9)
                        f.write(auto.canonical_line(case, expected, 0x3800, sw))
                for name in ('cpu.json', 'cpu-after.json', 'STARTED.json'):
                    auto.save(job / name, dict(synthetic_test_only=True))
                auto.durable(job / 'stderr.txt', b'')
                auto.save(job / 'COMPLETE.json', dict(status='OPENED_ONCE_DO_NOT_RERUN', instruction_retries=0,
                    outputs_sha256=suite.digest(job / 'outputs.txt.gz'), inputs_sha256=suite.digest(job / 'inputs.txt.gz'),
                    rows=12, cpu_context_id='context', binary_sha256='capture'))

            with patch.object(auto, 'verify_package', return_value=manifest), patch.object(auto.capture, 'run', fake_capture):
                auto.run(package)
                self.assertEqual(calls, ['job-000000'])
                self.assertFalse((base / 'job-000000').exists())
                self.assertEqual(json.loads((package / 'RUN_COMPLETE.json').read_text())['totals']['rows'], 12)
                auto.run(package)
                self.assertEqual(calls, ['job-000000'], 'checkpoint replay must not execute native again')
                # A missing DONE with a retained archive is uncertain, not new.
                done = package / 'observed/job-000000.DONE.json'
                done.rename(done.with_suffix('.saved'))
                with self.assertRaisesRegex(ValueError, 'uncertain'):
                    auto.run(package)
                self.assertEqual(calls, ['job-000000'])


def replay():
    reports = []
    for host, name in [('i7', 'job-000000'), ('i7', 'job-003570'),
                       ('skylake', 'job-000440'), ('skylake', 'job-007160')]:
        job = BASE / host / 'jobs' / name
        with gzip.open(job / 'predictions.json.gz', 'rt') as f:
            predictions = json.load(f)
        with gzip.open(job / 'inputs.txt.gz', 'rt') as f:
            ordered = [line.split()[0] for line in f]
        with gzip.open(job / 'outputs.txt.gz', 'rb') as f:
            payload = auto.encode_lines(f, ordered, predictions)
        packed = gzip.compress(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode(), mtime=0)
        decoded = json.loads(gzip.decompress(packed)); actual = b''.join(auto.decode_lines(decoded, ordered, predictions))
        with gzip.open(job / 'outputs.txt.gz', 'rb') as f:
            assert actual == f.read()
        number = int(name.split('-')[1])
        with (BASE / host / 'selected.bin').open('rb') as f:
            f.seek(number * 100000); records = list(struct.iter_unpack('<QHQH', f.read(100000)))
        assert [case for case, _ in auto.cases(records)] == ordered
        assert b''.join(struct.pack('<Q', n) for _, n in auto.cases(records)) == (job / 'indices.bin').read_bytes()
        reports.append(dict(host=host, job=name, rows=len(ordered), native_text_sha256=auto.sha(actual),
                            raw_text_bytes=len(actual), codec_bytes=len(packed), overrides=len(payload['raw_line_overrides'])))
    print(json.dumps(dict(status='PASS', software_only=True, replays=reports), indent=2), flush=True)


if __name__ == '__main__':
    tests = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(Codec),
                               unittest.defaultTestLoader.loadTestsFromTestCase(Lifecycle)])
    result = unittest.TextTestRunner(verbosity=2).run(tests)
    if not result.wasSuccessful():
        raise SystemExit(1)
    replay()
