#!/usr/bin/env python3
"""Read-only export of potential public input history, not hardware labels.

Known input files already mapped by the authenticated native bank inventory
are omitted by content hash. Software-only H1719 replay/build directories
are excluded explicitly. Unknown operands are conservative capture holds.
No private path is read by this program; no transcendental opcode is run.
"""
import argparse
import bz2
import gzip
import hashlib
import json
import lzma
import re
import sys
import zipfile
from pathlib import Path

PAIR = re.compile(rb'(?<![0-9a-f])([0-9a-f]{4})[\s:\",]+([0-9a-f]{16})(?![0-9a-f])', re.I)
CASE = re.compile(rb'n1-(fsin|fcos|fsincos)-(rn|rd|ru|rz)-(24|53|64)-([0-9a-f]{4})([0-9a-f]{16})', re.I)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True, type=Path)
    a = p.parse_args(); cfg = json.loads(a.config.read_text())
    known = set(cfg['mapped_input_hashes'])
    skipped = tuple(cfg['software_only_roots'])
    selected = set(); counts = dict(files=0, bytes=0, input_occurrences=0, case_occurrences=0, known_input_aliases=0)
    for root in cfg['roots']:
        root = Path(root)
        if not root.is_dir(): raise RuntimeError('missing explicit public history root')
        for path in root.rglob('*'):
            if path.is_symlink() or not path.is_file(): continue
            if any(part.startswith('.') for part in path.relative_to(root).parts): continue
            if any(str(path) == s or str(path).startswith(s + '/') for s in skipped): continue
            if path.suffix.lower() in ('.txt','.json','.jsonl','.tsv','.csv','.log','.out','.gz','.bz2','.xz','.zip','.c','.h','.py','.sh'):
                selected.add(path)
    stream = gzip.GzipFile(fileobj=sys.stdout.buffer, mode='wb', mtime=0)
    def scan(f):
        tail = b''
        while True:
            block = f.read(1 << 20)
            if not block: break
            counts['bytes'] += len(block); raw = tail + block
            tail = raw[-128:]
            # Legacy OK lines contain output encodings, never the input.
            # Their companion input files are scanned/mapped independently.
            # Avoid exporting hundreds of millions of output-only values.
            raw = re.sub(rb'(?m)^OK [^\n]*(?:\n|$)', b'', raw)
            # Occurrences are exclusion candidates only. Results and literals
            # can be overincluded; they never count as observed inputs.
            for m in PAIR.finditer(raw):
                stream.write(m[1].lower() + b' ' + m[2].lower() + b'\n')
                counts['input_occurrences'] += 1
            for m in CASE.finditer(raw):
                stream.write(m[4].lower() + b' ' + m[5].lower() + b'\n')
                counts['case_occurrences'] += 1
    for path in sorted(selected):
        counts['files'] += 1
        # Large input aliases are recognized only through a full hash. Labels
        # alone do not receive this exception.
        if path.suffix == '.txt' and digest(path) in known:
            counts['known_input_aliases'] += 1; continue
        if path.suffix == '.zip':
            with zipfile.ZipFile(path) as z:
                for member in z.infolist():
                    if not member.is_dir():
                        with z.open(member) as f: scan(f)
        else:
            opener = {'.gz':gzip.open,'.bz2':bz2.open,'.xz':lzma.open}.get(path.suffix, open)
            with opener(path,'rb') as f: scan(f)
        if counts['files'] % 500 == 0: print(json.dumps(counts), file=sys.stderr, flush=True)
    stream.close()
    print(json.dumps(dict(status='PUBLIC_HISTORY_EXPORT_COMPLETE',counts=counts,hardware_execution='none')), file=sys.stderr, flush=True)


if __name__ == '__main__': main()
