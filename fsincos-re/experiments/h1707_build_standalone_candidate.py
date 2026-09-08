#!/usr/bin/env python3
"""Normal-build packaging of the promoted, pinned H1638 numerical C graph.

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

SOURCE_SHA = 'e1e88e4ffa53f01f23ce11f678a17c5a9a699774decca632ecab072862b59029'
HEADERS = {
    'src/general/standalone_polynomial.h': '5a73364533fae1ba7a687480863fc48e54f30ed93760696bc19394de0b34e637',
    'src/general/standalone_table.h': '9786c6bd0644ba3036a9c92f6c4adbc6f93934366f041a731df94175c945057b',
    'src/general/standalone_tiny.h': 'baf65c0eb699ac8925676a055ff0827dcb3e943d2293c8a9c80c99bb9e7d2d45',
    'src/ia64_sf.h': 'a5e9d085f2607cbc43fecbadcce3cebf57620fb07d9509627ce2d27164d7758d',
    'src/p5_rom_constants.h': '2189e0063c913ee4004e09c8b80cb17afb16c95715ea579854e152088bbfce97',
}


def source_string(root):
    source = (root/'src/fsincos_skylake.c').read_text()
    assert hashlib.sha256(source.encode()).hexdigest() == SOURCE_SHA
    for name, sha in HEADERS.items():
        assert hashlib.sha256((root/name).read_bytes()).hexdigest() == sha, name
    # Undefine any command-line override before establishing the audited
    # numerical configuration. The outer CLI forbids runtime perturbations.
    values = {'G_ROUND84': 0, 'G_GENERAL_STANDALONE': 1,
        'G_GENERAL_TRACE': 1}
    prefix = '/* H1708 packaging of the promoted H1707 numerical graph. */\n'
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
