#!/usr/bin/env python3
"""Linux build/codec/scorer replay only; NEVER invoke a capture instruction."""
import argparse
import gzip
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import suite
import h1725_autonomous as auto


def main(package):
    build = json.loads((package / 'BUILD.json').read_text())
    for name, digest in build['public_source_pins'].items():
        assert suite.digest(package / name) == digest
    predictor = package / 'predictor'
    command = ['gcc', '-O2', '-o', str(predictor), str(package / 'experiments/h1719_saved_verifier.c'), '-lm']
    # Reuse a preserved build after an interrupted SOFTWARE replay; never
    # overwrite it. Numerical parity below is still mandatory on every replay.
    if not predictor.exists():
        compiled = subprocess.run(command, capture_output=True, text=True, check=True)
        auto.durable(package / 'build.stdout.txt', compiled.stdout.encode())
        auto.durable(package / 'build.stderr.txt', compiled.stderr.encode())
    predict, score = auto.original_functions(package, build['algorithm_pins'])
    checks = []
    for fixture in sorted((package / 'replay-fixtures').iterdir()):
        if not fixture.is_dir():
            continue
        records = list(auto.RECORD.iter_unpack((fixture / 'records.bin').read_bytes()))
        stage = Path(tempfile.mkdtemp(prefix='replay-', dir=package))
        predictions = predict(stage, records, predictor)
        with gzip.open(fixture / 'predictions.json.gz', 'rt') as f:
            assert predictions == json.load(f), 'Linux predictor differs from the original Mac artifact'
        for name in ('JOB.json', 'inputs.txt.gz', 'outputs.txt.gz', 'cpu.json', 'cpu-after.json', 'COMPLETE.json', 'STARTED.json', 'indices.bin', 'stderr.txt'):
            shutil.copyfile(fixture / name, stage / name)
        pairs = list(auto.cases(records))
        with gzip.open(stage / 'inputs.txt.gz', 'rt') as f:
            assert [suite.capture_line(c) + '\n' for c, _ in pairs] == f.readlines()
        counts, misses = score(stage, predictions)
        assert dict(counts) == json.loads((fixture / 'score.json').read_text())['counts'] and misses == 0
        job = json.loads((stage / 'JOB.json').read_text())
        cfg = dict(predictor_sha256=suite.digest(predictor), selection_sha256=build['selection_sha256'],
                   cpu_context_id=job['cpu_context_id'], capture_sha256=job['binary_sha256'])
        receipt = auto.seal(stage, package / (fixture.name + '-roundtrip.json.gz'), records, cfg, predictions)
        checks.append(dict(fixture=fixture.name, predictor_matches_original=True,
                           original_score_matches=True, **receipt))
    # Pure-memory tests of the ORIGINAL native freshness guard; no capture.
    for indices in ([2, 2], [-1], [auto.capture.CASES], [9]):
        bits = bytearray(4); bits[1] = 2
        try:
            auto.capture.reserve(bits, indices)
        except ValueError:
            pass
        else:
            raise AssertionError('invalid reservation accepted')
    bits = bytearray(4); auto.capture.reserve(bits, [0, 10, 31]); assert bits == bytearray([1, 4, 0, 128])
    auto.save(package / 'PREFLIGHT.json', dict(status='PASS', hardware_executions=0,
        predictor_sha256=suite.digest(predictor), compiler=subprocess.check_output(['gcc', '--version'], text=True).splitlines()[0],
        compile_command=command, replays=checks, reservation_controls=5))
    print((package / 'PREFLIGHT.json').read_text(), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--package', type=Path, required=True)
    main(p.parse_args().package.resolve())
