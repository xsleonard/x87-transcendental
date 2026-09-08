"""Public read-only proposal/history intersection; never executes FPTAN.

Every matching raw operand is a conservative hold, irrespective of the
instruction or whether an occurrence was input, output or source literal.
Only the supplied public proposal identities are reported, never labels.
"""
import bz2
from collections import Counter
import gzip
import json
import lzma
from pathlib import Path
import re
import sys
import tarfile
import zipfile

PAIR = re.compile(rb'(?<![0-9a-f])([0-9a-f]{4})[\s:\",]+([0-9a-f]{16})(?![0-9a-f])', re.I)


def main():
    directory = Path(sys.argv[1]).resolve()
    with gzip.open(directory / 'proposals.txt.gz', 'rt') as stream:
        candidates = {line.strip() for line in stream}
    assert candidates
    roots = sorted(p for p in Path('/root').iterdir() if p.is_dir() and not p.is_symlink()
                   and p != directory and (p.name.startswith(('fsincos', 'fpatan', 'fptan')) or re.match(r'h\d', p.name)))
    hits, counts, unread = set(), Counter(), []
    def scan(stream):
        tail = b''
        while True:
            block = stream.read(1 << 20)
            if not block:
                break
            counts['bytes'] += len(block)
            text = tail + block
            tail = text[-128:]
            for match in PAIR.finditer(text):
                operand = (match[1] + b' ' + match[2]).lower().decode('ascii')
                if operand in candidates:
                    hits.add(operand)
    suffixes = {'.c', '.h', '.py', '.sh', '.md', '.txt', '.json', '.jsonl', '.tsv', '.csv', '.log', '.out', '.gz', '.xz', '.bz2', '.zip', '.tar', '.tgz'}
    for root in roots:
        for path in sorted(root.rglob('*')):
            if path.is_symlink() or not path.is_file() or path.suffix.lower() not in suffixes:
                continue
            counts['files'] += 1
            try:
                with path.open('rb') as stream:
                    magic = stream.read(4)
                if magic == b'\x00\x05\x16\x07':
                    with path.open('rb') as stream:
                        scan(stream)
                elif path.name.endswith(('.tar.gz', '.tgz', '.tar', '.tar.xz', '.tar.bz2')):
                    with tarfile.open(path, 'r:*') as archive:
                        for member in archive:
                            if member.isfile():
                                with archive.extractfile(member) as stream:
                                    scan(stream)
                elif path.suffix == '.zip':
                    with zipfile.ZipFile(path) as archive:
                        for member in archive.infolist():
                            if not member.is_dir():
                                with archive.open(member) as stream:
                                    scan(stream)
                else:
                    opener = {'.gz': gzip.open, '.xz': lzma.open, '.bz2': bz2.open}.get(path.suffix, open)
                    with opener(path, 'rb') as stream:
                        scan(stream)
            except (OSError, EOFError, ValueError, tarfile.TarError, zipfile.BadZipFile) as error:
                unread.append(dict(path=str(path), error=type(error).__name__))
    print(json.dumps(dict(status='PUBLIC_HISTORY_INTERSECTION_COMPLETE' if not unread else 'INCOMPLETE_NO_CLEARANCE',
        roots=[str(p) for p in roots], counts=counts, held_operands=sorted(hits), unread=unread,
        hardware_executed=False, limits='Visible public text/archive history. Binary64 generator domain and private history are held separately. Unknown raw80 generator seeds/unavailable history are not claimed covered.')))


if __name__ == '__main__':
    main()
