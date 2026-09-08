#!/usr/bin/env python3
"""Build an analysis-only accumulator probe; do not edit the promoted model."""
import argparse
import subprocess
from pathlib import Path
from h1709_paired_retained_census import digest, save

SOURCE = '490039e787a89b4efa4df58f0804356cc47c9e882f0e6427b16923217e375e32'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    a = p.parse_args(); root = a.root.resolve(); out = a.output_dir.resolve()
    assert not out.exists() and digest(root/'src/fsincos_skylake.c') == SOURCE
    source = (root/'src/fsincos_skylake.c').read_text()
    anchor = 'static sf_t acc_round64_rc(u256 acc, int32_t scale, int neg_out, sf_rc_t rc)\n{'
    assert source.count(anchor) == 1
    source = source.replace(anchor, '''static u256 h1714_pre[16];
static int32_t h1714_scale[16];
static unsigned h1714_count;
''' + anchor + '''
    assert(h1714_count < 16);
    h1714_pre[h1714_count] = acc;
    h1714_scale[h1714_count++] = scale;
''')
    source = '#include <assert.h>\n#define main h1714_archived_cli_main\n' + source + '\n#undef main\n'
    source += (root/'experiments/h1714_rounding_boundary_scan.c').read_text()
    out.mkdir(parents=True)
    with (out/'instrumented.c').open('x') as f: f.write(source)
    proc = subprocess.run(['cc','-O2','-std=c11','-I',str(root/'src'),str(out/'instrumented.c'),
        '-lm','-o',str(out/'scanner')], capture_output=True, text=True, check=True)
    with (out/'build.stderr').open('x') as f: f.write(proc.stderr)
    evidence = {str(p.relative_to(root)): digest(p) for p in [
        root/'src/fsincos_skylake.c',root/'src/ia64_sf.h',root/'src/p5_rom_constants.h',
        *sorted((root/'src/general').glob('*.h')),Path(__file__),
        root/'experiments/h1714_rounding_boundary_scan.c']}
    save(out/'prepared.json', dict(status='SOFTWARE_ONLY_NOT_FROZEN', hardware_execution='none',
        candidate_changed=False, sha256=dict(evidence=evidence, binary=digest(out/'scanner'),
        instrumented=digest(out/'instrumented.c'))))
    print('PASS analysis-only build')


if __name__ == '__main__': main()
