#!/usr/bin/env python3
"""Build/run a bounded software-only paired materialization separator search."""
import argparse
import hashlib
import subprocess
from pathlib import Path
import h1710_build_paired_program as build
from h1709_paired_retained_census import digest, save


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--output-dir', required=True, type=Path)
    p.add_argument('--count', type=int, default=20000000)
    a = p.parse_args(); root = a.root.resolve(); out = a.output_dir.resolve()
    assert not out.exists() and 32768 <= a.count <= 100000000
    source = '#define main h1711_archived_main\n' + build.source_string(root)
    source += '\n#undef main\n' + (root / 'experiments/h1711_paired_discriminator_scan.c').read_text()
    out.mkdir(parents=True); binary = out / 'scan'
    proc = subprocess.run(['cc', '-O3', '-std=c11', '-DG_H1710_PAIRED=1', '-I', str(root / 'src'),
        '-I', str(root / 'experiments'), '-x', 'c', '-', '-lm', '-o', str(binary)],
        input=source, text=True, capture_output=True)
    assert proc.returncode == 0 and not proc.stderr, proc.stderr
    evidence = {name: digest(root / name) for name in ('src/fsincos_skylake.c', 'src/ia64_sf.h',
        'src/p5_rom_constants.h', 'src/general/standalone_polynomial.h', 'src/general/standalone_table.h',
        'src/general/standalone_tiny.h', 'experiments/h1710_paired_program.h',
        'experiments/h1710_build_paired_program.py', 'experiments/h1711_paired_discriminator_scan.c')}
    save(out / 'prepared.json', dict(experiment='h1711_paired_discriminator_scan', count=a.count,
        hardware_execution='none', manifest_frozen=False, sha256=dict(evidence=evidence,
        source=hashlib.sha256(source.encode()).hexdigest(), binary=digest(binary), script=digest(Path(__file__)))))
    with (out / 'proposals.txt').open('x') as output:
        subprocess.run([str(binary), str(a.count)], stdout=output, check=True)
    lines = (out / 'proposals.txt').read_text().splitlines()
    save(out / 'report.json', dict(status='SOFTWARE_ONLY_NOT_FROZEN', scanned=a.count,
        proposals=len(lines), unique_operands=len({tuple(s.split()[:2]) for s in lines}),
        last_vs_all_proposals=sum(bool(int(s.split()[2]) & 2) for s in lines),
        sha256=dict(prepared=digest(out / 'prepared.json'), proposals=digest(out / 'proposals.txt'))))


if __name__ == '__main__': main()
