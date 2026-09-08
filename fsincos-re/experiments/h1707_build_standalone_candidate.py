#!/usr/bin/env python3
"""Normal-build packaging of the unchanged, pinned H1638 numerical C graph.

No corpus, private ledger, solver or hardware is accessed. The generated C is
the same arithmetic program as H1638, with fixed switches and a restricted CLI.
Historical source text remains in the translation unit; H1702 audits the active
routes. This packaging is not a claim of final minimal-source delivery/FSINCOS.
"""
from __future__ import annotations
import argparse
import hashlib
import os
import shlex
import subprocess
from pathlib import Path
import h1638_tiny_c_transfer as candidate

SOURCE_SHA = '7c1eda2a245b9da3f4c24fa1abb06b8d929a24059909795b2303aa3bc9a22a4a'
HEADERS = {
    'experiments/h1630_shared_polynomial.h': '5c279565bf3ab5b1a02d92a24fb2e40dc3b12ab23498522768118890cf5c5310',
    'experiments/h1633_shared_table.h': '238ee52346049bbb292cb43958c01f8f1ddae20e4d3fad004bf74423f6dae66b',
    'experiments/h1638_tiny_closed_form.h': '910cbb03c7310ad86b77bce4ae64fd611d96374c794df0048922b7dc2f199227',
    'src/ia64_sf.h': 'a5e9d085f2607cbc43fecbadcce3cebf57620fb07d9509627ce2d27164d7758d',
    'src/p5_rom_constants.h': '2189e0063c913ee4004e09c8b80cb17afb16c95715ea579854e152088bbfce97',
}


def source_string(root):
    source = candidate.source_string(root)
    assert hashlib.sha256(source.encode()).hexdigest() == SOURCE_SHA
    for name, sha in HEADERS.items():
        assert hashlib.sha256((root/name).read_bytes()).hexdigest() == sha, name
    # Undefine any command-line override before establishing the audited
    # numerical configuration. The outer CLI forbids runtime perturbations.
    values = {'G_ROUND84': 0, 'G_H1630_POLYNOMIAL': 1,
        'G_H1633_TABLE': 1, 'G_H1638_TINY': 1}
    prefix = '/* Generated H1707 candidate packaging; no arithmetic edits. */\n'
    for name, value in values.items():
        prefix += f'#undef {name}\n#define {name} {value}\n'
    prefix += '#define main x87_candidate_laboratory_main\n'
    wrapper = (root/'src/general/fsin_fcos_candidate_cli.h').read_text()
    return prefix+source+'\n'+wrapper


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--binary', required=True, type=Path)
    parser.add_argument('--cc', default=os.environ.get('CC', 'cc'))
    parser.add_argument('--cflags', default='-O2')
    args = parser.parse_args(); root = args.root.resolve(); binary = args.binary.resolve()
    assert binary.parent.is_dir()
    source = source_string(root)
    command = shlex.split(args.cc)+shlex.split(args.cflags)+['-std=c11',
        '-I', str(root/'src'), '-I', str(root/'experiments'), '-x', 'c', '-', '-lm', '-o', str(binary)]
    proc = subprocess.run(command, input=source, text=True, capture_output=True)
    if proc.returncode:
        raise SystemExit(proc.stderr)
    if proc.stderr: print(proc.stderr, end='')
    print('Built standalone numerical candidate:', binary)


if __name__ == '__main__': main()
