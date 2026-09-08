#!/usr/bin/env python3
"""Add allowlisted saved replay fixtures to a newly built public package."""
import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'tmp/ledger33/current/h1725_full_campaign'


def main(package, host):
    # Refresh only our not-yet-deployed new module, not any campaign/model file.
    for name in ('h1725_autonomous.py', 'h1725_autonomous_preflight.py'):
        shutil.copyfile(ROOT / 'experiments' / name, package / name)
    fixtures = package / 'replay-fixtures'; fixtures.mkdir()
    numbers = (0, 3570) if host == 'i7' else (440, 7160)
    for number in numbers:
        source = BASE / host / 'jobs' / f'job-{number:06d}'
        target = fixtures / source.name; target.mkdir()
        for name in ('JOB.json', 'inputs.txt.gz', 'outputs.txt.gz', 'cpu.json', 'cpu-after.json',
                     'COMPLETE.json', 'STARTED.json', 'indices.bin', 'stderr.txt', 'predictions.json.gz', 'score.json'):
            shutil.copyfile(source / name, target / name)
        with (BASE / host / 'selected.bin').open('rb') as f:
            f.seek(number * 100000)
            with (target / 'records.bin').open('xb') as out:
                out.write(f.read(100000))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--package', type=Path, required=True)
    p.add_argument('--host', choices=('i7', 'skylake'), required=True); a = p.parse_args(); main(a.package, a.host)
