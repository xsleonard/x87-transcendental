#!/usr/bin/env python3
"""Read-only public capture-history search; no native x87 instruction.

Only submitted candidate significands and aggregate counts are returned.
Sources are explicit campaign directories. Includes compressed archives and
SQLite raw pages, which preserve ASCII canonical case IDs. Hidden personal
directories are excluded. Read/decompression failures are fatal, not passes.
"""
import argparse
import bz2
import gzip
import hashlib
import json
import lzma
import re
import zipfile
from collections import Counter
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--patterns',required=True,type=Path)
    p.add_argument('--roots',nargs='+',required=True,type=Path);a=p.parse_args()
    wanted=set(a.patterns.read_bytes().lower().split());assert wanted and all(re.fullmatch(rb'[0-9a-f]{16}',x) for x in wanted)
    token=re.compile(rb'[0-9a-fA-F]{16,}');hits=set();counts=Counter()
    def scan(f):
        tail=b''
        while True:
            block=f.read(1<<20)
            if not block:break
            counts['uncompressed_bytes']+=len(block);data=tail+block
            for m in token.finditer(data):
                word=m.group().lower()
                for j in range(len(word)-15):
                    candidate=word[j:j+16]
                    if candidate in wanted:hits.add(candidate)
            tail=data[-64:]
    selected=[]
    for root in a.roots:
        assert root.is_dir()
        for path in root.rglob('*'):
            if any(part.startswith('.') for part in path.relative_to(root).parts):continue
            if path.is_symlink() or not path.is_file():continue
            if path.suffix.lower() not in ('.txt','.json','.jsonl','.tsv','.csv','.log','.out','.gz','.bz2','.xz','.zip','.sqlite','.db'):
                continue
            selected.append(path)
    for index,path in enumerate(sorted(set(selected))):
        counts['files']+=1
        if path.suffix=='.zip':
            with zipfile.ZipFile(path) as archive:
                for info in archive.infolist():
                    if info.is_dir():continue
                    with archive.open(info) as f:scan(f)
        else:
            opener={'.gz':gzip.open,'.bz2':bz2.open,'.xz':lzma.open}.get(path.suffix,open)
            with opener(path,'rb') as f:scan(f)
    print(json.dumps(dict(status='PUBLIC_REMOTE_HISTORY_AUDITED',counts=dict(counts),
        matching_candidate_significands=sorted(h.decode() for h in hits),
        patterns_sha256=hashlib.sha256(a.patterns.read_bytes()).hexdigest(),
        roots=[str(r) for r in a.roots],hardware_execution='none',
        limits='Explicit public campaign trees, text/compressed records and ASCII IDs in SQLite; generated inputs need separate domain exclusion.')))


if __name__=='__main__':main()
