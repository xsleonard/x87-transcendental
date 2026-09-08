"""Execute the published pseudocode against every retained FPATAN observation.

Only Markdown Python blocks define the numerical functions. ROM constants
are exact public TSV values. Existing model functions are not called. The
optional memoization changes cost only and is local to this verification.
No native capture is run and all historical evidence remains read-only.
"""
import argparse
import collections
import csv
from fractions import Fraction
from functools import lru_cache
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys
import time

HERE = Path(__file__).resolve().parent
FPATAN = HERE.parent
BASE = FPATAN.parent / 'tmp/fpatan-re'
sys.path.insert(0, str(FPATAN))
from compressed_guard import digest
from prepare import save
from protocol import validate_output


def load_pseudocode():
    markdown = FPATAN / 'PSEUDOCODE.md'
    blocks = re.findall(r'^```python\n(.*?)^```', markdown.read_text(), re.M | re.S)
    assert len(blocks) == 5
    rom = {}
    with (FPATAN.parent / 'data/pentium-rom/rom-constants.tsv').open() as stream:
        for row in csv.DictReader(stream, delimiter='\t'):
            index = int(row['row'])
            if index in (19, 20) or 114 <= index <= 123 or 125 <= index <= 156:
                scale = int(row['exp'], 16) - 0xffff - 66
                value = Fraction(int(row['sig68'], 16))
                value *= 2 ** scale if scale >= 0 else Fraction(1, 1 << (-scale))
                rom[index] = -value if int(row['sign']) else value
    assert len(rom) == 44
    namespace = {'ROM': rom}
    exec(compile('\n'.join(blocks), str(markdown), 'exec'), namespace)
    namespace['finite_angle'] = lru_cache(maxsize=8192)(namespace['finite_angle'])
    return namespace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists()
    markdown = FPATAN / 'PSEUDOCODE.md'
    source_sha = digest(markdown)
    reference = BASE / 'd0029-clang-full-replay.json'
    baseline = json.loads(reference.read_text())
    jobs = sorted(p.parent.name for p in BASE.glob('d[0-9][0-9][0-9][0-9]/MANIFEST.json'))
    assert jobs == sorted(baseline['jobs'])
    namespace = load_pseudocode()
    raw80, evaluate = namespace['Raw80'], namespace['fpatan']
    totals = collections.Counter()
    modes, precisions, reports = collections.Counter(), collections.Counter(), {}
    started = time.time()
    save(args.out.with_suffix('.started.json'), dict(
        status='SAVED_CORPUS_PSEUDOCODE_REPLAY_STARTED', started_unix=started,
        pseudocode_sha256=source_sha, baseline_sha256=digest(reference),
        jobs=jobs, hardware_executed=False))
    for name in jobs:
        job = BASE / name
        manifest = json.loads((job / 'MANIFEST.json').read_text())
        complete = json.loads((job / 'COMPLETE.json').read_text())
        assert complete['state'] == 'OBSERVED'
        assert digest(job / 'MANIFEST.json') == complete['manifest_sha256']
        zipped = (job / 'inputs.txt.gz').exists()
        inputs = job / ('inputs.txt.gz' if zipped else 'inputs.txt')
        hardware = job / ('hardware.txt.gz' if zipped else 'hardware.txt')
        assert digest(inputs) == manifest['files'][inputs.name]
        expected_digest = complete['hardware_gzip_sha256' if zipped else 'hardware_sha256']
        assert digest(hardware) == expected_digest
        counts = collections.Counter()
        hasher = hashlib.sha256()
        output_hash = hashlib.sha256()
        opener = gzip.open if zipped else open
        with opener(inputs, 'rt') as src, opener(hardware, 'rt') as obs:
            for line, actual in zip(src, obs, strict=True):
                observed = validate_output(actual, line)
                fields = line.split()
                ys, ym, xs, xm = (int(v, 16) for v in fields[3:])
                value, c1, flags, before = evaluate(
                    raw80(ys, ym), raw80(xs, xm), fields[1].upper(), int(fields[2]))
                checks = dict(output_misses=value != (observed['se'], observed['sig']),
                              C1_misses=c1 != observed['C1'],
                              exception_misses=flags != (observed['sw'] & 63),
                              before_misses=before != (observed['before'] & 63))
                counts.update(rows=1, **{k: int(v) for k, v in checks.items()})
                assert not any(checks.values()), (name, line, checks, value, c1, flags, before)
                hasher.update(actual.encode())
                prediction = f'{fields[0]} {value.se:04x} {value.sig:016x} {c1} {flags:02x} {before:02x}\n'
                output_hash.update(prediction.encode())
                modes[fields[1]] += 1
                precisions[fields[2]] += 1
        assert counts['rows'] == complete['rows'] == manifest['rows']
        assert hasher.hexdigest() == complete['hardware_sha256']
        assert output_hash.hexdigest() == baseline['jobs'][name]['output_sha256']
        reports[name] = dict(counts=counts, hardware_sha256=hasher.hexdigest(),
                             output_sha256=output_hash.hexdigest())
        totals.update(counts)
        print(name, dict(counts), 'elapsed', round(time.time() - started, 1), flush=True)
    assert dict(totals) == baseline['counts']
    assert digest(markdown) == source_sha
    save(args.out, dict(status='PASS', hardware_executed=False,
        pseudocode_sha256=source_sha, baseline_sha256=digest(reference),
        script_sha256=digest(Path(__file__)), jobs=reports, counts=totals,
        rounding_modes=modes, precision_controls=precisions,
        seconds=time.time() - started,
        limit='All retained observations, not exhaustive raw80 or cross-CPU proof.'))
    print('PASS published pseudocode:', dict(totals), flush=True)


if __name__ == '__main__':
    main()
